"""Water quality interpretation from regime fingerprints + Stage 8 drivers (no re-validation)."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext, z_get
from cieml.ceam.models import InterpretationUnit, evidence_item


def interpret_water_quality(ctx: CEAMContext, regimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[InterpretationUnit] = []
    th = ctx.thresholds
    drivers = []
    if ctx.shap_drivers is not None and len(ctx.shap_drivers):
        drivers = ctx.shap_drivers.loc[ctx.shap_drivers["tier"].isin(["Dominant", "Secondary"]), "feature"].tolist()

    # Aggregate extremes across regimes
    do_low = [r for r in regimes if z_get(r.get("z_fingerprint") or {}, ctx, "do") <= th.get("do_depressed_mod", -0.8)]
    turb_hi = [r for r in regimes if z_get(r.get("z_fingerprint") or {}, ctx, "turbidity") >= th.get("turbidity_elevated_mod", 0.5)]
    sal_lo = [r for r in regimes if z_get(r.get("z_fingerprint") or {}, ctx, "salinity") <= th.get("salinity_fresh_mod", -0.5)]
    ph_lo = [r for r in regimes if z_get(r.get("z_fingerprint") or {}, ctx, "ph") <= th.get("ph_depressed_strong", -1.5)]

    def _var_unit(topic: str, obs: str, interp: str, regs: list, var: str, conf: str) -> InterpretationUnit:
        return InterpretationUnit(
            topic=topic,
            observation=obs,
            interpretation=interp,
            supporting_evidence=[
                evidence_item("stage_08", "regime z fingerprints", var, [r["regime"] for r in regs], "Campaign-relative z extremes", "strong"),
                evidence_item("stage_08", "shap_driver_ranks", "Dominant/Secondary", drivers[:8], "Explainability context", "moderate"),
            ],
            confidence=conf,
            uncertainty="Interpretations are relative to campaign means, not absolute water-quality standards.",
            limitations=["Not a regulatory compliance assessment.", "Causal sources not identified."],
            alternatives=["Sensor drift (mitigated if Stage 1–3 context is acceptable)."],
            level="interpretation" if regs else "observation",
        )

    units.append(
        _var_unit(
            "dissolved_oxygen",
            f"{len(do_low)} regime(s) show depressed DO relative to the campaign.",
            (
                "Low-oxygen fingerprints are present and may indicate hypoxia risk under restricted flushing "
                "when co-located with harbour-role membership — see regime module."
                if do_low
                else "No regime cleared the DO-depression gate; campaign-mean oxygen structure dominates."
            ),
            do_low,
            "do_mg_l__mean",
            "provisional" if do_low else "supported",
        )
    )
    if do_low and any(r.get("interpretive_family") == "hypoxic_regime" or "hypox" in str(r.get("title", "")).lower() for r in do_low):
        pass  # family already captures hypoxia-risk wording
    elif do_low:
        units[-1].limitations.append("Hypoxia as a clinical/ecological endpoint requires sustained DO below absolute thresholds not asserted here.")

    units.append(
        _var_unit(
            "salinity",
            f"{len(sal_lo)} regime(s) show salinity depression relative to the campaign.",
            (
                "Freshening relative to the campaign mean is observed; runoff influence is a hypothesis pending Stage 10 consistency."
                if sal_lo
                else "No salinity-depression regime gate cleared."
            ),
            sal_lo,
            "salinity_psu__mean",
            "provisional" if sal_lo else "supported",
        )
    )

    units.append(
        _var_unit(
            "turbidity",
            f"{len(turb_hi)} regime(s) show elevated turbidity relative to the campaign.",
            (
                "Elevated suspended-material fingerprints are present (resuspension and/or runoff candidates)."
                if turb_hi
                else "No elevated-turbidity regime gate cleared."
            ),
            turb_hi,
            "turbidity_fnu__mean",
            "provisional" if turb_hi else "supported",
        )
    )

    units.append(
        _var_unit(
            "ph",
            f"{len(ph_lo)} regime(s) show strongly depressed pH relative to the campaign.",
            (
                "Low pH co-occurring with low DO is consistent with respiration/organic loading; not proof of acid pollution."
                if ph_lo
                else "No strong pH-depression regime gate cleared."
            ),
            ph_lo,
            "ph__mean",
            "provisional" if ph_lo else "supported",
        )
    )

    # Temperature — report observation even if unused for family scoring historically
    temps = [(r["regime"], z_get(r.get("z_fingerprint") or {}, ctx, "temperature")) for r in regimes]
    units.append(
        InterpretationUnit(
            topic="temperature",
            observation=f"Regime temperature z-scores: {temps}.",
            interpretation="Temperature is reported as context; family labeling does not treat temperature as a primary process discriminator in the domain CEAM thresholds.",
            supporting_evidence=[evidence_item("stage_08", "z_fingerprints", "temperature_c__mean", temps, "Temperature fingerprint", "moderate")],
            confidence="supported",
            uncertainty="Thermal stratification cannot be inferred from station-day means.",
            limitations=["No vertical temperature profiles."],
            level="observation",
        )
    )

    # Conductivity / TSS if present in fingerprints
    for r in regimes:
        z = r.get("z_fingerprint") or {}
        if any("cond" in k or "tds" in k or "tss" in k for k in z):
            units.append(
                InterpretationUnit(
                    topic="conductivity_tds_tss",
                    observation="Conductivity/TDS/TSS features appear in regime fingerprints where measured.",
                    interpretation="Ionic strength and particulate proxies track salinity/turbidity families; CEAM does not invent TSS mechanisms when Stage 3 marked pairs not testable.",
                    supporting_evidence=[
                        evidence_item("stage_03", "stage03_physical_report.json", "deviations", (ctx.physical_report or {}).get("deviations"), "Physical pair testability", "moderate"),
                        evidence_item("stage_08", "z_fingerprints", "ionic/optical", list(z.keys()), "Available fingerprint keys", "moderate"),
                    ],
                    confidence="provisional",
                    uncertainty="TSS may be absent or zero-filled in some exports.",
                    limitations=["Do not claim TSS dynamics without dynamic-range evidence."],
                    level="interpretation",
                )
            )
            break

    qa = ctx.qa_report or {}
    if qa:
        units.append(
            InterpretationUnit(
                topic="qa_context",
                observation=f"Stage 1 severity_counts={qa.get('severity_counts')}; core_variables_present={len(qa.get('core_variables_present') or [])}.",
                interpretation="WQ interpretation assumes the audited record; CEAM does not re-run QA.",
                supporting_evidence=[evidence_item("stage_01", "stage01_qa_report.json", "severity_counts", qa.get("severity_counts"), "QA context", "strong")],
                confidence="provisional",
                uncertainty="Critical flags may still remain under flag-only policy.",
                limitations=["See Stage 1–2 for remediation paths."],
                level="observation",
            )
        )

    return [u.to_dict() for u in units]
