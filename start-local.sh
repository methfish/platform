#!/bin/bash
# PENSY Trading Platform - Simple Python Startup (No Docker, No Dependencies)

set -e

PROJECT_DIR="/Users/matteocrucito/Desktop/platform"
cd "$PROJECT_DIR"

echo "=========================================="
echo "🚀 PENSY TRADING PLATFORM"
echo "=========================================="
echo ""

# Step 1: Check Python
echo "✓ Checking Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Step 2: Virtual environment
if [ ! -d "venv" ]; then
    echo "✓ Creating virtual environment..."
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Step 3: Install core dependencies only
echo "✓ Installing required packages..."
pip install -q fastapi uvicorn pydantic pydantic-settings sqlalchemy aiosqlite alembic redis aiohttp structlog python-jose passlib httpx orjson 2>/dev/null || {
    echo "  Installing packages..."
    pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy aiosqlite alembic redis aiohttp structlog python-jose passlib httpx orjson
}

# Step 4: Create .env if needed
if [ ! -f ".env" ]; then
    echo "✓ Creating .env configuration..."
    cat > .env << 'EOF'
# Local Configuration - SQLite + In-Memory Redis
APP_ENV=development
LOG_LEVEL=INFO
DEBUG=true

# SQLite Database (local file)
DATABASE_URL=sqlite+aiosqlite:///./pensy_trading.db

# Redis - Local instance expected
REDIS_URL=redis://localhost:6379/0

# Binance - TESTNET ONLY
BINANCE_TESTNET=true
BINANCE_API_KEY=local_test_key
BINANCE_API_SECRET=local_test_secret

# Trading - PAPER MODE
LIVE_TRADING_ENABLED=false

# Risk - Conservative
MAX_ORDER_NOTIONAL=500
MAX_ORDER_QUANTITY=10
MAX_POSITION_NOTIONAL=2000
MAX_GROSS_EXPOSURE=5000
MAX_DAILY_LOSS=999999  # Disabled for testing
MAX_OPEN_ORDERS=100
MAX_ORDERS_PER_MINUTE=1000
SYMBOL_WHITELIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT

# Market Data Scraper
SCRAPER_INTERVAL_SECONDS=300
SCRAPER_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT
SCRAPER_OHLCV_INTERVALS=1h,4h,1d
SCRAPER_OHLCV_LIMIT=100

# Disable features that need external services for now
SKIP_MARKET_DATA_SCRAPER=true
EOF
    echo "  → .env created with SQLite configuration"
fi

# Step 5: Setup database
echo "✓ Setting up database..."
cd backend

# Check if migrations exist
if [ -f "alembic/versions/001_initial_schema.py" ]; then
    echo "  → Running migrations..."
    python3 -m alembic upgrade head 2>/dev/null || echo "  → Database already initialized"
else
    echo "  → First run, skipping migrations"
fi

# Step 6: Info
echo ""
echo "=========================================="
echo "✅ READY TO START!"
echo "=========================================="
echo ""
echo "Starting backend server on http://localhost:8000"
echo ""
echo "🌐 Once running, open:"
echo "   • API Docs:      http://localhost:8000/docs"
echo "   • Market Data:   http://localhost:8000/api/v1/markets/overview"
echo "   • Positions:     http://localhost:8000/api/v1/orders/positions/all"
echo "   • Risk Status:   http://localhost:8000/api/v1/risk/status"
echo ""
echo "🧪 Test in another terminal:"
echo "   curl http://localhost:8000/api/v1/markets/overview"
echo ""
echo "To stop: Press Ctrl+C"
echo ""
echo "=========================================="
echo ""

# Step 7: Start server
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
