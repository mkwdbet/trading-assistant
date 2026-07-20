from datetime import datetime, timedelta, timezone

import pytest

from app.backtest.models import BacktestRequest, Candle
from app.backtest.optimizer import optimize_exit_parameters


def _candle(index: int, *, close: float, high: float | None = None, low: float | None = None) -> Candle:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=4 * index)
    return Candle(
        open_time=ts,
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=1000,
    )


def test_optimizer_generates_ranked_results_and_reuses_entry_candidates() -> None:
    candles = [
        _candle(0, close=100),
        _candle(1, close=101.2, high=101.2, low=100.2),
        _candle(2, close=101.0, high=101.4, low=100.8),
        _candle(3, close=100),
        _candle(4, close=99.0, high=100.2, low=98.9),
        _candle(5, close=98.8, high=99.2, low=98.7),
    ]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="4h",
        conditions=[],
        atr_multiplier=1.0,
        risk_reward_ratio=1.0,
        max_holding_hours=8,
    )

    optimized = optimize_exit_parameters(
        candles,
        request,
        atr_values=[1, 1, 1, 1, 1, 1],
        atr_multiplier_range={"from": 1.0, "to": 1.0, "step": 1.0},
        risk_reward_ratio_range={"from": 1.0, "to": 2.0, "step": 1.0},
        filters={"min_trades": 0},
        sort_by="expectancy_r",
    )

    assert optimized["summary"]["total_combinations"] == 2
    assert optimized["summary"]["entry_candidate_count"] == 5
    assert optimized["summary"]["filtered_combinations"] == 2
    assert [row["rank"] for row in optimized["results"]] == [1, 2]
    assert optimized["results"][0]["expectancy_r"] >= optimized["results"][1]["expectancy_r"]
    assert optimized["results"][0]["atr_multiplier"] == pytest.approx(1.0)
    assert optimized["results"][0]["risk_reward_ratio"] in {1.0, 2.0}
    assert optimized["results"][0]["max_loss_streak"] >= 0


def test_optimizer_applies_minimum_trades_profit_factor_and_mdd_filters() -> None:
    candles = [
        _candle(0, close=100),
        _candle(1, close=101.1, high=101.2, low=100.5),
        _candle(2, close=101.3, high=101.4, low=100.8),
    ]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="4h",
        conditions=[],
        atr_multiplier=1.0,
        risk_reward_ratio=1.0,
        max_holding_hours=4,
    )

    optimized = optimize_exit_parameters(
        candles,
        request,
        atr_values=[1, 1, 1],
        atr_multiplier_range={"from": 1.0, "to": 1.0, "step": 1.0},
        risk_reward_ratio_range={"from": 1.0, "to": 1.0, "step": 1.0},
        filters={"min_trades": 2, "min_profit_factor": 1.2, "max_mdd": -30},
        sort_by="expectancy_r",
    )

    assert optimized["summary"]["total_combinations"] == 1
    assert optimized["summary"]["filtered_combinations"] == 0
    assert optimized["results"] == []
