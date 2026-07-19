"""Orchestrates claim-pack validators into one campaign-level audit.

Phase J: the validator list comes from the active claim pack (default
`coastal_monitoring_v1`), not a hardcoded H1–H6 import list. Pillar algebra is
unchanged — still `HypothesisValidator.run()`.
"""
from __future__ import annotations

from typing import Any

from cieml.claims import load_claim_pack, validators_for_pack
from cieml.evidence.base import HypothesisAssessment
from cieml.failure import build_failure_report


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    try:
        return len(value) == 0
    except TypeError:
        return False


def run_evidence_engine(
    evidence: dict[str, Any],
    register: dict[str, Any] | None = None,
    *,
    claim_pack: str | None = None,
) -> dict[str, Any]:
    register = register or {}
    pack_id = (
        claim_pack
        or register.get("claim_pack_id")
        or register.get("pack_id")
        or None
    )

    # SC-FMF: EBSVE failure assessment. An empty or unresolvable claim pack is
    # FATAL and must be reported structurally, not crash the caller —
    # load_claim_pack raises ValueError for an empty claims list and
    # FileNotFoundError for a pack_id that doesn't resolve to any file; both
    # leave EBSVE with zero claims to score, so both convert into one proper
    # failure report + abort_engine recovery instead of an unhandled exception.
    try:
        pack = load_claim_pack(pack_id)
        n_claims = len(pack.claims)
    except (ValueError, FileNotFoundError):
        pack = None
        n_claims = 0

    missing_evidence_keys = [k for k, v in evidence.items() if not str(k).startswith("_") and _is_empty(v)]
    failure_report = build_failure_report(
        "ebsve", {"n_claims": n_claims, "missing_evidence_keys": missing_evidence_keys}
    )

    if pack is None:
        return {
            "rule": "Claim pack is empty or failed to load; EBSVE cannot score any claim.",
            "claim_pack_id": pack_id or "unknown",
            "claim_pack_version": None,
            "hypotheses": {},
            "claims": {},
            "campaign_closure": "ABORTED",
            "campaign_mean_confidence": 0.0,
            "weakest_evidence": {"claim": None, "hypothesis": None, "pillar": None, "score": None},
            "failure_report": failure_report,
            "_assessments": {},
        }

    plugin_pairs = validators_for_pack(pack)

    assessments: dict[str, HypothesisAssessment] = {}
    for claim_id, validator_cls in plugin_pairs:
        validator = validator_cls(evidence, register)
        # Prefer pack claim_id if plugin forgot to set hypothesis_id
        if not getattr(validator, "hypothesis_id", None):
            validator.hypothesis_id = claim_id  # type: ignore[attr-defined]
        assessments[validator.hypothesis_id] = validator.run()

    closures = [a.classification for a in assessments.values()]
    if all(c == "DEFINITIVE" for c in closures):
        campaign_closure = "DEFINITIVE"
    elif any(c in ("PROVISIONAL", "DEFINITIVE") for c in closures):
        campaign_closure = "MIXED_PROVISIONAL"
    else:
        campaign_closure = "EXPLORATORY"

    mean_confidence = (
        float(sum(a.overall_confidence for a in assessments.values()) / len(assessments))
        if assessments
        else 0.0
    )

    # Identify exactly where the campaign's weakest evidence sits, across every
    # claim and pillar — this is what a reviewer asking "why should I trust
    # this claim" should be pointed at first.
    weakest_hid, weakest_pillar_name, weakest_score = None, None, 101.0
    for hid, a in assessments.items():
        for pname, pillar in a.pillars.items():
            if pillar.score < weakest_score:
                weakest_hid, weakest_pillar_name, weakest_score = hid, pname, pillar.score

    hyp_dicts = {hid: a.to_dict() for hid, a in assessments.items()}
    return {
        "rule": (
            f"DEFINITIVE requires every pillar >= {90:.0f}/100 for a claim; "
            f"PROVISIONAL requires the weakest pillar >= {70:.0f}/100; otherwise EXPLORATORY. "
            "Campaign closure is DEFINITIVE only if all claims are DEFINITIVE, "
            "MIXED_PROVISIONAL if any claim reaches PROVISIONAL or better, else EXPLORATORY."
        ),
        "claim_pack_id": pack.pack_id,
        "claim_pack_version": pack.version,
        # Artifact-stable key (Stage 14 / uncertainty / reporting)
        "hypotheses": hyp_dicts,
        # Phase J public alias
        "claims": hyp_dicts,
        "campaign_closure": campaign_closure,
        "campaign_mean_confidence": round(mean_confidence, 1),
        "weakest_evidence": {
            "claim": weakest_hid,
            "hypothesis": weakest_hid,  # legacy alias
            "pillar": weakest_pillar_name,
            "score": round(weakest_score, 1) if weakest_hid else None,
        },
        "failure_report": failure_report,
        "_assessments": assessments,
        # Not JSON-serializable; callers must pop before writing artifacts.
        "_claim_pack": pack,
    }
