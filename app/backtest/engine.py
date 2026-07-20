from app.backtest.models import BacktestRequest, BacktestResult, BacktestTrade, Candle
from app.conditions.registry import normalize_entry_conditions
from app.indicators.core import atr, ema, rsi, sma


def run_backtest(
    candles: list[Candle],
    request: BacktestRequest,
    *,
    atr_values: list[float | None] | None = None,
    condition_candles_by_timeframe: dict[str, list[Candle]] | None = None,
) -> BacktestResult:
    if len(candles) < 2:
        return BacktestResult(request=request, metrics=_metrics([]), trades=[])

    conditions = normalize_entry_conditions(request.conditions)
    context = _build_context(
        candles,
        request,
        conditions,
        atr_values=atr_values,
        condition_candles_by_timeframe=condition_candles_by_timeframe,
    )
    trades: list[BacktestTrade] = []
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

        trade, exit_index = _simulate_trade(
            candles,
            request,
            direction=direction,
            entry_index=index,
            atr_value=atr_value,
        )
        trades.append(trade)
        index = max(exit_index + 1, index + 1)

    return BacktestResult(request=request, metrics=_metrics(trades), trades=trades)


def _build_context(
    candles: list[Candle],
    request: BacktestRequest,
    conditions: list[dict],
    *,
    atr_values: list[float | None] | None,
    condition_candles_by_timeframe: dict[str, list[Candle]] | None = None,
) -> dict[str, list[float | None] | list[float]]:
    closes = [candle.close for candle in candles]
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    volumes = [candle.volume for candle in candles]
    context: dict[str, list[float | None] | list[float]] = {
        "close": closes,
        "sma7": sma(closes, 7),
        "sma21": sma(closes, 21),
        "sma60": sma(closes, 60),
        "rsi14": rsi(closes, 14),
        "atr14": atr_values if atr_values is not None else atr(highs, lows, closes, 14),
        "volume": volumes,
        "volume_sma20": sma(volumes, 20),
        "touch_tolerance_pct": [request.touch_tolerance_pct] * len(candles),
    }
    condition_candles_by_timeframe = condition_candles_by_timeframe or {}
    for condition in conditions:
        params = condition["params"]
        condition_timeframe = str(params.get("timeframe") or request.timeframe)
        condition_source = condition_candles_by_timeframe.get(condition_timeframe)
        condition_context = None
        if condition_source and condition_timeframe != request.timeframe:
            condition_context = _indicator_context_for_timeframe(
                base_candles=candles,
                source_candles=condition_source,
                timeframe=condition_timeframe,
                periods=_condition_periods(condition),
            )
        if condition["type"] in {"ma_alignment", "ma_touch", "ma_ordering"}:
            for period in _ma_periods(condition):
                for ma_type in _ma_types_for_period(condition, period):
                    key = _indicator_key(ma_type, period, condition_timeframe, request.timeframe)
                    values = (
                        condition_context[f"{ma_type}{period}"]
                        if condition_context
                        else _ma_values(ma_type, closes, period)
                    )
                    context.setdefault(key, values)
        if condition["type"] == "rsi_threshold":
            period = int(params["period"])
            key = _indicator_key("rsi", period, condition_timeframe, request.timeframe)
            values = condition_context[f"rsi{period}"] if condition_context else rsi(closes, period)
            context.setdefault(key, values)
        if condition["type"] in {"volume_ratio"}:
            period = int(params["period"])
            key = _indicator_key("volume_sma", period, condition_timeframe, request.timeframe)
            values = condition_context[f"volume_sma{period}"] if condition_context else sma(volumes, period)
            context.setdefault(key, values)
        if condition["type"] == "atr_rising":
            period = int(params["period"])
            key = _indicator_key("atr", period, condition_timeframe, request.timeframe)
            context.setdefault(
                key,
                condition_context[f"atr{period}"]
                if condition_context
                else atr_values if period == 14 and atr_values is not None else atr(highs, lows, closes, period),
            )
    return context


