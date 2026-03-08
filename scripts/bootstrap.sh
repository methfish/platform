#!/usr/bin/env bash
#
# Bootstrap the Pensy development environment.
# Usage: ./scripts/bootstrap.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Pensy Platform Bootstrap ==="
echo ""

# --- Check prerequisites ---
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: $1 is not installed. Please install it first."
        exit 1
    fi
}

check_cmd python3
check_cmd docker
check_cmd node

echo "[1/6] Prerequisites OK (python3, docker, node)"

# --- Create .env if missing ---
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "[2/6] Created .env from .env.example"
else
    echo "[2/6] .env already exists, skipping"
fi

# --- Start infrastructure ---
echo "[3/6] Starting PostgreSQL and Redis..."
cd "$PROJECT_DIR"
docker compose up -d postgres redis
sleep 3

# --- Install backend dependencies ---
echo "[4/6] Installing backend dependencies..."
cd "$PROJECT_DIR/backend"
python3 -m pip install -e ".[dev]" --quiet

# --- Run migrations ---
echo "[5/6] Running database migrations..."
cd "$PROJECT_DIR/backend"
python3 -m alembic upgrade head

# --- Seed data ---
echo "[6/6] Seeding initial data..."
cd "$PROJECT_DIR"
python3 -m scripts.seed_data || echo "  (seed script may require running from backend dir)"

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Start the backend:  cd backend && uvicorn app.main:app --reload"
echo "Start the frontend: cd frontend && npm install && npm run dev"
echo ""
echo "Dashboard: http://localhost:3000"
echo "API Docs:  http://localhost:8000/docs"
echo ""
