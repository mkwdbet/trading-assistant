import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Signal, StrategyState
from app.schemas import SignalCreate


def create_signal(db: Session, signal: SignalCreate) -> Signal:
    metrics = _extract_hypothetical_entry_metrics(signal)
    row = Signal(
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_name=signal.strategy_name,
        signal_type=signal.signal_type,
        market_state=signal.market_state,
        situation=signal.situation,
        dedupe_key=signal.dedupe_key,
        entry_price=metrics["entry_price"],
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


def _extract_hypothetical_entry_metrics(signal: SignalCreate) -> dict[str, float | None]:
    payload = signal.payload
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    tradingview = payload.get("tradingview") if isinstance(payload.get("tradingview"), dict) else {}
    data = tradingview.get("data") if isinstance(tradingview.get("data"), dict) else {}

    return {
        "entry_price": _to_float(signal.entry_price, metadata.get("price"), tradingview.get("price")),
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
