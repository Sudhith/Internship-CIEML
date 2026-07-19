"""Assemble FailureAssessment packets and campaign dossiers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cieml.failure.catalog import load_failure_catalog
from cieml.failure.detect import detect_hits
from cieml.failure.models import FailureModeHit, STATUS_FOR_SEVERITY, Severity


@dataclass
class FailureAssessment:
    engine_id: str
    status: str
    hits: list[FailureModeHit] = field(default_factory=list)
    confidence_multiplier: float = 1.0
    suppress_downstream: bool = False
    user_messages: list[dict[str, Any]] = field(default_factory=list)
    reviewer_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "status": self.status,
            "hits": [h.to_dict() for h in self.hits],
            "confidence_multiplier": self.confidence_multiplier,
            "suppress_downstream": self.suppress_downstream,
            "user_messages": self.user_messages,
            "reviewer_notes": self.reviewer_notes,
        }


def _multiplier(policy: dict[str, Any], hits: list[FailureModeHit]) -> float:
    table = policy.get("confidence_multipliers") or {}
    if not hits:
        return 1.0
    vals = [float(table.get(h.severity.value, 1.0)) for h in hits]
    compose = str(policy.get("compose") or "min").lower()
    if compose == "multiply":
        m = 1.0
        for v in vals:
            m *= v
        return float(max(0.0, min(1.0, m)))
    return float(min(vals))


def _build_assessment(engine_id: str, hits: list[FailureModeHit], policy: dict[str, Any]) -> FailureAssessment:
    if not hits:
        return FailureAssessment(engine_id=engine_id, status="ok")

    worst = max(hits, key=lambda h: h.severity.rank)
    status = STATUS_FOR_SEVERITY[worst.severity]
    mult = _multiplier(policy, hits)
    suppress_at = str(policy.get("suppress_recommendations_at") or "CRITICAL")
    suppress = any(h.severity.rank >= Severity[suppress_at].rank for h in hits)

    messages = []
    for h in hits:
        if h.severity.rank >= Severity.WARNING.rank:
            messages.append(
                {
                    "message_id": f"{h.mode_id}.v1",
                    "severity": h.severity.value,
                    "title": h.title,
                    "body": h.message,
                    "evidence": h.evidence,
                    "what_we_did": ", ".join(h.recovery_applied) or "recorded",
                }
            )

    notes = [f"{h.severity.value}: {h.mode_id} — {h.title}" for h in hits]
    return FailureAssessment(
        engine_id=engine_id,
        status=status,
        hits=hits,
        confidence_multiplier=mult,
        suppress_downstream=suppress and engine_id == "decision_support",
        user_messages=messages,
        reviewer_notes=notes,
    )


def assess_engine(engine_id: str, bundle: dict[str, Any] | None = None) -> FailureAssessment:
    catalog = load_failure_catalog()
    bundle = dict(bundle or {})
    all_hits = detect_hits(catalog, bundle)
    hits = [h for h in all_hits if h.engine_id == engine_id]
    return _build_assessment(engine_id, hits, catalog.policy)


def assess_campaign(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run detectors once; split assessments by engine."""
    catalog = load_failure_catalog()
    bundle = dict(bundle or {})
    hits = detect_hits(catalog, bundle)
    by_engine: dict[str, list[FailureModeHit]] = {}
    for h in hits:
        by_engine.setdefault(h.engine_id, []).append(h)

    assessments = {
        engine_id: _build_assessment(engine_id, by_engine.get(engine_id, []), catalog.policy).to_dict()
        for engine_id in sorted(set(m.engine_id for m in catalog.modes))
    }

    critical_plus = [h.to_dict() for h in hits if h.severity.rank >= Severity.CRITICAL.rank]
    return {
        "catalog_version": catalog.version,
        "n_hits": len(hits),
        "n_critical_plus": len(critical_plus),
        "assessments": assessments,
        "critical_plus": critical_plus,
        "suppress_recommendations": any(
            a.get("suppress_downstream") for a in assessments.values()
        ),
    }
