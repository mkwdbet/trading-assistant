# Trading Assistant Architecture

## 1. System Architecture

MVP is an alert-only system. It does not place trades.

Flow:

1. TradingView alert fires from a chart or Pine Script.
2. TradingView sends a webhook to FastAPI.
3. FastAPI validates the webhook secret.
4. FastAPI loads previous strategy state from SQLite.
5. Strategy Engine auto-discovers strategy classes from `strategies/`.
6. Each strategy evaluates state changes and events from the normalized webhook payload.
7. Generated signals are de-duplicated, saved to the database, then sent to enabled notification channels.
8. Latest strategy state is saved separately from signal events.
9. Signals can be queried through REST API and later exposed in a web dashboard.

Recommended deployment shape:

- Local MVP: FastAPI + SQLite + Docker Compose.
- VPS/AWS MVP: FastAPI container + PostgreSQL + HTTPS reverse proxy.
- Later: background queue, scheduler, dashboard, metrics, auth.

## 2. Folder Structure

```text
app/
  api/
    routes.py
  core/
    config.py
  db/
    models.py
    session.py
  services/
    kakao.py
    signal_repository.py
    strategy_engine.py
  strategies/
    base.py
    loader.py
  main.py
strategies/
  sma_strategy.py
docs/
  architecture.md
Dockerfile
docker-compose.yml
.env.example
.gitignore
README.md
```

`app/strategies/` contains framework code. Top-level `strategies/` contains user strategy plugins.

## 3. Strategy Model

MVP v1 uses only 4-hour SMA values:

- Symbol: `BTCUSDT.P` on Binance, accepted as `BTCUSDT.P` or `BINANCE:BTCUSDT.P`
- `SMA7`
- `SMA21`
- `SMA60`

Excluded from the current version:

- RSI
- MACD
- volume
- moving average gap
- Bollinger Bands

State:

| State | Condition |
| --- | --- |
| STRONG_BULL | `SMA7 > SMA21 > SMA60` |
| STRONG_BEAR | `SMA7 < SMA21 < SMA60` |
| WEAK_BULL | `SMA7 > SMA60`, but not `STRONG_BULL` |
| WEAK_BEAR | `SMA7 < SMA60`, but not `STRONG_BEAR` |
| NEUTRAL | none of the above |

Events:

| Event | Condition | Signal | Situation |
| --- | --- | --- | --- |
| 정배열 완성 | previous state is not `STRONG_BULL`, current state is `STRONG_BULL` | 상승 추세 전환 | 정배열 완성 |
| 역배열 완성 | previous state is not `STRONG_BEAR`, current state is `STRONG_BEAR` | 하락 추세 전환 | 역배열 완성 |
| 정배열 + 21선 터치 | current state is `STRONG_BULL`, price is near SMA21 | 매수 관심 | 21선 눌림 |
| 정배열 + 60선 터치 | current state is `STRONG_BULL`, price is near SMA60 | 강한 매수 관심 | 60선 눌림 |
| 역배열 + 21선 터치 | current state is `STRONG_BEAR`, price is near SMA21 | 매도 관심 | 21선 저항 |
| 역배열 + 60선 터치 | current state is `STRONG_BEAR`, price is near SMA60 | 강한 매도 관심 | 60선 저항 |

Touch rule:

```text
abs(price - SMA) / SMA <= touch_tolerance_pct
```

Default tolerance is `0.001`, or 0.1%. TradingView can override it in webhook `data.touch_tolerance_pct`.

Duplicate prevention:

- Same symbol + timeframe + strategy + event + state is sent at most once per 24 hours.
- If state changes and later returns, it is treated as a new event.
- State is stored separately in `strategy_states`; events are stored in `signals`.

## 4. Database Design

MVP table: `signals`

| Column | Type | Purpose |
| --- | --- | --- |
| id | integer PK | Signal ID |
| symbol | string | Symbol such as `NASDAQ:AAPL` |
| timeframe | string | Timeframe such as `15m` |
| strategy_name | string | Strategy plugin name |
| signal_type | string | Human signal such as `매수 관심` |
| market_state | string/null | State such as `STRONG_BULL` |
| situation | string/null | Context such as `21선 눌림` |
| dedupe_key | string/null | Stable event key for duplicate prevention |
| message | text | Human-readable alert text |
| payload_json | text/json | Original TradingView payload plus strategy metadata |
| occurred_at | datetime | Market event time |
| created_at | datetime | Server persistence time |

