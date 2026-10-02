from collections.abc import Sequence


def sma(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
            continue
        window = values[index + 1 - period : index + 1]
        result.append(sum(window) / period)
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    multiplier = 2 / (period + 1)
    previous: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period:
            result.append(None)
            continue
        if previous is None:
            previous = sum(values[index + 1 - period : index + 1]) / period
        else:
            previous = (value - previous) * multiplier + previous
        result.append(previous)
    return result


def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    if not values:
        return []
    result: list[float | None] = [None] * len(values)
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
        if index < period:
            continue
        avg_gain = sum(gains[index - period : index]) / period
        avg_loss = sum(losses[index - period : index]) / period
        if avg_loss == 0:
            result[index] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[index] = 100 - (100 / (1 + rs))
    return result


def wilder_rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    if not values:
        return []
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, period + 1):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = _rsi_from_averages(avg_gain, avg_loss)

    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = _rsi_from_averages(avg_gain, avg_loss)

    return result


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> list[float | None]:
    true_ranges: list[float] = []
    for index, high in enumerate(highs):
        low = lows[index]
        if index == 0:
            true_ranges.append(high - low)
        else:
            previous_close = closes[index - 1]
            true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sma(true_ranges, period)
