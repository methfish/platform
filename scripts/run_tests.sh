#!/usr/bin/env bash
#
# Run the Pensy test suite.
# Usage: ./scripts/run_tests.sh [unit|integration|e2e|all|cov]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

cd "$BACKEND_DIR"

MODE="${1:-all}"

case "$MODE" in
    unit)
        echo "=== Running Unit Tests ==="
        python3 -m pytest tests/unit/ -v
        ;;
    integration)
        echo "=== Running Integration Tests ==="
        python3 -m pytest tests/integration/ -v
        ;;
    e2e)
        echo "=== Running E2E Tests ==="
        python3 -m pytest tests/e2e/ -v
        ;;
    cov)
        echo "=== Running All Tests with Coverage ==="
        python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html
        echo ""
        echo "HTML coverage report: $BACKEND_DIR/htmlcov/index.html"
        ;;
    all)
        echo "=== Running All Tests ==="
        python3 -m pytest tests/ -v
        ;;
    *)
        echo "Usage: $0 [unit|integration|e2e|all|cov]"
        exit 1
        ;;
esac
