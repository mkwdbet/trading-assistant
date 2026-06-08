import httpx

from app.core.config import settings
from app.schemas import SignalCreate
from app.services.discord_formatter import format_discord_signal_embed


class DiscordNotifier:
    async def send_signal(self, signal: SignalCreate) -> None:
        if not settings.enable_discord_notifications:
            return
        if not settings.discord_webhook_url:
            raise RuntimeError(
                "DISCORD_WEBHOOK_URL is required when Discord notifications are enabled."
            )

        payload = {"username": settings.discord_username, "embeds": [format_discord_signal_embed(signal)]}

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.discord_webhook_url, json=payload)
            response.raise_for_status()
