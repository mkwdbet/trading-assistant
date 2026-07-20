from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.indicators.core import sma

YAHOO_CHART_BASE_URL = "https://query2.finance.yahoo.com/v8/finance/chart"

YAHOO_SYMBOL_ALIASES = {
    "SPX": "^GSPC",
    "TVC:SPX": "^GSPC",
    "SP500": "^GSPC",
    "S&P500": "^GSPC",
    "NDX": "^NDX",
    "NASDAQ:NDX": "^NDX",
    "DJI": "^DJI",
    "DXY": "DX-Y.NYB",
    "BTCUSDT.P": "BTC-USD",
    "BINANCE:BTCUSDT.P": "BTC-USD",
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
    rows = []
    for timestamp, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        rows.append(
            {
                "time": datetime.fromtimestamp(int(timestamp), tz=timezone.utc),
                "close": float(close),
            }
        )
    return rows
