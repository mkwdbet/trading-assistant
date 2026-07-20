from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.schemas import TradingViewWebhookPayload
from app.services.edge_alert_rules import (
    create_edge_alert_rule,
    evaluate_edge_alert_rules,
    list_edge_alert_rules,
)


def test_edge_rule_matches_tradingview_ticker_and_weekly_sma_touch() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        rule = create_edge_alert_rule(
            db,
            {
                "name": "S&P 500 weekly SMA60 touch",
                "symbol": "SPX",
                "timeframe": "1w",
                "direction": "LONG",
                "ma_period": 60,
                "tolerance_pct": 0.005,
                "cooldown_hours": 168,
                "thesis": "주봉 기준 S&P 500이 SMA60에 닿는 드문 장기 매수 관심 구간",
                "judgment": "장기투자 관점에서 희귀한 기술적 우위 후보입니다.",
            },
        )

        assert rule["symbol"] == "SPX"
        assert len(list_edge_alert_rules(db)) == 1

        payload = TradingViewWebhookPayload(
            symbol="TVC:SPX",
            timeframe="1W",
            price=5000.0,
            occurred_at=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc),
            data={"sma60": 5010.0},
        )

        matches = evaluate_edge_alert_rules(db, payload)

        assert len(matches) == 1
        _, signal = matches[0]
        assert signal.strategy_name == "rare_edge_rules"
        assert signal.signal_type == "희귀 매수 우위"
        assert signal.market_state == "RARE_EDGE"
        assert signal.situation == "SMA60 지지"
        assert signal.dedupe_key == "edge_rule_1_sma60_touch"
        assert signal.payload["edge_rule"]["name"] == "S&P 500 weekly SMA60 touch"


def test_edge_rule_does_not_match_when_price_is_outside_tolerance() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        create_edge_alert_rule(
            db,
            {
                "name": "QQQ daily SMA200 touch",
                "symbol": "QQQ",
                "timeframe": "1d",
                "direction": "LONG",
                "ma_period": 200,
                "tolerance_pct": 0.005,
            },
        )

        payload = TradingViewWebhookPayload(
            symbol="NASDAQ:QQQ",
            timeframe="1D",
            price=500.0,
            occurred_at=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc),
            data={"sma200": 450.0},
        )

        assert evaluate_edge_alert_rules(db, payload) == []
