from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app
from app.services.dashboard_analytics import build_dashboard_summary, build_settings_summary
from app.services.edge_alert_rules import create_edge_alert_rule

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
    assert "Rule Builder" in html
    assert 'class="metric-card"' in html
    assert 'class="workspace"' in html
    assert 'class="rule-form"' in html
    assert "discordStatus" in js
    assert "Backtest" not in html
    assert "Strategy Research" not in html
    assert "backtests" not in js
    assert "optimize" not in js.lower()


def test_dashboard_summary_counts_edge_rules() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
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


def test_settings_summary_reports_edge_evaluator_not_outcome_tracker() -> None:
    settings = build_settings_summary()

    assert settings["product"]["mode"] == "rare_edge_alerts_only"
    assert "edge_rule_evaluator" in settings
    assert "outcome_tracking" not in settings
