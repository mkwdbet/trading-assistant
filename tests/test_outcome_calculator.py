import pytest

from app.services.outcome_calculator import calculate_outcome


def test_calculate_long_outcome_returns_entry_relative_performance() -> None:
    outcome = calculate_outcome(
        direction="LONG",
        entry_price=100.0,
        price_after=110.0,
        max_price=115.0,
        min_price=96.0,
    )

    assert outcome.return_pct == pytest.approx(10.0)
    assert outcome.max_favorable_return_pct == pytest.approx(15.0)
    assert outcome.max_adverse_return_pct == pytest.approx(-4.0)


def test_calculate_short_outcome_returns_entry_relative_performance() -> None:
    outcome = calculate_outcome(
        direction="SHORT",
        entry_price=100.0,
        price_after=90.0,
        max_price=104.0,
        min_price=86.0,
    )

    assert outcome.return_pct == pytest.approx(10.0)
    assert outcome.max_favorable_return_pct == pytest.approx(14.0)
    assert outcome.max_adverse_return_pct == pytest.approx(-4.0)
