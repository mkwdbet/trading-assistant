from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomePerformance:
    return_pct: float
    max_favorable_return_pct: float
    max_adverse_return_pct: float


def calculate_outcome(
    *,
    direction: str,
    entry_price: float,
    price_after: float,
    max_price: float,
    min_price: float,
) -> OutcomePerformance:
    if entry_price == 0:
        raise ValueError("entry_price must not be zero")

    normalized_direction = direction.upper()
    if normalized_direction == "LONG":
        return OutcomePerformance(
            return_pct=(price_after - entry_price) / entry_price * 100,
            max_favorable_return_pct=(max_price - entry_price) / entry_price * 100,
            max_adverse_return_pct=(min_price - entry_price) / entry_price * 100,
        )
    if normalized_direction == "SHORT":
        return OutcomePerformance(
            return_pct=(entry_price - price_after) / entry_price * 100,
            max_favorable_return_pct=(entry_price - min_price) / entry_price * 100,
            max_adverse_return_pct=(entry_price - max_price) / entry_price * 100,
        )

    raise ValueError(f"Unsupported direction: {direction}")
