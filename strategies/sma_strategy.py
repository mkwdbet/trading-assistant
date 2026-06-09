from app.schemas import TradingViewWebhookPayload
from app.strategies.base import BaseStrategy, StrategyContext, StrategySignal


class SmaStrategy(BaseStrategy):
    name = "sma_strategy"
    description = "4-hour SMA 7/21/60 state and touch alert strategy."
    symbols = {"BTCUSDT.P", "BINANCE:BTCUSDT.P"}
    timeframes = {"240", "4h", "4H"}
    touch_tolerance_pct = 0.001

    last_evaluated_state: str | None = None

    def evaluate(
        self,
        payload: TradingViewWebhookPayload,
        context: StrategyContext,
    ) -> list[StrategySignal]:
        values = self._extract_values(payload)
        if values is None:
            self.last_evaluated_state = None
            return []

        price, sma7, sma21, sma60, tolerance_pct = values
        current_state = self._classify_state(sma7=sma7, sma21=sma21, sma60=sma60)
        previous_state = context.previous_state
        self.last_evaluated_state = current_state

        signals: list[StrategySignal] = []

        if previous_state != "STRONG_BULL" and current_state == "STRONG_BULL":
            signals.append(
                self._signal(
                    payload=payload,
                    signal_type="상승 추세 전환",
                    situation="정배열 완성",
                    current_state=current_state,
                    dedupe_key="strong_bull_completed",
                    reason=[
                        "4시간봉 SMA7 > SMA21 > SMA60 정배열 완성",
                        f"이전 상태: {previous_state or 'NONE'}",
                        "상승 추세 전환 가능성 발생",
                    ],
                    price=price,
                    sma7=sma7,
                    sma21=sma21,
                    sma60=sma60,
                )
            )

        if previous_state != "STRONG_BEAR" and current_state == "STRONG_BEAR":
            signals.append(
                self._signal(
                    payload=payload,
                    signal_type="하락 추세 전환",
                    situation="역배열 완성",
                    current_state=current_state,
                    dedupe_key="strong_bear_completed",
                    reason=[
                        "4시간봉 SMA7 < SMA21 < SMA60 역배열 완성",
                        f"이전 상태: {previous_state or 'NONE'}",
                        "하락 추세 전환 가능성 발생",
                    ],
                    price=price,
                    sma7=sma7,
                    sma21=sma21,
                    sma60=sma60,
                )
            )

        if current_state == "STRONG_BULL" and self._is_touch(price, sma21, tolerance_pct):
            signals.append(
                self._signal(
                    payload=payload,
                    signal_type="매수 관심",
                    situation="21선 눌림",
                    current_state=current_state,
                    dedupe_key="strong_bull_sma21_touch",
                    reason=[
                        "4시간봉 SMA7 > SMA21 > SMA60 유지",
                        "가격이 SMA21 재접근",
                        "상승 추세 유지 중",
                    ],
                    price=price,
                    sma7=sma7,
                    sma21=sma21,
                    sma60=sma60,
                )
            )

        if current_state == "STRONG_BULL" and self._is_touch(price, sma60, tolerance_pct):
            signals.append(
                self._signal(
                    payload=payload,
                    signal_type="강한 매수 관심",
                    situation="60선 눌림",
                    current_state=current_state,
                    dedupe_key="strong_bull_sma60_touch",
                    reason=[
                        "4시간봉 SMA7 > SMA21 > SMA60 유지",
                        "가격이 SMA60 재접근",
                        "장기 기준선 눌림 구간",
                    ],
                    price=price,
                    sma7=sma7,
                    sma21=sma21,
                    sma60=sma60,
                )
            )

        if current_state == "STRONG_BEAR" and self._is_touch(price, sma21, tolerance_pct):
            signals.append(
                self._signal(
                    payload=payload,
                    signal_type="매도 관심",
                    situation="21선 저항",
                    current_state=current_state,
                    dedupe_key="strong_bear_sma21_touch",
                    reason=[
                        "4시간봉 SMA7 < SMA21 < SMA60 유지",
                        "가격이 SMA21 재접근",
                        "하락 추세 저항 가능성",
                    ],
                    price=price,
                    sma7=sma7,
                    sma21=sma21,
                    sma60=sma60,
                )
            )

        if current_state == "STRONG_BEAR" and self._is_touch(price, sma60, tolerance_pct):
            signals.append(
                self._signal(
                    payload=payload,
                    signal_type="강한 매도 관심",
                    situation="60선 저항",
                    current_state=current_state,
                    dedupe_key="strong_bear_sma60_touch",
                    reason=[
                        "4시간봉 SMA7 < SMA21 < SMA60 유지",
                        "가격이 SMA60 재접근",
                        "장기 기준선 저항 구간",
                    ],
                    price=price,
                    sma7=sma7,
                    sma21=sma21,
                    sma60=sma60,
                )
            )

        return signals

    def _extract_values(
        self,
        payload: TradingViewWebhookPayload,
    ) -> tuple[float, float, float, float, float] | None:
        data = payload.data
        price = payload.price if payload.price is not None else data.get("close")
        sma7 = data.get("sma7", data.get("sma_7"))
        sma21 = data.get("sma21", data.get("sma_21"))
        sma60 = data.get("sma60", data.get("sma_60"))
        tolerance_pct = data.get("touch_tolerance_pct", self.touch_tolerance_pct)

        if price is None or sma7 is None or sma21 is None or sma60 is None:
            return None

        return (
            float(price),
            float(sma7),
            float(sma21),
            float(sma60),
            float(tolerance_pct),
        )

    def _classify_state(self, *, sma7: float, sma21: float, sma60: float) -> str:
        if sma7 > sma21 > sma60:
            return "STRONG_BULL"
        if sma7 < sma21 < sma60:
            return "STRONG_BEAR"
        if sma7 > sma60:
            return "WEAK_BULL"
        if sma7 < sma60:
            return "WEAK_BEAR"
        return "NEUTRAL"

    def _is_touch(self, price: float, moving_average: float, tolerance_pct: float) -> bool:
        if moving_average == 0:
            return False
        return abs(price - moving_average) / moving_average <= tolerance_pct

    def _signal(
        self,
        *,
        payload: TradingViewWebhookPayload,
        signal_type: str,
        situation: str,
        current_state: str,
        dedupe_key: str,
        reason: list[str],
        price: float,
        sma7: float,
        sma21: float,
        sma60: float,
    ) -> StrategySignal:
        return StrategySignal(
            strategy_name=self.name,
            signal_type=signal_type,
            market_state=current_state,
            situation=situation,
            message="\n".join(f"* {item}" for item in reason),
            reason=reason,
            dedupe_key=dedupe_key,
            occurred_at=payload.occurred_at,
            metadata={
                "price": price,
                "sma7": sma7,
                "sma21": sma21,
                "sma60": sma60,
            },
        )
