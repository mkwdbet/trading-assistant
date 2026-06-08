import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Signal, StrategyState
from app.schemas import SignalCreate


def create_signal(db: Session, signal: SignalCreate) -> Signal:
    row = Signal(
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_name=signal.strategy_name,
        signal_type=signal.signal_type,
        market_state=signal.market_state,
        situation=signal.situation,
        dedupe_key=signal.dedupe_key,
        message=signal.message,
        payload_json=json.dumps(signal.payload, ensure_ascii=False, default=str),
        occurred_at=signal.occurred_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


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
