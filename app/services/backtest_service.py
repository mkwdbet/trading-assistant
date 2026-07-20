import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.engine import run_backtest
from app.backtest.models import BacktestRequest, Candle
from app.conditions.registry import normalize_entry_conditions
from app.db.models import BacktestRun
from app.services.market_data import BinanceFuturesMarketData


async def run_and_store_backtest(
    db: Session,
    payload: dict[str, Any],
    *,
    market_data: BinanceFuturesMarketData | None = None,
) -> dict[str, Any]:
    risk = dict(payload.get("risk") or {})
    conditions = normalize_entry_conditions(
        payload.get("entry_conditions")
        if "entry_conditions" in payload
        else payload.get("conditions", [])
    )
    request = BacktestRequest(
        symbol=payload["symbol"],
        direction=payload.get("direction", "BOTH"),
        timeframe=payload.get("timeframe", "4h"),
        conditions=conditions,
        atr_multiplier=float(risk.get("sl_atr_multiplier", payload.get("atr_multiplier", 1.5))),
        risk_reward_ratio=float(risk.get("risk_reward_ratio", payload.get("risk_reward_ratio", 2.0))),
        max_holding_hours=int(risk.get("max_holding_hours", payload.get("max_holding_hours", 72))),
        touch_tolerance_pct=float(payload.get("touch_tolerance_pct", 0.001)),
    )
    start_time = _parse_datetime(payload["start_time"])
    end_time = _parse_datetime(payload["end_time"])

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
    result = run_backtest(
        candles,
        request,
        condition_candles_by_timeframe=condition_candles_by_timeframe,
    )
    trades = [trade.to_dict() for trade in result.trades]

    row = BacktestRun(
        name=payload.get("name"),
        symbol=request.symbol,
        direction=request.direction,
        timeframe=request.timeframe,
        start_time=start_time,
        end_time=end_time,
        conditions_json=json.dumps(request.conditions),
        atr_multiplier=request.atr_multiplier,
        risk_reward_ratio=request.risk_reward_ratio,
        max_holding_hours=request.max_holding_hours,
        metrics_json=json.dumps(result.metrics),
        trades_json=json.dumps(trades),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return _run_to_dict(row)


def list_backtest_runs(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.scalars(select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit))
    return [_run_to_dict(row, include_trades=False) for row in rows]


def get_backtest_run(db: Session, run_id: int) -> dict[str, Any] | None:
    row = db.get(BacktestRun, run_id)
    if row is None:
        return None
    run = _run_to_dict(row, include_trades=True)
    run["charts"] = build_backtest_run_charts(run)
    return run


def delete_backtest_run(db: Session, run_id: int) -> bool:
    row = db.get(BacktestRun, run_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def _run_to_dict(row: BacktestRun, *, include_trades: bool = True) -> dict[str, Any]:
    data = {
        "id": row.id,
        "name": row.name,
        "symbol": row.symbol,
        "direction": row.direction,
        "timeframe": row.timeframe,
        "start_time": row.start_time.isoformat(),
        "end_time": row.end_time.isoformat(),
        "conditions": json.loads(row.conditions_json),
        "atr_multiplier": row.atr_multiplier,
        "risk_reward_ratio": row.risk_reward_ratio,
        "max_holding_hours": row.max_holding_hours,
        "metrics": json.loads(row.metrics_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if include_trades:
        data["trades"] = json.loads(row.trades_json)
    return data


def build_backtest_run_charts(run: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    trades = list(run.get("trades") or [])
    equity_curve = []
    drawdown_curve = []
    monthly: dict[str, float] = {}
    equity = 0.0
    peak = 0.0

    for index, trade in enumerate(trades, start=1):
        return_pct = float(trade.get("return_pct") or 0)
        exit_time = trade.get("exit_time")
        equity += return_pct
        peak = max(peak, equity)
        month = str(exit_time)[:7] if exit_time else "unknown"
        monthly[month] = monthly.get(month, 0.0) + return_pct
        equity_curve.append(
            {
                "trade": index,
                "exit_time": exit_time,
                "equity_pct": equity,
            }
        )
        drawdown_curve.append(
            {
                "trade": index,
                "exit_time": exit_time,
                "drawdown_pct": equity - peak,
            }
        )

    return {
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "return_distribution": _return_distribution(trades),
        "monthly_returns": [
            {"month": month, "return_pct": value}
            for month, value in sorted(monthly.items())
        ],
    }


def _return_distribution(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = [
        ("< -3%", lambda value: value < -3),
        ("-3% to -1%", lambda value: -3 <= value < -1),
        ("-1% to 0%", lambda value: -1 <= value < 0),
        ("0% to 1%", lambda value: 0 <= value < 1),
        ("1% to 3%", lambda value: 1 <= value < 3),
        ("> 3%", lambda value: value >= 3),
    ]
    rows = []
    returns = [float(trade.get("return_pct") or 0) for trade in trades]
    for label, predicate in buckets:
        rows.append({"bucket": label, "count": sum(1 for value in returns if predicate(value))})
    return rows


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _fetch_condition_candles_by_timeframe(
    *,
    client: BinanceFuturesMarketData,
    request: BacktestRequest,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[Candle]]:
    timeframes = sorted(
        {
            str(condition.get("params", {}).get("timeframe"))
            for condition in request.conditions
            if condition.get("params", {}).get("timeframe")
            and str(condition.get("params", {}).get("timeframe")) != request.timeframe
        },
        key=_timeframe_sort_key,
    )
    candles_by_timeframe = {}
    for timeframe in timeframes:
        raw_klines = await client.get_klines(
            symbol=request.symbol,
            interval=_binance_interval(timeframe),
            start_time=start_time,
            end_time=end_time,
        )
        candles_by_timeframe[timeframe] = [_candle_from_kline(item) for item in raw_klines]
    return candles_by_timeframe


def _timeframe_sort_key(timeframe: str) -> int:
    if timeframe == "1M":
        return 720
    normalized = timeframe.lower()
    if normalized.endswith("h"):
        return int(normalized[:-1])
    if normalized.endswith("d"):
        return int(normalized[:-1]) * 24
    if normalized.endswith("w"):
        return int(normalized[:-1]) * 168
    return 0


def _binance_interval(timeframe: str) -> str:
    if timeframe == "1M":
        return "1M"
    normalized = timeframe.lower()
    if normalized in {"240", "4h", "4"}:
        return "4h"
    if normalized in {"1h", "12h", "1d", "3d", "1w"}:
        return normalized
    return normalized


def _candle_from_kline(item: list) -> Candle:
    return Candle(
        open_time=datetime.fromtimestamp(int(item[0]) / 1000),
        open=float(item[1]),
        high=float(item[2]),
        low=float(item[3]),
        close=float(item[4]),
        volume=float(item[5]),
    )
