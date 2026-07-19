"""Multi-source evidence fusion + EBSVE/uncertainty context."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext
from cieml.ceam.models import InterpretationUnit, evidence_item


def fuse_evidence(
    ctx: CEAMContext,
    *,
    regimes: list[dict[str, Any]],
    hydro: list[dict[str, Any]],
    wq: list[dict[str, Any]],
    meteo: list[dict[str, Any]],
    spatial: list[dict[str, Any]],
    temporal: list[dict[str, Any]],
    ecological: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach cross-cutting fusion packets and optional EBSVE confidence."""
    ebsve = ctx.ebsve or {}
    hyps = ebsve.get("hypotheses") or ebsve.get("claims") or {}
    claim_summary = {
        hid: {"classification": b.get("classification"), "overall_confidence": b.get("overall_confidence")}
        for hid, b in hyps.items()
    }

    fusion_unit = InterpretationUnit(
        topic="multi_source_fusion",
        observation=(
            f"CEAM fused modules: regimes={len(regimes)}, hydro={len(hydro)}, wq={len(wq)}, "
            f"meteo={len(meteo)}, spatial={len(spatial)}, temporal={len(temporal)}, eco={len(ecological)}."
        ),
        interpretation=(
            "Campaign environmental interpretation rests on Discovery structure, Explainability drivers, "
            "Anomaly catalog, External meteo tests, Spatiotemporal products, and optional EBSVE claim classes."
        ),
        supporting_evidence=[
            evidence_item("stage_06", "regime labels", "n_regimes", len(regimes), "Discovery", "strong"),
            evidence_item("stage_08", "shap", "n_drivers", len((regimes[0].get("campaign_wide_shap_drivers") if regimes else []) or []), "XAI", "moderate"),
            evidence_item("stage_09", "anomaly_report", "n_consensus", (ctx.anomaly_report or {}).get("n_consensus_anomalies"), "Anomalies", "moderate"),
            evidence_item("stage_10", "external_report", "support_frac", (ctx.external_report or {}).get("anomaly_external_support_frac"), "Meteo", "moderate"),
            evidence_item("stage_11", "spatial_temporal", "n_transitions", (ctx.spatial_report or {}).get("n_regime_transitions"), "Spatiotemporal", "moderate"),
            evidence_item("stage_14", "ebsve", "campaign_closure", ebsve.get("campaign_closure"), "Evidence court (if Phase 8 already run)", "moderate" if hyps else "weak"),
        ],
        confidence="provisional",
        uncertainty=(
            "If EBSVE is absent (Phase 7 before Stage 14), claim-level confidence is not yet available; "
            "CEAM still reports module-level confidence."
        ),
        limitations=["Fusion does not average unlike confidence scores into one number."],
        level="interpretation",
    )

    # Count rejected units
    all_units = hydro + wq + meteo + spatial + temporal + ecological
    n_rejected = sum(1 for u in all_units if u.get("rejected"))

    ledger = ctx.uncertainty_ledger or {}
    unc_note = None
    if ledger:
        unc_note = ledger.get("summary") or {"present": True}

    return {
        "fusion_packet": fusion_unit.to_dict(),
        "ebsve_claim_summary": claim_summary,
        "ebsve_campaign_closure": ebsve.get("campaign_closure"),
        "ebsve_mean_confidence": ebsve.get("campaign_mean_confidence"),
        "uncertainty_ledger_summary": unc_note,
        "n_interpretation_units": len(all_units) + len(regimes),
        "n_rejected_unsupported": n_rejected,
        "qa_context": {
            "stage01_severity_counts": (ctx.qa_report or {}).get("severity_counts"),
            "stage03_support_rate": (ctx.physical_report or {}).get("support_rate_required"),
        },
    }
