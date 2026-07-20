from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.edge_alert_rules import create_edge_alert_rule
from app.services.edge_market_data import EdgeMarketSnapshot
from app.services.edge_rule_evaluator import evaluate_saved_edge_rules


class FakeMarketData:
    async def get_snapshot(self, *, symbol: str, timeframe: str, ma_type: str, ma_period: int):
        return EdgeMarketSnapshot(
            symbol=symbol,
            provider_symbol="^GSPC",
            timeframe=timeframe,
            occurred_at=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc),
            close=5000.0,
            moving_average=5010.0,
            ma_key=f"{ma_type}{ma_period}",
        )


class FakeNotifier:
    def __init__(self) -> None:
        self.sent = []

    async def send_signal(self, signal) -> None:
        self.sent.append(signal)


def test_evaluate_saved_edge_rules_creates_signal_without_tradingview_alert() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        create_edge_alert_rule(
            db,
            {
                "name": "S&P 500 weekly SMA60 touch",
                "symbol": "SPX",
                "timeframe": "1w",
                "direction": "LONG",
                "ma_period": 60,
                "tolerance_pct": 0.005,
                "cooldown_hours": 168,
            },
        )
        notifier = FakeNotifier()

        result = run_async(
            evaluate_saved_edge_rules(
                db,
                market_data=FakeMarketData(),
                notifier=notifier,
            )
        )

        assert result["rules_evaluated"] == 1
        assert result["rules_matched"] == 1
        assert result["signals_created"] == 1
        assert len(notifier.sent) == 1
        assert notifier.sent[0].strategy_name == "rare_edge_rules"


def run_async(awaitable):
    import asyncio

    return asyncio.run(awaitable)
