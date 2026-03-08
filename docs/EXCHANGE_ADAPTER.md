# Pensy Platform - Exchange Adapter Guide

## Overview

The `ExchangeAdapter` ABC in `app/exchange/base.py` is the foundational abstraction. Every exchange implementation provides the same interface to the OMS, risk engine, and reconciliation service.

## Implementing a New Exchange

### 1. Create the adapter directory

```
app/exchange/my_exchange/
    __init__.py
    auth.py        # API key signing
    client.py      # REST client
    ws.py          # WebSocket manager
    adapter.py     # ExchangeAdapter implementation
    mappers.py     # Raw response -> normalized models
```

### 2. Implement the ABC methods

All methods are async. All financial values use `Decimal`. All responses use normalized models from `app/exchange/models.py`.

Key methods:
- `place_order()` - Submit order, return `ExchangeOrderResult`
- `cancel_order()` - Cancel order, return `ExchangeCancelResult`
- `get_order_status()` - Query single order
- `get_open_orders()` - List open orders
- `get_balances()` - Account balances
- `get_positions()` - Current positions
- `subscribe_ticker()` - Real-time price stream
- `subscribe_user_data()` - Order/fill update stream

### 3. Register in factory

Add your exchange to `app/exchange/factory.py`.

### 4. Add configuration

Add API key settings to `app/config.py` using `SecretStr`.

## Existing Adapters

| Adapter | Status | Notes |
|---------|--------|-------|
| PaperExchangeAdapter | Complete | Simulated fills, in-memory |
| BinanceSpotAdapter | Functional | Testnet tested |
| BinanceFuturesAdapter | Scaffold | Needs implementation |

## Paper Trading Adapter

The paper adapter simulates exchange behavior:
- Market orders fill at last price + configurable slippage
- Limit orders fill when price crosses the limit
- Commission is configurable (default 0.1%)
- Balances are tracked in-memory
- Prices must be seeded or come from a live feed
