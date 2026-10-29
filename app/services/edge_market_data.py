from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.indicators.core import sma
from app.services.market_data import BinanceFuturesMarketData

YAHOO_CHART_BASE_URL = "https://query2.finance.yahoo.com/v8/finance/chart"
logger = logging.getLogger(__name__)

YAHOO_SYMBOL_ALIASES = {
    "SPX": "^GSPC",
    "TVC:SPX": "^GSPC",
    "SP500": "^GSPC",
    "S&P500": "^GSPC",
    "NDX": "^NDX",
    "NASDAQ:NDX": "^NDX",
    "NQ1!": "NQ=F",
    "CME_MINI:NQ1!": "NQ=F",
    "DJI": "^DJI",
    "DXY": "DX-Y.NYB",
    "BTCUSDT.P": "BTC-USD",
    "BINANCE:BTCUSDT.P": "BTC-USD",
    "BTC/USD": "BTC-USD",
    "BTCUSD": "BTC-USD",
    "ETHUSDT.P": "ETH-USD",
    "BINANCE:ETHUSDT.P": "ETH-USD",
}


@dataclass(frozen=True)
class EdgeMarketSnapshot:
    symbol: str
    provider_symbol: str
    timeframe: str
    occurred_at: datetime
    close: float
    moving_average: float
    ma_key: str


@dataclass(frozen=True)
class EdgeMarketRow:
    time: datetime
    close: float
    high: float | None = None


