# AlphaForge (MVP v1)

개인용 트레이딩 알림 비서 MVP입니다. TradingView webhook을 받아 전략 플러그인을 평가하고, 신호를 DB에 저장한 뒤 Discord 알림을 보냅니다.

현재 범위는 알림 전용입니다. 자동매매나 주문 기능은 없습니다.

## Architecture

자세한 설계는 [docs/architecture.md](docs/architecture.md)를 확인하세요.

핵심 흐름:

```text
TradingView Alert -> Webhook -> FastAPI -> Signal Engine -> Discord Webhook
```

## MVP v1 Strategy

현재 구현 전략은 [strategies/sma_strategy.py](strategies/sma_strategy.py) 하나입니다.

적용 종목:

- `BTCUSDT.P`
- `BINANCE:BTCUSDT.P`

사용 지표:

- 4시간봉 SMA 7
- 4시간봉 SMA 21
- 4시간봉 SMA 60

사용하지 않는 지표:

- RSI
- MACD
- 거래량
- 이격도
- 볼린저밴드

상태:

- `STRONG_BULL`: `SMA7 > SMA21 > SMA60`
- `STRONG_BEAR`: `SMA7 < SMA21 < SMA60`
- `WEAK_BULL`: `SMA7 > SMA60`, 단 `STRONG_BULL`은 아님
- `WEAK_BEAR`: `SMA7 < SMA60`, 단 `STRONG_BEAR`은 아님

이벤트:

- 정배열 완성: `기존 상태 != STRONG_BULL`, `현재 상태 == STRONG_BULL`
- 역배열 완성: `기존 상태 != STRONG_BEAR`, `현재 상태 == STRONG_BEAR`
- 정배열 + 21선 터치: `STRONG_BULL` 상태에서 가격이 SMA21 근처 접근
- 정배열 + 60선 터치: `STRONG_BULL` 상태에서 가격이 SMA60 근처 접근
- 역배열 + 21선 터치: `STRONG_BEAR` 상태에서 가격이 SMA21 근처 접근
- 역배열 + 60선 터치: `STRONG_BEAR` 상태에서 가격이 SMA60 근처 접근

동일 종목, 동일 타임프레임, 동일 이벤트, 동일 상태는 24시간 동안 1회만 발송합니다. 상태가 바뀐 뒤 다시 같은 이벤트가 발생하면 새 이벤트로 간주합니다.

## Requirements

- Python 3.11+
- Docker Desktop, Docker 실행 시
- Git

## New PC Setup

새 노트북이나 데스크톱에서 작업할 때:

```powershell
git clone https://github.com/mkwdbet/trading-assistant.git
cd trading-assistant
copy .env.example .env
```

`.env`를 열어서 값을 채웁니다.

```text
TRADINGVIEW_WEBHOOK_SECRET=원하는_긴_랜덤_문자열
KAKAO_CHANNEL_PROVIDER_URL=비즈메시지_PROVIDER_API_URL
KAKAO_CHANNEL_API_KEY=비즈메시지_PROVIDER_API_KEY
KAKAO_CHANNEL_SENDER_KEY=카카오채널_SENDER_KEY
KAKAO_CHANNEL_RECIPIENT_PHONE=내_휴대폰번호
DISCORD_WEBHOOK_URL=디스코드_웹훅_URL
ENABLE_DISCORD_NOTIFICATIONS=true
ENABLE_KAKAO_NOTIFICATIONS=false
```

`.env`는 GitHub에 올리지 않습니다. `.env.example`만 공유합니다.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Run With Docker

```powershell
copy .env.example .env
docker compose up --build
```

Open:

- API docs: http://localhost:8000/docs

SQLite data is stored in `./data`.

## Test TradingView Webhook Locally

PowerShell example:

```powershell
$body = @{
  symbol = "BINANCE:BTCUSDT.P"
  timeframe = "240"
  event = "tradingview_alert"
  message = "SMA alert"
  price = 101.0
  data = @{
    sma7 = 105.0
    sma21 = 101.1
    sma60 = 95.0
    touch_tolerance_pct = 0.001
  }
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/webhooks/tradingview/change-me" `
  -ContentType "application/json" `
  -Body $body
```

Then check:

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/signals"
```

## Add A Strategy

새 전략은 top-level `strategies/` 폴더에 파일을 추가합니다.

```text
strategies/
  sma_strategy.py
  my_strategy.py
```

Example:

```python
from app.schemas import TradingViewWebhookPayload
from app.strategies.base import BaseStrategy, StrategyContext, StrategySignal


class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "My first custom strategy"

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
                market_state=context.previous_state,
                dedupe_key="my_signal",
                message="My condition occurred.",
                occurred_at=payload.occurred_at,
                metadata={"price": payload.price},
            )
        ]
```

서버를 재시작하면 자동 등록됩니다.

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/strategies"
```

## TradingView Setup

TradingView alert webhook URL:

```text
https://your-domain.com/api/v1/webhooks/tradingview/YOUR_SECRET
```

Message body:

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

TradingView Pine Script에서는 `SMA7`, `SMA21`, `SMA60` plot 이름이 webhook JSON의 `plot()` 이름과 일치해야 합니다.

TradingView에서 exchange prefix까지 포함해 보내고 싶으면 `symbol`에 `{{exchange}}:{{ticker}}`를 사용할 수 있습니다. 현재 전략은 `BTCUSDT.P`와 `BINANCE:BTCUSDT.P` 둘 다 허용합니다.

