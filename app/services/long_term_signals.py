from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.indicators.core import sma, wilder_rsi
from app.schemas import SignalCreate
from app.services.edge_market_data import EdgeMarketRow
from app.services.runtime_settings import get_setting, set_setting

logger = logging.getLogger(__name__)

STRATEGY_NAME = "long_term_technical_signals"
STATE_SETTING_KEY = "long_term_signal_state"
TIMEFRAME = "1w"

SMA_PROXIMITY_PERIOD = 200
SMA_PROXIMITY_THRESHOLD_PCT = 5.0
ATH_DRAWDOWN_THRESHOLDS_PCT = (-30.0, -40.0, -50.0)
RSI_PERIOD = 14
RSI_THRESHOLDS = {
    "Oversold": ("below", 35.0),
    "Extreme Oversold": ("below", 30.0),
    "Overbought": ("above", 70.0),
    "Extreme Overbought": ("above", 75.0),
}


@dataclass(frozen=True)
class LongTermAsset:
    symbol: str
    display_name: str


LONG_TERM_ASSETS = (
    LongTermAsset(symbol="BTC/USD", display_name="BTC/USD"),
    LongTermAsset(symbol="SPX", display_name="S&P500"),
)


def evaluate_long_term_signals(
    db: Session,
    *,
    asset: LongTermAsset,
    rows: list[EdgeMarketRow],
) -> list[SignalCreate]:
    if not rows:
        logger.warning("Skipping %s long-term signals: no weekly rows", asset.symbol)
        return []

    closes = [row.close for row in rows]
    state = _load_state(db)

    signals: list[SignalCreate] = []
    signals.extend(_evaluate_200w_sma(asset=asset, rows=rows, closes=closes, state=state))
    signals.extend(_evaluate_ath_drawdowns(asset=asset, rows=rows, state=state))
    signals.extend(_evaluate_weekly_rsi(asset=asset, rows=rows, closes=closes, state=state))

    _save_state(db, state)
    return signals


def _evaluate_200w_sma(
    *,
    asset: LongTermAsset,
    rows: list[EdgeMarketRow],
    closes: list[float],
    state: dict[str, bool],
) -> list[SignalCreate]:
    if len(closes) < SMA_PROXIMITY_PERIOD:
        logger.warning(
            "Skipping %s 200W SMA proximity: only %s weekly rows",
            asset.symbol,
            len(closes),
        )
        return []

    latest = rows[-1]
    latest_sma = sma(closes, SMA_PROXIMITY_PERIOD)[-1]
    if latest_sma in (None, 0):
        logger.warning("Skipping %s 200W SMA proximity: SMA unavailable", asset.symbol)
        return []

    distance_pct = ((latest.close / latest_sma) - 1) * 100
    is_active = abs(distance_pct) <= SMA_PROXIMITY_THRESHOLD_PCT
    dedupe_key = _state_key(asset.symbol, "200w_sma_proximity")
    if not _entered_state(state, dedupe_key, is_active):
        return []

    position = "Above MA" if latest.close >= latest_sma else "Below MA"
    reasons = [
        f"{asset.display_name} — 200W MA Proximity",
        f"Price: ${latest.close:,.2f}",
        f"200W MA: ${latest_sma:,.2f}",
        f"Distance: {distance_pct:+.2f}%",
        f"Position: {position}",
    ]
    return [
        _build_signal(
            asset=asset,
            signal_type="200W MA Proximity",
            analysis_signal_type="weekly_200sma_proximity",
            market_state="MA_PROXIMITY",
            situation="200W SMA proximity",
            dedupe_key=dedupe_key,
            price=latest.close,
            occurred_at=latest.time,
            reasons=reasons,
            metadata={
                "price": latest.close,
                "sma200": latest_sma,
                "distance_pct": distance_pct,
                "position": position,
                "threshold_pct": SMA_PROXIMITY_THRESHOLD_PCT,
            },
            direction="WATCH",
        )
    ]


