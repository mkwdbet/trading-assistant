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
https://rover-safari-repairs-substance.trycloudflare.com/api/v1/webhooks/tradingview/change-me
```

Steps:

1. Open TradingView chart for `BINANCE:BTCUSDT.P`.
2. Set timeframe to `4H`.
3. Open Pine Editor.
4. Paste `tradingview/btcusdtp_sma_alert.pine`.
5. Click `Add to chart`.
6. Create alert.
7. Condition: `Trading Assistant BTCUSDT.P SMA Alert`.
8. Select `Any alert() function call`.
9. Enable `Webhook URL`.
10. Paste the webhook URL above.
11. Save the alert.

The Pine script sends JSON only when one of the MVP v1 SMA events occurs on a confirmed 4H candle.
