import logging

from app.schemas import SignalCreate
from app.services.discord import DiscordNotifier
from app.services.kakao import KakaoNotifier

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self) -> None:
        self.notifiers = [
            DiscordNotifier(),
            KakaoNotifier(),
        ]

    async def send_signal(self, signal: SignalCreate) -> None:
        for notifier in self.notifiers:
            try:
                await notifier.send_signal(signal)
            except Exception:
                logger.exception("%s failed to send signal", notifier.__class__.__name__)
