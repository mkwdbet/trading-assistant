from datetime import datetime
from typing import Any

from app.backtest.models import BacktestRequest
from app.backtest.optimizer import optimize_exit_parameters
from app.conditions.registry import normalize_entry_conditions
from app.services.backtest_service import (
    _binance_interval,
    _candle_from_kline,
    _fetch_condition_candles_by_timeframe,
    _parse_datetime,
)
from app.services.market_data import BinanceFuturesMarketData


async def optimize_exit_backtest(
    payload: dict[str, Any],
    *,
    market_data: BinanceFuturesMarketData | None = None,
) -> dict[str, Any]:
    risk_optimization = dict(payload.get("risk_optimization") or {})
    request = BacktestRequest(
        symbol=payload["symbol"],
        direction=payload.get("direction", "BOTH"),
        timeframe=payload.get("timeframe", "4h"),
        conditions=normalize_entry_conditions(payload.get("entry_conditions", payload.get("conditions", []))),
        atr_multiplier=float(_range(payload, "atr_multiplier").get("from", 1.5)),
        risk_reward_ratio=float(_range(payload, "risk_reward_ratio").get("from", 2.0)),
        max_holding_hours=_max_holding_hours(risk_optimization, payload),
        touch_tolerance_pct=float(payload.get("touch_tolerance_pct", 0.001)),
    )
    start_time = _payload_datetime(payload, "start")
    end_time = _payload_datetime(payload, "end")

    client = market_data or BinanceFuturesMarketData()
    raw_klines = await client.get_klines(
        symbol=request.symbol,
        interval=_binance_interval(request.timeframe),
        start_time=start_time,
        end_time=end_time,
    )
    candles = [_candle_from_kline(item) for item in raw_klines]
    condition_candles_by_timeframe = await _fetch_condition_candles_by_timeframe(
        client=client,
        request=request,
        start_time=start_time,
        end_time=end_time,
    )
    return optimize_exit_parameters(
        candles,
        request,
        atr_multiplier_range=_range(payload, "atr_multiplier"),
        risk_reward_ratio_range=_range(payload, "risk_reward_ratio"),
        filters=dict(payload.get("filters") or {}),
        sort_by=str(payload.get("sort_by") or "expectancy_r"),
        condition_candles_by_timeframe=condition_candles_by_timeframe,
    )


def _range(payload: dict[str, Any], key: str) -> dict[str, float]:
    risk_optimization = dict(payload.get("risk_optimization") or {})
    value = risk_optimization.get(key) or payload.get(key) or {}
    return {
        "from": float(value.get("from", 1.0)),
        "to": float(value.get("to", value.get("from", 1.0))),
        "step": float(value.get("step", 0.1)),
    }


def _max_holding_hours(risk_optimization: dict[str, Any], payload: dict[str, Any]) -> int:
    value = risk_optimization.get("max_holding", payload.get("max_holding_hours", 72))
    if isinstance(value, str) and value.endswith("h"):
        return int(value[:-1])
    return int(value)


def _payload_datetime(payload: dict[str, Any], key: str) -> datetime:
    time_key = f"{key}_time"
    date_key = f"{key}_date"
    if payload.get(time_key):
        return _parse_datetime(payload[time_key])
    if payload.get(date_key):
        suffix = "T00:00:00+00:00" if key == "start" else "T23:59:59+00:00"
        return _parse_datetime(f"{payload[date_key]}{suffix}")
    raise ValueError(f"{time_key} or {date_key} is required")
