# Deployment Information

## Public URL
https://k5-l3b-day14-dolyhoangnam-2a202603777.onrender.com

## Platform
Render (Docker Multi-Stage Build + Render Key Value / Redis)

## Test Commands

### 1. Liveness Check (`GET /health` → `200`)
```bash
BASE="https://k5-l3b-day14-dolyhoangnam-2a202603777.onrender.com"
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

## Environment Variables Set (Configured on Render Dashboard, Not Hardcoded)
- `PORT` (Automatically injected by Render — `10000`)
- `ENVIRONMENT` (`production`)
- `REDIS_URL` (Internal URL of `day14-redis` Key Value service)
- `AGENT_API_KEY` (Secret API Key configured in Render Environment Variables)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
