import json
import sys
from datetime import datetime, timezone

from app.schemas import SignalCreate
from app.services.discord_formatter import format_discord_signal_embed

sys.stdout.reconfigure(encoding="utf-8")

signal = SignalCreate(
    symbol="BINANCE:BTCUSDT.P",
    timeframe="240",
    strategy_name="sma_strategy",
    signal_type="매도 관심",
    market_state="STRONG_BEAR",
    situation="21선 저항",
    dedupe_key="strong_bear_sma21_touch",
    message=(
        "* SMA7 < SMA21 < SMA60 역배열 유지\n"
        "* 가격이 SMA21에 재접근\n"
        "* 하락 추세 저항 가능성"
    ),
    occurred_at=datetime(2026, 6, 8, 8, 55, tzinfo=timezone.utc),
    payload={
        "reason": [
            "SMA7 < SMA21 < SMA60 역배열 유지",
            "가격이 SMA21에 재접근",
            "하락 추세 저항 가능성",
        ],
        "metadata": {
            "price": 101234.5678,
            "sma7": 100900.1234,
            "sma21": 101250.0,
            "sma60": 103000.9876,
        },
    },
)

print(json.dumps(format_discord_signal_embed(signal), ensure_ascii=False, indent=2))
