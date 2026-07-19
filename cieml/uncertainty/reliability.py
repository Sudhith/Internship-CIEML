"""Evidence Reliability Engine (SC-REL) -- Sec 7 of the v2 uncertainty redesign.

Scores the COMPLETENESS / REPRESENTATIVENESS of the evidence base behind a claim
-- NOT measurement noise (that axis is cieml.uncertainty.propagate). Bounded by
construction: a weighted mean of already-[0,1]-bounded coverage fractions needs
no saturating map, unlike the Measurement & Model Uncertainty axis, which is why
this module has no dependency on propagate.py.

Polarity: higher = MORE reliable/complete, matching Confidence's "higher is
better" convention -- the OPPOSITE polarity from Measurement & Model
Uncertainty ("higher is worse"). Documented explicitly because the asymmetry is
easy to get backwards when wiring a new consumer; where a uniform "higher is
worse" dashboard convention is wanted, compute `Evidence Gap = 100 - R`
alongside R rather than flipping R's own definition.

R is computed once per relevant object directly from campaign/domain design
metadata (station count, season count, method count, external source count) --
it does NOT propagate stage-to-stage like Measurement & Model Uncertainty does,
because it is a property of the campaign's design, not of noise accumulating
through processing. See design doc Sec 7 for the IPCC-guidance precedent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Domain-declared targets should live in configs/domains/<domain>.yaml under
# `evidence_reliability`; these are the fallback defaults when a domain profile
# doesn't declare them (e.g. stub domains), not scientific truth.
DEFAULT_TARGETS = {
    "spatial_stations": 8,
    "temporal_seasons": 4,
    "methodological_methods": 3,
    "external_sources": 2,
}
DEFAULT_WEIGHTS = {"spatial": 1.0, "temporal": 1.0, "methodological": 1.0, "external": 1.0}


@dataclass
class ReliabilityDimension:
    name: str
    coverage: float  # already saturated to [0, 1] by the caller (min(1, observed/target))
    weight: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "coverage": round(float(max(0.0, min(1.0, self.coverage))), 3),
            "weight": float(self.weight),
            "detail": self.detail,
        }


def score_evidence_reliability(dimensions: list[ReliabilityDimension]) -> dict[str, Any]:
    """R = 100 * weighted mean of [0,1] coverage fractions. Bounded by
    construction (a weighted mean of bounded quantities cannot exceed its
    bounds) -- no saturating map needed here, unlike the M axis."""
    if not dimensions:
        return {"score": None, "dimensions": [], "rule": "no dimensions supplied"}
    total_w = sum(d.weight for d in dimensions) or 1.0
    score = 100.0 * sum(d.coverage * d.weight for d in dimensions) / total_w
    return {
        "score": round(float(max(0.0, min(100.0, score))), 2),
        "dimensions": [d.to_dict() for d in dimensions],
        "rule": "weighted mean of declared [0,1] coverage fractions; bounded by construction (no saturation needed)",
    }


def _coverage(observed: float, target: float) -> float:
    if target <= 0:
        return 1.0
    return float(min(1.0, max(0.0, observed) / target))


def build_reliability_dimensions(
    *,
    n_stations: int,
    n_seasons: int,
    n_methods: int,
    n_external_sources: int,
    targets: dict[str, int] | None = None,
    weights: dict[str, float] | None = None,
) -> list[ReliabilityDimension]:
    t = {**DEFAULT_TARGETS, **(targets or {})}
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    return [
        ReliabilityDimension(
            "spatial_coverage",
            _coverage(n_stations, t["spatial_stations"]),
            w["spatial"],
            f"{n_stations}/{t['spatial_stations']} stations vs. domain-declared target",
        ),
        ReliabilityDimension(
            "temporal_coverage",
            _coverage(n_seasons, t["temporal_seasons"]),
            w["temporal"],
            f"{n_seasons}/{t['temporal_seasons']} seasons observed vs. annual-cycle target",
        ),
        ReliabilityDimension(
            "methodological_diversity",
            _coverage(n_methods, t["methodological_methods"]),
            w["methodological"],
            f"{n_methods}/{t['methodological_methods']} independent explanation/validation methods used",
        ),
        ReliabilityDimension(
            "external_source_diversity",
            _coverage(n_external_sources, t["external_sources"]),
            w["external"],
            f"{n_external_sources}/{t['external_sources']} independent external corroboration sources",
        ),
    ]
