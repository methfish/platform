# Pensy Quantitative Research Framework

## System Objective

Build a disciplined, data-driven micro trading research operation for a $2,000 account.

**Core principles:**
- Capital preservation over growth
- Measurable learning loops over fast profits
- Robustness over sophistication
- Survival first, optimization second

**Key difference from institutional systems:** We optimize for learning speed and capital preservation, not throughput or alpha capacity. Every dollar lost is 0.05% of capital — costs matter enormously.

---

## Research Loop

```
1. Collect Data → 2. Clean & Validate → 3. Generate Hypothesis
       ↑                                          ↓
8. Deploy/Reject ← 7. Out-of-Sample Test ← 6. Refine ← 5. Evaluate ← 4. Backtest
```

### Step-by-step:

| Step | Purpose | Input | Output | Common Mistake |
|------|---------|-------|--------|----------------|
| 1. Collect | Get raw market data | Exchange API | OHLCV bars, trades | Collecting too much data you won't use |
| 2. Clean | Remove gaps, validate | Raw data | Clean dataset | Ignoring missing bars or bad ticks |
| 3. Hypothesize | Form testable idea | Market observation | Strategy spec | Vague hypothesis that can't be falsified |
| 4. Backtest | Test against history | Strategy + data | Trade list + P&L | No fees, perfect fills, lookahead bias |
| 5. Evaluate | Measure performance | Backtest results | Metrics report | Focusing only on P&L, ignoring drawdown |
| 6. Refine | Improve parameters | Metrics + data | Updated params | Overfitting to in-sample data |
| 7. OOS Test | Validate on unseen data | Holdout data | OOS metrics | Using OOS data more than once |
| 8. Decide | Deploy, reject, or iterate | All evidence | Decision | Deploying based on one good backtest |

---

## Strategy Types Supported

### Grid Trading
- **Logic:** Place buy orders at fixed intervals below price, sell at intervals above
- **Best for:** Ranging markets, high-volume pairs
- **Key param:** `grid_size_pct` (distance between levels)
- **Failure mode:** Strong trends blow through grid levels
- **Min viable:** BTC/ETH 1% grid, $200 per level

### Market Making
- **Logic:** Post bid/ask quotes around mid-price, capture spread
- **Best for:** Stable markets with predictable volatility
- **Key params:** `spread_bps`, `max_inventory`, `num_levels`
- **Failure mode:** Inventory accumulation in trending market
- **Min viable:** Single-level quoting on one pair, paper mode

### Mean Reversion
- **Logic:** Buy when price is N std devs below SMA, sell when above
- **Best for:** Mean-reverting assets (many crypto pairs in ranges)
- **Key params:** `sma_period`, `entry_std`
- **Failure mode:** Regime change (mean shifts, trend emerges)
- **Min viable:** 20-period SMA, 2 std entry, single pair

### Breakout
- **Logic:** Buy new highs, sell new lows over lookback window
- **Best for:** Trending markets, momentum regimes
- **Key params:** `lookback` period
- **Failure mode:** Choppy/ranging markets cause whipsaws
- **Min viable:** 20-bar breakout, used mainly as control strategy

### Cross-Exchange Arbitrage
- **Logic:** Buy on exchange A where cheaper, sell on exchange B where more expensive
- **Best for:** Price discrepancies across venues
- **Key params:** `min_spread_bps`, `exchange_a`, `exchange_b`
- **Failure mode:** Transfer delays, fee asymmetry, slippage
- **Min viable:** Paper-only monitoring of price differences

---

## Backtesting Checklist

Before trusting any backtest result:

- [ ] **Fees included?** At least 0.1% maker/taker
- [ ] **Slippage modeled?** At least 2-5 bps
- [ ] **Spread cost included?** Half-spread on each trade
- [ ] **Partial fills considered?** Not all limit orders fill
- [ ] **No lookahead bias?** Signal uses only past data
- [ ] **Sufficient trades?** At least 30 round-trips
- [ ] **Sufficient time period?** At least 30 days
- [ ] **Out-of-sample tested?** Holdout data validation
- [ ] **Max drawdown acceptable?** Below 20% for $2k account
- [ ] **Sharpe realistic?** Below 3.0 (above is suspicious)
- [ ] **Win rate realistic?** Below 80% (above is suspicious)

---

## Key Metrics

### Must Track
| Metric | What It Tells You | Threshold |
|--------|-------------------|-----------|
| Net P&L | Bottom line | Positive after costs |
| Sharpe Ratio | Risk-adjusted return | > 1.0 for consideration |
| Max Drawdown % | Worst peak-to-trough | < 15% for $2k account |
| Win Rate | Hit ratio | 40-65% typical |
| Expectancy | Average $ per trade | Must be positive |
| Fee Drag % | Costs as % of gross profit | < 40% |
| Profit Factor | Gross wins / gross losses | > 1.5 |

### Misleading Metrics
- **Raw return %** without time period context
- **Win rate alone** (can be high with tiny wins and huge losses)
- **Backtest P&L** without cost modeling
- **Sharpe > 4** (almost certainly overfitting)

### Deployment Thresholds
Before risking live capital:
- Sharpe > 1.0 on out-of-sample data
- Max drawdown < 15%
- At least 50 trades in backtest
- Fee drag < 40% of gross profit
- Passed trust checks (no suspicious metrics)
- Paper traded for minimum 2 weeks

---

## Risk Management Rules

### Position Limits
- Max 10% of capital per strategy ($200 on $2k)
- Max 25% of capital deployed simultaneously ($500)
- Max position size: calculated from stop loss distance

### Loss Limits
- Max daily loss: 2% of capital ($40)
- Max weekly drawdown: 5% of capital ($100)
- Max per-trade risk: 1% of capital ($20)

