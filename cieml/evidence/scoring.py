"""Configurable classification thresholds and shared scoring helpers.

Every cutoff used anywhere in the evidence engine lives here as a named constant,
never as a magic number buried inside a validator, so a reviewer auditing the
framework can find and question every threshold in one place.
"""
from __future__ import annotations

import numpy as np

# --- Claim classification thresholds (pillars are scored continuously, 0-100) ---
DEFINITIVE_MIN_ALL_PILLARS = 90.0
PROVISIONAL_MIN_PILLAR = 70.0
# Below PROVISIONAL_MIN_PILLAR on the weakest pillar -> EXPLORATORY.

# --- Evidence-strength / maturity labels (informational, not gating) ---
STRENGTH_BANDS = [(90.0, "strong"), (70.0, "moderate"), (50.0, "weak"), (0.0, "insufficient")]
MATURITY_BANDS = [(90.0, "publication_ready"), (70.0, "provisional_finding"), (0.0, "exploratory_finding")]


def classify(pillar_scores: dict[str, float]) -> str:
    """DEFINITIVE requires every pillar >= DEFINITIVE_MIN_ALL_PILLARS; PROVISIONAL
    requires the weakest pillar to at least clear PROVISIONAL_MIN_PILLAR; otherwise
    EXPLORATORY. A single very weak pillar cannot be averaged away by strong ones —
    the classification is gated on the *minimum*, not the mean, so one missing line
    of evidence cannot be hidden behind three strong ones."""
    vals = list(pillar_scores.values())
    if not vals:
        return "EXPLORATORY"
    weakest = min(vals)
    if weakest >= DEFINITIVE_MIN_ALL_PILLARS:
        return "DEFINITIVE"
    if weakest >= PROVISIONAL_MIN_PILLAR:
        return "PROVISIONAL"
    return "EXPLORATORY"


def _band_label(value: float, bands: list[tuple[float, str]]) -> str:
    for thr, label in bands:
        if value >= thr:
            return label
    return bands[-1][1]


def evidence_strength_label(mean_score: float) -> str:
    return _band_label(mean_score, STRENGTH_BANDS)


def maturity_label(mean_score: float, min_score: float) -> str:
    # Maturity also respects the weakest pillar, for the same reason classify() does.
    return _band_label(min(mean_score, min_score + 10.0), MATURITY_BANDS)


def score_from_fraction(frac: float, good: float = 1.0, bad: float = 0.0) -> float:
    """Linear map onto [0, 100]: `frac` at or beyond `good` -> 100, at or beyond
    `bad` (on the other side of good) -> 0, clipped in between. Handles both
    increasing (good > bad) and decreasing (good < bad) metrics."""
    if frac is None or not np.isfinite(frac):
        return 0.0
    if good == bad:
        return 100.0 if frac >= good else 0.0
    t = (frac - bad) / (good - bad)
    return float(np.clip(t, 0.0, 1.0) * 100.0)


def score_from_bands(value: float, bands: list[tuple[float, float]]) -> float:
    """`bands`: list of (threshold, score) pairs sorted by threshold descending.
    Returns the score of the first band whose threshold `value` meets or exceeds,
    or 0.0 if value is below every threshold."""
    if value is None or not np.isfinite(value):
        return 0.0
    for thr, sc in bands:
        if value >= thr:
            return float(sc)
    return 0.0


def weighted_mean(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    if not scores:
        return 0.0
    if weights is None:
        return float(np.mean(list(scores.values())))
    total_w = sum(weights.get(k, 1.0) for k in scores)
    if total_w <= 0:
        return float(np.mean(list(scores.values())))
    return float(sum(scores[k] * weights.get(k, 1.0) for k in scores) / total_w)
