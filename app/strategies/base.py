from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.schemas import TradingViewWebhookPayload


@dataclass(frozen=True)
class StrategySignal:
    strategy_name: str
    signal_type: str
    message: str
    occurred_at: datetime
    market_state: str | None = None
    situation: str | None = None
    reason: list[str] = field(default_factory=list)
    dedupe_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyContext:
    previous_state: str | None = None


class BaseStrategy(ABC):
    name: str
    description: str = ""
    enabled: bool = True
    symbols: set[str] | None = None
    timeframes: set[str] | None = None

    def supports(self, payload: TradingViewWebhookPayload) -> bool:
        symbol_ok = self.symbols is None or payload.symbol in self.symbols
        timeframe_ok = self.timeframes is None or payload.timeframe in self.timeframes
        return symbol_ok and timeframe_ok

    @abstractmethod
    def evaluate(
        self,
        payload: TradingViewWebhookPayload,
        context: StrategyContext,
    ) -> list[StrategySignal]:
        """Return zero or more signals for a TradingView webhook payload."""