class YahooEdgeMarketData:
    def __init__(self, base_url: str = YAHOO_CHART_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_snapshot(
        self,
        *,
        symbol: str,
        timeframe: str,
        ma_type: str,
        ma_period: int,
    ) -> EdgeMarketSnapshot | None:
        if ma_type.lower() != "sma":
            raise ValueError("Only SMA snapshots are supported")

        provider_symbol = normalize_yahoo_symbol(symbol)
        interval = _yahoo_interval(timeframe)
        range_value = _range_for_period(timeframe, ma_period)
        result = await self._get_chart(provider_symbol, interval=interval, range_value=range_value)
        rows = _extract_rows(result)
        if len(rows) < ma_period:
            return None

        closes = [row["close"] for row in rows]
        values = sma(closes, ma_period)
        latest_ma = values[-1]
        if latest_ma is None:
            return None

        latest = rows[-1]
        return EdgeMarketSnapshot(
            symbol=symbol,
            provider_symbol=provider_symbol,
            timeframe=timeframe,
            occurred_at=latest["time"],
            close=latest["close"],
            moving_average=latest_ma,
            ma_key=f"{ma_type.lower()}{ma_period}",
        )

    async def get_weekly_series(self, *, symbol: str) -> list[EdgeMarketRow]:
        provider_symbol = normalize_yahoo_symbol(symbol)
        result = await self._get_chart(provider_symbol, interval="1wk", range_value="max")
        rows = _extract_rows(result)
        return [EdgeMarketRow(time=row["time"], close=row["close"], high=row.get("high")) for row in rows]

    async def _get_chart(self, symbol: str, *, interval: str, range_value: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/{symbol}",
                params={"interval": interval, "range": range_value},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
                    ),
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()


class BinancePerpetualEdgeMarketData:
    def __init__(self, futures: BinanceFuturesMarketData | None = None) -> None:
        self.futures = futures or BinanceFuturesMarketData()

    async def get_snapshot(
        self, *, symbol: str, timeframe: str, ma_type: str, ma_period: int
    ) -> EdgeMarketSnapshot | None:
        if ma_type.lower() != "sma":
            raise ValueError("Only SMA snapshots are supported")

        intervals = {"1w": timedelta(weeks=1), "1d": timedelta(days=1), "4h": timedelta(hours=4)}
        if timeframe not in intervals:
            raise ValueError(f"Unsupported Binance timeframe: {timeframe}")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - intervals[timeframe] * (ma_period + 10)
        klines = await self.futures.get_klines(
            symbol="BTCUSDT.P", interval=timeframe, start_time=start_time, end_time=end_time
        )
        if len(klines) < ma_period:
            logger.warning(
                "Skipping %s %s SMA%s: only %s Binance futures candles",
                symbol, timeframe, ma_period, len(klines),
            )
            return None
        closes = [float(row[4]) for row in klines]
        moving_average = sma(closes, ma_period)[-1]
        if moving_average is None:
            return None
        return EdgeMarketSnapshot(
            symbol=symbol,
            provider_symbol="BTCUSDT",
            timeframe=timeframe,
            occurred_at=datetime.fromtimestamp(int(klines[-1][0]) / 1000, tz=timezone.utc),
            close=closes[-1],
            moving_average=moving_average,
            ma_key=f"sma{ma_period}",
        )

    async def get_weekly_series(self, *, symbol: str) -> list[EdgeMarketRow]:
        klines = await self.futures.get_klines(
            symbol="BTCUSDT.P",
            interval="1w",
            start_time=datetime(2019, 9, 1, tzinfo=timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        return [
            EdgeMarketRow(
                time=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                close=float(row[4]),
                high=float(row[2]),
            )
            for row in klines
        ]


class EdgeMarketData:
    def __init__(
        self,
        yahoo: YahooEdgeMarketData | None = None,
        binance: BinancePerpetualEdgeMarketData | None = None,
    ) -> None:
        self.yahoo = yahoo or YahooEdgeMarketData()
        self.binance = binance or BinancePerpetualEdgeMarketData()

    async def get_snapshot(
        self, *, symbol: str, timeframe: str, ma_type: str, ma_period: int
    ) -> EdgeMarketSnapshot | None:
        provider = self.binance if _is_btc_perpetual(symbol) else self.yahoo
        return await provider.get_snapshot(
            symbol=symbol, timeframe=timeframe, ma_type=ma_type, ma_period=ma_period
        )

    async def get_weekly_series(self, *, symbol: str) -> list[EdgeMarketRow]:
        provider = self.binance if _is_btc_perpetual(symbol) else self.yahoo
        return await provider.get_weekly_series(symbol=symbol)


def _is_btc_perpetual(symbol: str) -> bool:
    normalized = symbol.strip().upper().removeprefix("BINANCE:")
    return normalized in {"BTCUSDT.P", "BTC/USD"}


def normalize_yahoo_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized in YAHOO_SYMBOL_ALIASES:
        return YAHOO_SYMBOL_ALIASES[normalized]
    if ":" in normalized:
        normalized = normalized.split(":", 1)[1]
    if normalized.endswith(".P"):
        return normalized.replace(".P", "-USD")
    return normalized


def _yahoo_interval(timeframe: str) -> str:
    normalized = timeframe.lower()
    if normalized in {"1w", "w", "week"}:
        return "1wk"
    if normalized in {"1d", "d", "day"}:
        return "1d"
    if normalized in {"4h", "240"}:
        return "1h"
    return "1d"


def _range_for_period(timeframe: str, ma_period: int) -> str:
    normalized = timeframe.lower()
    if normalized in {"1w", "w", "week"}:
        years = max(3, int(ma_period / 52) + 3)
        return f"{min(years, 10)}y"
    if normalized in {"4h", "240"}:
        return "730d"
    years = max(2, int(ma_period / 252) + 2)
    return f"{min(years, 10)}y"


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("chart", {}).get("result") or []
    if not results:
        return []
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    highs = quote.get("high") or []
    rows = []
    for index, (timestamp, close) in enumerate(zip(timestamps, closes, strict=False)):
        if close is None:
            continue
        high = highs[index] if index < len(highs) else None
        rows.append(
            {
                "time": datetime.fromtimestamp(int(timestamp), tz=timezone.utc),
                "close": float(close),
                "high": float(high) if high is not None else None,
            }
        )
    return rows