def _conditions_match(
    context: dict[str, list[float | None] | list[float]],
    conditions: list[dict],
    index: int,
) -> bool:
    return all(_condition_match(context, condition, index) for condition in conditions)


def _condition_match(
    context: dict[str, list[float | None] | list[float]],
    condition: str | dict,
    index: int,
) -> bool:
    if isinstance(condition, str):
        condition = normalize_entry_conditions([condition])[0]

    condition_type = condition["type"]
    params = condition["params"]
    timeframe = params.get("timeframe")
    close = context["close"][index]

    if condition_type == "ma_alignment":
        fast = context[_condition_indicator_key("sma", int(params["fast"]), timeframe, context)][index]
        mid = context[_condition_indicator_key("sma", int(params["mid"]), timeframe, context)][index]
        slow = context[_condition_indicator_key("sma", int(params["slow"]), timeframe, context)][index]
        if None in (fast, mid, slow):
            return False
        if params["direction"] == "bullish":
            return fast > mid > slow
        return fast < mid < slow
    if condition_type == "ma_touch":
        ma_value = context[_condition_indicator_key("sma", int(params["period"]), timeframe, context)][index]
        tolerance = float(params["tolerance_pct"])
        return ma_value is not None and abs(close - ma_value) / ma_value <= tolerance
    if condition_type == "ma_ordering":
        values = [_ma_ordering_value(context, item, timeframe, index) for item in params["items"]]
        if any(value is None for value in values):
            return False
        return all(left > right for left, right in zip(values, values[1:], strict=False))
    if condition_type == "rsi_threshold":
        rsi_value = context[_condition_indicator_key("rsi", int(params["period"]), timeframe, context)][index]
        return _compare(rsi_value, params["operator"], float(params["value"]))
    if condition_type == "volume_ratio":
        volume = context["volume"][index]
        average = context[_condition_indicator_key("volume_sma", int(params["period"]), timeframe, context)][index]
        if average is None:
            return False
        return _compare(volume / average, params["operator"], float(params["ratio"]))
    if condition_type == "atr_rising":
        key = _condition_indicator_key("atr", int(params["period"]), timeframe, context)
        atr_value = context[key][index]
        previous_atr = context[key][index - 1] if index > 0 else None
        return atr_value is not None and previous_atr is not None and atr_value > previous_atr
    return False


def _direction_for_request(
    request: BacktestRequest,
    context: dict[str, list[float | None] | list[float]],
    index: int,
) -> str | None:
    if request.direction in {"LONG", "SHORT"}:
        return request.direction
    if request.direction != "BOTH":
        return None
    if _condition_match(context, "ma_bullish_4h", index):
        return "LONG"
    if _condition_match(context, "ma_bearish_4h", index):
        return "SHORT"
    return None


