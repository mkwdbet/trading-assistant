from datetime import datetime, timedelta, timezone

import pytest

from app.backtest.engine import run_backtest
from app.backtest.engine import _hours_per_bar
from app.backtest.models import BacktestRequest, Candle


def _candle(index: int, *, close: float, high: float | None = None, low: float | None = None) -> Candle:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=4 * index)
    return Candle(
        open_time=ts,
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=1000 + index,
    )


def _hourly_candle(index: int, *, close: float, high: float | None = None, low: float | None = None) -> Candle:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)
    return Candle(
        open_time=ts,
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=1000 + index,
    )


def test_long_backtest_records_take_profit_win() -> None:
    candles = [
        _candle(0, close=100),
        _candle(1, close=100.5, high=100.5, low=99.5),
        _candle(2, close=101.0, high=101.0, low=99.5),
        _candle(3, close=101.5, high=101.5, low=99.5),
        _candle(4, close=101.8, high=101.8, low=99.5),
        _candle(5, close=102.0, high=102.1, low=99.5),
    ]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="4h",
        conditions=[],
        atr_multiplier=1.0,
        risk_reward_ratio=2.0,
        max_holding_hours=24,
        touch_tolerance_pct=0.001,
    )

    result = run_backtest(candles, request, atr_values=[1, 1, 1, 1, 1, 1])

    assert result.metrics["total_trades"] == 1
    assert result.metrics["wins"] == 1
    assert result.metrics["win_rate_pct"] == pytest.approx(100)
    assert result.trades[0].exit_reason == "TP"
    assert result.trades[0].return_pct == pytest.approx(2.0)
    assert result.trades[0].return_r == pytest.approx(2.0)
    assert result.trades[0].stop_distance_pct == pytest.approx(1.0)


def test_short_backtest_records_stop_loss() -> None:
    candles = [
        _candle(0, close=100),
        _candle(1, close=99.8, high=100.5, low=98.5),
        _candle(2, close=99.5, high=100.5, low=98.5),
        _candle(3, close=99.2, high=100.5, low=98.5),
        _candle(4, close=99.0, high=100.5, low=98.5),
        _candle(5, close=99.0, high=101.1, low=98.5),
    ]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="SHORT",
        timeframe="4h",
        conditions=[],
        atr_multiplier=1.0,
        risk_reward_ratio=2.0,
        max_holding_hours=24,
        touch_tolerance_pct=0.001,
    )

    result = run_backtest(candles, request, atr_values=[1, 1, 1, 1, 1, 1])

    assert result.metrics["total_trades"] == 1
    assert result.metrics["losses"] == 1
    assert result.trades[0].exit_reason == "SL"
    assert result.trades[0].return_pct == pytest.approx(-1.0)
    assert result.trades[0].return_r == pytest.approx(-1.0)


def test_same_candle_touching_tp_and_sl_uses_conservative_stop_first() -> None:
    candles = [
        _candle(0, close=100),
        _candle(1, close=100.5, high=100.5, low=99.5),
        _candle(2, close=101.0, high=101.0, low=99.5),
        _candle(3, close=101.5, high=101.5, low=99.5),
        _candle(4, close=101.8, high=101.8, low=99.5),
        _candle(5, close=101.0, high=102.1, low=98.9),
    ]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="4h",
        conditions=[],
        atr_multiplier=1.0,
        risk_reward_ratio=2.0,
        max_holding_hours=24,
        touch_tolerance_pct=0.001,
    )

    result = run_backtest(candles, request, atr_values=[1, 1, 1, 1, 1, 1])

    assert result.trades[0].exit_reason == "SL"
    assert result.metrics["losses"] == 1


def test_parameterized_ma_alignment_condition_filters_entries() -> None:
    candles = [_candle(index, close=100 + index) for index in range(70)]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="4h",
        conditions=[
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
        ],
        atr_multiplier=1.0,
        risk_reward_ratio=2.0,
        max_holding_hours=24,
        touch_tolerance_pct=0.001,
    )

    result = run_backtest(candles, request, atr_values=[1] * len(candles))

    assert result.metrics["total_trades"] > 0
    assert result.trades[0].entry_time == candles[59].open_time


def test_ma_ordering_condition_filters_entries_with_price_and_ema() -> None:
    candles = [_candle(index, close=100 + index) for index in range(80)]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="4h",
        conditions=[
            {
                "type": "ma_ordering",
                "params": {
                    "timeframe": "4h",
                    "items": [
                        {"source": "price"},
                        {"source": "ma", "ma_type": "ema", "period": 21},
                        {"source": "ma", "ma_type": "sma", "period": 60},
                    ],
                },
            }
        ],
        atr_multiplier=1.0,
        risk_reward_ratio=2.0,
        max_holding_hours=24,
        touch_tolerance_pct=0.001,
    )

    result = run_backtest(candles, request, atr_values=[1] * len(candles))

    assert result.metrics["total_trades"] > 0
    assert result.trades[0].entry_time == candles[59].open_time


def test_condition_timeframe_uses_aligned_higher_timeframe_indicator_values() -> None:
    candles = [
        _hourly_candle(0, close=100),
        _hourly_candle(1, close=100),
        _hourly_candle(2, close=100),
        _hourly_candle(3, close=100),
        _hourly_candle(4, close=100),
        _hourly_candle(5, close=100),
        _hourly_candle(6, close=100),
        _hourly_candle(7, close=100),
        _hourly_candle(8, close=100),
        _hourly_candle(9, close=100, high=102.2, low=99.8),
    ]
    four_hour_candles = [
        Candle(
            open_time=datetime(2025, 12, 31, 20, tzinfo=timezone.utc) + timedelta(hours=4 * index),
            open=100,
            high=100,
            low=100,
            close=100,
            volume=1000,
        )
        for index in range(3)
    ]
    request = BacktestRequest(
        symbol="BTCUSDT.P",
        direction="LONG",
        timeframe="1h",
        conditions=[
            {
                "type": "ma_touch",
                "params": {
                    "timeframe": "4h",
                    "ma_type": "sma",
                    "period": 3,
                    "tolerance_pct": 0.001,
                },
            }
        ],
        atr_multiplier=1.0,
        risk_reward_ratio=2.0,
        max_holding_hours=4,
    )

    result = run_backtest(
        candles,
        request,
        atr_values=[1] * len(candles),
        condition_candles_by_timeframe={"4h": four_hour_candles},
    )

    assert result.metrics["total_trades"] == 1
    assert result.trades[0].entry_time == candles[8].open_time


def test_hours_per_bar_supports_research_timeframes() -> None:
    assert _hours_per_bar("1h") == 1
    assert _hours_per_bar("4h") == 4
    assert _hours_per_bar("12h") == 12
    assert _hours_per_bar("1d") == 24
    assert _hours_per_bar("3d") == 72
    assert _hours_per_bar("1w") == 168
    assert _hours_per_bar("1M") == 720
