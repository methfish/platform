# 🚀 GET PENSY RUNNING - 5 MINUTE SETUP

## The Quickest Path to Live UX

Since your system requires PostgreSQL + Redis, the fastest way is Docker. Here's how:

---

## Step 1️⃣: Install Docker Desktop for Mac (3 minutes)

**Download & Install:**
- Go to: https://www.docker.com/products/docker-desktop
- Download "Docker.dmg" (Apple Silicon if M1/M2/M3, Intel if older Mac)
- Drag Docker to Applications folder
- Launch Docker.app from Applications
- Wait for Docker to start (you'll see icon in top menu bar)

**Verify it works:**
```bash
docker --version
# Should show: Docker version X.X.X
```

---

## Step 2️⃣: Start Everything with One Command (1 minute)

```bash
cd /Users/matteocrucito/Desktop/platform

# Set up environment
cp .env.example .env

# Start all services (PostgreSQL, Redis, Backend, Frontend)
docker compose up --build
```

**Wait for this message:**
```
✅ Application startup complete
Uvicorn running on http://0.0.0.0:8000
```

Then open in your browser:

---

## 🌐 THE FULL USER EXPERIENCE

### 1. **API Dashboard** (Interactive API Testing)
```
http://localhost:8000/docs
```
Click "Try it out" on any endpoint to test

### 2. **View Market Data**
```
http://localhost:8000/api/v1/markets/overview
```
Shows: Bitcoin, Ethereum, Solana, BNB prices + movers

### 3. **Check Risk Status**
```
http://localhost:8000/api/v1/risk/status
```
Shows: Daily loss limit, position limits, kill switch status

### 4. **Place a Test Paper Trade**
```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 0.5
  }'
```

Response shows order created in database

### 5. **See Your Position**
```bash
curl http://localhost:8000/api/v1/orders/positions/all
```

Shows: Your BTC position, entry price, PnL

### 6. **Place a Limit Order**
```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSDT",
    "side": "BUY",
    "order_type": "LIMIT",
    "quantity": 1.0,
    "price": "2000"
  }'
```

Order queues and waits for price to drop to $2000

### 7. **View All Orders**
```bash
curl http://localhost:8000/api/v1/orders
```

Shows: FILLED orders and PENDING limit orders

### 8. **Test Kill Switch**
```bash
curl -X POST http://localhost:8000/api/v1/risk/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"activate": true}'
```

All future orders blocked immediately

### 9. **View Screener Data**
```bash
curl http://localhost:8000/api/v1/markets/symbols
```

Shows: All symbols with RSI, trend, momentum scores

### 10. **View Heatmap**
```bash
curl http://localhost:8000/api/v1/markets/heatmap
```

Shows: Volume-weighted grid of price changes

---

## 📊 WHAT YOU'LL SEE

### Backend Running:
```
✅ Application startup complete
📊 PENSY ORDER EXECUTION PLATFORM
✅ Market Data Scraper: Started
✅ Risk Engine: Initialized
✅ Order Execution: Ready (PAPER mode)
```

### Database:
- PostgreSQL running in container
- Tables created: users, orders, positions, fills, market_data
- Schema migrations applied

### Live Services:
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (inside Docker)
- **Redis**: localhost:6379 (inside Docker)

---

## 🧪 FULL TEST FLOW (10 minutes)

```bash
# 1. Check API is alive
curl http://localhost:8000/docs

# 2. Get market overview
curl http://localhost:8000/api/v1/markets/overview | jq .

# 3. Check risk limits
curl http://localhost:8000/api/v1/risk/status | jq .

# 4. Place BUY order
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.1}'

# 5. See new position
curl http://localhost:8000/api/v1/orders/positions/all | jq .

# 6. Place SELL to close position
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","side":"SELL","order_type":"MARKET","quantity":0.1}'

# 7. See closed position with realized PnL
curl http://localhost:8000/api/v1/orders/positions/all | jq .

# 8. View all orders and fills
curl http://localhost:8000/api/v1/orders | jq .

# 9. View recent risk events
curl http://localhost:8000/api/v1/risk/events | jq .

# 10. Activate kill switch
curl -X POST http://localhost:8000/api/v1/risk/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"activate": true}'

# 11. Try to place order (should be blocked)
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.1}'
# Should error: "Kill switch is active"
```

---

## 🛑 STOP EVERYTHING

```bash
# In the terminal where docker compose is running:
Ctrl+C

# Or in another terminal:
docker compose down
```

---

## ⚠️ IMPORTANT NOTES

✅ **All trades are SIMULATED** - No real money involved
✅ **PAPER TRADING MODE** - Uses fake balances
✅ **TESTNET BINANCE** - Testing API keys only
✅ **Kill Switch Works** - Can stop all orders immediately
✅ **Risk Limits Active** - $1,000 daily loss max, position limits enforced

---

## If Docker Installation Fails

**Alternative Option 1: Use Online IDE**
- Use Replit.com or GitHub Codespaces
- They have Docker pre-installed
- Clone your repo there and run

**Alternative Option 2: Try Docker via Homebrew**
```bash
# Install Homebrew first (if you want to skip. just do Docker Desktop above)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Then
brew install docker docker-compose
colima start  # Virtual machine for Docker on Mac
```

**Recommended: Just install Docker Desktop** - It's the official Mac app, easiest setup

---

## 🎯 NEXT: WHAT TO DO AFTER

1. **Paper trade** for a few minutes to see it work
2. **Try different order types** (MARKET vs LIMIT)
3. **Test kill switch** - verify it blocks orders
4. **Place big orders** - see position limits kick in
5. **Close positions** - watch PnL calculations work

Then you'll have full confidence before going live with real money.

---

*Ready? Install Docker Desktop, then run:*
```bash
cd /Users/matteocrucito/Desktop/platform
docker compose up --build
```

Let me know when Docker is done installing! 🚀
