"""Hydrodynamic interpretation from fingerprints + spatial context (no invented processes)."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext, z_get
from cieml.ceam.models import InterpretationUnit, evidence_item


def interpret_hydrodynamics(ctx: CEAMContext, regimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[InterpretationUnit] = []
    th = ctx.thresholds

    fresh_regs = [
        r
        for r in regimes
        if r.get("z_fingerprint") and z_get(r["z_fingerprint"], ctx, "salinity") <= th.get("salinity_fresh_mod", -0.5)
    ]
    marine_regs = [
        r
        for r in regimes
        if r.get("z_fingerprint") and z_get(r["z_fingerprint"], ctx, "salinity") >= th.get("salinity_marine_strong", 0.8)
    ]
    turb_regs = [
        r
        for r in regimes
        if r.get("z_fingerprint") and z_get(r["z_fingerprint"], ctx, "turbidity") >= th.get("turbidity_elevated_mod", 0.5)
    ]

    if fresh_regs:
        units.append(
            InterpretationUnit(
                topic="freshwater_influence",
                observation=f"{len(fresh_regs)} regime(s) show campaign-relative salinity depression.",
                interpretation="Freshwater-influenced coastal water masses are present in the discovered structure.",
                supporting_evidence=[
                    evidence_item(
                        "stage_06/08",
                        "regime fingerprints",
                        "salinity_psu__mean",
                        [r["regime"] for r in fresh_regs],
                        "Low-salinity endmember regimes",
                        "strong",
                    ),
                ],
                confidence="provisional",
                uncertainty="Salinity depression is relative to this campaign mean, not an absolute estuary classification.",
                limitations=["Does not identify a specific river source without tracers."],
                alternatives=["Sensor bias or local evaporation contrasts (less likely if physical pairs supported)."],
                level="interpretation",
            )
        )
    else:
        units.append(
            InterpretationUnit(
                topic="freshwater_influence",
                observation="No regime cleared the domain salinity-depression gate.",
                interpretation="Insufficient fingerprint evidence for a freshwater-influenced endmember in this campaign.",
                supporting_evidence=[
                    evidence_item("stage_08", "z_fingerprints", "salinity", None, "No regime below salinity_fresh_mod", "moderate")
                ],
                confidence="supported",
                uncertainty="Absence of a low-S regime does not prove absence of episodic freshwater events.",
                limitations=["Event-scale freshening may appear only in Stage 9/10 anomalies."],
                level="observation",
            )
        )

    if marine_regs:
        units.append(
            InterpretationUnit(
                topic="marine_influence",
                observation=f"{len(marine_regs)} regime(s) show elevated salinity relative to the campaign.",
                interpretation="A higher-salinity / marine-influenced endmember is consistent with the fingerprints.",
                supporting_evidence=[
                    evidence_item(
                        "stage_08",
                        "z_fingerprints",
                        "salinity",
                        [r["regime"] for r in marine_regs],
                        "High-S regimes",
                        "moderate",
                    )
                ],
                confidence="provisional",
                uncertainty="Relative z-scores; absolute oceanic endmember not proven.",
                limitations=["No tide gauge or current meter inputs in this CEAM pass."],
                level="interpretation",
            )
        )
    else:
        units.append(
            InterpretationUnit(
                topic="marine_influence",
                observation="No regime exceeded the domain marine-salinity gate.",
                interpretation="Marine endmember labeling is not supported at the regime scale for this campaign.",
                supporting_evidence=[],
                confidence="provisional",
                uncertainty="Open-coast stations may still be marine-influenced without a high-S cluster.",
                limitations=["Stratification and tidal mixing cannot be assessed from sonde means alone."],
                level="observation",
            )
        )

    mix = [r for r in fresh_regs if r in turb_regs]
    if mix:
        units.append(
            InterpretationUnit(
                topic="mixing_zones",
                observation=f"Regime(s) {[r['regime'] for r in mix]} co-express low salinity and elevated turbidity.",
                interpretation="Consistent with mixing / runoff-influenced turbid water rather than a pure marine endmember.",
                supporting_evidence=[
                    evidence_item(
                        "stage_08",
                        "z_fingerprints",
                        "salinity+turbidity",
                        [r["regime"] for r in mix],
                        "Joint fingerprint",
                        "moderate",
                    )
                ],
                confidence="provisional",
                uncertainty="Mixing zone geometry is not mapped spatially beyond station membership.",
                limitations=["No direct mixing fraction or residence-time estimate."],
                alternatives=["Sediment resuspension with unrelated salinity variability."],
                level="interpretation",
            )
        )
    else:
        units.append(
            InterpretationUnit(
                topic="mixing_zones",
                observation="No regime jointly cleared freshwater and elevated-turbidity gates.",
                interpretation="A distinct mixing-zone regime label is not supported by fingerprint co-occurrence.",
                supporting_evidence=[],
                confidence="provisional",
                uncertainty="Mixing may still occur transiently (see temporal/anomaly modules).",
                limitations=["Estuarine circulation patterns not observable from this sensor pack alone."],
                level="observation",
            )
        )

    units.append(
        InterpretationUnit(
            topic="stratification_and_tides",
            observation="Campaign inputs are station-day multiparameter means without vertical profiles or tidal harmonics.",
            interpretation="Stratification and tidal influence cannot be assessed from available Stage 6/8/11 products.",
            supporting_evidence=[
                evidence_item(
                    "framework",
                    "sampling_design",
                    None,
                    "station-day aggregates",
                    "No depth profiles / tide series in CEAM inputs",
                    "strong",
                )
            ],
            confidence="supported",
            uncertainty="N/A — capability out of scope for current artifacts.",
            limitations=["Do not infer stratification or tidal pumping."],
            level="observation",
            rejected=True,
            reject_reason="No supporting vertical or tidal evidence in upstream artifacts.",
        )
    )

    phys = ctx.physical_report or {}
    if phys:
        units.append(
            InterpretationUnit(
                topic="physical_consistency_context",
                observation=(
                    f"Stage 3 required-pair support rate={phys.get('support_rate_required')}, "
                    f"broken={phys.get('n_required_broken')}."
                ),
                interpretation=(
                    "Hydrodynamic family labels are interpreted against a physically coherent sonde record "
                    "(context only; validation not repeated)."
                ),
                supporting_evidence=[
                    evidence_item(
                        "stage_03",
                        "stage03_physical_report.json",
                        "support_rate_required",
                        phys.get("support_rate_required"),
                        "Physical Knowledge Engine result",
                        "strong",
                    )
                ],
                confidence="provisional",
                uncertainty="Physical coherence does not uniquely identify hydrodynamic regimes.",
                limitations=["CEAM does not re-test pairwise relationships."],
                level="observation",
            )
        )

    return [u.to_dict() for u in units]
