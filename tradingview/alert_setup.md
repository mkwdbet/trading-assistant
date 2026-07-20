# TradingView Alert Setup

Symbol:

```text
BINANCE:BTCUSDT.P
```

Timeframe:

```text
4H
```

Webhook URL:

```text
https://YOUR_DOMAIN/api/v1/webhooks/tradingview/YOUR_SECRET
```

Steps:

1. Open TradingView chart for `BINANCE:BTCUSDT.P`.
2. Set timeframe to `4H`.
3. Open Pine Editor.
4. Paste `tradingview/btcusdtp_sma_alert.pine`.
5. Click `Add to chart`.
6. Create alert.
7. Condition: `AlphaForge BTCUSDT.P SMA Alert`.
8. Select `Any alert() function call`.
9. Enable `Webhook URL`.
10. Paste the webhook URL above.
11. Save the alert.

The Pine script sends JSON only when one of the MVP v1 SMA events occurs on a confirmed 4H candle.

Alert behavior:

```text
Any alert() function call
```

The script handles alert frequency internally.

- Trend completion alerts fire only on confirmed 4H candle close.
- SMA21/SMA60 touch alerts fire in real time when price first enters the touch zone.
- The same touch signal type is sent at most once per 4H bar.
- This keeps touch alerts fast while avoiding TradingView's automatic shutdown caused by too many triggers in a short period.
