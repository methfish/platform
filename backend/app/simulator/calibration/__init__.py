"""
Simulator calibration package.

Provides estimators and a walk-forward calibration routine to
derive realistic simulator parameters from historical OHLCV data.

Public API:
    walk_forward_calibrate  — Main calibration entry point
    ParameterStore          — Persist/load calibrated parameters
    format_walk_forward_report — Human-readable report
    format_snapshot_report     — Single-snapshot report

Estimators (used internally, also available directly):
    volatility              — Close-to-close, Parkinson, Garman-Klass, Yang-Zhang
    fill_probability        — Fill rate by distance from mid
    adverse_selection       — Post-fill mid-price movement
    ofi                     — Order flow imbalance predictive power
    queue_model             — Queue depletion rate estimation
"""

from app.simulator.calibration.parameter_store import (
    CalibratedParam,
    CalibrationSnapshot,
    ParameterStore,
)
from app.simulator.calibration.report import (
    format_snapshot_report,
    format_walk_forward_report,
)
from app.simulator.calibration.walk_forward import (
    WalkForwardResult,
    walk_forward_calibrate,
)

__all__ = [
    "walk_forward_calibrate",
    "WalkForwardResult",
    "ParameterStore",
    "CalibrationSnapshot",
    "CalibratedParam",
    "format_walk_forward_report",
    "format_snapshot_report",
]
