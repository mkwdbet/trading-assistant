from app.schemas import TradingViewWebhookPayload
from app.strategies.base import StrategyContext, StrategySignal
from app.strategies.loader import discover_strategies


class StrategyEngine:
    def __init__(self) -> None:
        self.strategies = discover_strategies()

    def list_strategies(self) -> list[dict[str, str]]:
        return [
            {"name": strategy.name, "description": strategy.description}
            for strategy in self.strategies
        ]

    def evaluate(
        self,
        payload: TradingViewWebhookPayload,
        contexts: dict[str, StrategyContext] | None = None,
    ) -> list[StrategySignal]:
        signals: list[StrategySignal] = []
        for strategy in self.strategies:
            if strategy.supports(payload):
                context = (contexts or {}).get(strategy.name, StrategyContext())
                signals.extend(strategy.evaluate(payload, context))
        return signals