def _simulate_trade(
    candles: list[Candle],
    request: BacktestRequest,
    *,
    direction: str,
    entry_index: int,
    atr_value: float,
) -> tuple[BacktestTrade, int]:
    entry_candle = candles[entry_index]
    entry_price = entry_candle.close
    stop_distance = atr_value * request.atr_multiplier
    target_distance = stop_distance * request.risk_reward_ratio
    max_bars = max(1, request.max_holding_hours // _hours_per_bar(request.timeframe))

    if direction == "LONG":
        stop_price = entry_price - stop_distance
        target_price = entry_price + target_distance
    else:
        stop_price = entry_price + stop_distance
        target_price = entry_price - target_distance

    end_index = min(len(candles) - 1, entry_index + max_bars)
    window = candles[entry_index + 1 : end_index + 1]
    exit_price = candles[end_index].close
    exit_reason = "TIME_EXIT"
    exit_index = end_index

    for offset, candle in enumerate(window, start=entry_index + 1):
        if direction == "LONG":
            stopped = candle.low <= stop_price
            targeted = candle.high >= target_price
            if stopped:
                exit_price = stop_price
                exit_reason = "SL"
                exit_index = offset
                break
            if targeted:
                exit_price = target_price
                exit_reason = "TP"
                exit_index = offset
                break
        else:
            stopped = candle.high >= stop_price
            targeted = candle.low <= target_price
            if stopped:
                exit_price = stop_price
                exit_reason = "SL"
                exit_index = offset
                break
            if targeted:
                exit_price = target_price
                exit_reason = "TP"
                exit_index = offset
                break

    observed = candles[entry_index + 1 : exit_index + 1] or [entry_candle]
    max_price = max(candle.high for candle in observed)
    min_price = min(candle.low for candle in observed)
    if direction == "LONG":
        return_pct = (exit_price - entry_price) / entry_price * 100
        mfe_pct = (max_price - entry_price) / entry_price * 100
        mae_pct = (min_price - entry_price) / entry_price * 100
    else:
        return_pct = (entry_price - exit_price) / entry_price * 100
        mfe_pct = (entry_price - min_price) / entry_price * 100
        mae_pct = (entry_price - max_price) / entry_price * 100
    stop_distance_pct = stop_distance / entry_price * 100 if entry_price else None
    return_r = return_pct / stop_distance_pct if stop_distance_pct else None

    return (
        BacktestTrade(
            symbol=request.symbol,
            direction=direction,
            entry_time=entry_candle.open_time,
            entry_price=entry_price,
            exit_time=candles[exit_index].open_time,
            exit_price=exit_price,
            exit_reason=exit_reason,
            return_pct=return_pct,
            mfe_pct=mfe_pct,
            mae_pct=mae_pct,
            return_r=return_r,
            stop_distance_pct=stop_distance_pct,
        ),
        exit_index,
    )


def _metrics(trades: list[BacktestTrade]) -> dict[str, float | int | None]:
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": None,
            "avg_return_pct": None,
            "expectancy_pct": None,
            "expectancy_r": None,
            "profit_factor": None,
            "mdd_pct": None,
            "avg_mfe_pct": None,
            "avg_mae_pct": None,
            "max_consecutive_losses": 0,
        }

    wins = [trade for trade in trades if trade.return_pct > 0]
    losses = [trade for trade in trades if trade.return_pct < 0]
    gross_profit = sum(trade.return_pct for trade in wins)
    gross_loss = abs(sum(trade.return_pct for trade in losses))
    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": len(wins) / len(trades) * 100,
        "avg_return_pct": _avg([trade.return_pct for trade in trades]),
        "expectancy_pct": _avg([trade.return_pct for trade in trades]),
        "expectancy_r": _avg([trade.return_r for trade in trades if trade.return_r is not None]),
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "mdd_pct": _max_drawdown([trade.return_pct for trade in trades]),
        "avg_mfe_pct": _avg([trade.mfe_pct for trade in trades]),
        "avg_mae_pct": _avg([trade.mae_pct for trade in trades]),
        "max_consecutive_losses": _max_consecutive_losses(trades),
    }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values)