### Kill Switch Triggers
- Daily loss exceeds limit → halt all trading
- API disconnects > 30 seconds → cancel all open orders
- Spread widens > 3x normal → pause market making
- Slippage > 10bps on 3 consecutive fills → investigate
- Inventory > 80% of max → stop adding to position

---

## Daily Operating Cadence

### Daily (10 min)
1. Check data ingestion ran successfully
2. Review paper trading P&L
3. Check for anomalies (unusual fills, spread changes)
4. Verify system health (API connections, DB size)

### Weekly (30 min)
1. Compare strategy performance across the week
2. Review parameter stability
3. Archive failed hypotheses with reasons
4. Propose model updates (or confirm no changes needed)

### Monthly (1 hour)
1. Full portfolio review
2. Capital allocation adjustments (if warranted)
3. Model retirement decisions
4. Research priority setting for next month

---

## MVP Build Plan

### Phase 1: Data Collection (Week 1)
- Collect BTC/USDT and ETH/USDT 1m + 5m candles
- Backfill 30 days of history
- Verify data quality (no gaps, valid prices)
- **Success:** 50K+ clean bars in database

### Phase 2: First Backtests (Week 2)
- Run grid and mean reversion backtests
- Compare with and without fees
- Identify best parameter ranges
- **Success:** 5+ backtests with realistic cost model

### Phase 3: Cost Awareness (Week 3)
- Compare naive vs realistic backtests
- Quantify fee drag on each strategy
- Identify strategies that survive costs
- **Success:** Understand true cost impact per strategy

### Phase 4: Paper Trading (Weeks 4-5)
- Deploy best-performing strategy in paper mode
- Monitor for 2 weeks minimum
- Compare paper results to backtest expectations
- **Success:** Paper P&L within 50% of backtest estimate

### Phase 5: Tiny Live (Week 6+)
- Deploy with $100-200 maximum
- Monitor closely for first 50 trades
- Compare to paper results
- **Success:** Live results match paper within 30%

### Phase 6: Scale (Month 3+)
- Only if Phase 5 is successful
- Increase allocation gradually (2x every 2 weeks)
- Add second strategy only after first is stable
- **Success:** Consistent positive expectancy over 100+ trades

---

## Agent Behavior Rules

The AI research assistant must:
- Be skeptical of all results until independently validated
- Flag overfitting risk whenever fewer than 50 trades are used
- Compare results across different market regimes
- Never assume profitability from limited tests
- Always include costs in any P&L discussion
- Prioritize survival metrics (drawdown) over growth metrics (return)

The AI research assistant must not:
- Optimize blindly for maximum return
- Use unrealistic fill assumptions (100% fill rate on limits)
- Recommend leverage for a $2k account
- Present single-regime results as robust findings
- Ignore fee drag or slippage

---

## Technical Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (React)                 │
│  Dashboard │ Research │ Strategies │ Risk         │
└────────────────────┬────────────────────────────┘
                     │ REST API
┌────────────────────┴────────────────────────────┐
│               FastAPI Backend                     │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Research  │ │ Strategy │ │ Risk Engine      │ │
│  │ API      │ │ Engine   │ │ (19 checks)      │ │
│  └────┬─────┘ └────┬─────┘ └──────────────────┘ │
│       │             │                             │
│  ┌────┴─────┐ ┌────┴─────┐ ┌──────────────────┐ │
│  │ Backtest │ │ MM / Arb │ │ OMS + Fill       │ │
│  │ Engine   │ │ Runner   │ │ Handler          │ │
│  └────┬─────┘ └────┬─────┘ └──────────────────┘ │
│       │             │                             │
│  ┌────┴─────┐ ┌────┴──────────────────────────┐ │
│  │ Metrics  │ │ Exchange Adapters             │ │
│  │ Calc     │ │ Paper │ Binance │ Futures     │ │
│  └──────────┘ └───────────────────────────────┘ │
│                                                   │
│  ┌────────────────────────────────────────────┐  │
│  │ Data Pipeline (CCXT → PostgreSQL)          │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
           │
┌──────────┴──────────┐
│  PostgreSQL + Redis  │
│  (Docker Compose)    │
└─────────────────────┘
```

---

## Cost Models Available

| Model | Maker Fee | Taker Fee | Slippage | Spread | Use Case |
|-------|-----------|-----------|----------|--------|----------|
| `binance_spot` | 0.10% | 0.10% | 2 bps | 2 bps | Default realistic |
| `binance_bnb` | 0.075% | 0.075% | 2 bps | 2 bps | With BNB discount |
| `conservative` | 0.10% | 0.10% | 5 bps | 5 bps | Worst-case testing |
| `zero` | 0% | 0% | 0 | 0 | Naive baseline only |

**Rule:** Always compare `binance_spot` vs `zero` to understand true cost impact.

---

## Output Templates

### Backtest Summary
```
Strategy: grid | Symbol: BTCUSDT | Period: 30d | Bars: 8,640

P&L:     +$23.45 (1.17% return)
Sharpe:  1.24 | Sortino: 1.78 | Calmar: 0.89
Max DD:  -1.32% ($26.40)
Trades:  47 | Win Rate: 55.3% | Profit Factor: 1.61
Fees:    $8.12 (25.7% of gross) | Avg Hold: 42m

Trust:   PASS (all checks passed)
```

### Risk Alert
```
[ALERT] Daily loss limit approaching
Current: -$35.20 / -$40.00 limit (88%)
Action:  Reduce position sizes or halt new entries
```

### Deployment Recommendation
```
Strategy:    grid_btc_1pct
Confidence:  MODERATE
Evidence:    52 backtest trades, 2 weeks paper, Sharpe 1.3
Risk:        Max $200 allocation, $20 stop per trade
Next review: After 50 live trades
```
