from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.backtest.engine import (
    _build_context,
    _conditions_match,
    _direction_for_request,
    _max_drawdown,
    _simulate_trade,
)
from app.backtest.models import BacktestRequest, BacktestTrade, Candle
from app.conditions.registry import normalize_entry_conditions


MAX_OPTIMIZATION_COMBINATIONS = 5000


def optimize_exit_parameters(
    candles: list[Candle],
    request: BacktestRequest,
    *,
    atr_multiplier_range: dict[str, float],
    risk_reward_ratio_range: dict[str, float],
    filters: dict[str, Any] | None = None,
    sort_by: str = "expectancy_r",
    atr_values: list[float | None] | None = None,
    condition_candles_by_timeframe: dict[str, list[Candle]] | None = None,
) -> dict[str, Any]:
    atr_multipliers = _range_values(atr_multiplier_range)
    risk_reward_ratios = _range_values(risk_reward_ratio_range)
    total_combinations = len(atr_multipliers) * len(risk_reward_ratios)
    if total_combinations > MAX_OPTIMIZATION_COMBINATIONS:
        raise ValueError(f"Too many optimization combinations: {total_combinations}")

    entry_candidates = _entry_candidates(
        candles,
        request,
        atr_values=atr_values,
        condition_candles_by_timeframe=condition_candles_by_timeframe,
    )
    results = []
    for atr_multiplier in atr_multipliers:
        for risk_reward_ratio in risk_reward_ratios:
            combo_request = replace(
                request,
                atr_multiplier=atr_multiplier,
                risk_reward_ratio=risk_reward_ratio,
            )
            trades = _simulate_combo(candles, combo_request, entry_candidates)
            row = _combo_metrics(
                trades,
                atr_multiplier=atr_multiplier,
                risk_reward_ratio=risk_reward_ratio,
            )
            if _passes_filters(row, filters or {}):
                results.append(row)

    results = _sort_results(results, sort_by)
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank

    best_by_expectancy = max(results, key=lambda row: row["expectancy_r"] or float("-inf"), default=None)
    return {
        "summary": {
            "total_combinations": total_combinations,
            "filtered_combinations": len(results),
            "entry_candidate_count": len(entry_candidates),
            "best_by_expectancy": _best_summary(best_by_expectancy),
        },
        "results": results,
    }


def _entry_candidates(
    candles: list[Candle],
    request: BacktestRequest,
    *,
    atr_values: list[float | None] | None,
    condition_candles_by_timeframe: dict[str, list[Candle]] | None,
) -> list[dict[str, Any]]:
    if len(candles) < 2:
        return []

    conditions = normalize_entry_conditions(request.conditions)
    context = _build_context(
        candles,
        request,
        conditions,
        atr_values=atr_values,
        condition_candles_by_timeframe=condition_candles_by_timeframe,
    )
    candidates = []
    index = 0
    while index < len(candles) - 1:
        if not _conditions_match(context, conditions, index):
            index += 1
            continue

        atr_value = context["atr14"][index]
        if atr_value is None or atr_value <= 0:
            index += 1
            continue

        direction = _direction_for_request(request, context, index)
        if direction is None:
            index += 1
            continue

        candidates.append({"entry_index": index, "direction": direction, "atr_value": float(atr_value)})
        index += 1
    return candidates


def _simulate_combo(
    candles: list[Candle],
    request: BacktestRequest,
    entry_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    trades = []
    blocked_until = -1
    for candidate in entry_candidates:
        entry_index = int(candidate["entry_index"])
        if entry_index <= blocked_until:
            continue
        trade, exit_index = _simulate_trade(
            candles,
            request,
            direction=str(candidate["direction"]),
            entry_index=entry_index,
            atr_value=float(candidate["atr_value"]),
        )
        trades.append(
            {
                "trade": trade,
                "return_r": _return_r(
                    trade,
                    atr_value=float(candidate["atr_value"]),
                    atr_multiplier=request.atr_multiplier,
                ),
            }
        )
        blocked_until = max(exit_index, entry_index)
    return trades


def _combo_metrics(
    rows: list[dict[str, Any]],
    *,
    atr_multiplier: float,
    risk_reward_ratio: float,
) -> dict[str, Any]:
    trades: list[BacktestTrade] = [row["trade"] for row in rows]
    return_rs = [float(row["return_r"]) for row in rows]
    wins = [trade for trade in trades if trade.return_pct > 0]
    losses = [trade for trade in trades if trade.return_pct < 0]
    gross_profit = sum(trade.return_pct for trade in wins)
    gross_loss = abs(sum(trade.return_pct for trade in losses))
    total_trades = len(trades)
    return {
        "rank": None,
        "atr_multiplier": atr_multiplier,
        "risk_reward_ratio": risk_reward_ratio,
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / total_trades * 100 if total_trades else None,
        "expectancy_r": _avg(return_rs),
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "mdd": _max_drawdown([trade.return_pct for trade in trades]) if trades else None,
        "max_loss_streak": _max_loss_streak(trades),
        "avg_mfe": _avg([trade.mfe_pct for trade in trades]),
        "avg_mae": _avg([trade.mae_pct for trade in trades]),
        "total_return": sum(trade.return_pct for trade in trades),
        "avg_return": _avg([trade.return_pct for trade in trades]),
    }


def _return_r(trade: BacktestTrade, *, atr_value: float, atr_multiplier: float) -> float:
    stop_distance = atr_value * atr_multiplier
    if stop_distance <= 0 or trade.entry_price <= 0:
        return 0.0
    risk_pct = stop_distance / trade.entry_price * 100
    if risk_pct <= 0:
        return 0.0
    return trade.return_pct / risk_pct


def _passes_filters(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    min_trades = int(filters.get("min_trades") or 0)
    if row["total_trades"] < min_trades:
        return False

    min_profit_factor = filters.get("min_profit_factor")
    if min_profit_factor not in (None, ""):
        if row["profit_factor"] is None or row["profit_factor"] < float(min_profit_factor):
            return False

    max_mdd = filters.get("max_mdd")
    if max_mdd not in (None, "") and row["mdd"] is not None:
        if row["mdd"] <= float(max_mdd):
            return False

    return True


def _sort_results(results: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    key = {
        "expectancy_r": "expectancy_r",
        "profit_factor": "profit_factor",
        "mdd": "mdd",
        "win_rate": "win_rate",
        "total_return": "total_return",
    }.get(sort_by, "expectancy_r")
    return sorted(results, key=lambda row: row[key] if row[key] is not None else float("-inf"), reverse=True)


def _range_values(config: dict[str, float]) -> list[float]:
    start = Decimal(str(config["from"]))
    stop = Decimal(str(config["to"]))
    step = Decimal(str(config["step"]))
    if step <= 0:
        raise ValueError("Range step must be greater than zero")
    if stop < start:
        raise ValueError("Range to must be greater than or equal to from")

    values = []
    current = start
    while current <= stop:
        values.append(float(current))
        current += step
    return values


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _max_loss_streak(trades: list[BacktestTrade]) -> int:
    current = 0
    maximum = 0
    for trade in trades:
        if trade.return_pct < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def _best_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "atr_multiplier": row["atr_multiplier"],
        "risk_reward_ratio": row["risk_reward_ratio"],
        "expectancy_r": row["expectancy_r"],
    }
