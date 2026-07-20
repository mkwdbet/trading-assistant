from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    direction: str
    timeframe: str
    conditions: list[str | dict[str, Any]]
    atr_multiplier: float
    risk_reward_ratio: float
    max_holding_hours: int
    touch_tolerance_pct: float = 0.001


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    exit_reason: str
    return_pct: float
    mfe_pct: float
    mae_pct: float
    return_r: float | None = None
    stop_distance_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["entry_time"] = self.entry_time.isoformat()
        row["exit_time"] = self.exit_time.isoformat()
        return row


@dataclass(frozen=True)
class BacktestResult:
    request: BacktestRequest
    metrics: dict[str, float | int | None]
    trades: list[BacktestTrade]