MVP table: `strategy_states`

| Column | Type | Purpose |
| --- | --- | --- |
| id | integer PK | State row ID |
| symbol | string | Symbol |
| timeframe | string | Timeframe |
| strategy_name | string | Strategy plugin name |
| current_state | string | Latest known state |
| payload_json | text/json | Latest payload snapshot |
| updated_at | datetime | Market event time |
| created_at | datetime | First persistence time |

Unique key:

```text
symbol + timeframe + strategy_name
```

Indexes are defined on symbol, timeframe, strategy, signal type, market state, dedupe key, and event time.

Future tables:

- `strategies`: enabled/disabled strategy registry and per-strategy settings.
- `instruments`: managed symbols and exchange metadata.
- `notification_events`: delivery status, retry count, provider response.
- `users`: dashboard login and notification targets.

## 5. API Design

Base URL: `/api/v1`

### `POST /webhooks/tradingview/{secret}`

Receives TradingView alerts.

Example body:

```json
{
  "symbol": "BINANCE:BTCUSDT.P",
  "timeframe": "240",
  "event": "tradingview_alert",
  "message": "SMA 4H update",
  "price": 101.0,
  "occurred_at": "2026-06-08T05:00:00Z",
  "data": {
    "sma7": 105.0,
    "sma21": 101.1,
    "sma60": 95.0,
    "touch_tolerance_pct": 0.001
  }
}
```

Response:

```json
{
  "signals_created": 1,
  "duplicates_skipped": 0
}
```

### `GET /strategies`

Returns auto-discovered strategy plugins.

### `GET /signals`

Query signal history.

Query parameters:

- `symbol`
- `timeframe`
- `strategy_name`
- `limit`, default `100`, max `500`

## 6. TradingView Integration

TradingView webhook is the cleanest MVP integration.

1. Create an alert in TradingView.
2. Enable webhook URL.
3. Set URL:

```text
https://your-domain.com/api/v1/webhooks/tradingview/YOUR_SECRET
```

4. Use JSON message body:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "{{interval}}",
  "event": "tradingview_alert",
  "message": "SMA 4H update",
  "price": {{close}},
  "occurred_at": "{{time}}",
  "data": {
    "sma7": {{plot("SMA7")}},
    "sma21": {{plot("SMA21")}},
    "sma60": {{plot("SMA60")}},
    "touch_tolerance_pct": 0.001
  }
}
```

Notes:

- TradingView should send 4-hour data for MVP v1.
- Pine Script plot names must match `SMA7`, `SMA21`, and `SMA60`.
- This backend classifies state, detects events, records signals, and sends notifications.
- For local testing from TradingView, use a tunnel such as ngrok or Cloudflare Tunnel.

## 7. Notification Integration

### Discord Webhook

Discord is the recommended first alert channel for MVP v1 because it is free and only requires a webhook URL.

Setup:

1. Create a Discord server.
2. Create a channel such as `trading-alerts`.
3. Open channel settings.
4. Open `Integrations` -> `Webhooks`.
5. Create a webhook and copy its URL.
6. Put the URL in `.env`.

Environment variables:

```text
DISCORD_WEBHOOK_URL=
DISCORD_USERNAME=Trading Assistant
ENABLE_DISCORD_NOTIFICATIONS=true
```

The Discord payload uses an embed with:

- symbol and signal type
- timeframe
- market state
- situation
- strategy
- occurred time
- reason message

### KakaoTalk Channel

MVP does not use KakaoTalk "Send message to me".

The target design is:

```text
Trading Signal -> FastAPI -> Kakao Channel message provider -> Dedicated KakaoTalk Channel -> You
```

Kakao Developers' message API is intended for user-to-user flows inside the same service. For a service or channel to directly send informational alerts to a user, use Kakao Business Message products such as AlimTalk/FriendTalk or a provider that supports those products.

Setup:

1. Create a dedicated KakaoTalk Channel, such as `Trading Alert Bot`.
2. Add the channel as a friend from your personal KakaoTalk account.
3. Connect Kakao Business Message, AlimTalk, FriendTalk, or a compatible provider.
4. Create a message template for trading alerts if the provider requires template approval.
5. Put provider credentials in `.env`.
6. Set `ENABLE_KAKAO_NOTIFICATIONS=true`.

Environment variables:

```text
KAKAO_CHANNEL_PROVIDER_URL=
KAKAO_CHANNEL_API_KEY=
KAKAO_CHANNEL_SENDER_KEY=
KAKAO_CHANNEL_ID=
KAKAO_CHANNEL_RECIPIENT_PHONE=
KAKAO_CHANNEL_TEMPLATE_CODE=TRADING_SIGNAL
```

Current implementation sends:

- symbol
- timeframe
- signal type
- market state
- situation
- reasons

Message format:

```text
BTCUSDT.P

