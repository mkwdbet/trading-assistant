import httpx

from app.core.config import settings
from app.schemas import SignalCreate


class KakaoNotifier:
    async def send_signal(self, signal: SignalCreate) -> None:
        if not settings.enable_kakao_notifications:
            return
        if not settings.kakao_channel_provider_url:
            raise RuntimeError(
                "KAKAO_CHANNEL_PROVIDER_URL is required when Kakao notifications are enabled."
            )
        if not settings.kakao_channel_api_key:
            raise RuntimeError(
                "KAKAO_CHANNEL_API_KEY is required when Kakao notifications are enabled."
            )
        if not settings.kakao_channel_recipient_phone:
            raise RuntimeError(
                "KAKAO_CHANNEL_RECIPIENT_PHONE is required when Kakao notifications are enabled."
            )

        message = (
            f"{signal.symbol}\n\n"
            f"신호:\n{signal.signal_type}\n\n"
            f"상태:\n{signal.market_state or '-'}\n\n"
            f"상황:\n{signal.situation or '-'}\n\n"
            f"이유:\n{signal.message}"
        )
        payload = {
            "sender_key": settings.kakao_channel_sender_key,
            "channel_id": settings.kakao_channel_id,
            "recipient_phone": settings.kakao_channel_recipient_phone,
            "template_code": settings.kakao_channel_template_code,
            "message": message,
            "template_variables": {
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "strategy": signal.strategy_name,
                "signal_type": signal.signal_type,
                "occurred_at": signal.occurred_at.isoformat(),
                "message": signal.message,
            },
        }
        headers = {
            "Authorization": f"Bearer {settings.kakao_channel_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.kakao_channel_provider_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
