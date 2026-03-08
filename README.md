# Pensy Order Execution Platform

Proprietary order execution platform for cryptocurrency trading. Supports automated and manual order execution with comprehensive risk management, position tracking, and an admin dashboard.

## Architecture

```
┌─────────────────────────────────┐
│     React Admin Dashboard       │
│  (Orders, Positions, Risk, PnL) │
└──────────┬──────────────────────┘
           │ HTTP/REST + WebSocket
           ▼
┌──────────────────────────────────────────────┐
│              FastAPI Backend                  │
│                                              │
│  ┌─────┐ ┌──────┐ ┌────────┐ ┌──────────┐  │
│  │ OMS │ │ Risk │ │Position│ │ Strategy │  │
│  │     │ │Engine│ │Tracker │ │ Runner   │  │
│  └──┬──┘ └──────┘ └────────┘ └──────────┘  │
│     │                                        │
│  ┌──┴────────────────────────────────────┐  │
│  │      Exchange Adapter Layer           │  │
│  │  ┌───────┐ ┌────────┐ ┌──────────┐  │  │
│  │  │ Paper │ │Binance │ │ Binance  │  │  │
│  │  │Adapter│ │  Spot  │ │ Futures  │  │  │
│  │  └───────┘ └────────┘ └──────────┘  │  │
│  └───────────────────────────────────────┘  │
└──────────┬────────────────┬─────────────────┘
           │                │
    ┌──────┴──┐      ┌─────┴───┐
    │PostgreSQL│      │  Redis  │
    └─────────┘      └─────────┘
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### 1. Clone and Configure

```bash
cp .env.example .env
# Edit .env if needed (defaults work for paper trading)
```

### 2. Start Services

```bash
# Start everything with Docker
make up

# OR start infrastructure only and run backend locally
docker compose up -d postgres redis
cd backend && pip install -e ".[dev]"
cd backend && alembic upgrade head
python -m scripts.seed_data
cd backend && uvicorn app.main:app --reload
```

### 3. Access

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:3000
- **Health Check**: http://localhost:8000/health

### Default Credentials (Paper Mode)
- Admin: `admin` / `admin123`
- Operator: `operator` / `operator123`

## Paper Trading (Default Mode)

The platform boots in **PAPER** trading mode by default. Paper trading:
- Uses a simulated exchange adapter
- Fills market orders at last price + configurable slippage
- Fills limit orders when price crosses the limit
- Tracks positions, PnL, and balances identically to live mode
- All risk checks run the same way
- Seed initial prices with `make seed`

## Enabling Live Trading

**WARNING: Live trading places REAL orders on the exchange.**

Live trading requires TWO independent safety gates:

1. Set environment variable: `LIVE_TRADING_ENABLED=true`
2. After startup, confirm via admin API:
   ```
   POST /api/v1/admin/live-mode-confirm
   {"confirm": true, "confirmation_phrase": "I confirm live trading"}
   ```

Both must be true for live orders to be submitted. The dashboard shows a prominent PAPER/LIVE indicator at all times.

### Kill Switch

To immediately halt all trading:
```
POST /api/v1/risk/kill-switch
{"activate": true}
```

Or use the Kill Switch button in the dashboard. This blocks all new order submissions globally.

## Environment Variables

See `.env.example` for all variables with descriptions. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVE_TRADING_ENABLED` | `false` | Must be `true` for live trading |
| `DATABASE_URL` | (see .env) | PostgreSQL connection string |
| `REDIS_URL` | (see .env) | Redis connection string |
| `BINANCE_API_KEY` | (empty) | Binance API key for live trading |
| `MAX_ORDER_NOTIONAL` | `10000` | Max order value in USDT |
| `MAX_DAILY_LOSS` | `5000` | Max daily loss before blocking |
| `SYMBOL_WHITELIST` | `BTCUSDT,ETHUSDT,SOLUSDT` | Allowed trading pairs |

## Running Migrations

```bash
cd backend
alembic upgrade head          # Apply all migrations
alembic downgrade -1          # Rollback last migration
alembic revision --autogenerate -m "description"  # Create new migration
```

## Running Tests

```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests
make test-cov          # Tests with coverage report
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/orders` | List orders |
| POST | `/api/v1/orders` | Submit order |
| POST | `/api/v1/orders/{id}/cancel` | Cancel order |
| GET | `/api/v1/positions` | List positions |
| GET | `/api/v1/pnl` | PnL summary |
| GET | `/api/v1/risk/status` | Risk engine status |
| POST | `/api/v1/risk/kill-switch` | Toggle kill switch |
| GET | `/api/v1/strategies` | List strategies |
| POST | `/api/v1/strategies/{id}/enable` | Enable strategy |
| GET | `/api/v1/market-data/tickers` | Current prices |
| POST | `/api/v1/reconciliation/run` | Run reconciliation |
| GET | `/api/v1/audit-logs` | Audit trail |

## Known Limitations (v1)

- Single-process monolith (suitable for moderate throughput, not HFT)
- Binance futures adapter is scaffold only
- No WebSocket-based market data for paper trading (uses seeded prices)
- Reconciliation runs on-demand only (no scheduler yet)
- JWT auth is basic scaffold (no refresh token rotation)
- No rate limiting on API endpoints
- No TLS termination (use nginx/reverse proxy in production)

## Roadmap

- [ ] Multi-exchange support (Bybit, OKX)
- [ ] WebSocket market data for paper trading via Binance public streams
- [ ] Scheduled reconciliation jobs
- [ ] Smart order routing
- [ ] Advanced strategy SDK
- [ ] Backtesting engine
- [ ] Alert integrations (Slack, Telegram)
- [ ] Role-based access control
- [ ] API rate limiting
- [ ] Kubernetes deployment manifests
