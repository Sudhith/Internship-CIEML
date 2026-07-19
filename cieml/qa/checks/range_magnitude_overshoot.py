"""QA check: literature-band range violations + magnitude overshoot (Phase D pilot).

Extracted from stage01_audit._classify_range so turbidity-class extreme spikes
are configurable via domain.qa.range_magnitude_overshoot rather than hardcoded.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def classify_range(
    series: pd.Series,
    lo: float,
    hi: float,
    *,
    critical_overshoot_ratio: float = 2.0,
    suspicious_frac_out: float = 0.01,
    elevated_frac_out: float = 0.05,
) -> dict[str, Any]:
    s = pd.to_numeric(series, errors="coerce")
    n = int(s.notna().sum())
    if n == 0:
        return {
            "severity": "Suspicious",
            "reason": "all_missing",
            "frac_out": 1.0,
            "n": 0,
            "max_overshoot_ratio": 0.0,
            "check_id": "range_magnitude_overshoot",
        }
    out = ~s.between(lo, hi) & s.notna()
    frac = float(out.mean())
    if frac == 0:
        return {
            "severity": "Acceptable",
            "reason": "within_literature_band",
            "frac_out": 0.0,
            "n": n,
            "max_overshoot_ratio": 0.0,
            "check_id": "range_magnitude_overshoot",
        }

    band_width = max(hi - lo, 1e-9)
    excess = np.maximum((s[out] - hi).clip(lower=0), (lo - s[out]).clip(lower=0))
    overshoot_ratio = float(excess.max() / band_width) if len(excess) else 0.0

    if overshoot_ratio >= critical_overshoot_ratio:
        return {
            "severity": "Critical",
            "reason": "extreme_magnitude_violation",
            "frac_out": frac,
            "n": n,
            "max_overshoot_ratio": overshoot_ratio,
            "check_id": "range_magnitude_overshoot",
        }
    if frac < suspicious_frac_out:
        severity, reason = "Suspicious", "rare_range_violations"
    elif frac < elevated_frac_out:
        severity, reason = "Suspicious", "elevated_range_violations"
    else:
        severity, reason = "Critical", "frequent_range_violations"
    return {
        "severity": severity,
        "reason": reason,
        "frac_out": frac,
        "n": n,
        "max_overshoot_ratio": overshoot_ratio,
        "check_id": "range_magnitude_overshoot",
    }


def run_range_magnitude_overshoot(
    observations: pd.DataFrame,
    plausibility_ranges: dict[str, tuple[float, float]],
    core_variables: list[str] | None = None,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit Stage-01-compatible issue rows for range / overshoot violations."""
    params = params or {}
    critical_overshoot_ratio = float(params.get("critical_overshoot_ratio", 2.0))
    suspicious_frac_out = float(params.get("suspicious_frac_out", 0.01))
    elevated_frac_out = float(params.get("elevated_frac_out", 0.05))
    core = list(core_variables or [])
    issues: list[dict[str, Any]] = []

    for col, (lo, hi) in plausibility_ranges.items():
        if col not in observations.columns:
            issues.append(
                {
                    "category": "missing_core_variable",
                    "variable": col,
                    "severity": "Critical" if col in core[:6] else "Suspicious",
                    "detail": "variable_absent",
                    "check_id": "range_magnitude_overshoot",
                }
            )
            continue
        verdict = classify_range(
            observations[col],
            lo,
            hi,
            critical_overshoot_ratio=critical_overshoot_ratio,
            suspicious_frac_out=suspicious_frac_out,
            elevated_frac_out=elevated_frac_out,
        )
        if verdict["severity"] != "Acceptable":
            issues.append(
                {
                    "category": "range_violation",
                    "variable": col,
                    "severity": verdict["severity"],
                    "detail": (
                        f"{verdict['reason']}; frac_out={verdict['frac_out']:.4f}; "
                        f"max_overshoot_ratio={verdict['max_overshoot_ratio']:.2f}; band=[{lo},{hi}]"
                    ),
                    "check_id": "range_magnitude_overshoot",
                }
            )
    return issues
