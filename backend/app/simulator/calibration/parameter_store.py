"""
Parameter store — persist and load calibrated simulator parameters.

Stores calibrated parameters as versioned JSON files:
  calibration_store/
    EURUSD/
      latest.json           → symlink to most recent
      2025-01-15T10:30.json → timestamped snapshot
      2025-01-08T10:30.json → previous snapshot

Each snapshot contains:
  - Calibrated SimulatorConfig parameter overrides
  - Metadata: calibration time, data window, bar count, estimator outputs
  - Confidence scores per parameter (how much data backs it)

The parameter store does NOT require a database — it's file-based
so it works in dev, CI, and production without migration.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional


@dataclass
class CalibratedParam:
    """A single calibrated parameter with metadata."""

    name: str
    value: float
    unit: str                  # "bps", "pct", "ms", "usd", "dimensionless"
    source: str                # Which estimator produced this
    confidence: float = 0.0    # 0-1, based on data quantity and stability
    n_observations: int = 0


@dataclass
class CalibrationSnapshot:
    """Complete calibration result, ready to persist."""

    symbol: str
    calibrated_at: str = ""
    data_start: str = ""
    data_end: str = ""
    n_bars: int = 0
    interval: str = ""
    parameters: list[CalibratedParam] = field(default_factory=list)
    # Raw estimator outputs for audit trail
    estimator_summaries: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict."""
        return {
            "symbol": self.symbol,
            "calibrated_at": self.calibrated_at,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "n_bars": self.n_bars,
            "interval": self.interval,
            "parameters": [
                {
                    "name": p.name,
                    "value": p.value,
                    "unit": p.unit,
                    "source": p.source,
                    "confidence": p.confidence,
                    "n_observations": p.n_observations,
                }
                for p in self.parameters
            ],
            "estimator_summaries": self.estimator_summaries,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CalibrationSnapshot:
        """Deserialize from dict."""
        params = [
            CalibratedParam(**p) for p in d.get("parameters", [])
        ]
        return cls(
            symbol=d.get("symbol", ""),
            calibrated_at=d.get("calibrated_at", ""),
            data_start=d.get("data_start", ""),
            data_end=d.get("data_end", ""),
            n_bars=d.get("n_bars", 0),
            interval=d.get("interval", ""),
            parameters=params,
            estimator_summaries=d.get("estimator_summaries", {}),
        )

    def get_param(self, name: str) -> Optional[CalibratedParam]:
        """Look up a parameter by name."""
        for p in self.parameters:
            if p.name == name:
                return p
        return None

    def to_config_overrides(self) -> dict[str, Any]:
        """
        Convert calibrated parameters to SimulatorConfig field overrides.

        Returns a dict suitable for: SimulatorConfig(**defaults, **overrides)
        """
        mapping = {
            "spread_bps": "spread_bps",
            "slippage_bps": "slippage_bps",
            "queue_behind_pct": "queue_behind_pct",
            "fill_rate_pct": "fill_rate_pct",
            "maker_fee_rate": "maker_fee_rate",
            "taker_fee_rate": "taker_fee_rate",
        }
        overrides = {}
        for p in self.parameters:
            if p.name in mapping:
                config_field = mapping[p.name]
                overrides[config_field] = Decimal(str(p.value))
        return overrides


class ParameterStore:
    """
    File-based store for calibrated parameters.

    Directory layout:
      {base_dir}/{symbol}/
        latest.json
        {timestamp}.json
    """

    def __init__(self, base_dir: str | Path = "calibration_store") -> None:
        self._base_dir = Path(base_dir)

    def save(self, snapshot: CalibrationSnapshot) -> Path:
        """
        Save a calibration snapshot to disk.

        Creates a timestamped file and updates the latest symlink.
        Returns the path to the saved file.
        """
        symbol_dir = self._base_dir / snapshot.symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)

        # Timestamp for filename
        ts = snapshot.calibrated_at or datetime.now(timezone.utc).isoformat()
        safe_ts = ts.replace(":", "-").replace("+", "p")
        filename = f"{safe_ts}.json"
        filepath = symbol_dir / filename

        # Write JSON
        with open(filepath, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2, default=str)

        # Update latest symlink
        latest = symbol_dir / "latest.json"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(filename)

        return filepath

    def load_latest(self, symbol: str) -> Optional[CalibrationSnapshot]:
        """Load the most recent calibration for a symbol."""
        latest = self._base_dir / symbol / "latest.json"
        if not latest.exists():
            return None
        return self._load_file(latest)

    def load_snapshot(self, symbol: str, timestamp: str) -> Optional[CalibrationSnapshot]:
        """Load a specific calibration snapshot by timestamp."""
        safe_ts = timestamp.replace(":", "-").replace("+", "p")
        filepath = self._base_dir / symbol / f"{safe_ts}.json"
        if not filepath.exists():
            return None
        return self._load_file(filepath)

    def list_snapshots(self, symbol: str) -> list[str]:
        """List all available calibration timestamps for a symbol."""
        symbol_dir = self._base_dir / symbol
        if not symbol_dir.exists():
            return []
        return sorted([
            f.stem for f in symbol_dir.glob("*.json")
            if f.name != "latest.json" and not f.is_symlink()
        ])

    def _load_file(self, path: Path) -> Optional[CalibrationSnapshot]:
        """Load a snapshot from a JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return CalibrationSnapshot.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
