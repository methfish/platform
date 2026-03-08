# START PENSY - 3 STEPS

## Step 1️⃣ Install Docker (3 min, one-time)

**Visit:** https://www.docker.com/products/docker-desktop

**Download:** Choose for your Mac (Apple Silicon OR Intel)

**Install:** Drag to Applications folder

**Start:** Launch Docker.app from Applications (wait for menu bar icon)

---

## Step 2️⃣ One Command (runs everything)

Open Terminal and paste this:

```bash
cd /Users/matteocrucito/Desktop/platform && docker compose up --build
```

Wait for:
```
✅ Application startup complete
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## Step 3️⃣ Open In Browser

Click any of these links:

- **🧪 Test API:** http://localhost:8000/docs
- **📊 Market Data:** http://localhost:8000/api/v1/markets/overview
- **✅ Your Positions:** http://localhost:8000/api/v1/orders/positions/all
- **⚠️ Risk Status:** http://localhost:8000/api/v1/risk/status

---

## 🎮 Quick Test (Without Browser)

```bash
# In a NEW terminal window (keep docker compose running in first window):

# See available market data
curl http://localhost:8000/api/v1/markets/overview

# Place a test trade
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.1}'

# See your position
curl http://localhost:8000/api/v1/orders/positions/all

# Close the position
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","side":"SELL","order_type":"MARKET","quantity":0.1}'

# Check PnL
curl http://localhost:8000/api/v1/orders/positions/all

# Kill switch
curl -X POST http://localhost:8000/api/v1/risk/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"activate": true}'
```

---

## ⏹️ Stop

Press `Ctrl+C` in the terminal running docker compose

---

## 🎯 That's It

Docker Desktop (3 min install) → One command → Live platform in browser

Everything else is pre-configured. No mess.
