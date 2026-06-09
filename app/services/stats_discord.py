import httpx

from app.core.config import settings
from app.services.signal_stats import find_best_signal_type


async def send_stats_to_discord(stats: dict) -> None:
    if not settings.enable_discord_notifications or not settings.discord_webhook_url:
        return

    payload = {
        "username": settings.discord_username,
        "embeds": [format_stats_embed(stats)],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(settings.discord_webhook_url, json=payload)
        response.raise_for_status()


def format_stats_embed(stats: dict) -> dict:
    overall_24h = stats["overall"]["24h"]
    best = find_best_signal_type(stats, "24h")
    best_text = "-"
    if best is not None:
        signal_type, horizon = best
        best_text = (
            f"{signal_type}\n"
            f"24H Avg Return: {_format_pct(horizon['avg_return_pct'])}\n"
            f"Win Rate: {_format_pct(horizon['win_rate_pct'])}"
        )

    return {
        "title": "TradingAssistant Signal Stats",
        "color": 0x3498DB,
        "description": f"Total Signals: {stats['total_signals']}",
        "fields": [
            {"name": "LONG Signals", "value": str(stats["long_signals"]), "inline": True},
            {"name": "SHORT Signals", "value": str(stats["short_signals"]), "inline": True},
            {
                "name": "24H Performance",
                "value": (
                    f"Avg Return: {_format_pct(overall_24h['avg_return_pct'])}\n"
                    f"Win Rate: {_format_pct(overall_24h['win_rate_pct'])}\n"
                    f"Avg MFE: {_format_pct(overall_24h['avg_max_favorable_return_pct'])}\n"
                    f"Avg MAE: {_format_pct(overall_24h['avg_max_adverse_return_pct'])}"
                ),
                "inline": False,
            },
            {"name": "Best Signal Type", "value": best_text, "inline": False},
        ],
    }


def _format_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
