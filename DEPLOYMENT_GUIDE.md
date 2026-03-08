# PENSY LIVE TRADING - COMPLETE DEPLOYMENT & SETUP GUIDE

## Overview

This guide walks you through deploying the Pensy trading platform to production and preparing for live trading.

**Timeline: ~1-2 hours for basic setup + 1-2 weeks for paper trading validation**

---

## Phase 1: Local Development (Optional - for testing)

### Prerequisites
- macOS with Homebrew
- Python 3.10+
- Git

### Local Setup

```bash
# 1. Navigate to project
cd /Users/matteocrucito/Desktop/platform/backend

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env from example
cp /Users/matteocrucito/Desktop/platform/.env.example .env

# 5. Edit .env with your settings
nano .env

# 6. Start PostgreSQL locally (if you have it)
# Option A: Using Docker
docker-compose up -d

# Option B: Using Homebrew
brew install postgresql redis
brew services start postgresql
brew services start redis

# 7. Run migrations
alembic upgrade head

# 8. Start server
uvicorn app.main:app --reload --port 8000

# 9. Visit http://localhost:8000/docs
```

---

## Phase 2: Cloud Deployment (RECOMMENDED)

### Option A: Heroku (Easiest for getting started)

**Cost: ~$50-100/month**

```bash
# 1. Install Heroku CLI
# macOS:
brew tap heroku/brew && brew install heroku

# 2. Login to Heroku
heroku login

# 3. Create app
heroku create pensy-trading-prod

# 4. Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# 5. Add Redis
heroku addons:create heroku-redis:premium-0

# 6. Set environment variables
heroku config:set APP_ENV=production
heroku config:set LIVE_TRADING_ENABLED=false
heroku config:set BINANCE_TESTNET=true
heroku config:set BINANCE_API_KEY=your_key_here
heroku config:set BINANCE_API_SECRET=your_secret_here
heroku config:set MAX_ORDER_NOTIONAL=2000
heroku config:set MAX_DAILY_LOSS=1000
# ... (see deploy-heroku.sh)

# 7. Deploy
cd platform/backend
git push heroku main

# 8. Run migrations
heroku run alembic upgrade head

# 9. Verify
heroku logs --tail

# 10. Test API
curl https://pensy-trading-prod.herokuapp.com/docs
```

**View Settings:**
```bash
heroku config -a pensy-trading-prod
```

**View Logs:**
```bash
heroku logs --tail -a pensy-trading-prod
```

### Option B: AWS (More control, scalable)

**Cost: ~$20-50/month**

```bash
# 1. Create AWS Account
# https://aws.amazon.com

# 2. Create RDS PostgreSQL instance
# - Instance class: db.t3.micro (free tier eligible)
# - Storage: 20GB
# - Multi-AZ: No
# - Public accessibility: Yes
# - DB name: pensy_production

# 3. Create ElastiCache Redis
# - Node type: cache.t3.micro
# - Number of cache nodes: 1
# - Multi-AZ: No

# 4. Create EC2 instance
# - AMI: Ubuntu 22.04
# - Instance type: t3.micro (free tier)
# - Security group: Allow ports 8000, 22

# 5. SSH into EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# 6. Setup on EC2
sudo apt-get update
sudo apt-get install python3-pip git
git clone https://github.com/methfish/platform.git
cd platform/backend
pip3 install -r requirements.txt

# 7. Create .env
nano .env

# Configure database URLs:
DATABASE_URL=postgresql+asyncpg://user:password@your-rds-endpoint:5432/pensy_production
REDIS_URL=redis://your-redis-endpoint:6379/0

# 8. Run migrations
alembic upgrade head

# 9. Start with supervisor/systemd
# Create /etc/systemd/system/pensy.service
[Unit]
Description=Pensy Trading Platform
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/platform/backend
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target

# Start service
sudo systemctl enable pensy
sudo systemctl start pensy
sudo systemctl status pensy

# View logs
sudo journalctl -u pensy -f
```

### Option C: DigitalOcean App Platform (Good middle ground)

**Cost: ~$5-20/month**

1. Go to https://cloud.digitalocean.com
2. Click "Create" → "App"
3. Connect GitHub repo: `methfish/platform`
4. Set build command: `cd backend && pip install -r requirements.txt`
5. Set run command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080`
6. Add Managed Database (PostgreSQL + Redis)
7. Set environment variables (same as above)
8. Deploy

---

## Phase 3: Monitoring & Alerts

### Option A: Heroku Monitoring

```bash
# View app metrics
heroku metrics -a pensy-trading-prod

# View errors
heroku logs --tail -a pensy-trading-prod | grep ERROR
```

### Option B: Datadog (Recommended)

```bash
# 1. Sign up: https://www.datadoghq.com
# 2. Set API key in Heroku/AWS
heroku config:set DD_API_KEY=xxx

# 3. Monitor in Datadog dashboard
# - CPU usage
# - Memory
# - Database connections
# - API response times
# - Error rates
```

### Option C: Simple Slack Alerts

```bash
# 1. Create Slack webhook
# 2. Set in .env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# 3. Errors will auto-post to Slack
```

---

## Phase 4: Testing Before Going Live

### 1. Test Market Data Scraper

```bash
# Test endpoint
curl https://your-app.herokuapp.com/api/v1/markets/overview

