import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Signal, SignalOutcome, StrategyState
from app.schemas import SignalCreate

ANALYSIS_SIGNAL_TYPES = {
    "strong_bull_sma21_touch": "bullish_21ma_touch",
    "strong_bull_sma60_touch": "bullish_60ma_touch",
    "strong_bear_sma21_touch": "bearish_21ma_touch",
    "strong_bear_sma60_touch": "bearish_60ma_touch",
    "strong_bull_completed": "bullish_trend_completed",
    "strong_bear_completed": "bearish_trend_completed",
}


def create_signal(db: Session, signal: SignalCreate) -> Signal:
    metrics = _extract_hypothetical_entry_metrics(signal)
    analysis_signal_type = signal.analysis_signal_type or _analysis_type_for_signal(signal)
    direction = signal.direction or _direction_for_signal(signal)
    row = Signal(
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_name=signal.strategy_name,
        signal_type=signal.signal_type,
        direction=direction,
        analysis_signal_type=analysis_signal_type,
        market_state=signal.market_state,
        situation=signal.situation,
        dedupe_key=signal.dedupe_key,
        entry_price=metrics["entry_price"],
        current_price=metrics["current_price"],
        sma7=metrics["sma7"],
        sma21=metrics["sma21"],
        sma60=metrics["sma60"],
        message=signal.message,
        payload_json=json.dumps(signal.payload, ensure_ascii=False, default=str),
        occurred_at=signal.occurred_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _analysis_type_for_signal(signal: SignalCreate) -> str | None:
    if signal.dedupe_key in ANALYSIS_SIGNAL_TYPES:
        return ANALYSIS_SIGNAL_TYPES[signal.dedupe_key]
    return None


def _direction_for_signal(signal: SignalCreate) -> str | None:
    if signal.market_state == "STRONG_BULL" or "매수" in signal.signal_type or "상승" in signal.signal_type:
        return "LONG"
    if signal.market_state == "STRONG_BEAR" or "매도" in signal.signal_type or "하락" in signal.signal_type:
        return "SHORT"
    return None


def _extract_hypothetical_entry_metrics(signal: SignalCreate) -> dict[str, float | None]:
    payload = signal.payload
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    tradingview = payload.get("tradingview") if isinstance(payload.get("tradingview"), dict) else {}
    data = tradingview.get("data") if isinstance(tradingview.get("data"), dict) else {}

    return {
        "entry_price": _to_float(signal.entry_price, metadata.get("price"), tradingview.get("price")),
        "current_price": _to_float(
            signal.current_price,
            signal.entry_price,
            metadata.get("price"),
            tradingview.get("price"),
        ),
        "sma7": _to_float(signal.sma7, metadata.get("sma7"), data.get("sma7"), data.get("sma_7")),
        "sma21": _to_float(signal.sma21, metadata.get("sma21"), data.get("sma21"), data.get("sma_21")),
        "sma60": _to_float(signal.sma60, metadata.get("sma60"), data.get("sma60"), data.get("sma_60")),
    }


def _to_float(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def create_signal_outcome(
    db: Session,
    *,
    signal_id: int,
    horizon_hours: int,
    target_time: datetime,
    evaluated_at: datetime,
    price_after: float,
    return_pct: float,
    max_price: float,
    min_price: float,
    max_favorable_return_pct: float,
    max_adverse_return_pct: float,
) -> SignalOutcome:
    row = SignalOutcome(
        signal_id=signal_id,
        horizon_hours=horizon_hours,
        target_time=target_time,
        evaluated_at=evaluated_at,
        price_after=price_after,
        return_pct=return_pct,
        max_price=max_price,
        min_price=min_price,
        max_favorable_return_pct=max_favorable_return_pct,
        max_adverse_return_pct=max_adverse_return_pct,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def signal_outcome_exists(db: Session, *, signal_id: int, horizon_hours: int) -> bool:
    stmt = (
        select(SignalOutcome)
        .where(SignalOutcome.signal_id == signal_id)
        .where(SignalOutcome.horizon_hours == horizon_hours)
        .limit(1)
    )
    return db.scalar(stmt) is not None


def list_trackable_signals(db: Session) -> list[Signal]:
    stmt = (
        select(Signal)
        .where(Signal.entry_price.is_not(None))
        .where(Signal.direction.is_not(None))
        .order_by(Signal.occurred_at.asc())
    )
    return list(db.scalars(stmt))


def list_signal_outcomes(db: Session) -> list[SignalOutcome]:
    return list(db.scalars(select(SignalOutcome)))


def list_signals(
    db: Session,
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy_name: str | None = None,
    limit: int = 100,
) -> list[Signal]:
    stmt = select(Signal).order_by(Signal.occurred_at.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(Signal.symbol == symbol)
    if timeframe:
        stmt = stmt.where(Signal.timeframe == timeframe)
    if strategy_name:
        stmt = stmt.where(Signal.strategy_name == strategy_name)
    return list(db.scalars(stmt))


def has_recent_duplicate_signal(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    strategy_name: str,
    dedupe_key: str | None,
    market_state: str | None,
    occurred_at: datetime,
    cooldown_hours: int = 24,
) -> bool:
    if dedupe_key is None:
        return False

    cutoff = occurred_at - timedelta(hours=cooldown_hours)
    stmt = (
        select(Signal)
        .where(Signal.symbol == symbol)
        .where(Signal.timeframe == timeframe)
        .where(Signal.strategy_name == strategy_name)
        .where(Signal.dedupe_key == dedupe_key)
        .where(Signal.market_state == market_state)
        .where(Signal.occurred_at >= cutoff)
        .limit(1)
    )
    return db.scalar(stmt) is not None


def get_strategy_state(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    strategy_name: str,
) -> StrategyState | None:
    stmt = (
        select(StrategyState)
        .where(StrategyState.symbol == symbol)
        .where(StrategyState.timeframe == timeframe)
        .where(StrategyState.strategy_name == strategy_name)
    )
    return db.scalar(stmt)


def upsert_strategy_state(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    strategy_name: str,
    current_state: str,
    payload: dict,
    updated_at: datetime | None = None,
) -> StrategyState:
    state = get_strategy_state(
        db,
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
    )
    timestamp = updated_at or datetime.now(timezone.utc)
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)

    if state is None:
        state = StrategyState(
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=strategy_name,
            current_state=current_state,
            payload_json=payload_json,
            updated_at=timestamp,
        )
        db.add(state)
    else:
        state.current_state = current_state
        state.payload_json = payload_json
        state.updated_at = timestamp

    db.commit()
    db.refresh(state)
    return state
