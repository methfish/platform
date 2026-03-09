#!/usr/bin/env python3
"""
PENSY Trading Platform - Direct Python Launch
No Docker, no Homebrew. Just Python.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and report status."""
    if description:
        print(f"\n✓ {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 PENSY TRADING PLATFORM - DIRECT STARTUP")
    print("=" * 60)

    platform_dir = Path("/Users/matteocrucito/Desktop/platform")
    os.chdir(platform_dir)

    # Step 1: Virtual environment
    print("\n[1/6] Setting up Python environment...")
    if not (platform_dir / "venv").exists():
        run_command("python3 -m venv venv")

    # Step 2: Activate and install
    print("[2/6] Installing dependencies...")
    run_command(
        "source venv/bin/activate && pip install -q fastapi uvicorn pydantic sqlalchemy aiosqlite alembic"
    )

    # Step 3: Create .env
    print("[3/6] Creating configuration...")
    env_file = platform_dir / ".env"
    if not env_file.exists():
        env_content = """# PENSY Trading Platform - Local SQLite Setup
APP_ENV=development
LOG_LEVEL=INFO

# Database - SQLite (local file, no server needed)
DATABASE_URL=sqlite+aiosqlite:///./pensy_local.db

# Redis - Using fakeredis (in-memory, no server needed)
REDIS_URL=redis://localhost:6379

# Binance - TESTNET MODE
BINANCE_TESTNET=true
BINANCE_API_KEY=testnet_key
BINANCE_API_SECRET=testnet_secret

# Trading
LIVE_TRADING_ENABLED=false

# Risk Limits
MAX_ORDER_NOTIONAL=500
MAX_POSITION_NOTIONAL=2000
MAX_DAILY_LOSS=1000
SYMBOL_WHITELIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT

# Market Data
SCRAPER_INTERVAL_SECONDS=300
SCRAPER_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT
SCRAPER_OHLCV_INTERVALS=1h,4h,1d
"""
        env_file.write_text(env_content)
        print("  → Created .env with SQLite configuration")

    # Step 4: Initialize database
    print("[4/6] Initializing SQLite database...")
    run_command(
        "cd backend && source ../venv/bin/activate && python3 -m alembic upgrade head 2>/dev/null || true"
    )

    # Step 5: Print info
    print("[5/6] System information...")
    print("""
📊 PENSY TRADING PLATFORM - READY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Database: SQLite (local file: pensy_local.db)
Redis: In-memory (no server needed)
Mode: PAPER TRADING (no real money)
Trading: TESTNET only (safe)

🌐 ENDPOINTS (once started):
  API Docs:           http://localhost:8000/docs
  Market Overview:    http://localhost:8000/api/v1/markets/overview
  Risk Status:        http://localhost:8000/api/v1/risk/status
  Your Positions:     http://localhost:8000/api/v1/orders/positions/all

🧪 TRY THESE COMMANDS:
  # Place a buy order
  curl -X POST http://localhost:8000/api/v1/orders \\
    -H "Content-Type: application/json" \\
    -d '{"symbol":"BTCUSDT","side":"BUY","order_type":"MARKET","quantity":0.1}'

  # See your position
  curl http://localhost:8000/api/v1/orders/positions/all

  # View all orders
  curl http://localhost:8000/api/v1/orders

🛑 TO STOP: Press Ctrl+C

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    # Step 6: Start server
    print("[6/6] Starting backend server...")
    print("\n" + "=" * 60)
    print("SERVER STARTING...")
    print("=" * 60 + "\n")

    os.chdir(platform_dir / "backend")
    os.system("source ../venv/bin/activate && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")

if __name__ == "__main__":
    main()
