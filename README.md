# Long-Term Edge Radar

개인용 장기투자 기술적 우위 레이더입니다.

이 프로젝트는 자동매매나 단타 알림을 위한 시스템이 아닙니다. S&P 500 주봉 SMA60 터치처럼 자주 오지 않지만 차트를 확인할 가치가 있는 장기 기술적 조건을 감시하고, 조건이 발생하면 Discord로 알림을 보냅니다.

## Current Scope

현재 프로젝트의 핵심 흐름:

```text
Saved Edge Rules -> Scheduled Market Data Check -> Signal Storage -> Discord Alert
```

보조 흐름:

```text
TradingView Webhook -> FastAPI -> Matching Edge Rule -> Discord Alert
```

현재 웹에서 지원하는 규칙은 `가격이 특정 SMA에 지정 오차 범위 내 접근`하는 형태입니다.

예시:

- `SPX` 주봉 `SMA60` 0.5% 이내 접근
- `QQQ` 일봉 `SMA200` 1.0% 이내 접근
- `SPY` 주봉 `SMA100` 0.7% 이내 접근

더 복잡한 아이디어는 웹 조건 빌더로 억지로 만들지 않고, Codex와 대화하면서 코드 전략으로 추가하는 방향을 권장합니다.

## Removed Direction

이전 MVP에 있던 단타 중심 기능은 새 제품 방향에서 제외되었습니다.

- BTCUSDT.P 4시간봉 SMA 7/21/60 단타 전략 제거
- 단타 전략 엔진 API 비노출
- 백테스트 랩 UI/API 비노출
- 익절/손절 최적화 UI/API 비노출
- 가상 진입 결과 추적기 비활성화

DB에 과거 테이블이 남아있을 수는 있지만, 현재 앱의 사용 흐름에서는 쓰지 않습니다.

## Tech Stack

- Python
- FastAPI
- SQLite
- Discord Webhook
- Docker
- GitHub

## Local Setup

```powershell
git clone https://github.com/mkwdbet/trading-assistant.git
cd trading-assistant
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- Dashboard: http://127.0.0.1:8000/dashboard
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Environment

`.env`는 GitHub에 올리지 않습니다. `.env.example`만 커밋합니다.

필수 설정:

```env
APP_ENV=local
DATABASE_URL=sqlite:///./data/trading_assistant.sqlite3
TRADINGVIEW_WEBHOOK_SECRET=change-me

DISCORD_WEBHOOK_URL=
DISCORD_USERNAME=Long-Term Edge Radar
ENABLE_DISCORD_NOTIFICATIONS=true

ENABLE_EDGE_RULE_EVALUATOR=true
EDGE_RULE_EVALUATOR_INTERVAL_SECONDS=3600
```

## Dashboard

```text
http://127.0.0.1:8000/dashboard
```

현재 대시보드에서 할 수 있는 일:

- 장기 Edge Rule 추가
- 저장된 Edge Rule 삭제
- 저장된 조건 즉시 평가
- 최근 알림 이력 확인
- Discord/evaluator 설정 상태 확인

## Current Saved Rule

로컬 DB 기준으로 현재 저장된 대표 규칙:

```text
S&P 500 weekly SMA60 touch
symbol: SPX
timeframe: 1w
direction: LONG
rule: SMA60 touch
tolerance: 0.5%
cooldown: 168h
```

서버가 켜져 있으면 1시간마다 이 규칙을 평가합니다.

## API

Base URL:

```text
/api/v1
```

Endpoints:

```text
GET    /edge-rules
POST   /edge-rules
POST   /edge-rules/evaluate
DELETE /edge-rules/{rule_id}

POST   /webhooks/tradingview/{secret}

GET    /dashboard
GET    /signals
GET    /signals/{signal_id}
GET    /settings
```

## Edge Rule Payload

```json
{
  "name": "S&P 500 weekly SMA60 touch",
  "symbol": "SPX",
  "timeframe": "1w",
  "direction": "LONG",
  "ma_type": "sma",
  "ma_period": 60,
  "tolerance_pct": 0.005,
  "cooldown_hours": 168,
  "thesis": "주봉 기준 S&P 500이 SMA60에 닿는 드문 장기 매수 관심 구간",
  "judgment": "장기투자 관점에서 희귀한 기술적 우위 후보입니다. 즉시 진입이 아니라 차트 확인용 알림입니다.",
  "enabled": true
}
```

## Market Data

저장된 Edge Rule은 서버가 Yahoo Finance chart API에서 가격 데이터를 가져와 평가합니다.

내부 심볼 매핑 예시:

- `SPX` -> `^GSPC`
- `NDX` -> `^NDX`
- `DJI` -> `^DJI`
- `BTCUSDT.P` -> `BTC-USD`

TradingView에서 직접 webhook을 보내는 방식도 유지합니다. 이 경우 webhook payload 안에 `price`와 `sma60` 같은 값을 포함해야 합니다.

## Discord Alerts

Discord webhook URL만 있으면 무료로 알림을 받을 수 있습니다.

`.env`:

```env
DISCORD_WEBHOOK_URL=복사한_웹훅_URL
DISCORD_USERNAME=Long-Term Edge Radar
ENABLE_DISCORD_NOTIFICATIONS=true
```

알림에는 종목, 타임프레임, 신호, 상황, 이유, 발생 시간이 포함됩니다.

## Docker

```powershell
copy .env.example .env
docker compose up --build
```

SQLite 데이터는 `./data`에 저장됩니다.

## AWS/VPS Deployment

24시간 운영하려면 AWS Lightsail, EC2, 또는 일반 VPS에 올립니다.

요약:

```bash
git clone https://github.com/mkwdbet/trading-assistant.git
cd trading-assistant
cp .env.production.example .env
nano .env
bash scripts/deploy_prod.sh
```

운영 서버에서 `ENABLE_EDGE_RULE_EVALUATOR=true`이면 PC를 꺼도 서버가 계속 조건을 평가하고 Discord 알림을 보냅니다.

## Future Strategy Workflow

앞으로 새 아이디어가 생기면 이런 식으로 진행합니다.

```text
사용자: QQQ가 주봉 SMA100에 닿고, 시장이 과열이 아닐 때만 알림 받고 싶어.
Codex: 조건을 정리하고 코드 전략 또는 Edge Rule로 구현.
테스트: 로컬에서 수동 평가.
배포: GitHub push 후 AWS 반영.
```

웹에서 모든 조건을 자유롭게 조립하는 기능은 당장 만들지 않습니다. 혼자 쓰는 서비스라면 Codex와 대화하면서 명확한 전략 파일을 하나씩 추가하는 방식이 더 단순하고 오래 유지하기 좋습니다.
