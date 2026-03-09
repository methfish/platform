"""
Calibration report generator.

Produces a structured text report from a WalkForwardResult or
CalibrationSnapshot. Designed for terminal output and logging.
"""

from __future__ import annotations

from typing import Optional

from app.simulator.calibration.parameter_store import CalibrationSnapshot
from app.simulator.calibration.walk_forward import WalkForwardResult


def format_snapshot_report(snapshot: CalibrationSnapshot) -> str:
    """Format a CalibrationSnapshot as a human-readable report."""
    lines = []
    w = 70

    lines.append("=" * w)
    lines.append(f"CALIBRATION REPORT — {snapshot.symbol}")
    lines.append("=" * w)
    lines.append(f"  Calibrated at:   {snapshot.calibrated_at}")
    lines.append(f"  Data range:      {snapshot.data_start} → {snapshot.data_end}")
    lines.append(f"  Bars:            {snapshot.n_bars}")
    lines.append(f"  Interval:        {snapshot.interval}")

    # Parameters
    lines.append(f"\n{'─' * w}")
    lines.append("CALIBRATED PARAMETERS")
    lines.append(f"{'─' * w}")
    lines.append(
        f"  {'Parameter':<28} {'Value':>10} {'Unit':<14} "
        f"{'Conf':>5} {'Source':<20}"
    )
    lines.append(f"  {'─' * 26}  {'─' * 10} {'─' * 14} {'─' * 5} {'─' * 20}")
    for p in snapshot.parameters:
        lines.append(
            f"  {p.name:<28} {p.value:>10.4f} {p.unit:<14} "
            f"{p.confidence:>5.2f} {p.source:<20}"
        )

    # Estimator summaries
    summaries = snapshot.estimator_summaries
    if "volatility" in summaries:
        lines.append(f"\n{'─' * w}")
        lines.append("VOLATILITY ESTIMATORS")
        lines.append(f"{'─' * w}")
        vol = summaries["volatility"]
        for est, val in vol.items():
            if val is not None:
                lines.append(f"  {est:<20} {val:>10.4f} (annualized)")

    if "fill_probability" in summaries:
        lines.append(f"\n{'─' * w}")
        lines.append("FILL PROBABILITY")
        lines.append(f"{'─' * w}")
        fp = summaries["fill_probability"]
        lines.append(f"  Buy half-life:           {_fmt(fp.get('buy_half_life_bps'))} bps")
        lines.append(f"  Sell half-life:          {_fmt(fp.get('sell_half_life_bps'))} bps")
        lines.append(f"  Recommended spread:      {_fmt(fp.get('recommended_spread_bps'))} bps")

    if "adverse_selection" in summaries:
        lines.append(f"\n{'─' * w}")
        lines.append("ADVERSE SELECTION")
        lines.append(f"{'─' * w}")
        adv = summaries["adverse_selection"]
        lines.append(f"  Mean buy adverse:        {adv.get('mean_buy_adverse_bps', 0):.2f} bps")
        lines.append(f"  Mean sell adverse:       {adv.get('mean_sell_adverse_bps', 0):.2f} bps")
        lines.append(f"  Recommended slippage:    {adv.get('recommended_slippage_bps', 0):.2f} bps")
        if "horizons" in adv:
            lines.append(f"  {'Horizon':>8} {'Buy (bps)':>10} {'Sell (bps)':>11}")
            for h in adv["horizons"]:
                lines.append(
                    f"  {h['bars']:>8} {h['buy_bps']:>10.2f} {h['sell_bps']:>11.2f}"
                )

    if "ofi" in summaries:
        lines.append(f"\n{'─' * w}")
        lines.append("ORDER FLOW IMBALANCE")
        lines.append(f"{'─' * w}")
        ofi = summaries["ofi"]
        lines.append(f"  Max R²:                  {ofi.get('max_r_squared', 0):.4f}")
        lines.append(f"  Best horizon:            {ofi.get('best_horizon', 0)} bars")
        lines.append(f"  OFI is predictive:       {ofi.get('is_predictive', False)}")

    if "queue_depletion" in summaries:
        lines.append(f"\n{'─' * w}")
        lines.append("QUEUE DEPLETION")
        lines.append(f"{'─' * w}")
        qd = summaries["queue_depletion"]
        lines.append(f"  Recommended queue_behind_pct: {qd.get('recommended_queue_behind_pct', 0):.4f}")
        lines.append(f"  Recommended fill_rate_pct:    {qd.get('recommended_fill_rate_pct', 0):.4f}")
        if "estimates" in qd:
            lines.append(f"  {'Dist (bps)':>10} {'Mean drain':>11} {'Episodes':>9} {'Immediate%':>11}")
            for e in qd["estimates"]:
                lines.append(
                    f"  {e['distance_bps']:>10.1f} {e['mean_drain_bars']:>11.2f} "
                    f"{e['n_episodes']:>9} {e.get('immediate_pct', 0):>10.1%}"
                )

    # SimulatorConfig overrides
    overrides = snapshot.to_config_overrides()
    if overrides:
        lines.append(f"\n{'─' * w}")
        lines.append("SIMULATORCONFIG OVERRIDES")
        lines.append(f"{'─' * w}")
        lines.append("  SimulatorConfig(")
        for k, v in overrides.items():
            lines.append(f'      {k}=Decimal("{v}"),')
        lines.append("  )")

    lines.append(f"\n{'=' * w}")
    return "\n".join(lines)