신호:
매수 관심

상태:
STRONG_BULL

상황:
21선 눌림

이유:
* 4시간봉 SMA7 > SMA21 > SMA60 유지
* 가격이 SMA21 재접근
* 상승 추세 유지 중
```

Provider payload:

The current implementation posts a normalized JSON payload to `KAKAO_CHANNEL_PROVIDER_URL`. Since each business message provider has a slightly different REST format, only `app/services/kakao.py` should need provider-specific mapping after the provider is selected.

Production improvement:

- Persist provider request/response.
- Persist notification delivery result.
- Add retry policy for temporary provider API failures.
- Add multiple recipients or escalation channels.

## 8. Docker Configuration

`Dockerfile` builds the FastAPI app.

`docker-compose.yml` runs:

- API container on port `8000`
- local `./data` volume for SQLite persistence
- local `./strategies` volume so strategy edits are picked up after server restart

## 9. Environment And GitHub

`.env` is never committed. `.env.example` is committed.

Committed project files:

- `app/`
- `strategies/`
- `docs/`
- `README.md`
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`
- `pyproject.toml`

Ignored files:

- `.env`
- `.venv/`
- `data/`
- SQLite database files
- Python cache/build artifacts

GitHub repository:

```text
https://github.com/mkwdbet/trading-assistant.git
```

## 10. Deployment

VPS MVP:

1. Install Docker and Docker Compose.
2. Clone GitHub repository: `https://github.com/mkwdbet/trading-assistant.git`.
3. Copy `.env.production.example` to `.env`.
4. Set webhook secret, public domain, ACME email, and Discord webhook URL.
5. Run `bash scripts/deploy_prod.sh`.
6. Caddy terminates HTTPS and reverse proxies to FastAPI.
7. Register HTTPS webhook URL in TradingView.

Detailed AWS deployment: `docs/aws_deployment.md`.

AWS option:

- Lightsail or EC2 for simple VPS-like operation.
- RDS PostgreSQL when signal history becomes important.
- ECS/Fargate when container orchestration is needed.
- Secrets Manager or SSM Parameter Store for environment variables.

## 11. Strategy Plugin Design

Add a new file in `strategies/`.

Rules:

- Define a class that inherits `BaseStrategy`.
- Set a unique `name`.
- Implement `evaluate(payload, context)`.
- Return `[]` when no signal occurs.
- Return one or more `StrategySignal` objects when conditions match.
- Restart the server to load the new file.

Example:

```python
from app.schemas import TradingViewWebhookPayload
from app.strategies.base import BaseStrategy, StrategyContext, StrategySignal


class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "My custom condition"
    symbols = {"BINANCE:BTCUSDT"}
    timeframes = {"240"}

    def evaluate(
        self,
        payload: TradingViewWebhookPayload,
        context: StrategyContext,
    ) -> list[StrategySignal]:
        if payload.data.get("my_condition") is not True:
            return []

        return [
            StrategySignal(
                strategy_name=self.name,
                signal_type="my_signal",
                dedupe_key="my_signal",
                message="My condition occurred.",
                occurred_at=payload.occurred_at,
                metadata={"price": payload.price},
            )
        ]
```

## 12. Roadmap

Phase 1:

- TradingView webhook receiver
- Strategy plugin loader
- SQLite signal storage
- KakaoTalk Channel provider notification
- Docker local execution

Phase 2:

- PostgreSQL option
- Kakao Channel provider response logging
- Notification delivery audit table
- Strategy enable/disable settings
- More detailed filtering for signal history

Phase 3:

- Web dashboard
- User login
- Strategy config UI
- Backtesting import/export
- Scheduled market data polling where webhook is insufficient

Phase 4:

- Queue worker for notification retries
- Multi-user notification targets
- AWS/VPS production hardening
- Observability, logs, metrics, alert health checks
