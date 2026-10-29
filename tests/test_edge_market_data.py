import asyncio
from datetime import datetime, timezone

from app.services.edge_market_data import (
    BinancePerpetualEdgeMarketData,
    EdgeMarketData,
    EdgeMarketRow,
    EdgeMarketSnapshot,
    normalize_yahoo_symbol,
)


def test_tradingview_nq_continuous_futures_uses_yahoo_futures_symbol() -> None:
    assert normalize_yahoo_symbol("NQ1!") == "NQ=F"
    assert normalize_yahoo_symbol("CME_MINI:NQ1!") == "NQ=F"


class FakeFutures:
    def __init__(self, count: int = 365) -> None:
        self.count = count
        self.calls = []

    async def get_klines(self, **kwargs):
        self.calls.append(kwargs)
        return [
            [1_600_000_000_000 + index * 86_400_000, "100", "105", "95", "100"]
            for index in range(self.count)
        ]


class FakeYahoo:
    async def get_snapshot(self, **kwargs):
        return EdgeMarketSnapshot(
            symbol=kwargs["symbol"],
            provider_symbol="^GSPC",
            timeframe=kwargs["timeframe"],
            occurred_at=datetime.now(timezone.utc),
            close=5000.0,
            moving_average=4900.0,
            ma_key="sma60",
        )

    async def get_weekly_series(self, *, symbol: str):
        return [EdgeMarketRow(time=datetime.now(timezone.utc), close=5000.0)]


def test_btc_snapshot_uses_binance_perpetual_klines() -> None:
    futures = FakeFutures()
    source = EdgeMarketData(yahoo=FakeYahoo(), binance=BinancePerpetualEdgeMarketData(futures))

    snapshot = asyncio.run(
        source.get_snapshot(symbol="BTCUSDT.P", timeframe="1d", ma_type="sma", ma_period=365)
    )

    assert snapshot is not None
    assert snapshot.provider_symbol == "BTCUSDT"
    assert snapshot.close == 100.0
    assert snapshot.moving_average == 100.0
    assert futures.calls[0]["symbol"] == "BTCUSDT.P"
    assert futures.calls[0]["interval"] == "1d"
    weekly_rows = asyncio.run(source.get_weekly_series(symbol="BTCUSDT.P"))
    assert weekly_rows[0].high == 105.0
    assert futures.calls[1]["interval"] == "1w"


def test_btc_snapshot_skips_insufficient_history_and_spx_uses_yahoo() -> None:
    futures = FakeFutures(count=199)
    source = EdgeMarketData(yahoo=FakeYahoo(), binance=BinancePerpetualEdgeMarketData(futures))

    missing = asyncio.run(
        source.get_snapshot(symbol="BTC/USD", timeframe="1w", ma_type="sma", ma_period=200)
    )
    assert missing is None
    spx = asyncio.run(source.get_snapshot(symbol="SPX", timeframe="1w", ma_type="sma", ma_period=60))
    assert spx is not None
    assert spx.provider_symbol == "^GSPC"
    assert len(futures.calls) == 1
