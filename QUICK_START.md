# PENSY QUICK START - 30 MINUTE SETUP

## Prerequisites (5 minutes)

You need:
- Heroku account: https://dashboard.heroku.com (free)
- Heroku CLI: `brew tap heroku/brew && brew install heroku`
- Git installed
- Binance account: https://www.binance.com

## Deploy to Heroku (10 minutes)

```bash
# 1. Login to Heroku
heroku login

# 2. Create app
heroku create pensy-trading

# 3. Add databases
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:premium-0

# 4. Set key configuration
heroku config:set \
  APP_ENV=production \
  LIVE_TRADING_ENABLED=false \
  BINANCE_TESTNET=true \
  MAX_ORDER_NOTIONAL=2000 \
  MAX_DAILY_LOSS=1000 \
  SYMBOL_WHITELIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT

# 5. Deploy code
cd /Users/matteocrucito/Desktop/platform
git add -A
git commit -m "Deployment setup: Heroku Procfile, requirements, guides"
git push heroku main

# 6. Run migrations
heroku run alembic upgrade head

# 7. Verify it works
curl https://pensy-trading.herokuapp.com/docs
```

## Add Binance API Keys (2 minutes)

1. Go to https://www.binance.com/en/account/api-management
2. Create new API key
3. Copy key and secret
4. Add to Heroku:

```bash
heroku config:set BINANCE_API_KEY=your_key_here
heroku config:set BINANCE_API_SECRET=your_secret_here
```

## Test Endpoints (5 minutes)

```bash
# Market overview
curl https://pensy-trading.herokuapp.com/api/v1/markets/overview

# Risk status
curl https://pensy-trading.herokuapp.com/api/v1/risk/status

# All endpoints
curl https://pensy-trading.herokuapp.com/docs
```

## Watch Logs (Ongoing)

```bash
# See what's happening
heroku logs --tail
```

## Monitor Dashboard

```bash
# Real-time metrics
curl https://pensy-trading.herokuapp.com/api/v1/risk/monitoring-dashboard
```

## Troubleshooting

**App not deploying?**
```bash
heroku logs --tail
# Fix errors shown
git push heroku main
```

**Binance API not working?**
```bash
heroku logs --tail | grep -i binance
# Verify API key is correct
heroku config | grep BINANCE
```

**Database migration failed?**
```bash
heroku run alembic current
heroku run alembic upgrade head
```

---

## Next Steps

1. ✅ Deploy (done above)
2. Paper trade for 1-2 weeks (see DEPLOYMENT_GUIDE.md)
3. Review LIVE_TRADING_CHECKLIST.md
4. Go live when ready

---

**You're ready to trade!** 🚀

For detailed setup: See `DEPLOYMENT_GUIDE.md`
For safety: See `LIVE_TRADING_CHECKLIST.md`