def _max_drawdown(returns: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    return max_drawdown


def _max_consecutive_losses(trades: list[BacktestTrade]) -> int:
    current = 0
    maximum = 0
    for trade in trades:
        if trade.return_pct < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def _hours_per_bar(timeframe: str) -> int:
    if timeframe == "1M":
        return 720
    normalized = timeframe.lower()
    if normalized in {"240", "4h", "4"}:
        return 4
    if normalized.endswith("h"):
        return max(1, int(normalized[:-1]))
    if normalized.endswith("d"):
        return max(1, int(normalized[:-1]) * 24)
    if normalized.endswith("w"):
        return max(1, int(normalized[:-1]) * 168)
    return 4


def _indicator_context_for_timeframe(
    *,
    base_candles: list[Candle],
    source_candles: list[Candle],
    timeframe: str,
    periods: set[int],
) -> dict[str, list[float | None] | list[float]]:
    closes = [candle.close for candle in source_candles]
    highs = [candle.high for candle in source_candles]
    lows = [candle.low for candle in source_candles]
    volumes = [candle.volume for candle in source_candles]
    source_context: dict[str, list[float | None] | list[float]] = {
        "close": closes,
        "volume": volumes,
    }
    for period in periods | {14, 20}:
        source_context[f"sma{period}"] = sma(closes, period)
        source_context[f"ema{period}"] = ema(closes, period)
        source_context[f"rsi{period}"] = rsi(closes, period)
        source_context[f"atr{period}"] = atr(highs, lows, closes, period)
        source_context[f"volume_sma{period}"] = sma(volumes, period)
    return {
        key: _align_series_to_base(
            base_candles=base_candles,
            source_candles=source_candles,
            source_values=values,
            source_timeframe=timeframe,
        )
        for key, values in source_context.items()
    }


def _align_series_to_base(
    *,
    base_candles: list[Candle],
    source_candles: list[Candle],
    source_values: list[float | None] | list[float],
    source_timeframe: str,
) -> list[float | None]:
    aligned = []
    source_index = -1
    source_close_hours = _hours_per_bar(source_timeframe)
    for candle in base_candles:
        while source_index + 1 < len(source_candles):
            next_candle = source_candles[source_index + 1]
            next_close_time = next_candle.open_time + _time_delta(source_close_hours)
            if next_close_time > candle.open_time:
                break
            source_index += 1
        aligned.append(source_values[source_index] if source_index >= 0 else None)
    return aligned


def _time_delta(hours: int):
    from datetime import timedelta

    return timedelta(hours=hours)


def _indicator_key(prefix: str, period: int, condition_timeframe: str, request_timeframe: str) -> str:
    base_key = f"{prefix}{period}"
    if condition_timeframe == request_timeframe:
        return base_key
    return f"{base_key}@{condition_timeframe}"


def _condition_indicator_key(
    prefix: str,
    period: int,
    timeframe: str | None,
    context: dict[str, list[float | None] | list[float]],
) -> str:
    base_key = f"{prefix}{period}"
    if timeframe:
        timeframe_key = f"{base_key}@{timeframe}"
        if timeframe_key in context:
            return timeframe_key
    return base_key


def _ma_periods(condition: dict) -> list[int]:
    params = condition["params"]
    if condition["type"] == "ma_alignment":
        return [int(params["fast"]), int(params["mid"]), int(params["slow"])]
    if condition["type"] == "ma_touch":
        return [int(params["period"])]
    if condition["type"] == "ma_ordering":
        return sorted({int(item["period"]) for item in params["items"] if item["source"] == "ma"})
    return []


def _condition_periods(condition: dict) -> set[int]:
    params = condition["params"]
    if condition["type"] == "ma_alignment":
        return {int(params["fast"]), int(params["mid"]), int(params["slow"])}
    if condition["type"] == "ma_ordering":
        return {int(item["period"]) for item in params["items"] if item["source"] == "ma"}
    if condition["type"] in {"ma_touch", "rsi_threshold", "volume_ratio", "atr_rising"}:
        return {int(params["period"])}
    return set()


def _ma_types_for_period(condition: dict, period: int) -> set[str]:
    if condition["type"] == "ma_ordering":
        return {
            str(item["ma_type"])
            for item in condition["params"]["items"]
            if item["source"] == "ma" and int(item["period"]) == period
        }
    return {"sma"}


def _ma_values(ma_type: str, closes: list[float], period: int) -> list[float | None]:
    if ma_type == "ema":
        return ema(closes, period)
    return sma(closes, period)


def _ma_ordering_value(
    context: dict[str, list[float | None] | list[float]],
    item: dict,
    timeframe: str | None,
    index: int,
) -> float | None:
    if item["source"] == "price":
        return context["close"][index]
    key = _condition_indicator_key(str(item["ma_type"]), int(item["period"]), timeframe, context)
    return context[key][index]


def _compare(value: float | None, operator: str, target: float) -> bool:
    if value is None:
        return False
    if operator == ">=":
        return value >= target
    if operator == "<=":
        return value <= target
    raise ValueError(f"Unsupported operator: {operator}")
