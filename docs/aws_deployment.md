# AWS 24/7 Deployment

Recommended MVP target:

```text
AWS Lightsail or EC2 Ubuntu 22.04/24.04
Docker Compose
Caddy HTTPS reverse proxy
SQLite persisted in ./data
Discord webhook notifications
```

## 1. Create AWS Server

Use either Lightsail or EC2.

Minimum MVP size:

- Ubuntu 22.04 or 24.04
- 1 vCPU
- 1 GB RAM
- 20 GB disk

Open inbound ports:

```text
22/tcp   SSH
80/tcp   HTTP for Caddy ACME challenge
443/tcp  HTTPS webhook endpoint
```

## 2. Point Domain To Server

Create a DNS A record:

```text
alerts.your-domain.com -> AWS public IPv4
```

Caddy needs a real domain pointing to the server to issue HTTPS certificates automatically.

## 3. Install Docker

SSH into the server:

```bash
ssh ubuntu@YOUR_SERVER_IP
```

Install Docker:

```bash
curl -fsSL https://raw.githubusercontent.com/mkwdbet/trading-assistant/main/scripts/aws_ubuntu_setup.sh -o aws_ubuntu_setup.sh
bash aws_ubuntu_setup.sh
```

Log out and back in so Docker group permissions apply.

## 4. Clone Project

```bash
git clone https://github.com/mkwdbet/trading-assistant.git
cd trading-assistant
cp .env.production.example .env
```

Edit `.env`:

```bash
nano .env
```

Required production values:

```env
APP_ENV=production
PUBLIC_DOMAIN=alerts.your-domain.com
ACME_EMAIL=you@example.com
TRADINGVIEW_WEBHOOK_SECRET=replace-with-long-random-secret
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
ENABLE_DISCORD_NOTIFICATIONS=true
```

Generate a secret:

```bash
openssl rand -hex 32
```

## 5. Start Production Stack

```bash
bash scripts/deploy_prod.sh
```

Check containers:

```bash
docker compose -f docker-compose.prod.yml ps
```

Check health:

```bash
curl https://alerts.your-domain.com/health
```

Expected:

```json
{"status":"ok","env":"production"}
```

## 6. Test Webhook

```bash
SECRET="your-secret"
DOMAIN="alerts.your-domain.com"

curl -X POST "https://${DOMAIN}/api/v1/webhooks/tradingview/${SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BINANCE:BTCUSDT.P",
    "timeframe": "240",
    "event": "manual_test",
    "message": "AWS production test",
    "price": 101.0,
    "data": {
      "sma7": 90.0,
      "sma21": 100.0,
      "sma60": 110.0,
      "touch_tolerance_pct": 0.001
    }
  }'
```

## 7. Update TradingView

Webhook URL:

```text
https://alerts.your-domain.com/api/v1/webhooks/tradingview/YOUR_SECRET
```

Keep the existing Pine script alert. Only replace the webhook URL and secret.

## 8. Operations

View logs:

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f caddy
```

Update app:

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Restart:

```bash
docker compose -f docker-compose.prod.yml restart
```

Stop:

```bash
docker compose -f docker-compose.prod.yml down
```

Back up SQLite:

```bash
mkdir -p backups
cp data/trading_assistant.sqlite3 "backups/trading_assistant_$(date +%Y%m%d_%H%M%S).sqlite3"
```

