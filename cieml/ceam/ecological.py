"""Ecological implications — observation vs interpretation vs hypothesis."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext, z_get
from cieml.ceam.models import InterpretationUnit, evidence_item


def interpret_ecological(ctx: CEAMContext, regimes: list[dict[str, Any]], meteo: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[InterpretationUnit] = []
    th = ctx.thresholds

    hypoxia_regs = [
        r
        for r in regimes
        if r.get("interpretive_family") == "hypoxic_regime"
        or "low-oxygen" in str(r.get("title", "")).lower()
        or z_get(r.get("z_fingerprint") or {}, ctx, "do") <= th.get("do_depressed_strong", -1.5)
    ]
    if hypoxia_regs:
        units.append(
            InterpretationUnit(
                topic="hypoxia_risk",
                observation=f"Regime(s) {[r['regime'] for r in hypoxia_regs]} show strongly depressed DO fingerprints and/or hypoxic family labels.",
                interpretation="Potential ecosystem stress via low-oxygen conditions is a plausible interpretation for harbour-associated states; absolute hypoxia endpoints are not certified.",
                supporting_evidence=[
                    evidence_item("stage_08", "z_fingerprints", "do_mg_l__mean", [r["regime"] for r in hypoxia_regs], "DO depression", "strong"),
                    evidence_item("stage_06", "labels", "interpretive_family", [r.get("interpretive_family") for r in hypoxia_regs], "Family labels", "moderate"),
                ],
                confidence="provisional",
                uncertainty="Campaign-relative z-scores ≠ regulatory hypoxia thresholds.",
                limitations=["Do not claim fish kills or biodiversity loss without biological surveys."],
                alternatives=["Transient oxygen dips without ecological impact."],
                level="hypothesis",
            )
        )
    else:
        units.append(
            InterpretationUnit(
                topic="hypoxia_risk",
                observation="No regime cleared strong DO-depression / hypoxic-family gates.",
                interpretation="Hypoxia-risk interpretation is not supported at the regime scale.",
                supporting_evidence=[],
                confidence="supported",
                uncertainty="Episodic low-DO anomalies may still exist in Stage 9.",
                limitations=[],
                level="observation",
            )
        )

    fresh = [r for r in regimes if "freshwater" in str(r.get("interpretive_family", ""))]
    if fresh:
        units.append(
            InterpretationUnit(
                topic="freshwater_stress",
                observation=f"Freshwater-influenced family assigned to regime(s) {[r['regime'] for r in fresh]}.",
                interpretation="Organisms adapted to marine salinity may experience freshwater stress during these states — hypothesis only.",
                supporting_evidence=[
                    evidence_item("ceam.regime", "interpretive_family", "freshwater_influenced_regime", [r["regime"] for r in fresh], "Family label", "moderate"),
                ],
                confidence="exploratory",
                uncertainty="No biological response data.",
                limitations=["Do not assert mortality or community shift."],
                level="hypothesis",
            )
        )

    turb = [r for r in regimes if "sediment" in str(r.get("interpretive_family", "")) or "turbid" in str(r.get("title", "")).lower()]
    if turb:
        units.append(
            InterpretationUnit(
                topic="sediment_disturbance",
                observation=f"Turbid/sediment-associated regimes: {[r['regime'] for r in turb]}.",
                interpretation="Elevated suspended material may reduce light and disturb benthic habitats — interpretive, not measured.",
                supporting_evidence=[
                    evidence_item("stage_08", "turbidity z", "turbidity_fnu__mean", [r["regime"] for r in turb], "Turbidity fingerprints", "moderate"),
                ],
                confidence="exploratory",
                uncertainty="Optical turbidity ≠ mass flux of sediment transport.",
                limitations=["No light-attenuation or benthic samples."],
                level="hypothesis",
            )
        )

    # Anthropogenic — only if evidence; typically reject
    units.append(
        InterpretationUnit(
            topic="anthropogenic_influence",
            observation="No independent tracer or discharge inventory is present in upstream CIEML artifacts.",
            interpretation="Anthropogenic source attribution is not scientifically supported by CEAM inputs.",
            supporting_evidence=[
                evidence_item("framework", "scope", None, "no tracers", "CEAM constraint", "strong"),
            ],
            confidence="supported",
            uncertainty="N/A",
            limitations=["Harbour-role low oxygen is consistent with multiple natural and human mechanisms."],
            level="observation",
            rejected=True,
            reject_reason="Unsupported without tracers / inventories.",
        )
    )

    # Link meteo support if rainfall unit supported
    rain_ok = any(u.get("topic") == "rainfall_influence" and not u.get("rejected") and "associated" in str(u.get("interpretation", "")).lower() for u in meteo)
    if rain_ok:
        units.append(
            InterpretationUnit(
                topic="runoff_linked_events",
                observation="Stage 10 supports precip–anomaly association.",
                interpretation="Some episodic water-quality excursions are consistent with wet-weather forcing (associative).",
                supporting_evidence=[evidence_item("stage_10", "event_tests", "precip", True, "Meteo consistency", "moderate")],
                confidence="provisional",
                uncertainty="Mechanism remains unclear for many enrichment tags.",
                limitations=["Not proof of river discharge volume."],
                level="interpretation",
            )
        )

    return [u.to_dict() for u in units]
