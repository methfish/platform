# Pensy Platform - Risk Controls

## Overview

The risk engine runs 15+ checks synchronously before any order reaches the exchange. All checks implement `BaseRiskCheck` and return a structured `RiskCheckResponse`.

## Risk Checks

| # | Check | Description | Config Variable |
|---|-------|-------------|-----------------|
| 1 | Kill Switch | Blocks ALL orders when active | Runtime toggle |
| 2 | Order Size | Max quantity and notional per order | `MAX_ORDER_QUANTITY`, `MAX_ORDER_NOTIONAL` |
| 3 | Position Limit | Max position size per symbol | `MAX_POSITION_NOTIONAL` |
| 4 | Daily Loss | Max aggregate daily loss | `MAX_DAILY_LOSS` |
| 5 | Order Rate | Max orders per minute | `MAX_ORDERS_PER_MINUTE` |
| 6 | Price Deviation | Limit price vs market deviation | `PRICE_DEVIATION_THRESHOLD` |
| 7 | Symbol Whitelist | Only allowed symbols | `SYMBOL_WHITELIST` |
| 8 | Duplicate Order | Identical order within time window | 5-second window |
| 9 | Drawdown | Max drawdown from peak equity | Configurable |
| 10 | Leverage | Max leverage for futures | Configurable |
| 11 | Concentration | Single-asset portfolio concentration | Configurable |
| 12 | Cancel Rate | Cancel-to-fill ratio limit | Configurable |
| 13 | PnL Threshold | Per-trade max loss | Configurable |
| 14 | Margin Check | Available margin for futures | Configurable |
| 15 | Trading Hours | Allowed trading windows | 24/7 default for crypto |

## Risk Profiles

Three predefined profiles with different limit thresholds:
- **Conservative**: Tight limits for initial testing
- **Moderate**: Balanced for normal operation (default)
- **Aggressive**: Wide limits for experienced operators

## Adding a New Risk Check

1. Create `app/risk/checks/my_check.py`
2. Implement `BaseRiskCheck` with `name` property and `evaluate()` method
3. Register in the risk engine's check list
4. Add config variables if needed
5. Write unit test

## Kill Switch

The kill switch is the most critical safety control. When active:
- ALL new orders are immediately rejected
- It's checked FIRST before any other risk checks
- Can be activated via API or dashboard
- Requires explicit deactivation to resume trading
