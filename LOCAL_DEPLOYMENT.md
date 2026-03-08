# LOCAL DEPLOYMENT GUIDE

**Goal:** Get the full system running on your machine for testing before cloud deployment

---

## STEP 1: Install PostgreSQL & Redis (5 minutes)

### On macOS:
```bash
# Install PostgreSQL
brew tap homebrew/services
brew install postgresql

# Install Redis
brew install redis

# Start both services
brew services start postgresql
brew services start redis
```

### Verify Installation:
```bash
psql --version
redis-cli ping  # Should return "PONG"
```

---

## STEP 2: Create Local Database (2 minutes)

```bash
# Create the database
createdb pensy

# Verify it was created
psql -l | grep pensy
```

---

## STEP 3: Setup Python Environment (3 minutes)

```bash
cd /Users/matteocrucito/Desktop/platform

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

---

## STEP 4: Configure Environment (2 minutes)

```bash
cd /Users/matteocrucito/Desktop/platform/backend

# Copy environment template
cp .env.example .env

# Edit .env with local settings:
cat > .env << 'EOF'
# Local Development Setup
APP_ENV=development
LOG_LEVEL=DEBUG

# Database (local)
DATABASE_URL=postgresql+asyncpg://postgres:@localhost/pensy

# Redis (local)
REDIS_URL=redis://localhost:6379

# Binance - Use TESTNET for safety
BINANCE_TESTNET=true
BINANCE_API_KEY=your_testnet_key
BINANCE_API_SECRET=your_testnet_secret

# Trading - PAPER MODE
LIVE_TRADING_ENABLED=false

# Risk Limits (Conservative)
MAX_ORDER_NOTIONAL=500
MAX_POSITION_NOTIONAL=2000
MAX_DAILY_LOSS=1000
MAX_OPEN_ORDERS=5
SYMBOL_WHITELIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT

# Market Data Scraper
SCRAPER_INTERVAL_SECONDS=300
SCRAPER_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT
SCRAPER_OHLCV_INTERVALS=1h,4h,1d
EOF
```

**Note:** You'll need Binance testnet API keys. Get them at:
https://testnet.binance.vision/

---

## STEP 5: Run Database Migrations (2 minutes)

```bash
cd /Users/matteocrucito/Desktop/platform/backend

# Initialize database schema
python -m alembic upgrade head

# Verify current version
python -m alembic current
# Should show: "d3bb78b9acae (head)"
```

---

## STEP 6: Start the Backend Server (1 minute)

```bash
cd /Users/matteocrucito/Desktop/platform/backend

# Run the FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

> **Keep this terminal open** — This is your backend server

---

## STEP 7: Test the System

### In a NEW terminal, test endpoints:

#### 1. Check API is alive
```bash
curl http://localhost:8000/docs
# Should open Swagger UI in browser (or return HTML)
```

#### 2. Get Market Overview
```bash
curl http://localhost:8000/api/v1/markets/overview | jq .
```

#### 3. Check Risk Status
```bash
curl http://localhost:8000/api/v1/risk/status | jq .
```

#### 4. List Orders
```bash
curl http://localhost:8000/api/v1/orders | jq .
```

---

## STEP 8: Run Paper Trading Test

### Place a Test Order
```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 0.001
  }' | jq .
```

**Expected Response:**
```json
{
  "client_order_id": "order_abc123",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "status": "PENDING",
  "filled_quantity": 0,
  "trading_mode": "PAPER"
}
```

### Check Position Was Created
```bash
curl http://localhost:8000/api/v1/orders/positions/all | jq .
```

**Expected Response:**
```json
[
  {
    "symbol": "BTCUSDT",
    "side": "LONG",
    "quantity": "0.001",
    "entry_price": "42500.25",
    "realized_pnl": "0"
  }
]
```

---

## STEP 9: Monitor Logs

Watch the server logs to see what's happening:

```bash
# In the server terminal, look for:
# - "Executing MARKET order BUY BTCUSDT 0.001"
# - "Creating position LONG BTCUSDT 0.001 @ 42500.25"
# - "Position updated successfully"
```

---

## Testing Checklist

Run through these to validate everything works:

### Market Data
- [ ] `GET /api/v1/markets/overview` returns top movers
- [ ] `GET /api/v1/markets/symbols` returns screener data
- [ ] `GET /api/v1/markets/symbols/BTCUSDT` returns analysis
- [ ] `GET /api/v1/markets/symbols/BTCUSDT/ohlcv?interval=1h` returns candlesticks
- [ ] `GET /api/v1/markets/heatmap` returns grid data
- [ ] `GET /api/v1/markets/movers` returns gainers/losers

### Risk Management
- [ ] `GET /api/v1/risk/status` shows all limits
- [ ] `POST /api/v1/risk/kill-switch` returns success
- [ ] `GET /api/v1/risk/monitoring-dashboard` shows metrics
- [ ] `GET /api/v1/risk/events` shows recent events

### Order Execution
- [ ] `POST /api/v1/orders` places order successfully
- [ ] `GET /api/v1/orders` lists orders
- [ ] `GET /api/v1/orders/{order_id}` returns order details
- [ ] `POST /api/v1/orders/{order_id}/cancel` cancels pending order
- [ ] `GET /api/v1/orders/positions/all` returns open positions

### Paper Trading
- [ ] Place MARKET order → gets filled
- [ ] Place LIMIT order → queued until price hit
- [ ] Fill creates position in database
- [ ] Multiple fills average entry price correctly
- [ ] Closing position realizes PnL

---

## Troubleshooting

### PostgreSQL Connection Error
```
Error: connect to server failed
```
**Fix:**
```bash
brew services start postgresql
createdb pensy
```

### Redis Connection Error
```
Error: cannot connect to Redis
```
**Fix:**
```bash
brew services start redis
redis-cli ping
```

### Port 8000 Already in Use
```bash
# Find what's using port 8000
lsof -i :8000

# Kill it and restart
kill -9 <PID>
```

### Alembic Migration Failed
```bash
# Reset and reapply
python -m alembic downgrade base
python -m alembic upgrade head
```

### Binance API Connection Fails
- Check `BINANCE_API_KEY` is correct in `.env`
- Check `BINANCE_API_SECRET` is correct in `.env`
- Verify testnet keys (not live keys)
- Check you're on correct network if using VPN

---

## Next Steps After Local Testing

Once everything works locally:

1. **Paper trade for 1-2 weeks** on local environment
2. **Monitor logs** for any errors
3. **Validate PnL calculations** against manual math
4. **Test kill switch** regularly
5. **Check daily loss reset** at UTC midnight

Then either:
- **Deploy to Heroku** for cloud-based testing (see QUICK_START.md)
- **Or continue local* if you prefer

---

## Quick Command Reference

```bash
# Start services
brew services start postgresql redis

# Start backend server
cd /Users/matteocrucito/Desktop/platform/backend
source ../venv/bin/activate
python -m uvicorn app.main:app --reload

# Test endpoints
curl http://localhost:8000/docs
curl http://localhost:8000/api/v1/markets/overview
curl http://localhost:8000/api/v1/risk/status

# Check logs
grep ERROR ~/your-log-file.log
```

---

*Ready to get started? Follow the steps above in order. Let me know if you hit any issues!*
