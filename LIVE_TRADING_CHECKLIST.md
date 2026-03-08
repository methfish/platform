# PENSY LIVE TRADING - FINAL CHECKLIST

## Pre-Deployment System Validation

### Database & Cache
- [ ] PostgreSQL running with 20GB+ storage
- [ ] Redis cache running with >1GB memory
- [ ] Database backups configured (daily)
- [ ] Connection strings tested and verified
- [ ] Migrations applied successfully: `alembic current` shows latest version

### API & Endpoints
- [ ] Backend server running without errors
- [ ] Swagger docs accessible: `/docs`
- [ ] Health check passing: `GET /health`
- [ ] All 6 market endpoints responding (overview, symbols, ohlcv, heatmap, movers)
- [ ] All 3 risk endpoints responding (status, events, monitoring-dashboard)
- [ ] Kill switch endpoint tested and works

### Binance Connection
- [ ] Binance API keys obtained (TESTNET first!)
- [ ] API keys added to environment
- [ ] Connection test passed: `GET /api/v1/markets/overview` returns data
- [ ] Testnet mode verified: orders execute in testnet
- [ ] Rate limiting working: no 429 errors

### Risk Engine
- [ ] Kill switch tested: POST blocks all orders ✓
- [ ] Order size limits enforced: MAX_ORDER_NOTIONAL tested
- [ ] Position limits enforced: MAX_POSITION_NOTIONAL tested
- [ ] Daily loss limit enforced: tested with simulated losses
- [ ] Symbol whitelist enforced: unauthorized symbol rejected
- [ ] Exchange health check running without errors

### Market Data Scraper
- [ ] Scraper running: task shows in logs
- [ ] Ticker data updated: `GET /api/v1/markets/overview` shows fresh data
- [ ] OHLCV data persisted: Database has 1h/4h/1d bars
- [ ] Data quality checked: No null values, reasonable prices
- [ ] Scraper restarts on failure: Monitoring shows uptime

### Monitoring & Logging
- [ ] Structured logging working: JSON logs in stdout
- [ ] Error logs tested: Can find errors in logs
- [ ] Monitoring dashboard: All metrics showing
- [ ] Alerts configured: Slack/Telegram sending test messages
- [ ] Rate limiting metrics: Requests/second monitored
- [ ] Error rate metrics: Errors tracked and alerted

### Paper Trading (1-2 weeks minimum)
- [ ] Placed test orders: Confirms to DB correctly
- [ ] Position tracking: Manual calc matches system
- [ ] PnL calculation: Accurate against Binance
- [ ] Fill prices: Reasonable and realistic
- [ ] Daily reset: Loss counter resets at UTC midnight
- [ ] Multiple orders: Can hold multiple positions simultaneously
- [ ] Risk warnings: 80% threshold alerts working
- [ ] Market data feed: Prices realistic and updating

### Performance & Load Testing
- [ ] API response time: <500ms for non-database queries
- [ ] Database response time: <100ms for index queries
- [ ] Concurrent connections: Can handle 10+ simultaneous requests
- [ ] Memory usage: Stable without leaks
- [ ] CPU usage: Normal load <30%
- [ ] Network: No packet loss

---

## Pre-Live Trading Setup

### Configuration Verification
- [ ] APP_ENV=production
- [ ] LIVE_TRADING_ENABLED=false (for now)
- [ ] BINANCE_TESTNET=false (REAL Binance)
- [ ] BINANCE_API_KEY set (REAL key, NOT test)
- [ ] BINANCE_API_SECRET set (REAL secret)

### Risk Profile Review
```
Size Limits:
- [ ] MAX_ORDER_NOTIONAL = $2,000 (conservative)
- [ ] MAX_ORDER_QUANTITY = 10 units
- [ ] MAX_POSITION_NOTIONAL = $10,000
- [ ] MAX_GROSS_EXPOSURE = $20,000

Loss Limits:
- [ ] MAX_DAILY_LOSS = $1,000 (absolute max before stop)
- [ ] PRICE_DEVIATION_THRESHOLD = 2% (anti-slippage)

Rate Limits:
- [ ] MAX_OPEN_ORDERS = 5
- [ ] MAX_ORDERS_PER_MINUTE = 10
- [ ] STALE_PRICE_THRESHOLD = 30 seconds

Symbol Control:
- [ ] SYMBOL_WHITELIST = BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT only
```

