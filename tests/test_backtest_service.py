import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.backtest_service import (
    build_backtest_run_charts,
    delete_backtest_run,
    get_backtest_run,
    list_backtest_runs,
    run_and_store_backtest,
)


class FakeMarketData:
    def __init__(self) -> None:
        self.intervals: list[str] = []

    async def get_klines(self, *, symbol: str, interval: str, start_time: datetime, end_time: datetime) -> list[list]:
        self.intervals.append(interval)
        step_hours = 24 if interval == "1d" else 4
        return [_kline(index, step_hours=step_hours) for index in range(70)]


def _kline(index: int, *, step_hours: int = 4) -> list:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=step_hours * index)
    price = 100 + index
    return [
        int(ts.timestamp() * 1000),
        str(price),
        str(price + 0.5),
        str(price - 0.5),
        str(price),
        str(1000 + index),
    ]


def test_backtest_service_accepts_entry_conditions_and_risk_object() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    result = asyncio.run(
        run_and_store_backtest(
            db,
            {
                "name": "parameterized-test",
                "symbol": "BTCUSDT.P",
                "direction": "LONG",
                "timeframe": "4h",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-02-01T00:00:00Z",
                "entry_conditions": [
                    {
                        "type": "ma_alignment",
                        "params": {"direction": "bullish", "fast": 7, "mid": 21, "slow": 60},
                    }
                ],
                "risk": {
                    "sl_atr_multiplier": 1.2,
                    "risk_reward_ratio": 1.8,
                    "max_holding_hours": 48,
                },
            },
            market_data=FakeMarketData(),
        )
    )

    assert result["conditions"] == [
        {
            "type": "ma_alignment",
            "params": {
                "direction": "bullish",
                "timeframe": "4h",
                "ma_type": "sma",
                "fast": 7,
                "mid": 21,
                "slow": 60,
            },
        }
    ]
    assert result["atr_multiplier"] == 1.2
    assert result["risk_reward_ratio"] == 1.8
    assert result["max_holding_hours"] == 48
    assert result["metrics"]["total_trades"] > 0


def test_backtest_service_fetches_condition_timeframe_candles() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    market_data = FakeMarketData()

    asyncio.run(
        run_and_store_backtest(
            db,
            {
                "name": "multi-timeframe-test",
                "symbol": "BTCUSDT.P",
                "direction": "LONG",
                "timeframe": "1h",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-02-01T00:00:00Z",
                "entry_conditions": [
                    {
                        "type": "ma_alignment",
                        "params": {
                            "direction": "bullish",
                            "timeframe": "1d",
                            "ma_type": "sma",
                            "fast": 7,
                            "mid": 21,
                            "slow": 60,
                        },
                    }
                ],
                "risk": {"sl_atr_multiplier": 1.2, "risk_reward_ratio": 1.8, "max_holding_hours": 48},
            },
            market_data=market_data,
        )
    )

    assert market_data.intervals == ["1h", "1d"]


def test_backtest_run_detail_and_delete() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    result = asyncio.run(
        run_and_store_backtest(
            db,
            {
                "name": "run-detail-test",
                "symbol": "BTCUSDT.P",
                "direction": "LONG",
                "timeframe": "4h",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-02-01T00:00:00Z",
                "entry_conditions": [],
                "risk": {"sl_atr_multiplier": 1.2, "risk_reward_ratio": 1.8, "max_holding_hours": 24},
            },
            market_data=FakeMarketData(),
        )
    )

    detail = get_backtest_run(db, result["id"])

    assert detail is not None
    assert detail["id"] == result["id"]
    assert "trades" in detail
    assert delete_backtest_run(db, result["id"]) is True
    assert delete_backtest_run(db, result["id"]) is False
    assert list_backtest_runs(db) == []


def test_build_backtest_run_charts_from_trade_returns() -> None:
    run = {
        "trades": [
            {"exit_time": "2026-01-05T00:00:00", "return_pct": 2.0},
            {"exit_time": "2026-01-10T00:00:00", "return_pct": -1.5},
            {"exit_time": "2026-02-01T00:00:00", "return_pct": 3.0},
        ]
    }

    charts = build_backtest_run_charts(run)

    assert charts["equity_curve"] == [
        {"trade": 1, "exit_time": "2026-01-05T00:00:00", "equity_pct": 2.0},
        {"trade": 2, "exit_time": "2026-01-10T00:00:00", "equity_pct": 0.5},
        {"trade": 3, "exit_time": "2026-02-01T00:00:00", "equity_pct": 3.5},
    ]
    assert charts["drawdown_curve"] == [
        {"trade": 1, "exit_time": "2026-01-05T00:00:00", "drawdown_pct": 0.0},
        {"trade": 2, "exit_time": "2026-01-10T00:00:00", "drawdown_pct": -1.5},
        {"trade": 3, "exit_time": "2026-02-01T00:00:00", "drawdown_pct": 0.0},
    ]
    assert charts["return_distribution"] == [
        {"bucket": "< -3%", "count": 0},
        {"bucket": "-3% to -1%", "count": 1},
        {"bucket": "-1% to 0%", "count": 0},
        {"bucket": "0% to 1%", "count": 0},
        {"bucket": "1% to 3%", "count": 1},
        {"bucket": "> 3%", "count": 1},
    ]
    assert charts["monthly_returns"] == [
        {"month": "2026-01", "return_pct": 0.5},
        {"month": "2026-02", "return_pct": 3.0},
    ]
