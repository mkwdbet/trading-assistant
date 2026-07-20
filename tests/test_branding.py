from app.core.config import Settings
from app.main import create_app
from app.services.stats_discord import format_stats_embed


def test_fastapi_metadata_uses_alphaforge_branding() -> None:
    app = create_app()

    assert app.title == "AlphaForge"
    assert "crypto trading strategies" in app.description


def test_discord_defaults_and_stats_embed_use_alphaforge_branding() -> None:
    settings = Settings(_env_file=None)
    stats = {
        "total_signals": 10,
        "long_signals": 6,
        "short_signals": 4,
        "overall": {
            "24h": {
                "avg_return_pct": 1.2,
                "win_rate_pct": 60.0,
                "avg_max_favorable_return_pct": 2.1,
                "avg_max_adverse_return_pct": -0.8,
            }
        },
        "by_signal_type": {},
    }

    embed = format_stats_embed(stats)

    assert settings.discord_username == "AlphaForge"
    assert embed["title"] == "AlphaForge Signal Stats"
