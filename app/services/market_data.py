from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"


@dataclass(frozen=True)
class PriceWindow:
    price_after: float
    max_price: float
    min_price: float


def normalize_binance_futures_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[1]
    return normalized.replace(".P", "")


class BinanceFuturesMarketData:
    def __init__(self, base_url: str = BINANCE_FUTURES_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_price_window(
        self,
        *,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> PriceWindow | None:
        klines = await self._get_klines(
            symbol=normalize_binance_futures_symbol(symbol),
            start_time=start_time,
            end_time=end_time,
        )
        if not klines:
            return None

        highs = [float(item[2]) for item in klines]
        lows = [float(item[3]) for item in klines]
        price_after = float(klines[-1][4])
        return PriceWindow(price_after=price_after, max_price=max(highs), min_price=min(lows))

    async def get_klines(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[list]:
        return await self._get_klines(
            symbol=normalize_binance_futures_symbol(symbol),
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

    async def _get_klines(
        self,
        *,
        symbol: str,
        interval: str = "1m",
        start_time: datetime,
        end_time: datetime,
    ) -> list[list]:
        start_ms = _to_epoch_ms(start_time)
        end_ms = _to_epoch_ms(end_time)
        current_start = start_ms
        rows: list[list] = []

        async with httpx.AsyncClient(timeout=15) as client:
            while current_start <= end_ms:
                response = await client.get(
                    f"{self.base_url}/fapi/v1/klines",
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "startTime": current_start,
                        "endTime": end_ms,
                        "limit": 1000,
                    },
                )
                response.raise_for_status()
                batch = response.json()
                if not batch:
                    break

                rows.extend(batch)
                next_start = int(batch[-1][0]) + 60_000
                if next_start <= current_start:
                    break
                current_start = next_start

        return rows


def _to_epoch_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)
