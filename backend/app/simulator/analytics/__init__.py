"""
Simulator analytics and reporting package.

Produces 6 structured reports from simulation results:
  1. BacktestSummaryReport    — overall performance metrics
  2. PnLAttributionReport     — alpha/spread/slippage/commission decomposition
  3. FillToxicityReport       — adverse selection after fills
  4. InventoryBehaviorReport  — position management analysis
  5. RegimeBehaviorReport     — performance by volatility/trend regime
  6. ParameterStabilityReport — calibration parameter stability

Each report is both machine-readable (.to_dict() → JSON) and
human-readable (.format() → text).
"""

from app.simulator.analytics.generators import (
    generate_backtest_summary,
    generate_fill_toxicity,
    generate_full_report,
    generate_inventory_behavior,
    generate_parameter_stability,
    generate_pnl_attribution,
    generate_regime_behavior,
)
from app.simulator.analytics.schemas import (
    BacktestSummaryReport,
    FillToxicityReport,
    FullAnalyticsReport,
    InventoryBehaviorReport,
    ParameterStabilityReport,
    PnLAttributionReport,
    RegimeBehaviorReport,
)

__all__ = [
    "generate_full_report",
    "generate_backtest_summary",
    "generate_pnl_attribution",
    "generate_fill_toxicity",
    "generate_inventory_behavior",
    "generate_regime_behavior",
    "generate_parameter_stability",
    "FullAnalyticsReport",
    "BacktestSummaryReport",
    "PnLAttributionReport",
    "FillToxicityReport",
    "InventoryBehaviorReport",
    "RegimeBehaviorReport",
    "ParameterStabilityReport",
]
