# Deployment Information

## Public URL
https://k5-l3b-day14-dolyhoangnam-agent-production.up.railway.app

## Platform
Railway (Docker Multi-Stage Build + Managed Redis)

## Test Commands

### 1. Liveness Check (`GET /health` → `200`)
```bash
BASE="https://k5-l3b-day14-dolyhoangnam-agent-production.up.railway.app"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Expected: 200
```

### 2. Readiness Check (`GET /ready` → `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Expected: 200
```

### 3. API Test without API Key (`POST /ask` → `401`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Expected: 401
```

### 4. API Test with valid API Key (`POST /ask` → `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# Expected: 200
```

## Environment Variables Set (Configured on Cloud Dashboard, Not Hardcoded)
- `PORT` (Automatically injected by Railway / set to `8000`)
- `ENVIRONMENT` (`production`)
- `REDIS_URL` (`${{Redis.REDIS_URL}}` — linked to Railway Redis service)
- `AGENT_API_KEY` (Secret API Key configured in Railway Variables)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
