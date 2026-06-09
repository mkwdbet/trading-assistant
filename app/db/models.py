from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    timeframe: Mapped[str] = mapped_column(String(30), index=True)
    strategy_name: Mapped[str] = mapped_column(String(120), index=True)
    signal_type: Mapped[str] = mapped_column(String(80), index=True)
    direction: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    analysis_signal_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    market_state: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    situation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma7: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma21: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma60: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    __table_args__ = (
        UniqueConstraint("signal_id", "horizon_hours", name="uq_signal_outcome_signal_horizon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_id: Mapped[int] = mapped_column(Integer, index=True)
    horizon_hours: Mapped[int] = mapped_column(Integer, index=True)
    target_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price_after: Mapped[float] = mapped_column(Float)
    return_pct: Mapped[float] = mapped_column(Float, index=True)
    max_price: Mapped[float] = mapped_column(Float)
    min_price: Mapped[float] = mapped_column(Float)
    max_favorable_return_pct: Mapped[float] = mapped_column(Float)
    max_adverse_return_pct: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StrategyState(Base):
    __tablename__ = "strategy_states"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "strategy_name",
            name="uq_strategy_state_symbol_timeframe_strategy",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    timeframe: Mapped[str] = mapped_column(String(30), index=True)
    strategy_name: Mapped[str] = mapped_column(String(120), index=True)
    current_state: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