def format_walk_forward_report(result: WalkForwardResult) -> str:
    """Format a full walk-forward calibration report."""
    lines = []
    w = 70

    lines.append("=" * w)
    lines.append(f"WALK-FORWARD CALIBRATION — {result.symbol}")
    lines.append("=" * w)
    lines.append(f"  Total bars:      {result.n_bars}")
    lines.append(f"  Windows:         {result.n_windows}")
    lines.append(f"  Train size:      {result.train_size} bars")
    lines.append(f"  Test size:       {result.test_size} bars")
    lines.append(f"  Step size:       {result.step_size} bars")

    # Stability metrics
    if result.stability:
        lines.append(f"\n{'─' * w}")
        lines.append("PARAMETER STABILITY")
        lines.append(f"{'─' * w}")
        lines.append(
            f"  {'Parameter':<28} {'Mean':>10} {'Std':>10} "
            f"{'CV':>6} {'Stable':>7}"
        )
        lines.append(f"  {'─' * 26}  {'─' * 10} {'─' * 10} {'─' * 6} {'─' * 7}")
        for s in result.stability:
            stable_str = "YES" if s.is_stable else "NO"
            lines.append(
                f"  {s.param_name:<28} {s.mean:>10.4f} {s.std:>10.4f} "
                f"{s.cv:>6.2f} {stable_str:>7}"
            )

    # Per-window summary
    if result.windows:
        lines.append(f"\n{'─' * w}")
        lines.append("PER-WINDOW CALIBRATIONS")
        lines.append(f"{'─' * w}")
        # Show key params across windows
        key_params = ["spread_bps", "slippage_bps", "queue_behind_pct"]
        header = f"  {'Window':>6} {'Bars':>12}"
        for kp in key_params:
            header += f" {kp:>16}"
        lines.append(header)

        for win in result.windows:
            row = f"  {win.window_idx:>6} {win.train_start_bar:>5}-{win.train_end_bar:<5}"
            for kp in key_params:
                p = win.snapshot.get_param(kp)
                if p is not None:
                    row += f" {p.value:>16.4f}"
                else:
                    row += f" {'—':>16}"
            lines.append(row)

    # Final calibration
    if result.final_snapshot:
        lines.append("")
        lines.append(format_snapshot_report(result.final_snapshot))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt(val: Optional[float]) -> str:
    """Format a float or None."""
    if val is None:
        return "N/A"
    return f"{val:.2f}"
