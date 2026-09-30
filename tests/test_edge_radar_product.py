from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.config import settings as app_settings
from app.db.models import Base, Signal
from app.db.session import get_db
from app.main import create_app
from app.services.dashboard_analytics import build_dashboard_summary, build_settings_summary
from app.services.edge_alert_rules import create_edge_alert_rule
from app.services.runtime_settings import set_discord_webhook_url

ROOT = Path(__file__).resolve().parents[1]


def test_fastapi_metadata_uses_edge_radar_branding() -> None:
    app = create_app()

    assert app.title == "Long-Term Edge Radar"
    assert "long-term investing radar" in app.description


def test_discord_default_name_matches_edge_radar() -> None:
    settings = Settings(_env_file=None)

    assert settings.discord_username == "Long-Term Edge Radar"


def test_dashboard_is_edge_radar_only() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert "Long-Term Edge Radar" in html
    assert "신호별 진행 상태" in html
    assert 'class="metric-card"' in html
    assert 'class="workspace"' in html
    assert 'id="signalBoard"' in html
    assert "renderSignalBoard" in js
    assert 'id="sendTestAlertButton"' in html
    assert 'id="discordSettingsForm"' in html
    assert "discordStatus" in js
    assert "/api/v1/notifications/discord/test" in js
    assert "/api/v1/settings/discord" in js
    assert "Backtest" not in html
    assert "Strategy Research" not in html
    assert "backtests" not in js
    assert "optimize" not in js.lower()


def test_dashboard_summary_counts_edge_rules() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        create_edge_alert_rule(
            db,
            {
                "name": "S&P 500 weekly SMA60 touch",
                "symbol": "SPX",
                "timeframe": "1w",
                "direction": "LONG",
                "ma_period": 60,
                "tolerance_pct": 0.005,
                "cooldown_hours": 168,
            },
        )

        summary = build_dashboard_summary(db)

    assert summary["counts"]["active_rules"] == 1
    assert summary["counts"]["total_rules"] == 1
    assert summary["counts"]["total_signals"] == 0
    assert summary["rules_by_timeframe"] == {"1w": 1}
    assert summary["rule_summaries"][0]["name"] == "S&P 500 weekly SMA60 touch"
    assert summary["rule_summaries"][0]["signal_count"] == 0
    assert summary["rule_summaries"][0]["last_signal_at"] is None


def test_settings_summary_reports_edge_evaluator_not_outcome_tracker() -> None:
    settings = build_settings_summary()

    assert settings["product"]["mode"] == "rare_edge_alerts_only"
    assert "edge_rule_evaluator" in settings
    assert "outcome_tracking" not in settings


def test_settings_summary_uses_saved_discord_webhook() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        set_discord_webhook_url(
            db,
            "https://discord.com/api/webhooks/1234567890/test-token",
        )
        summary = build_settings_summary(db)

    assert summary["discord"]["configured"] is True
    assert summary["discord"]["masked_webhook"].endswith("...-token")


def test_delete_legacy_sma_signals_keeps_edge_radar_signals() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        db.add_all(
            [
                Signal(
                    symbol="BINANCE:BTCUSDT.P",
                    timeframe="240",
                    strategy_name="sma_strategy",
                    signal_type="매수 관심",
                    message="legacy",
                    payload_json="{}",
                    occurred_at=datetime(2026, 6, 13, 8, 0, 0),
                ),
                Signal(
                    symbol="BTCUSDT.P",
                    timeframe="1w",
                    strategy_name="rare_edge_rules",
                    signal_type="희귀 매수 우위",
                    message="edge",
                    payload_json="{}",
                    occurred_at=datetime(2026, 9, 29, 15, 7, 6),
                ),
            ]
        )
        db.commit()

    def override_get_db():
        with session_factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.delete(f"/api/v1/signals/legacy-sma/{app_settings.tradingview_webhook_secret}")

    assert response.status_code == 200
    assert response.json()["deleted"] == 1
    assert response.json()["remaining"] == 1
    with session_factory() as db:
        remaining = db.query(Signal).one()
    assert remaining.strategy_name == "rare_edge_rules"
