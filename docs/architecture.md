# Long-Term Edge Radar Architecture

## Product Intent

Long-Term Edge Radar is a personal investing assistant for rare, high-value technical moments.

It is not a trading bot, not an order execution system, and no longer a short-term crypto signal system. Its job is to quietly monitor long-term conditions and send a Discord alert when a chart deserves attention.

Primary example:

```text
S&P 500 weekly price touches or approaches SMA60
```

## Runtime Flow

```text
FastAPI startup
-> SQLite init
-> background edge evaluator starts
-> evaluator loads enabled Edge Rules
-> market data provider fetches latest candles
-> rule evaluator checks rare technical condition
-> duplicate guard checks cooldown
-> signal is stored
-> Discord webhook alert is sent
```

Optional webhook flow:

```text
TradingView Alert
-> POST /api/v1/webhooks/tradingview/{secret}
-> matching saved Edge Rules are evaluated
-> signal is stored and sent to Discord
```

## Main Components

```text
app/
  api/
    routes.py                # Long-term radar API only
  core/
    config.py                # .env settings
  db/
    models.py                # signals and edge_alert_rules
    session.py               # SQLite init
  services/
    edge_alert_rules.py      # Rule CRUD and matching logic
    edge_market_data.py      # Yahoo Finance data provider
    edge_rule_evaluator.py   # Scheduled evaluator loop
    signal_repository.py     # Signal persistence and duplicate guard
    discord.py               # Discord webhook sender
    discord_formatter.py     # Discord embed formatting
    dashboard_analytics.py   # Dashboard summary data
  static/
    dashboard/
      index.html
      styles.css
      app.js
  main.py
```

## Database

### `edge_alert_rules`

Stores the long-term conditions to monitor.

| Column | Purpose |
| --- | --- |
| `id` | Rule id |
| `name` | Human rule name |
| `symbol` | Ticker such as `SPX`, `QQQ`, `AAPL` |
| `timeframe` | `1w`, `1d`, `4h` |
| `direction` | `LONG`, `SHORT`, `WATCH` |
| `ma_type` | Currently `sma` |
| `ma_period` | Moving average period, e.g. `60` |
| `tolerance_pct` | Touch tolerance as decimal, e.g. `0.005` |
| `thesis` | Why this condition matters |
| `judgment` | How to interpret the alert |
| `enabled` | Rule switch |
| `cooldown_hours` | Duplicate prevention window |

### `signals`

Stores every alert that actually fired.

| Column | Purpose |
| --- | --- |
| `symbol` | Signal ticker |
| `timeframe` | Signal timeframe |
| `strategy_name` | Currently `rare_edge_rules` |
| `signal_type` | Human alert type |
| `direction` | `LONG`, `SHORT`, or null |
| `situation` | Short situation label |
| `dedupe_key` | Stable key for cooldown |
| `entry_price` | Price at signal |
| `current_price` | Same as latest price for radar alerts |
| `message` | Human-readable reason text |
| `payload_json` | Raw source data and rule metadata |
| `occurred_at` | Market data timestamp |

Old tables such as `backtest_runs`, `signal_outcomes`, and `strategy_states` may exist in old SQLite files, but they are no longer part of the active product flow.

## API

Base URL:

```text
/api/v1
```

Active endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/edge-rules` | List saved rules |
| POST | `/edge-rules` | Create a rule |
| POST | `/edge-rules/evaluate` | Run evaluation now |
| DELETE | `/edge-rules/{rule_id}` | Delete a rule |
| POST | `/webhooks/tradingview/{secret}` | Optional TradingView payload ingestion |
| GET | `/dashboard` | Dashboard summary |
| GET | `/signals` | Signal history |
| GET | `/signals/{signal_id}` | Signal detail |
| GET | `/settings` | Runtime settings summary |

Removed from active API:

- Strategy plugin list
- Backtest runs
- Backtest strategy presets
- Exit optimization
- Outcome tracking
- Signal stats Discord report

## Rule Evaluation

Current MVP condition:

```text
abs(price - SMA) / SMA <= tolerance_pct
```

Example:

```text
SPX weekly SMA60 touch
price: 5200
SMA60: 5178
tolerance_pct: 0.005
distance: 0.42%
=> match
```

Duplicate prevention:

```text
same symbol + timeframe + rule id + condition type
=> suppressed during cooldown_hours
```

## Market Data

Scheduled evaluation uses Yahoo Finance chart data.

Common aliases:

| Input | Provider Symbol |
| --- | --- |
| `SPX` | `^GSPC` |
| `NDX` | `^NDX` |
| `DJI` | `^DJI` |
| `BTCUSDT.P` | `BTC-USD` |
| `ETHUSDT.P` | `ETH-USD` |

If a ticker does not work through Yahoo, add an alias or use TradingView webhook payloads for that asset.

## Notification

Primary channel:

```text
Discord Webhook
```

Kakao channel integration remains optional and provider-dependent, but it is not the default path.

## Deployment

Local:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Docker:

```powershell
docker compose up --build
```

AWS/VPS:

```bash
git clone https://github.com/mkwdbet/trading-assistant.git
cd trading-assistant
cp .env.production.example .env
nano .env
bash scripts/deploy_prod.sh
```

For 24-hour alerts, keep the server process alive on AWS/VPS with:

```env
ENABLE_EDGE_RULE_EVALUATOR=true
EDGE_RULE_EVALUATOR_INTERVAL_SECONDS=3600
ENABLE_DISCORD_NOTIFICATIONS=true
```

## Future Expansion

Preferred workflow:

1. Describe a new rare condition in natural language.
2. Codex turns it into a specific rule or code strategy.
3. Add focused tests.
4. Run locally.
5. Push to GitHub.
6. Deploy to AWS/VPS.

Likely future signals:

- `SPX` weekly SMA60/SMA100/SMA200 retest
- `QQQ` daily or weekly SMA200 retest
- Long-term index drawdown into moving average support
- VIX risk regime filter
- Dollar index risk filter
- Cross-asset confirmation for equity exposure
