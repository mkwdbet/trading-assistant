from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.schemas import SignalCreate
from app.services.signal_repository import create_signal


def test_create_signal_persists_edge_radar_metrics() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        signal = SignalCreate(
            symbol="SPX",
            timeframe="1w",
            strategy_name="rare_edge_rules",
            signal_type="희귀 매수 우위",
            direction="LONG",
            analysis_signal_type="rare_sma60_touch",
            market_state="RARE_EDGE",
            situation="SMA60 지지",
            dedupe_key="edge_rule_1_sma60_touch",
            message="S&P 500 weekly SMA60 touch.",
            occurred_at=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc),
            payload={
                "tradingview": {"price": 5200.0, "data": {"sma60": 5180.0}},
                "metadata": {"price": 5200.0, "sma60": 5180.0},
            },
        )

        row = create_signal(db, signal)

    assert row.symbol == "SPX"
    assert row.entry_price == 5200.0
    assert row.current_price == 5200.0
    assert row.sma60 == 5180.0
    assert row.direction == "LONG"
    assert row.analysis_signal_type == "rare_sma60_touch"
