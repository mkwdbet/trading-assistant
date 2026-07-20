from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Signal, SignalOutcome

TRACKED_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "PEPEUSDT",
)

HORIZONS = (12, 24, 48, 72)


def build_dashboard_summary(
    db: Session,
    *,
    now: datetime | None = None,
    strategy_name: str | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    signals = _signals(db, strategy_name=strategy_name)
    outcomes = _outcomes_by_signal(db)
    joined = _joined_outcomes(signals, outcomes)

    return {
        "selected_strategy": strategy_name,
        "counts": {
            "total_signals": len(signals),
            "long_signals": sum(1 for signal in signals if signal.direction == "LONG"),
            "short_signals": sum(1 for signal in signals if signal.direction == "SHORT"),
            "signals_7d": _count_since(signals, now - timedelta(days=7)),
            "signals_30d": _count_since(signals, now - timedelta(days=30)),
        },
        "horizons": _summarize_horizons([item["outcome"] for item in joined]),
        "charts": {
            "daily_signal_counts": _daily_signal_counts(signals),
            "cumulative_signal_counts": _cumulative_signal_counts(signals),
            "symbol_avg_returns": build_performance_summary(
                db,
                strategy_name=strategy_name,
            )["symbols"],
            "signal_type_avg_returns": build_strategy_analysis(
                db,
                strategy_name=strategy_name,
            )["signal_types"],
        },
    }


def build_signal_rows(
    db: Session,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy_name: str | None = None,
    direction: str | None = None,
    signal_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(Signal).order_by(Signal.occurred_at.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(Signal.symbol == symbol)
    if timeframe:
        stmt = stmt.where(Signal.timeframe == timeframe)
    if strategy_name:
        stmt = stmt.where(Signal.strategy_name == strategy_name)
    if direction:
        stmt = stmt.where(Signal.direction == direction)
    if signal_type:
        stmt = stmt.where(Signal.analysis_signal_type == signal_type)
    if start:
        stmt = stmt.where(Signal.occurred_at >= start)
    if end:
        stmt = stmt.where(Signal.occurred_at <= end)

    rows = list(db.scalars(stmt))
    outcomes = _outcomes_by_signal(db)
    return [_signal_row(signal, outcomes.get(signal.id, [])) for signal in rows]


def build_signal_detail(db: Session, signal_id: int) -> dict[str, Any] | None:
    signal = db.get(Signal, signal_id)
    if signal is None:
        return None
    outcomes = _outcomes_by_signal(db).get(signal.id, [])
    return _signal_row(signal, outcomes)


def build_performance_summary(
    db: Session,
    *,
    horizon_hours: int = 24,
    strategy_name: str | None = None,
) -> dict[str, Any]:
    signals = _signals(db, strategy_name=strategy_name)
    outcomes = _outcomes_by_signal(db)
    groups: dict[str, list[SignalOutcome]] = defaultdict(list)
    signal_counts: dict[str, int] = defaultdict(int)

    for signal in signals:
        signal_counts[signal.symbol] += 1
        for outcome in outcomes.get(signal.id, []):
            if outcome.horizon_hours == horizon_hours:
                groups[signal.symbol].append(outcome)

    symbols = []
    for symbol, count in signal_counts.items():
        summary = _summarize_outcome_list(groups.get(symbol, []))
        symbols.append({"symbol": symbol, "signal_count": count, **summary})

    symbols.sort(key=lambda item: (item["avg_return_pct"] is None, -(item["avg_return_pct"] or 0)))
    return {"horizon_hours": horizon_hours, "selected_strategy": strategy_name, "symbols": symbols}


def build_strategy_analysis(
    db: Session,
    *,
    horizon_hours: int = 24,
    strategy_name: str | None = None,
) -> dict[str, Any]:
    signals = _signals(db, strategy_name=strategy_name)
    outcomes = _outcomes_by_signal(db)
    groups: dict[str, list[SignalOutcome]] = defaultdict(list)
    signal_counts: dict[str, int] = defaultdict(int)

    for signal in signals:
        signal_type = signal.analysis_signal_type or signal.signal_type
        signal_counts[signal_type] += 1
        for outcome in outcomes.get(signal.id, []):
            if outcome.horizon_hours == horizon_hours:
                groups[signal_type].append(outcome)

    signal_types = []
    for signal_type, count in signal_counts.items():
        summary = _summarize_outcome_list(groups.get(signal_type, []))
        signal_types.append({"signal_type": signal_type, "signal_count": count, **summary})

    signal_types.sort(
        key=lambda item: (item["avg_return_pct"] is None, -(item["avg_return_pct"] or 0))
    )
    return {
        "horizon_hours": horizon_hours,
        "selected_strategy": strategy_name,
        "best_signal_type": signal_types[0] if signal_types else None,
        "signal_types": signal_types,
    }


def build_research_summary(
    db: Session,
    *,
    horizon_hours: int = 24,
    limit: int = 20,
    strategy_name: str | None = None,
) -> dict[str, Any]:
    signals = {signal.id: signal for signal in _signals(db, strategy_name=strategy_name)}
    outcomes = [
        outcome
        for outcome in db.scalars(select(SignalOutcome).where(SignalOutcome.horizon_hours == horizon_hours))
        if outcome.signal_id in signals
    ]
    ranked = sorted(outcomes, key=lambda outcome: outcome.return_pct, reverse=True)

    return {
        "horizon_hours": horizon_hours,
        "selected_strategy": strategy_name,
        "top_winners": [_research_row(signals[outcome.signal_id], outcome) for outcome in ranked[:limit]],
        "top_losers": [
            _research_row(signals[outcome.signal_id], outcome)
            for outcome in sorted(outcomes, key=lambda outcome: outcome.return_pct)[:limit]
        ],
    }


def build_settings_summary() -> dict[str, Any]:
    return {
        "tracked_symbols": list(TRACKED_SYMBOLS),
        "discord": {
            "enabled": settings.enable_discord_notifications,
            "configured": bool(settings.discord_webhook_url),
            "masked_webhook": _mask_secret(settings.discord_webhook_url),
        },
        "outcome_tracking": {
            "enabled": settings.enable_outcome_tracking,
            "interval_seconds": settings.outcome_tracker_interval_seconds,
            "horizons": list(HORIZONS),
        },
    }


def _signals(db: Session, *, strategy_name: str | None = None) -> list[Signal]:
    stmt = select(Signal).order_by(Signal.occurred_at.asc())
    if strategy_name:
        stmt = stmt.where(Signal.strategy_name == strategy_name)
    return list(db.scalars(stmt))


def _outcomes_by_signal(db: Session) -> dict[int, list[SignalOutcome]]:
    grouped: dict[int, list[SignalOutcome]] = defaultdict(list)
    for outcome in db.scalars(select(SignalOutcome).order_by(SignalOutcome.horizon_hours.asc())):
        grouped[outcome.signal_id].append(outcome)
    return grouped


def _joined_outcomes(
    signals: list[Signal],
    outcomes_by_signal: dict[int, list[SignalOutcome]],
) -> list[dict[str, Signal | SignalOutcome]]:
    signals_by_id = {signal.id: signal for signal in signals}
    joined = []
    for signal_id, outcomes in outcomes_by_signal.items():
        signal = signals_by_id.get(signal_id)
        if signal is None:
            continue
        joined.extend({"signal": signal, "outcome": outcome} for outcome in outcomes)
    return joined


def _signal_row(signal: Signal, outcomes: list[SignalOutcome]) -> dict[str, Any]:
    return {
        "signal": {
            "id": signal.id,
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "strategy_name": signal.strategy_name,
            "signal_type": signal.signal_type,
            "analysis_signal_type": signal.analysis_signal_type,
            "direction": signal.direction,
            "market_state": signal.market_state,
            "situation": signal.situation,
            "entry_price": signal.entry_price,
            "current_price": signal.current_price,
            "sma7": signal.sma7,
            "sma21": signal.sma21,
            "sma60": signal.sma60,
            "message": signal.message,
            "occurred_at": signal.occurred_at.isoformat(),
            "created_at": signal.created_at.isoformat() if signal.created_at else None,
        },
        "outcomes": {
            f"{outcome.horizon_hours}h": {
                "price_after": outcome.price_after,
                "return_pct": outcome.return_pct,
                "max_price": outcome.max_price,
                "min_price": outcome.min_price,
                "max_favorable_return_pct": outcome.max_favorable_return_pct,
                "max_adverse_return_pct": outcome.max_adverse_return_pct,
                "evaluated_at": outcome.evaluated_at.isoformat(),
            }
            for outcome in outcomes
        },
    }


def _summarize_horizons(outcomes: list[SignalOutcome]) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[int, list[SignalOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[outcome.horizon_hours].append(outcome)
    return {f"{horizon}h": _summarize_outcome_list(grouped.get(horizon, [])) for horizon in HORIZONS}


def _summarize_outcome_list(outcomes: list[SignalOutcome]) -> dict[str, float | int | None]:
    if not outcomes:
        return {
            "outcome_count": 0,
            "avg_return_pct": None,
            "win_rate_pct": None,
            "avg_mfe_pct": None,
            "avg_mae_pct": None,
        }

    count = len(outcomes)
    return {
        "outcome_count": count,
        "avg_return_pct": _avg([outcome.return_pct for outcome in outcomes]),
        "win_rate_pct": sum(1 for outcome in outcomes if outcome.return_pct > 0) / count * 100,
        "avg_mfe_pct": _avg([outcome.max_favorable_return_pct for outcome in outcomes]),
        "avg_mae_pct": _avg([outcome.max_adverse_return_pct for outcome in outcomes]),
    }


def _daily_signal_counts(signals: list[Signal]) -> list[dict[str, int | str]]:
    counts: dict[str, int] = defaultdict(int)
    for signal in signals:
        counts[_utc(signal.occurred_at).date().isoformat()] += 1
    return [{"date": date, "count": counts[date]} for date in sorted(counts)]


def _cumulative_signal_counts(signals: list[Signal]) -> list[dict[str, int | str]]:
    total = 0
    rows = []
    for item in _daily_signal_counts(signals):
        total += int(item["count"])
        rows.append({"date": item["date"], "count": total})
    return rows


def _research_row(signal: Signal, outcome: SignalOutcome) -> dict[str, Any]:
    return {
        "signal_id": signal.id,
        "symbol": signal.symbol,
        "direction": signal.direction,
        "signal_type": signal.analysis_signal_type or signal.signal_type,
        "signal_time": signal.occurred_at.isoformat(),
        "entry_price": signal.entry_price,
        "return_pct": outcome.return_pct,
        "mfe_pct": outcome.max_favorable_return_pct,
        "mae_pct": outcome.max_adverse_return_pct,
    }


def _count_since(signals: list[Signal], cutoff: datetime) -> int:
    cutoff = _utc(cutoff)
    return sum(1 for signal in signals if _utc(signal.occurred_at) >= cutoff)


def _avg(values: list[float]) -> float:
    return sum(values) / len(values)


def _mask_secret(value: str) -> str | None:
    if not value:
        return None
    return f"{value[:30]}...{value[-6:]}"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
