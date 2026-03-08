#!/bin/bash
# PENSY LIVE TRADING - COMPLETE SETUP SCRIPT
# Deploys backend to Heroku + configures AWS RDS + Redis

set -e

echo "========================================="
echo "PENSY LIVE TRADING - DEPLOYMENT SETUP"
echo "========================================="
echo ""

# ============ STEP 1: Prerequisites ============
echo "STEP 1: Checking prerequisites..."

if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI not found. Install from: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "❌ Git not found. Please install git."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

echo "✅ Prerequisites OK"
echo ""

# ============ STEP 2: Heroku Login ============
echo "STEP 2: Logging into Heroku..."
heroku login
echo ""

# ============ STEP 3: Create Heroku App ============
APP_NAME="pensy-trading-$(date +%s)"
echo "STEP 3: Creating Heroku app: $APP_NAME"
heroku create $APP_NAME

# ============ STEP 4: Add PostgreSQL Addon ============
echo "STEP 4: Adding PostgreSQL database..."
heroku addons:create heroku-postgresql:mini -a $APP_NAME

# ============ STEP 5: Add Redis Addon ============
echo "STEP 5: Adding Redis cache..."
heroku addons:create heroku-redis:premium-0 -a $APP_NAME

# ============ STEP 6: Set Environment Variables ============
echo "STEP 6: Configuring environment variables..."
heroku config:set -a $APP_NAME \
  APP_ENV=production \
  LOG_LEVEL=INFO \
  LIVE_TRADING_ENABLED=false \
  BINANCE_TESTNET=true \
  MAX_ORDER_NOTIONAL=2000 \
  MAX_ORDER_QUANTITY=10 \
  MAX_POSITION_NOTIONAL=10000 \
  MAX_GROSS_EXPOSURE=20000 \
  MAX_DAILY_LOSS=1000 \
  MAX_OPEN_ORDERS=5 \
  SYMBOL_WHITELIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT \
  SCRAPER_INTERVAL_SECONDS=300 \
  SCRAPER_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT \
  SCRAPER_OHLCV_INTERVALS=1h,4h,1d

echo "❓ Add your Binance API keys (testnet first!):"
echo "   heroku config:set BINANCE_API_KEY=xxx BINANCE_API_SECRET=yyy -a $APP_NAME"
echo ""

# ============ STEP 7: Deploy to Heroku ============
echo "STEP 7: Deploying backend to Heroku..."
cd backend
git push heroku main

# ============ STEP 8: Run Migrations ============
echo "STEP 8: Running database migrations..."
heroku run alembic upgrade head -a $APP_NAME

# ============ STEP 9: Verify Deployment ============
echo "STEP 9: Verifying deployment..."
sleep 5
curl -s https://$APP_NAME.herokuapp.com/docs > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ API is online!"
else
    echo "❌ API health check failed"
    exit 1
fi

# ============ STEP 10: Display Summary ============
echo ""
echo "========================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "========================================="
echo ""
echo "📊 Dashboard URLs:"
echo "   API Docs: https://$APP_NAME.herokuapp.com/docs"
echo "   Risk Status: https://$APP_NAME.herokuapp.com/api/v1/risk/status"
echo "   Monitoring: https://$APP_NAME.herokuapp.com/api/v1/risk/monitoring-dashboard"
echo ""
echo "🔧 Next Steps:"
echo "   1. Get Binance API keys from: https://www.binance.com/en/account/api-management"
echo "   2. Add keys: heroku config:set BINANCE_API_KEY=xxx BINANCE_API_SECRET=yyy -a $APP_NAME"
echo "   3. Monitor logs: heroku logs --tail -a $APP_NAME"
echo "   4. Test endpoints: curl https://$APP_NAME.herokuapp.com/docs"
echo ""
echo "⚠️  IMPORTANT - Paper Trading ONLY until validated!"
echo "   LIVE_TRADING_ENABLED=true requires admin approval"
echo ""
echo "App Name: $APP_NAME"
echo "Save this for future reference!"
