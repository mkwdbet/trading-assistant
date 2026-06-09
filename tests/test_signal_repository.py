from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.schemas import SignalCreate
from app.services.signal_repository import create_signal


def test_create_signal_persists_hypothetical_entry_metrics() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        signal = SignalCreate(
            symbol="BINANCE:BTCUSDT.P",
            timeframe="240",
            strategy_name="sma_strategy",
            signal_type="매수 관심",
            market_state="STRONG_BULL",
            situation="21선 눌림",
            dedupe_key="strong_bull_sma21_touch",
            message="Hypothetical entry signal.",
            occurred_at=datetime(2026, 6, 9, 13, 30, tzinfo=timezone.utc),
            payload={
                "tradingview": {
                    "price": 101.5,
                    "data": {
                        "sma7": 105.0,
                        "sma21": 101.7,
                        "sma60": 95.0,
                    },
                },
                "metadata": {
                    "price": 101.5,
                    "sma7": 105.0,
                    "sma21": 101.7,
                    "sma60": 95.0,
                },
            },
        )

        row = create_signal(db, signal)

        assert row.entry_price == 101.5
        assert row.current_price == 101.5
        assert row.sma7 == 105.0
        assert row.sma21 == 101.7
        assert row.sma60 == 95.0
        assert row.direction == "LONG"
        assert row.analysis_signal_type == "bullish_21ma_touch"
