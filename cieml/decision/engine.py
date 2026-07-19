"""Build monitoring decision-support packets (role-based, evidence-linked)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cieml.decision.gate import gate_recommendations
from cieml.decision.templates import load_sensor_map, load_templates


def build_decision_support(
    shap_drivers: pd.DataFrame | None,
    interpretations: list[dict[str, Any]] | None = None,
    anomaly_catalog: pd.DataFrame | None = None,
    external_report: dict[str, Any] | None = None,
    *,
    claim_classifications: dict[str, str] | None = None,
    campaign_mean_confidence: float | None = None,
) -> dict[str, Any]:
    """Core DSS builder used by Stage 13.

    Returns structures matching the legacy stage13 report keys for artifact stability.
    """
    drivers = shap_drivers.copy() if shap_drivers is not None and len(shap_drivers) else pd.DataFrame()
    interps = interpretations or []
    external_report = external_report or {}
    templates = load_templates()
    sensor_map = load_sensor_map()

    prio_df = _sensor_prioritization(drivers, sensor_map)
    ewi_df = _early_warning(interps)
    decision_rules = list(templates.get("decision_rules") or [])
    strategy = _monitoring_strategy(prio_df, templates)
    budget = _budget_tiers(prio_df)
    management = _management_recs(external_report, prio_df)

    gate = gate_recommendations(claim_classifications, campaign_mean_confidence)
    # If no claim pack results yet (Phase 7 before EBSVE), do not suppress solely
    # for missing classifications — only when explicitly weak evidence is supplied
    # or drivers are entirely absent.
    if claim_classifications is None and campaign_mean_confidence is None:
        if len(prio_df) == 0:
            gate = {
                "suppress_recommendations": True,
                "status": "failed",
                "confidence_multiplier": 0.4,
                "failure_assessment": {"engine_id": "decision_support", "status": "failed", "hits": []},
                "reason": "No regime drivers available — insufficient evidence for actionable recommendations.",
            }
        else:
            gate = {
                "suppress_recommendations": False,
                "status": "ok",
                "confidence_multiplier": 1.0,
                "failure_assessment": {"engine_id": "decision_support", "status": "ok", "hits": []},
                "reason": "Pre-EBSVE provisional recommendations (drivers present); finalize gate after Stage 14.",
            }

    actionable = not gate["suppress_recommendations"]
    recommendations = []
    for row in (management if actionable else []):
        recommendations.append(
            {
                **row,
                "actionable": True,
                "confidence": "provisional",
                "limitations": [
                    "Associative drivers (SHAP), not proven causality.",
                    "Numeric cutoffs from one campaign are not transferable — re-run CIEML.",
                ],
                "evidence_refs": ["stage08_shap_driver_ranks.csv", "stage12_interpretation_detail.json", "stage10_external_report.json"],
            }
        )

    diagnostic_only = []
    if not actionable:
        diagnostic_only = [
            {
                "finding": "Evidence gate suppressed actionable recommendations",
                "recommendation": gate["reason"],
                "actionable": False,
                "confidence": "insufficient",
                "limitations": ["Do not use as monitoring policy until EBSVE/FMF gate clears."],
                "evidence_refs": ["stage14_four_pillar_closure.json", "cieml.failure"],
            }
        ]

    return {
        "sensor_prioritization": prio_df,
        "early_warning_indicators": ewi_df,
        "adaptive_monitoring": strategy,
        "decision_rules": decision_rules,
        "budget_tiers": budget,
        "management_recommendations": management if actionable else diagnostic_only,
        "recommendation_packets": recommendations if actionable else diagnostic_only,
        "gate": gate,
        "actionable": actionable,
        "contract_id": "SC-DSS",
        "phase": "K",
    }


def _sensor_prioritization(drivers: pd.DataFrame, sensor_map: dict[str, dict[str, str]]) -> pd.DataFrame:
    rows = []
    if len(drivers):
        for _, r in drivers.iterrows():
            feat = r["feature"]
            meta = sensor_map.get(feat, {"measurand": str(feat), "sensor_family": "Other"})
            tier = r.get("tier", "Negligible")
            priority = {"Dominant": 1, "Secondary": 2, "Negligible": 3}.get(tier, 3)
            rows.append(
                {
                    "feature": feat,
                    "measurand": meta.get("measurand", feat),
                    "sensor_family": meta.get("sensor_family", "Other"),
                    "tier": tier,
                    "priority_rank": priority,
                    "mean_abs_shap": float(r.get("mean_abs_shap", np.nan)),
                    "recommendation": (
                        "Core continuous monitoring — highest interpretive value for regimes"
                        if priority == 1
                        else "Retain in standard multiparameter package"
                        if priority == 2
                        else "Optional / lower frequency if budget-constrained"
                    ),
                    "confidence": "linked_to_shap_tier",
                    "limitations": "SHAP importance is associative with regime structure, not causal proof.",
                }
            )
    return pd.DataFrame(rows).sort_values(["priority_rank", "mean_abs_shap"], ascending=[True, False]) if rows else pd.DataFrame()


def _early_warning(interps: list[dict[str, Any]]) -> pd.DataFrame:
    ewi = []
    for interp in interps:
        fam = interp.get("interpretive_family")
        title = str(interp.get("title", ""))
        if fam in {"hypoxic_regime", "harbour_regime"} or "harbour" in title.lower():
            ewi.append(
                {
                    "indicator": "DO depression + pH depression co-occurrence",
                    "metric_guidance": "Flag station-days where DO and pH are jointly below campaign median by a large margin (see Stage 12 z-fingerprints).",
                    "linked_regime": interp.get("title"),
                    "station_role": "harbour_embayment",
                    "action": "Increase harbour-role DO/pH sampling frequency; inspect organic loading and flushing.",
                }
            )
        if fam in {"freshwater_influenced_regime", "sediment_resuspension_regime"} or "turbid" in title.lower():
            ewi.append(
                {
                    "indicator": "Turbidity rise with salinity drop",
                    "metric_guidance": "Co-movement of high turbidity and low salinity relative to station baseline.",
                    "linked_regime": interp.get("title"),
                    "station_role": "open_coast",
                    "action": "Trigger event sampling after rainfall / runoff; pair with meteo alerts.",
                }
            )
    if not ewi:
        ewi.append(
            {
                "indicator": "Multivariate consensus anomaly rate",
                "metric_guidance": "Use Stage 9 consensus anomaly flag as a generic early-warning until regime-specific EWIs stabilize.",
                "linked_regime": "all",
                "station_role": "any",
                "action": "Review flagged station-days within 24–48 h.",
            }
        )
    return pd.DataFrame(ewi).drop_duplicates(subset=["indicator"])


def _monitoring_strategy(prio_df: pd.DataFrame, templates: dict[str, Any]) -> dict[str, Any]:
    defaults = templates.get("default_minimum_sensors") or ["DO", "pH", "Salinity", "Turbidity", "Temperature"]
    return {
        "baseline": {
            "frequency": str(templates.get("baseline_frequency") or "").strip(),
            "minimum_sensor_set": (
                prio_df.loc[prio_df["priority_rank"] <= 2, "measurand"].tolist() if len(prio_df) else list(defaults)
            ),
        },
        "adaptive_triggers": list(templates.get("adaptive_triggers") or []),
        "spatial_design": list(templates.get("spatial_design") or []),
        "station_roles": dict(templates.get("station_roles") or {}),
    }


def _budget_tiers(prio_df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "tier": "Essential",
            "sensors": prio_df.loc[prio_df["priority_rank"] == 1, "sensor_family"].drop_duplicates().tolist() if len(prio_df) else ["ODO", "pH"],
            "rationale": "Dominant SHAP drivers of regime structure.",
        },
        {
            "tier": "Standard",
            "sensors": prio_df.loc[prio_df["priority_rank"] <= 2, "sensor_family"].drop_duplicates().tolist() if len(prio_df) else ["ODO", "pH", "CTD", "Turbidity"],
            "rationale": "Dominant + Secondary drivers; recommended multiparameter package.",
        },
        {
            "tier": "Extended",
            "sensors": prio_df["sensor_family"].drop_duplicates().tolist() if len(prio_df) else [],
            "rationale": "Full package including lower-tier / derived indices for research campaigns.",
        },
    ]


def _management_recs(external_report: dict[str, Any], prio_df: pd.DataFrame) -> list[dict[str, str]]:
    support_frac = external_report.get("anomaly_external_support_frac")
    dominant = []
    if len(prio_df):
        dominant = prio_df.loc[prio_df["priority_rank"] == 1, "measurand"].tolist()
    return [
        {
            "finding": "Spatially structured regimes including harbour low-oxygen and open-coast turbid/fresher states",
            "recommendation": "Maintain dual harbour–open-coast monitoring design (roles); do not average all stations into a single coastal index.",
        },
        {
            "finding": f"Partial meteo support for anomalies (support_frac={support_frac})",
            "recommendation": "Couple sonde QA with rainfall/wind event alerts; investigate non-meteo anomalies as possible sensor or local process signals.",
        },
        {
            "finding": f"Dominant interpretive drivers: {', '.join(dominant) if dominant else 'see SHAP tiers'}",
            "recommendation": "Prioritize ODO and pH calibration/maintenance budgets over lower-tier sensors when Dominant tier includes oxygen/pH family.",
        },
    ]
