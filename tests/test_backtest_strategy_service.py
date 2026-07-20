from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import BacktestRun, Base
from app.services.backtest_strategy_service import (
    build_backtest_strategy_performance,
    delete_backtest_strategy,
    list_backtest_strategies,
    save_backtest_strategy,
)


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_save_backtest_strategy_normalizes_conditions_and_risk() -> None:
    db = _session()

    strategy = save_backtest_strategy(
        db,
        {
            "name": "SMA21 pullback",
            "symbol": "BTCUSDT.P",
            "direction": "LONG",
            "timeframe": "4h",
            "entry_conditions": ["ma_bullish_4h", {"type": "ma_touch", "params": {"period": 21}}],
            "risk": {"sl_atr_multiplier": 1.4, "risk_reward_ratio": 2.2, "max_holding_hours": 48},
        },
    )

    assert strategy["name"] == "SMA21 pullback"
    assert strategy["conditions"][0]["type"] == "ma_alignment"
    assert strategy["conditions"][1] == {
        "type": "ma_touch",
        "params": {"timeframe": "4h", "ma_type": "sma", "period": 21, "tolerance_pct": 0.001},
    }
    assert strategy["risk"] == {
        "sl_atr_multiplier": 1.4,
        "risk_reward_ratio": 2.2,
        "max_holding_hours": 48,
    }


def test_save_backtest_strategy_updates_existing_name() -> None:
    db = _session()

    first = save_backtest_strategy(
        db,
        {
            "name": "Reusable",
            "symbol": "BTCUSDT.P",
            "direction": "LONG",
            "timeframe": "4h",
            "entry_conditions": [],
            "risk": {"sl_atr_multiplier": 1.5, "risk_reward_ratio": 2.0, "max_holding_hours": 24},
        },
    )
    second = save_backtest_strategy(
        db,
        {
            "name": "Reusable",
            "symbol": "ETHUSDT.P",
            "direction": "SHORT",
            "timeframe": "4h",
            "entry_conditions": ["ma_bearish_4h"],
            "risk": {"sl_atr_multiplier": 1.1, "risk_reward_ratio": 1.8, "max_holding_hours": 12},
        },
    )

    strategies = list_backtest_strategies(db)

    assert first["id"] == second["id"]
    assert len(strategies) == 1
    assert strategies[0]["symbol"] == "ETHUSDT.P"
    assert strategies[0]["direction"] == "SHORT"
    assert strategies[0]["conditions"][0]["params"]["direction"] == "bearish"


def test_delete_backtest_strategy_returns_boolean() -> None:
    db = _session()
    strategy = save_backtest_strategy(
        db,
        {
            "name": "Delete me",
            "symbol": "BTCUSDT.P",
            "direction": "BOTH",
            "timeframe": "4h",
            "entry_conditions": [],
            "risk": {"sl_atr_multiplier": 1.5, "risk_reward_ratio": 2.0, "max_holding_hours": 24},
        },
    )

    assert delete_backtest_strategy(db, strategy["id"]) is True
    assert delete_backtest_strategy(db, strategy["id"]) is False
    assert list_backtest_strategies(db) == []


def test_build_backtest_strategy_performance_groups_runs_by_name() -> None:
    db = _session()
    save_backtest_strategy(
        db,
        {
            "name": "Preset A",
            "symbol": "BTCUSDT.P",
            "direction": "LONG",
            "timeframe": "4h",
            "entry_conditions": [],
            "risk": {"sl_atr_multiplier": 1.5, "risk_reward_ratio": 2.0, "max_holding_hours": 24},
        },
    )
    save_backtest_strategy(
        db,
        {
            "name": "Preset B",
            "symbol": "ETHUSDT.P",
            "direction": "SHORT",
            "timeframe": "4h",
            "entry_conditions": [],
            "risk": {"sl_atr_multiplier": 1.5, "risk_reward_ratio": 2.0, "max_holding_hours": 24},
        },
    )
    db.add_all(
        [
            BacktestRun(
                name="Preset A",
                symbol="BTCUSDT.P",
                direction="LONG",
                timeframe="4h",
                start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2026, 1, 31, tzinfo=timezone.utc),
                conditions_json="[]",
                atr_multiplier=1.5,
                risk_reward_ratio=2.0,
                max_holding_hours=24,
                metrics_json='{"total_trades": 10, "win_rate_pct": 60, "avg_return_pct": 1.2, "profit_factor": 1.8, "mdd_pct": -3.0, "max_consecutive_losses": 2}',
                trades_json="[]",
            ),
            BacktestRun(
                name="Preset A",
                symbol="BTCUSDT.P",
                direction="LONG",
                timeframe="4h",
                start_time=datetime(2026, 2, 1, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 28, tzinfo=timezone.utc),
                conditions_json="[]",
                atr_multiplier=1.5,
                risk_reward_ratio=2.0,
                max_holding_hours=24,
                metrics_json='{"total_trades": 6, "win_rate_pct": 50, "avg_return_pct": -0.4, "profit_factor": 0.8, "mdd_pct": -4.0, "max_consecutive_losses": 3}',
                trades_json="[]",
            ),
        ]
    )
    db.commit()

    rows = build_backtest_strategy_performance(db)

    preset_a = next(row for row in rows if row["name"] == "Preset A")
    preset_b = next(row for row in rows if row["name"] == "Preset B")
    assert preset_a["run_count"] == 2
    assert preset_a["total_trades"] == 16
    assert preset_a["avg_return_pct"] == pytest.approx(0.4)
    assert preset_a["avg_win_rate_pct"] == 55
    assert preset_a["avg_profit_factor"] == 1.3
    assert preset_a["worst_mdd_pct"] == -4.0
    assert preset_a["max_consecutive_losses"] == 3
    assert preset_b["run_count"] == 0
    assert preset_b["avg_return_pct"] is None