# Check response has ticker data
# Should return:
# {
#   "tickers": [...],
#   "total_symbols": 20,
#   "top_gainers": [...],
#   "top_losers": [...]
# }
```

### 2. Test Risk Engine

```bash
# Get risk status
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.herokuapp.com/api/v1/risk/status

# Should return:
# {
#   "kill_switch_active": false,
#   "trading_mode": "PAPER",
#   "daily_loss": "0",
#   "open_positions_count": 0
# }
```

### 3. Test Monitoring Dashboard

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.herokuapp.com/api/v1/risk/monitoring-dashboard

# Should show all limits, metrics, recent events
```

### 4. Paper Trade for 1-2 Weeks

- Place small test orders (PAPER mode only)
- Monitor position tracking
- Verify risk limits work
- Check daily loss calculation
- Validate kill switch blocks orders
- Test all API endpoints

### 5. Pre-Live Checklist

```
□ Market data scraper running
□ Binance connection stable (testnet)
□ All API endpoints responding
□ Risk dashboard showing correct data
□ Kill switch tested and works
□ Paper trades tracked correctly
□ Daily loss calculation accurate
□ Position PnL calculation matches manual calc
□ Alerts configured (Slack/Telegram)
□ Logging working
□ Backups configured
□ Monitoring dashboard showing metrics
□ Database backups working
□ Rate limits enforced
□ Symbol whitelist prevents unauthorized trades
```

---

## Phase 5: Going Live

### CRITICAL: Before Enabling Live Trading

1. **Get Real Binance API Keys**
   - Log in to https://www.binance.com
   - Account → API Management
   - Create new key (DO NOT use existing keys)
   - Enable: Spot Trading, Read-Only for now
   - IP whitelist your server

2. **Update Configuration**
   ```bash
   heroku config:set BINANCE_TESTNET=false
   heroku config:set LIVE_TRADING_ENABLED=false  # Still false!
   heroku config:set BINANCE_API_KEY=your_real_key
   heroku config:set BINANCE_API_SECRET=your_real_secret
   ```

3. **Test with Real Connection (Paper)**
   - API will connect to LIVE Binance
   - But trades execute in PAPER mode
   - Run this for 24-48 hours
   - Verify all metrics match reality

4. **Enable Live Trading**
   - Only when fully confident
   - Start with CONSERVATIVE limits
   - Watch first 24 hours closely
   - Have manual kill switch ready

   ```bash
   heroku config:set LIVE_TRADING_ENABLED=true
   # Then call: POST /api/v1/admin/authorize-live-trading
   ```

5. **Monitor Continuously**
   - Dashboard: Check daily loss, exposure
   - Logs: 0 errors, normal operation
   - Orders: Verify fills, prices are reasonable
   - Positions: Track PnL accurately

---

## Emergency Procedures

### Kill Switch (Stops All Trades)

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"activate": true}' \
  https://your-app.herokuapp.com/api/v1/risk/kill-switch

# Verify
curl https://your-app.herokuapp.com/api/v1/risk/status
# Should show: "kill_switch_active": true
```

### Stop the Server Immediately

```bash
# Heroku
heroku dyno:stop web -a pensy-trading-prod

# AWS
sudo systemctl stop pensy

# DigitalOcean
In console: Click "Stop App"
```

### Revert to Paper Mode

```bash
heroku config:set LIVE_TRADING_ENABLED=false -a pensy-trading-prod
```

---

## Maintenance

### Daily
- Check monitoring dashboard for any WARNING/CRITICAL
- Review logs for errors
- Verify market data is fresh
- Check kill switch works

### Weekly
- Review performance metrics
- Analyze trade metrics
- Optimize risk limits if needed
- Check database size

### Monthly
- Update dependencies: `pip install -u requirements.txt`
- Review and rotate API keys
- Backup database
- Review logs for patterns

---

## Support & Troubleshooting

### API Not Responding
```bash
# Check logs
heroku logs --tail -a pensy-trading-prod

# Restart
heroku dyno:restart -a pensy-trading-prod

# Check status
curl https://your-app.herokuapp.com/docs
```

### Market Data Not Updating
```bash
# Check scraper
curl https://your-app.herokuapp.com/api/v1/markets/overview

# Check logs for scraper errors (look for "Scraped" messages)
heroku logs --tail -a pensy-trading-prod | grep -i "scraper"
```

### Database Connection Issues
```bash
# Check database URL
heroku config -a pensy-trading-prod | grep DATABASE_URL

# Test connection
heroku pg:info -a pensy-trading-prod

# View db logs
heroku logs --dyno=postgres -a pensy-trading-prod
```

### Risk Checks Not Firing
```bash
# Test manually
curl -X POST https://your-app.herokuapp.com/api/v1/risk/kill-switch \
  -d '{"activate": true}' \
  -H "Authorization: Bearer XXX"

# Verify
curl https://your-app.herokuapp.com/api/v1/risk/status
```

---

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Heroku (Web dyno) | $25-50 |
| PostgreSQL | $9 |
| Redis | $15-30 |
| Monitoring (optional) | $0-100+ |
| **Total** | **$49-180/mo** |

### Cost Optimization
- Use free tier initially (limited scale)
- Upgrade only when needed
- Stop non-production apps
- Use spot instances on AWS

---

## Next Steps

1. **Choose deployment option** (Heroku recommended for beginners)
2. **Run deploy script** (10 minutes)
3. **Test endpoints** (15 minutes)
4. **Paper trade** (1-2 weeks)
5. **Go live** (with caution!)

---

**Good luck! Happy trading! 🚀**
