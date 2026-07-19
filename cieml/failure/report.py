"""The one shared Failure Report Object builder (SC-FMF).

Every analytical engine (Discovery, Explainability, Anomaly Intelligence,
EBSVE, Framework Validation, Decision Support) calls `build_failure_report`
identically. No engine-specific failure-handling logic exists anywhere else —
only the `bundle` dict each call site assembles from its own live metrics
differs; the evaluation, severity composition, and report shape are shared.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cieml.failure.assess import assess_engine
from cieml.failure.catalog import load_failure_catalog
from cieml.failure.models import FailureModeHit


def _uncertainty_contribution(policy: dict[str, Any], hits: list[FailureModeHit]) -> float:
    """Independent severity -> raw uncertainty magnitude, composed by MAX
    (not min, and not derived from confidence_multiplier at all). Confidence
    composes by `min` because one bad pillar should not be diluted by good
    ones; uncertainty composes by `max` because an additional failure mode
    must never REDUCE reported doubt. The asymmetry is deliberate: these are
    two independent axes (SC-FMF Sec 6), not mirror images of one number.
    """
    table = policy.get("uncertainty_contributions") or {}
    if not hits:
        return 0.0
    vals = [float(table.get(h.severity.value, 0.0)) for h in hits]
    return float(max(vals))


def build_failure_report(engine_id: str, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run -> evaluate failure modes -> assign severity -> adjust confidence ->
    adjust uncertainty -> generate warnings -> generate recovery suggestions ->
    return a structured report for the caller to attach to its own output and
    pass downstream. Deterministic given a fixed `bundle` (SC-FMF Sec 5).
    """
    catalog = load_failure_catalog()
    assessment = assess_engine(engine_id, bundle)
    uncertainty_adj = _uncertainty_contribution(catalog.policy, assessment.hits)

    scientific_impact: list[str] = []
    for h in assessment.hits:
        if h.pillar_impact:
            scientific_impact.append(f"{h.pillar_impact} pillar affected by {h.mode_id} ({h.severity.value})")
        else:
            scientific_impact.append(f"{h.mode_id} ({h.severity.value}): {h.title}")

    recovery = sorted({r for h in assessment.hits for r in h.recovery_applied})
    worst_severity = max((h.severity for h in assessment.hits), key=lambda s: s.rank) if assessment.hits else None

    return {
        "engine": engine_id,
        "failure_modes_triggered": [h.mode_id for h in assessment.hits],
        "severity": worst_severity.value if worst_severity else "NONE",
        "confidence_adjustment": {
            "multiplier": assessment.confidence_multiplier,
            "rule": "min(confidence_multipliers[severity] for each triggered hit); 1.0 if no hits",
        },
        "uncertainty_adjustment": {
            "raw_contribution": uncertainty_adj,
            "rule": "max(uncertainty_contributions[severity] for each triggered hit); 0.0 if no hits — "
            "independent table from confidence_multipliers, never 100 - confidence",
        },
        "scientific_impact": scientific_impact,
        "recovery_suggestions": recovery,
        "blocking_status": assessment.status in {"failed", "aborted"},
        "status": assessment.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hits": [h.to_dict() for h in assessment.hits],
        "user_messages": assessment.user_messages,
        "catalog_version": catalog.version,
    }
