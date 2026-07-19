"""Stage 13: Decision Support + Applicability Domain (Phase K).

Orchestrates `cieml.decision` (SC-DSS) and `cieml.applicability` (SC-APP).
Artifact filenames stay stable for evidence loaders / H6.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from cieml.applicability import build_applicability_domain
from cieml.config import PHASE7_DIR
from cieml.decision import build_decision_support


def run_stage13(
    shap_drivers: pd.DataFrame | None,
    interpretations: list[dict[str, Any]] | None,
    anomaly_catalog: pd.DataFrame | None = None,
    external_report: dict[str, Any] | None = None,
    output_dir: Path | None = None,
    *,
    claim_classifications: dict[str, str] | None = None,
    campaign_mean_confidence: float | None = None,
    domain_name: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE7_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Domain / campaign context (optional — degrade gracefully)
    domain_notes: list[str] = []
    core_variables: list[str] = []
    n_stations = None
    try:
        from cieml.domain import get_default_domain, load_campaign

        dom = get_default_domain()
        domain_name = domain_name or dom.name
        domain_notes = list(dom.applicability_notes or [])
        core_variables = list(dom.core_variables or [])
        camp = load_campaign()
        campaign_id = campaign_id or camp.campaign_id
        n_stations = len(camp.stations) if camp.stations else None
    except FileNotFoundError:
        # No domain/campaign profile yet; degrade to defaults. A bare
        # `except Exception` here would also swallow a genuine domain-schema
        # ValueError, silently hiding a real Domain Configuration Layer failure.
        domain_name = domain_name or "coastal"
        campaign_id = campaign_id or "unknown_campaign"

    dss = build_decision_support(
        shap_drivers,
        interpretations,
        anomaly_catalog=anomaly_catalog,
        external_report=external_report,
        claim_classifications=claim_classifications,
        campaign_mean_confidence=campaign_mean_confidence,
    )

    prio_df: pd.DataFrame = dss["sensor_prioritization"]
    ewi_df: pd.DataFrame = dss["early_warning_indicators"]
    decision_rules = dss["decision_rules"]
    budget = dss["budget_tiers"]
    management = dss["management_recommendations"]
    strategy = dss["adaptive_monitoring"]

    rec_ids = [f"M{i+1}" for i in range(len(management))]
    applicability = build_applicability_domain(
        domain_name=domain_name,
        domain_notes=domain_notes,
        campaign_id=campaign_id,
        n_stations=n_stations,
        core_variables=core_variables,
        recommendation_ids=rec_ids,
    )

    # Figures (same paths as before)
    fig_paths: dict[str, str] = {}
    if len(prio_df):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        sns.barplot(data=prio_df, x="mean_abs_shap", y="measurand", hue="tier", dodge=False, ax=ax)
        ax.set_title("Stage 13 — Sensor prioritization from regime drivers")
        fig.tight_layout()
        p = fig_dir / "fig_stage13_sensor_priority.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["sensor_priority"] = str(p)

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.axis("off")
    boxes = [
        (0.02, "Ingest &\nQA/QC"),
        (0.22, "Regimes &\nSHAP drivers"),
        (0.42, "Anomalies +\nmeteo check"),
        (0.62, "Decision\nrules R1–R4"),
        (0.82, "Adaptive\nsampling"),
    ]
    for x, txt in boxes:
        ax.add_patch(plt.Rectangle((x, 0.35), 0.15, 0.4, fill=True, color="#d9e3f0", ec="#1f4e79", lw=1.5))
        ax.text(x + 0.075, 0.55, txt, ha="center", va="center", fontsize=9)
    for x0, x1 in [(0.17, 0.22), (0.37, 0.42), (0.57, 0.62), (0.77, 0.82)]:
        ax.annotate("", xy=(x1, 0.55), xytext=(x0, 0.55), arrowprops=dict(arrowstyle="->", color="#1f4e79"))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Stage 13 — Decision-support workflow")
    fig.tight_layout()
    p2 = fig_dir / "fig_stage13_decision_workflow.png"
    fig.savefig(p2, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["workflow"] = str(p2)

    report = {
        "sensor_prioritization": prio_df.to_dict(orient="records") if len(prio_df) else [],
        "early_warning_indicators": ewi_df.to_dict(orient="records"),
        "adaptive_monitoring": strategy,
        "decision_rules": decision_rules,
        "budget_tiers": budget,
        "management_recommendations": management,
        "recommendation_packets": dss.get("recommendation_packets") or [],
        "applicability_domain": applicability,
        "gate": dss.get("gate"),
        "actionable": dss.get("actionable"),
        "contract_ids": ["SC-DSS", "SC-APP"],
        "phase": "K",
        "figures": fig_paths,
    }

    if len(prio_df):
        prio_df.to_csv(output_dir / "stage13_sensor_prioritization.csv", index=False)
    ewi_df.to_csv(output_dir / "stage13_early_warning_indicators.csv", index=False)
    pd.DataFrame(decision_rules).to_csv(output_dir / "stage13_decision_rules.csv", index=False)
    pd.DataFrame(budget).to_csv(output_dir / "stage13_budget_tiers.csv", index=False)
    pd.DataFrame(management).to_csv(output_dir / "stage13_management_recommendations.csv", index=False)
    (output_dir / "stage13_applicability_domain.json").write_text(
        json.dumps(applicability, indent=2), encoding="utf-8"
    )
    (output_dir / "stage13_decision_gate.json").write_text(
        json.dumps(dss.get("gate") or {}, indent=2), encoding="utf-8"
    )
    report_path = output_dir / "stage13_decision_support_report.json"
    report["outputs"] = {"prioritization": str(output_dir / "stage13_sensor_prioritization.csv")}
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md = [
        "# CIEML 2.0 — Monitoring Decision Brief",
        "",
        f"**Actionable recommendations:** {'yes' if dss.get('actionable') else 'no (diagnostic only)'}",
        "",
        "## Sensor priority",
    ]
    if len(prio_df):
        for _, r in prio_df.iterrows():
            md.append(f"- **{r['measurand']}** ({r['tier']}): {r['recommendation']}")
    md += ["", "## Early-warning indicators"]
    for _, r in ewi_df.iterrows():
        md.append(f"- **{r['indicator']}** → {r['action']}")
    md += ["", "## Applicability"]
    md.append("Applies to:")
    for a in applicability.get("applies_to") or []:
        md.append(f"- {a}")
    md.append("")
    md.append("Does **not** apply to:")
    for a in applicability.get("does_not_apply_to") or []:
        md.append(f"- {a}")
    md += ["", f"**Transfer rule:** {applicability.get('transfer_rule')}", ""]
    if strategy.get("spatial_design"):
        md += ["## Spatial design (roles)", ""]
        for line in strategy["spatial_design"]:
            md.append(f"- {line}")
    (output_dir / "stage13_decision_brief.md").write_text("\n".join(md), encoding="utf-8")

    return {"prioritization": prio_df, "ewi": ewi_df, "report": report}
