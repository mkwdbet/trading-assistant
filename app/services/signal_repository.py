import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Signal
from app.schemas import SignalCreate


def create_signal(db: Session, signal: SignalCreate) -> Signal:
    metrics = _extract_signal_metrics(signal)
    row = Signal(
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_name=signal.strategy_name,
        signal_type=signal.signal_type,
        direction=signal.direction,
        analysis_signal_type=signal.analysis_signal_type,
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


def _extract_signal_metrics(signal: SignalCreate) -> dict[str, float | None]:
    metadata = signal.payload.get("metadata") if isinstance(signal.payload.get("metadata"), dict) else {}
    source = signal.payload.get("tradingview") if isinstance(signal.payload.get("tradingview"), dict) else {}
    data = source.get("data") if isinstance(source.get("data"), dict) else {}

    return {
        "entry_price": _to_float(signal.entry_price, metadata.get("price"), source.get("price")),
        "current_price": _to_float(
            signal.current_price,
            signal.entry_price,
            metadata.get("price"),
            source.get("price"),
        ),
        "sma7": _to_float(signal.sma7, metadata.get("sma7"), data.get("sma7"), data.get("sma_7")),
        "sma21": _to_float(
            signal.sma21,
            metadata.get("sma21"),
            data.get("sma21"),
            data.get("sma_21"),
        ),
        "sma60": _to_float(
            signal.sma60,
            metadata.get("sma60"),
            data.get("sma60"),
            data.get("sma_60"),
        ),
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