로컬 PC에서 TradingView webhook을 직접 받으려면 ngrok 또는 Cloudflare Tunnel 같은 터널을 사용하세요.

현재 사용할 Pine Script와 설정값은 [tradingview/btcusdtp_sma_alert.pine](tradingview/btcusdtp_sma_alert.pine) 및 [tradingview/alert_setup.md](tradingview/alert_setup.md)에 정리되어 있습니다.

## Discord Webhook Setup

무료 MVP 알림 채널로 Discord 웹훅을 권장합니다.

1. Discord 서버를 만듭니다.
2. 알림을 받을 채널을 만듭니다. 예: `trading-alerts`
3. 채널 설정으로 이동합니다.
4. `연동` 또는 `Integrations`에서 `Webhooks`를 엽니다.
5. 새 웹훅을 만들고 URL을 복사합니다.
6. `.env`에 아래 값을 입력합니다.

```env
DISCORD_WEBHOOK_URL=복사한_웹훅_URL
DISCORD_USERNAME=AlphaForge
ENABLE_DISCORD_NOTIFICATIONS=true
```

Discord를 먼저 쓰면 카카오 알림톡 승인/과금 없이 TradingView -> FastAPI -> 알림 흐름을 바로 검증할 수 있습니다.

## KakaoTalk Setup

이 프로젝트는 `나에게 보내기` API를 사용하지 않습니다. 별도 카카오톡 채널을 만들고, 그 채널에서 내 카카오톡으로 알림이 오도록 설계합니다.

권장 방식:

1. 카카오톡 채널을 새로 생성합니다. 예: `Trading Alert Bot`
2. 내 카카오톡 계정으로 해당 채널을 친구 추가합니다.
3. 카카오 비즈메시지, 알림톡 또는 친구톡 발송이 가능한 provider를 연결합니다.
4. provider에서 발급받은 API URL, API key, sender key, template code를 `.env`에 입력합니다.
5. 수신 대상은 `.env`의 `KAKAO_CHANNEL_RECIPIENT_PHONE`에 내 휴대폰 번호로 설정합니다.
6. 실제 발송 시 `ENABLE_KAKAO_NOTIFICATIONS=true`로 바꿉니다.

처음 개발할 때는 `false`로 두면 DB 저장까지만 확인할 수 있습니다.

현재 코드는 provider별 API 차이를 흡수하기 위해 표준 payload를 `KAKAO_CHANNEL_PROVIDER_URL`로 POST합니다. 실제 provider가 정해지면 [app/services/kakao.py](app/services/kakao.py)의 payload 매핑만 해당 provider 규격에 맞추면 됩니다.

## GitHub Sync Rules

커밋 대상:

- `app/`
- `strategies/`
- `docs/`
- `tradingview/`
- `scripts/`
- `README.md`
- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `Caddyfile`
- `.env.example`
- `.env.production.example`
- `.gitignore`
- `pyproject.toml`

커밋 금지:

- `.env`
- `data/`
- `logs/`
- `tools/`
- `backups/`
- SQLite DB 파일
- `.venv/`

## Deployment

24시간 운영은 AWS Lightsail 또는 EC2에 배포합니다. 자세한 절차는 [docs/aws_deployment.md](docs/aws_deployment.md)를 확인하세요.

요약:

```bash
git clone https://github.com/mkwdbet/trading-assistant.git
cd trading-assistant
cp .env.production.example .env
nano .env
bash scripts/deploy_prod.sh
```

운영 webhook URL:

```text
https://YOUR_DOMAIN/api/v1/webhooks/tradingview/YOUR_SECRET
```

운영 구성은 Docker Compose + Caddy HTTPS reverse proxy를 사용합니다.
## Web Dashboard

The app serves a built-in research dashboard from the same FastAPI process.

Local URL:

```text
http://127.0.0.1:8000/dashboard
```

Production URL:

```text
http://YOUR_SERVER_OR_DOMAIN/dashboard
```

Dashboard API endpoints:

```text
GET /api/v1/dashboard
GET /api/v1/signals
GET /api/v1/signals/{signal_id}
GET /api/v1/performance
GET /api/v1/strategy-analysis
GET /api/v1/research
GET /api/v1/settings
```

The dashboard is a dark, static HTML/CSS/JavaScript interface under
`app/static/dashboard`. It uses the existing SQLite `signals` and
`signal_outcomes` tables, so no extra build step is required.

Research views:

- Dashboard: total signals, LONG/SHORT counts, recent activity, horizon returns, win rates.
- Signals: filterable signal list with 24h and 72h returns.
- Signal detail: entry metrics and 12h/24h/48h/72h outcome detail.
- Performance: symbol-level performance comparison.
- Strategy Analysis: signal-type performance comparison and best signal highlight.
- Research: top winners and losers for later strategy review.
- Settings: tracked symbols and safe Discord/outcome-tracking status.

## Backtest Lab MVP

The dashboard includes a first Backtest Lab for strategy research.

API:

```text
GET /api/v1/conditions
POST /api/v1/backtests/run
GET /api/v1/backtests
```

Current MVP supports:

- Binance futures candles
- 4H timeframe
- LONG / SHORT / BOTH
- Condition Registry based checkboxes
- ATR-based stop loss
- Risk-reward based take profit
- Max holding time
- Conservative same-candle handling: SL is counted first when TP and SL are both touched

Returned metrics include total trades, wins, losses, win rate, average return,
expectancy, profit factor, MDD, average MFE, average MAE, and max consecutive losses.
