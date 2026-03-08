# Pensy Platform - Architecture

## Overview

Pensy is a modular monolith order execution platform. All services run in a single FastAPI process with clean module boundaries. This design prioritizes correctness, debuggability, and simplicity over distributed scalability in v1.

## Module Map

| Module | Responsibility |
|--------|---------------|
| `exchange/` | Exchange adapter ABC + implementations (paper, Binance) |
| `oms/` | Order management - lifecycle, state machine, validation |
| `risk/` | Risk engine with 15+ composable checks |
| `position/` | Position tracking, PnL calculation, snapshots |
| `market_data/` | Market data subscription, normalization, caching |
| `strategy/` | Strategy interface, runner, examples |
| `reconciliation/` | Internal vs exchange state comparison |
| `auth/` | JWT authentication, password hashing, RBAC |
| `api/` | REST endpoints, WebSocket, schemas, middleware |
| `observability/` | Structured logging, metrics, health checks |
| `core/` | Enums, events, exceptions, types |
| `models/` | SQLAlchemy ORM models |
| `db/` | Database session, repository pattern |

## Key Design Principles

1. **Paper trading as a first-class adapter** - The PaperExchangeAdapter implements the same ABC as live adapters. All OMS logic, risk checks, and position tracking work identically.

2. **Explicit order state machine** - Every order state transition is validated against a formal FSM. Illegal transitions raise exceptions immediately.

3. **Write-ahead persistence** - Critical state is committed to PostgreSQL BEFORE events are emitted. If the process crashes, the database tells us exactly where we were.

4. **Decimal everywhere** - All financial calculations use Python Decimal. Database uses NUMERIC(28,12). Never float.

5. **Double-gate live trading** - Requires BOTH environment variable AND runtime operator confirmation.

## Data Flow: Order Submission

```
API Request -> Order Validation -> Risk Engine (15 checks)
    -> State Machine (PENDING -> APPROVED)
    -> DB Persist
    -> Exchange Adapter (paper or live)
    -> State Machine (APPROVED -> SUBMITTED)
    -> DB Persist
    -> [Fill Event from Exchange]
    -> Fill Handler -> Position Update -> PnL Update
    -> State Machine (SUBMITTED -> FILLED)
    -> DB Persist -> Event Bus -> WebSocket -> Dashboard
```

## Future Extraction Points

When scale requires it, these modules can be extracted to separate services:
- Market data ingestion -> separate WebSocket service
- Strategy runner -> separate worker process
- Reconciliation -> scheduled job / cron service
