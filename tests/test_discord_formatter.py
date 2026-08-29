from datetime import datetime, timezone

from app.schemas import SignalCreate
from app.services.discord_formatter import format_discord_signal_embed


def test_signal_embed_uses_long_term_edge_layout() -> None:
    signal = SignalCreate(
        id=123,
        symbol="SPX",
        timeframe="1w",
        strategy_name="rare_edge_rules",
        signal_type="희귀 매수 우위",
        direction="LONG",
        analysis_signal_type="rare_sma60_touch",
        market_state="RARE_EDGE",
        situation="SMA60 지지",
        dedupe_key="edge_rule_1_sma60_touch",
        entry_price=5200.0,
        current_price=5200.0,
        message="\n".join(
            [
                "* 주봉 SPX 가격이 SMA60에 재접근",
                "* 현재가 5,200.00, 기준선 5,180.00, 이격 0.39%",
            ]
        ),
        occurred_at=datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc),
        payload={
            "reason": ["주봉 SPX 가격이 SMA60에 재접근"],
            "edge_rule": {
                "thesis": "주봉 기준 S&P 500이 SMA60에 닿는 드문 장기 매수 관심 구간",
                "judgment": "즉시 진입이 아니라 차트 확인용 알림입니다.",
            },
        },
    )

    embed = format_discord_signal_embed(signal)

    assert embed["title"] == "🟢 SPX | 희귀 매수 우위"
    assert "**상황**" in embed["description"]
    assert "S&P 500이 SMA60에 닿는 드문 장기 매수 관심 구간" in embed["description"]
    assert "**판단**" in embed["description"]
    assert "**이유**" in embed["description"]
    fields = {field["name"]: field["value"] for field in embed["fields"]}
    assert fields["Timeframe"] == "1W"
    assert fields["State"] == "RARE_EDGE"
    assert fields["Situation"] == "SMA60 지지"
    assert fields["Strategy"] == "rare_edge_rules"
    assert fields["Price"] == "5,200.00"
    assert fields["Occurred At"] == "2026-08-30 12:00 KST"
    assert embed["footer"]["text"] == "Long-Term Edge Radar"
