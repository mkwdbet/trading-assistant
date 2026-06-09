from datetime import datetime, timezone

from app.schemas import SignalCreate
from app.services.discord_formatter import format_discord_signal_embed


def test_signal_embed_uses_detailed_analysis_layout() -> None:
    signal = SignalCreate(
        id=123,
        symbol="BINANCE:BTCUSDT.P",
        timeframe="240",
        strategy_name="sma_strategy",
        signal_type="매수 관심",
        direction="LONG",
        analysis_signal_type="bullish_21ma_touch",
        market_state="STRONG_BULL",
        situation="21선 눌림",
        dedupe_key="strong_bull_sma21_touch",
        entry_price=105432.1,
        current_price=105432.1,
        sma7=104813.25,
        sma21=104256.78,
        sma60=100987.55,
        message="\n".join(
            [
                "* 4시간봉 SMA7 > SMA21 > SMA60 유지",
                "* 가격이 SMA21 재접근",
                "* 상승 추세 유지 중",
            ]
        ),
        occurred_at=datetime(2026, 6, 9, 3, 0, 45, tzinfo=timezone.utc),
        payload={"reason": ["4시간봉 SMA7 > SMA21 > SMA60 유지"]},
    )

    embed = format_discord_signal_embed(signal)

    assert embed["title"] == "🟢 BINANCE:BTCUSDT.P | 매수 관심"
    assert "📈 **상황**" in embed["description"]
    assert "SMA21이 가격을 아래에서 지지하고 재접근" in embed["description"]
    assert "🎯 **판단**" in embed["description"]
    assert "🔷 **이유**" in embed["description"]
    fields = {field["name"]: field["value"] for field in embed["fields"]}
    assert fields["현재가 (Last Price)"] == "105,432.10 USDT"
    assert fields["SMA21 대비"] == "+1.13%"
    assert fields["Signal ID"] == "123"
    assert fields["Signal Time (KST)"] == "2026-06-09 12:00:45"
    assert "12시간 후 / 24시간 후 / 48시간 후 / 72시간 후" in fields["⏳ 성과 추적 예정"]
    assert "투자에 대한 최종 책임" in embed["footer"]["text"]