def _evaluate_ath_drawdowns(
    *,
    asset: LongTermAsset,
    rows: list[EdgeMarketRow],
    state: dict[str, bool],
) -> list[SignalCreate]:
    latest = rows[-1]
    ath = max((row.high if row.high is not None else row.close) for row in rows)
    if ath <= 0:
        logger.warning("Skipping %s ATH drawdown: ATH unavailable", asset.symbol)
        return []

    drawdown_pct = ((latest.close / ath) - 1) * 100
    signals: list[SignalCreate] = []
    for threshold in ATH_DRAWDOWN_THRESHOLDS_PCT:
        is_active = drawdown_pct <= threshold
        threshold_label = _format_threshold(threshold)
        dedupe_key = _state_key(asset.symbol, f"ath_drawdown_{threshold_label}")
        if not _entered_state(state, dedupe_key, is_active):
            continue

        reasons = [
            f"{asset.display_name} — ATH Drawdown",
            f"Price: ${latest.close:,.2f}",
            f"ATH: ${ath:,.2f}",
            f"Drawdown: {drawdown_pct:.2f}%",
            f"Threshold crossed: {threshold:.0f}%",
        ]
        signals.append(
            _build_signal(
                asset=asset,
                signal_type="ATH Drawdown",
                analysis_signal_type=f"ath_drawdown_{threshold_label}",
                market_state="ATH_DRAWDOWN",
                situation=f"ATH drawdown {threshold:.0f}%",
                dedupe_key=dedupe_key,
                price=latest.close,
                occurred_at=latest.time,
                reasons=reasons,
                metadata={
                    "price": latest.close,
                    "ath": ath,
                    "drawdown_pct": drawdown_pct,
                    "threshold_pct": threshold,
                },
                direction="LONG",
            )
        )
    return signals


def _evaluate_weekly_rsi(
    *,
    asset: LongTermAsset,
    rows: list[EdgeMarketRow],
    closes: list[float],
    state: dict[str, bool],
) -> list[SignalCreate]:
    values = wilder_rsi(closes, RSI_PERIOD)
    latest_rsi = values[-1] if values else None
    if latest_rsi is None:
        logger.warning(
            "Skipping %s weekly RSI: only %s weekly rows",
            asset.symbol,
            len(closes),
        )
        return []

    latest = rows[-1]
    signals: list[SignalCreate] = []
    for status, (side, threshold) in RSI_THRESHOLDS.items():
        is_active = latest_rsi <= threshold if side == "below" else latest_rsi >= threshold
        threshold_key = status.lower().replace(" ", "_")
        dedupe_key = _state_key(asset.symbol, f"weekly_rsi_{threshold_key}")
        if not _entered_state(state, dedupe_key, is_active):
            continue

        reasons = [
            f"{asset.display_name} — Weekly RSI",
            f"RSI({RSI_PERIOD}): {latest_rsi:.2f}",
            f"Status: {status}",
            f"Price: ${latest.close:,.2f}",
        ]
        signals.append(
            _build_signal(
                asset=asset,
                signal_type=f"Weekly RSI {status}",
                analysis_signal_type=f"weekly_rsi_{threshold_key}",
                market_state="WEEKLY_RSI",
                situation=status,
                dedupe_key=dedupe_key,
                price=latest.close,
                occurred_at=latest.time,
                reasons=reasons,
                metadata={
                    "price": latest.close,
                    "rsi": latest_rsi,
                    "rsi_period": RSI_PERIOD,
                    "threshold": threshold,
                    "status": status,
                },
                direction="LONG" if side == "below" else "SHORT",
            )
        )
    return signals


def _build_signal(
    *,
    asset: LongTermAsset,
    signal_type: str,
    analysis_signal_type: str,
    market_state: str,
    situation: str,
    dedupe_key: str,
    price: float,
    occurred_at,
    reasons: list[str],
    metadata: dict[str, Any],
    direction: str,
) -> SignalCreate:
    return SignalCreate(
        symbol=asset.symbol,
        timeframe=TIMEFRAME,
        strategy_name=STRATEGY_NAME,
        signal_type=signal_type,
        direction=direction,
        analysis_signal_type=analysis_signal_type,
        market_state=market_state,
        situation=situation,
        dedupe_key=dedupe_key,
        entry_price=price,
        current_price=price,
        message="\n".join(f"* {reason}" for reason in reasons),
        occurred_at=occurred_at,
        payload={
            "reason": reasons,
            "metadata": metadata,
            "long_term_signal": {
                "asset": asset.display_name,
                "symbol": asset.symbol,
                "timeframe": TIMEFRAME,
                "signal_type": analysis_signal_type,
            },
        },
    )


def _entered_state(state: dict[str, bool], key: str, is_active: bool) -> bool:
    was_active = bool(state.get(key))
    state[key] = is_active
    return is_active and not was_active


def _load_state(db: Session) -> dict[str, bool]:
    raw = get_setting(db, STATE_SETTING_KEY)
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Long-term signal state is invalid JSON; resetting state")
        return {}
    if not isinstance(decoded, dict):
        return {}
    return {str(key): bool(value) for key, value in decoded.items()}


def _save_state(db: Session, state: dict[str, bool]) -> None:
    set_setting(db, STATE_SETTING_KEY, json.dumps(state, sort_keys=True))


def _state_key(symbol: str, signal_key: str) -> str:
    normalized = symbol.upper().replace("/", "_").replace(":", "_")
    return f"{STRATEGY_NAME}:{normalized}:{signal_key}"


def _format_threshold(value: float) -> str:
    return str(abs(int(value))).replace(".", "_")
