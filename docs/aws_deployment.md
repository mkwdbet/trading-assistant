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
ENABLE_EDGE_RULE_EVALUATOR=true
EDGE_RULE_EVALUATOR_INTERVAL_SECONDS=3600
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

Check dashboard:

```bash
curl -I https://alerts.your-domain.com/dashboard
curl https://alerts.your-domain.com/api/v1/dashboard
```

When using the current EC2 IP without a domain:

```text
http://3.34.230.202/dashboard
```

## 6. Test Manual Evaluation

Saved rules can be evaluated without TradingView:

```bash
curl -X POST "https://alerts.your-domain.com/api/v1/edge-rules/evaluate"
```

Expected response:

```json
{
  "rules_evaluated": 1,
  "rules_matched": 0,
  "signals_created": 0,
  "duplicates_skipped": 0,
  "rules_failed": 0
}
```

## 7. Optional TradingView Webhook Test

```bash
SECRET="your-secret"
DOMAIN="alerts.your-domain.com"

curl -X POST "https://${DOMAIN}/api/v1/webhooks/tradingview/${SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "TVC:SPX",
    "timeframe": "1W",
    "event": "manual_test",
    "message": "SPX weekly SMA60 test",
    "price": 5200.0,
    "data": {
      "sma60": 5185.0
    }
  }'
```

## 8. Optional TradingView Setup

Webhook URL:

```text
https://alerts.your-domain.com/api/v1/webhooks/tradingview/YOUR_SECRET
```
TradingView is optional. The default production path is scheduled server-side evaluation of saved Edge Rules.

## 9. Operations

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

If GitHub auth is not available, copy the changed files to the server and then run:

```bash
cd /home/ubuntu/trading-assistant
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

