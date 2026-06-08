from app.schemas import SignalCreate
from app.services.discord import DiscordNotifier
from app.services.kakao import KakaoNotifier


class NotificationService:
    def __init__(self) -> None:
        self.notifiers = [
            DiscordNotifier(),
            KakaoNotifier(),
        ]

    async def send_signal(self, signal: SignalCreate) -> None:
        for notifier in self.notifiers:
            await notifier.send_signal(signal)
