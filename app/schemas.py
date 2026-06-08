from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class TradingViewWebhookPayload(BaseModel):
    symbol: str = Field(..., examples=["NASDAQ:AAPL", "BINANCE:BTCUSDT"])
    timeframe: str = Field(..., examples=["1m", "15m", "1D"])
    event: str = Field(default="tradingview_alert")
    message: str = ""
    price: float | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)


class SignalCreate(BaseModel):
    symbol: str
    timeframe: str
    strategy_name: str
    signal_type: str
    market_state: str | None = None
    situation: str | None = None
    dedupe_key: str | None = None
    message: str
    occurred_at: datetime
    payload: dict[str, Any]


class SignalRead(BaseModel):
    id: int
    symbol: str
    timeframe: str
    strategy_name: str
    signal_type: str
    market_state: str | None
    situation: str | None
    message: str
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
