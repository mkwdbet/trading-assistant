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