### Disaster Recovery Plan
- [ ] Kill switch tested: 5 second activation time
- [ ] Manual stop procedure: Server shutdown works
- [ ] Database backup schedule: Daily at 02:00 UTC
- [ ] Rollback plan: Can revert to previous version
- [ ] Data recovery: Can restore from backup
- [ ] Communication plan: Know who to contact if issues

### Operational Readiness
- [ ] 24/7 monitoring: Someone watching dashboard
- [ ] Escalation plan: Know when to call for help
- [ ] Documentation: Standard operational procedures written
- [ ] Team training: All operators know kill switch location
- [ ] Communication: Slack/email alerts working

---

## LIVE TRADING APPROVAL PHASE

### Day 0: Transition to Real Binance (Paper Mode)
```bash
heroku config:set BINANCE_TESTNET=false -a pensy-trading-prod
# But LIVE_TRADING_ENABLED still = false
```

- [ ] Order real data: Prices match Binance exactly
- [ ] Paper orders: Still simulate trades, no real $
- [ ] Full 24-hour cycle: Overnight trading working
- [ ] Alert storms: Verify alerts not overwhelming
- [ ] Database growth: Manageable
- [ ] Error rate: 0 in production logs
- [ ] Performance: Consistent response times

**Validation duration: 24-48 hours**

### Day 2-3: Enable Live Trading (Micro Positions)

Only when ALL above complete! ⚠️

```bash
# 1. Enable live trading
heroku config:set LIVE_TRADING_ENABLED=true -a pensy-trading-prod

# 2. Confirm authorization
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  https://pensy-trading-prod.herokuapp.com/api/v1/admin/authorize-live-trading

# 3. Start with MICRO positions
# Example: $100-500 only, not $2,000 max
MAX_ORDER_NOTIONAL=500
MAX_POSITION_NOTIONAL=1000
```

- [ ] First order placed successfully
- [ ] Order matches Binance: Check fill price, quantity
- [ ] Order in account: Appears in Binance dashboard
- [ ] PnL tracking: System calc matches Binance
- [ ] Risk tracking: Position counts towards limits
- [ ] Monitoring: Dashboard shows live position
- [ ] No errors: Logs clean

**Duration: First day (1-5 trades)**

### Day 4: Gradual Increase

Increase positions slowly only if everything perfect:

```
Day 1-2: $100-500 per position
Day 3-5: $500-1,000 per position
Day 6-14: $1,000-2,000 per position
Week 3+: Full limits if confidence high
```

- [ ] Daily loss tracker: Stays positive or minimal
- [ ] Any losses <$100/day: Acceptable
- [ ] Performance stable: No degradation
- [ ] No risk violations: All checks passing
- [ ] Market conditions: Normal, no extremes

### Week 2+: Full Production

Only after 2 weeks of perfect operation:

```bash
# Increase to normal limits
heroku config:set MAX_ORDER_NOTIONAL=2000 -a pensy-trading-prod
heroku config:set MAX_POSITION_NOTIONAL=10000 -a pensy-trading-prod
heroku config:set MAX_GROSS_EXPOSURE=20000 -a pensy-trading-prod
```

- [ ] P&L positive or reasonable
- [ ] Zero critical incidents
- [ ] Monitoring solid
- [ ] Team confident
- [ ] Still watch closely for 1 month

---

## Post-Live Trading (Ongoing)

### Daily (Every trading day)
- [ ] Check monitoring dashboard before market open
- [ ] Review overnight trades (if any)
- [ ] Verify daily loss at reset
- [ ] Check for any WARN/CRITICAL alerts
- [ ] Confirm market data freshness

### Weekly
- [ ] Review trade performance
- [ ] Check database size
- [ ] Review error logs
- [ ] Validate backups working

### Monthly
- [ ] Full system health check
- [ ] Review and optimize limits
- [ ] Update API keys if needed
- [ ] Document lessons learned

---

## KILL SWITCH - EMERGENCY STOP

```bash
# Activate immediately if:
# - Strange prices (>10% deviation)
# - Database lag (>10 seconds)
# - API errors (>1% error rate)
# - Unexpected losses
# - Any system anomaly

# Activate via API:
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"activate": true}' \
  https://pensy-trading-prod.herokuapp.com/api/v1/risk/kill-switch

# Verify:
curl https://pensy-trading-prod.herokuapp.com/api/v1/risk/status
# Should show: "kill_switch_active": true
```

---

## Sign-Off

**I have completed and verified all checklist items above.**

- System Owner: ___________________
- Date: ___________________
- Approval: ___________________

---

*This is financial software. Take it seriously! 🎯*
