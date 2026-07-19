"""Where claims and recommendations may be trusted — and where they must not."""
from __future__ import annotations

from typing import Any


DEFAULT_TRANSFER_RULE = (
    "Re-run CIEML Stages 4–9 (features through anomalies) on the new campaign; "
    "reuse framework logic and domain profile, not site-specific numeric cutoffs or regime names."
)


def build_applicability_domain(
    *,
    domain_name: str | None = None,
    domain_notes: list[str] | None = None,
    campaign_id: str | None = None,
    n_stations: int | None = None,
    core_variables: list[str] | None = None,
    recommendation_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Campaign-level applicability packet (backward-compatible keys + Phase K extensions)."""
    domain_name = domain_name or "coastal"
    notes = list(domain_notes or [])
    cores = list(core_variables or [])

    applies_to = [
        f"Multiparameter sonde campaigns in the '{domain_name}' domain profile with role-diverse stations "
        "(harbour/embayment + open-coast when relevant).",
        "Decision support for monitoring *design* — not real-time regulatory compliance enforcement.",
    ]
    if notes:
        applies_to.extend(notes)
    if n_stations is not None:
        applies_to.append(f"Campaign designs with comparable station count scale (this campaign n_stations={n_stations}).")

    does_not = [
        "Universal numeric thresholds transplanted to other sites without re-running CIEML stages.",
        "Causal attribution of pollution sources without independent tracers and Stage 10+ evidence.",
        "Satellite-only or tide-gauge-only networks without in situ sondes.",
        "Unobserved habitats / seasons / forcing regimes (unknown transfer ≠ safe transfer).",
    ]
    if cores:
        missing_msg = "Sites lacking the domain core variable set required for physical/QA engines."
        does_not.insert(1, missing_msg)

    # Coverage gaps — conditions never claimed as observed unless caller tags them
    coverage_gaps = [
        "Seasons / years not sampled in this campaign",
        "Habitats not represented by station roles in this campaign",
        "External forcings not covered by Stage 10 providers",
    ]

    packet = {
        "contract_id": "SC-APP",
        "phase": "K",
        "domain": domain_name,
        "campaign_id": campaign_id,
        # Legacy keys (Stage 13 / H6 validator)
        "applies_to": applies_to,
        "does_not_apply_to": does_not,
        "transfer_rule": DEFAULT_TRANSFER_RULE,
        "coverage_gaps": coverage_gaps,
        "transfer_confidence_note": (
            "Transfer confidence is stricter than in-campaign claim confidence; "
            "absence of a listed exclusion does not imply permission."
        ),
        "claims": {},  # filled by enrich_with_claims
        "recommendations": {},
    }

    for rid in recommendation_ids or []:
        packet["recommendations"][rid] = {
            "recommendation_id": rid,
            "applies_to": list(applies_to[:2]),
            "does_not_apply_to": list(does_not[:2]),
            "transfer_rule": DEFAULT_TRANSFER_RULE,
            "transfer_confidence": "low_until_reanalysis",
        }
    return packet


def enrich_with_claims(
    applicability: dict[str, Any],
    claim_assessments: dict[str, Any],
) -> dict[str, Any]:
    """Attach per-claim applicability from EBSVE assessment dicts.

    `claim_assessments` is typically pillars['hypotheses'] or pillars['claims'].
    """
    out = dict(applicability)
    claims_block: dict[str, Any] = {}
    for claim_id, block in (claim_assessments or {}).items():
        classification = block.get("classification") or "EXPLORATORY"
        conf = block.get("overall_confidence")
        # Stricter transfer: EXPLORATORY → do not transfer conclusions
        if classification == "DEFINITIVE":
            transfer_confidence = "moderate_within_domain"
            extra_excludes = ["Other aquatic domains without a matching domain profile re-run"]
        elif classification == "PROVISIONAL":
            transfer_confidence = "low_provisional"
            extra_excludes = ["Any site without re-running discovery/XAI/anomaly stages"]
        else:
            transfer_confidence = "do_not_transfer"
            extra_excludes = [
                "Do not transfer this claim's conclusions; evidence class is EXPLORATORY.",
            ]
        claims_block[claim_id] = {
            "claim_id": claim_id,
            "in_campaign_classification": classification,
            "in_campaign_confidence": conf,
            "applies_to": list(out.get("applies_to") or [])[:3],
            "does_not_apply_to": list(out.get("does_not_apply_to") or []) + extra_excludes,
            "transfer_rule": out.get("transfer_rule") or DEFAULT_TRANSFER_RULE,
            "transfer_confidence": transfer_confidence,
        }
    out["claims"] = claims_block
    out["n_claims"] = len(claims_block)
    return out
