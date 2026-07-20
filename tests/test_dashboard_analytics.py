from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.models import Signal, SignalOutcome
from app.services.dashboard_analytics import (
    build_dashboard_summary,
    build_performance_summary,
    build_research_summary,
    build_signal_detail,
    build_strategy_analysis,
)


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_factory()


def _add_signal(
    db,
    *,
    symbol: str,
    direction: str,
    analysis_signal_type: str,
    entry_price: float,
    occurred_at: datetime,
    strategy_name: str = "sma_strategy",
) -> Signal:
    signal = Signal(
        symbol=symbol,
        timeframe="4h",
        strategy_name=strategy_name,
        signal_type=analysis_signal_type,
        direction=direction,
        analysis_signal_type=analysis_signal_type,
        market_state="STRONG_BULL" if direction == "LONG" else "STRONG_BEAR",
        situation="SMA touch",
        dedupe_key=analysis_signal_type,
        entry_price=entry_price,
        current_price=entry_price,
        sma7=entry_price * 1.02,
        sma21=entry_price,
        sma60=entry_price * 0.96,
        message="research signal",
        payload_json="{}",
        occurred_at=occurred_at,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def _add_outcome(db, signal: Signal, horizon: int, return_pct: float) -> None:
    db.add(
        SignalOutcome(
            signal_id=signal.id,
            horizon_hours=horizon,
            target_time=signal.occurred_at + timedelta(hours=horizon),
            evaluated_at=signal.occurred_at + timedelta(hours=horizon, minutes=5),
            price_after=signal.entry_price * (1 + return_pct / 100),
            return_pct=return_pct,
            max_price=signal.entry_price * 1.04,
            min_price=signal.entry_price * 0.98,
            max_favorable_return_pct=abs(return_pct) + 1,
            max_adverse_return_pct=-2.0,
        )
    )
    db.commit()


def test_dashboard_summary_counts_horizon_performance_and_charts() -> None:
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with _session() as db:
        btc = _add_signal(
            db,
            symbol="BINANCE:BTCUSDT.P",
            direction="LONG",
            analysis_signal_type="bullish_21ma_touch",
            entry_price=100.0,
            occurred_at=now - timedelta(days=1),
        )
        eth = _add_signal(
            db,
            symbol="BINANCE:ETHUSDT.P",
            direction="SHORT",
            analysis_signal_type="bearish_60ma_touch",
            entry_price=200.0,
            occurred_at=now - timedelta(days=10),
        )
        _add_outcome(db, btc, 24, 4.0)
        _add_outcome(db, eth, 24, -2.0)
        _add_outcome(db, btc, 72, 6.0)

        summary = build_dashboard_summary(db, now=now)

    assert summary["counts"]["total_signals"] == 2
    assert summary["counts"]["long_signals"] == 1
    assert summary["counts"]["short_signals"] == 1
    assert summary["counts"]["signals_7d"] == 1
    assert summary["counts"]["signals_30d"] == 2
    assert summary["horizons"]["24h"]["avg_return_pct"] == pytest.approx(1.0)
    assert summary["horizons"]["24h"]["win_rate_pct"] == pytest.approx(50.0)
    assert summary["horizons"]["72h"]["avg_return_pct"] == pytest.approx(6.0)
    assert summary["charts"]["daily_signal_counts"]
    assert summary["charts"]["cumulative_signal_counts"][-1]["count"] == 2


def test_performance_strategy_research_and_detail_summaries() -> None:
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with _session() as db:
        winner = _add_signal(
            db,
            symbol="BINANCE:BTCUSDT.P",
            direction="LONG",
            analysis_signal_type="bullish_21ma_touch",
            entry_price=100.0,
            occurred_at=now - timedelta(days=3),
        )
        loser = _add_signal(
            db,
            symbol="BINANCE:SOLUSDT.P",
            direction="SHORT",
            analysis_signal_type="bearish_21ma_touch",
            entry_price=50.0,
            occurred_at=now - timedelta(days=2),
        )
        _add_outcome(db, winner, 24, 5.0)
        _add_outcome(db, loser, 24, -3.0)

        performance = build_performance_summary(db, horizon_hours=24)
        strategy = build_strategy_analysis(db, horizon_hours=24)
        research = build_research_summary(db, horizon_hours=24, limit=20)
        detail = build_signal_detail(db, winner.id)

    assert performance["symbols"][0]["symbol"] == "BINANCE:BTCUSDT.P"
    assert performance["symbols"][0]["avg_return_pct"] == pytest.approx(5.0)
    assert strategy["best_signal_type"]["signal_type"] == "bullish_21ma_touch"
    assert research["top_winners"][0]["signal_id"] == winner.id
    assert research["top_losers"][0]["signal_id"] == loser.id
    assert detail["signal"]["id"] == winner.id
    assert detail["outcomes"]["24h"]["return_pct"] == pytest.approx(5.0)


def test_strategy_name_filter_limits_dashboard_research_and_comparisons() -> None:
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with _session() as db:
        sma = _add_signal(
            db,
            symbol="BINANCE:BTCUSDT.P",
            direction="LONG",
            analysis_signal_type="bullish_21ma_touch",
            entry_price=100.0,
            occurred_at=now - timedelta(days=1),
            strategy_name="sma_strategy",
        )
        rsi = _add_signal(
            db,
            symbol="BINANCE:ETHUSDT.P",
            direction="LONG",
            analysis_signal_type="rsi_oversold_rebound",
            entry_price=200.0,
            occurred_at=now - timedelta(days=1),
            strategy_name="rsi_strategy",
        )
        _add_outcome(db, sma, 24, 4.0)
        _add_outcome(db, rsi, 24, 9.0)

        dashboard = build_dashboard_summary(db, now=now, strategy_name="rsi_strategy")
        performance = build_performance_summary(db, horizon_hours=24, strategy_name="rsi_strategy")
        strategy = build_strategy_analysis(db, horizon_hours=24, strategy_name="rsi_strategy")
        research = build_research_summary(db, horizon_hours=24, strategy_name="rsi_strategy")

    assert dashboard["counts"]["total_signals"] == 1
    assert dashboard["horizons"]["24h"]["avg_return_pct"] == pytest.approx(9.0)
    assert performance["symbols"] == [
        {
            "symbol": "BINANCE:ETHUSDT.P",
            "signal_count": 1,
            "outcome_count": 1,
            "avg_return_pct": pytest.approx(9.0),
            "win_rate_pct": pytest.approx(100.0),
            "avg_mfe_pct": pytest.approx(10.0),
            "avg_mae_pct": pytest.approx(-2.0),
        }
    ]
    assert strategy["best_signal_type"]["signal_type"] == "rsi_oversold_rebound"
    assert research["top_winners"][0]["signal_id"] == rsi.id
