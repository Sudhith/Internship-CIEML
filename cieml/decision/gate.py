"""Gate actionable recommendations using SC-FMF / evidence strength."""
from __future__ import annotations

from typing import Any

from cieml.failure import assess_engine


def gate_recommendations(
    claim_classifications: dict[str, str] | None = None,
    campaign_mean_confidence: float | None = None,
    *,
    applicability_domain: dict[str, Any] | None = None,
    force_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return suppress flag + failure assessment for Decision Support.

    When claim evidence is weak (FMF `dss_low_evidence`), actionable
    recommendations must be suppressed; a diagnostic brief may still be emitted.
    """
    bundle = dict(force_bundle or {})
    if claim_classifications is not None:
        bundle["claim_classifications"] = dict(claim_classifications)
    if campaign_mean_confidence is not None:
        bundle["campaign_mean_confidence"] = float(campaign_mean_confidence)
    if applicability_domain is not None:
        bundle["applicability_domain"] = dict(applicability_domain)

    assessment = assess_engine("decision_support", bundle)
    return {
        "suppress_recommendations": bool(assessment.suppress_downstream) or assessment.status in {"failed", "aborted"},
        "status": assessment.status,
        "confidence_multiplier": assessment.confidence_multiplier,
        "failure_assessment": assessment.to_dict(),
        "reason": (
            "Insufficient evidence for actionable recommendations (SC-FMF / SC-DSS)."
            if assessment.suppress_downstream or assessment.status in {"failed", "aborted"}
            else "Evidence sufficient for provisional recommendations."
        ),
    }
