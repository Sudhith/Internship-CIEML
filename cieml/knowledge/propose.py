"""Propose KB entries from a finished campaign — does not mutate domain profiles."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from cieml.knowledge.store import KnowledgeStore, load_store


def propose_from_campaign(
    *,
    campaign_id: str,
    domain: str,
    pillars: dict[str, Any] | None = None,
    applicability: dict[str, Any] | None = None,
    physical_report: dict[str, Any] | None = None,
    anomaly_report: dict[str, Any] | None = None,
    framework_version: str | None = None,
    store: KnowledgeStore | None = None,
    output_summary_path: Path | None = None,
) -> dict[str, Any]:
    """Create candidate KB entries + optional domain-update proposal (pending review)."""
    store = store or load_store()
    pillars = pillars or {}
    hyps = pillars.get("hypotheses") or pillars.get("claims") or {}
    applicability = applicability or {}
    written = []

    # Entry: campaign claim closure snapshot
    claim_summary = {
        hid: {
            "classification": b.get("classification"),
            "overall_confidence": b.get("overall_confidence"),
        }
        for hid, b in hyps.items()
    }
    entry = {
        "entry_id": f"claims_{campaign_id}",
        "kind": "claim_closure_snapshot",
        "grade": "candidate",
        "campaign_id": campaign_id,
        "domain": domain,
        "framework_version": framework_version,
        "payload": {
            "campaign_closure": pillars.get("campaign_closure"),
            "claims": claim_summary,
        },
        "provenance": {
            "campaign_id": campaign_id,
            "artifacts": [
                "outputs/phase8/stage14_four_pillar_closure.json",
                "outputs/phase7/stage13_applicability_domain.json",
            ],
        },
    }
    written.append(str(store.write_entry(entry)))

    # Entry: applicability transfer rule memory
    if applicability:
        app_entry = {
            "entry_id": f"applicability_{campaign_id}",
            "kind": "applicability_summary",
            "grade": "candidate",
            "campaign_id": campaign_id,
            "domain": domain,
            "payload": {
                "applies_to": applicability.get("applies_to"),
                "does_not_apply_to": applicability.get("does_not_apply_to"),
                "transfer_rule": applicability.get("transfer_rule"),
                "n_claim_records": len(applicability.get("claims") or {}),
            },
            "provenance": {
                "campaign_id": campaign_id,
                "artifacts": ["stage13_applicability_domain.json"],
            },
        }
        written.append(str(store.write_entry(app_entry)))

    # Entry: physical support rate (if present)
    if physical_report:
        phys_entry = {
            "entry_id": f"physical_support_{campaign_id}",
            "kind": "physical_relationship_support",
            "grade": "candidate",
            "campaign_id": campaign_id,
            "domain": domain,
            "payload": {
                "support_rate_required": physical_report.get("support_rate_required"),
                "n_required_broken": physical_report.get("n_required_broken"),
            },
            "provenance": {
                "campaign_id": campaign_id,
                "artifacts": ["stage03_physical_report.json"],
            },
        }
        written.append(str(store.write_entry(phys_entry)))

    # Domain proposal — suggested note only, never applied
    proposal = {
        "proposal_id": f"domain_note_{domain}_{campaign_id}",
        "target_domain": domain,
        "action": "append_applicability_note",
        "suggested_note": (
            f"Campaign {campaign_id} contributed candidate claim/applicability memory; "
            "curator may promote supported patterns after multi-campaign review."
        ),
        "requires_human_review": True,
        "auto_applied": False,
        "provenance": {"campaign_id": campaign_id, "kb_entries": written},
    }
    prop_path = str(store.write_domain_proposal(proposal))

    summary = {
        "contract_id": "SC-KB",
        "campaign_id": campaign_id,
        "domain": domain,
        "entries_written": written,
        "domain_proposal": prop_path,
        "domain_profile_mutated": False,
        "note": "Append-only KB write; configs/domains/ unchanged.",
    }
    if output_summary_path is not None:
        import json

        Path(output_summary_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
