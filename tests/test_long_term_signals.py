from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.edge_market_data import EdgeMarketRow
from app.services.long_term_signals import LongTermAsset, evaluate_long_term_signals


ASSET = LongTermAsset(symbol="BTC/USD", display_name="BTC/USD")


def test_200w_sma_proximity_signal_enters_once() -> None:
    with session_factory() as db:
        rows = make_rows([100.0] * 200 + [103.0])

        first = evaluate_long_term_signals(db, asset=ASSET, rows=rows)
        second = evaluate_long_term_signals(db, asset=ASSET, rows=rows)

        assert "weekly_200sma_proximity" in {signal.analysis_signal_type for signal in first}
        assert second == []


def test_ath_drawdown_threshold_can_reenter_after_recovery() -> None:
    with session_factory() as db:
        rows = make_rows([100.0] * 210 + [59.0], high=100.0)

        first = evaluate_long_term_signals(db, asset=ASSET, rows=rows)
        first_types = {signal.analysis_signal_type for signal in first}

        assert "ath_drawdown_30" in first_types
        assert "ath_drawdown_40" in first_types
        assert "ath_drawdown_50" not in first_types
        assert evaluate_long_term_signals(db, asset=ASSET, rows=rows) == []

        evaluate_long_term_signals(db, asset=ASSET, rows=make_rows([100.0] * 210 + [65.0], high=100.0))
        reentry = evaluate_long_term_signals(db, asset=ASSET, rows=rows)
        reentry_types = {signal.analysis_signal_type for signal in reentry}

        assert "ath_drawdown_40" in reentry_types
        assert "ath_drawdown_30" not in reentry_types


def test_weekly_wilder_rsi_extreme_signals() -> None:
    with session_factory() as db:
        rows = make_rows([100.0 - index for index in range(40)])

        signals = evaluate_long_term_signals(db, asset=ASSET, rows=rows)
        signal_types = {signal.analysis_signal_type for signal in signals}

        assert "weekly_rsi_oversold" in signal_types
        assert "weekly_rsi_extreme_oversold" in signal_types


def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def make_rows(closes: list[float], high: float | None = None) -> list[EdgeMarketRow]:
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [
        EdgeMarketRow(
            time=start + timedelta(weeks=index),
            close=close,
            high=high if high is not None else close,
        )
        for index, close in enumerate(closes)
    ]
