"""Stage 12: Coastal Environmental Analysis Module (CEAM).

Interprets upstream CIEML artifacts (Discovery, XAI, Anomalies, Meteo, Spatiotemporal,
QA/Physics context, optional EBSVE). Does not re-run those engines.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from cieml.ceam import run_ceam
from cieml.config import PHASE1_DIR, PHASE2_DIR, PHASE4_DIR, PHASE5_DIR, PHASE6_DIR, PHASE7_DIR, PHASE8_DIR


def run_stage12(
    regime_labels: pd.DataFrame,
    regime_profiles: pd.DataFrame | None = None,
    shap_drivers: pd.DataFrame | None = None,
    output_dir: Path | None = None,
    *,
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    phase8_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE7_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    ceam = run_ceam(
        regime_labels=regime_labels,
        regime_profiles=regime_profiles,
        shap_drivers=shap_drivers,
        phase1_dir=phase1_dir or PHASE1_DIR,
        phase2_dir=phase2_dir or PHASE2_DIR,
        phase4_dir=phase4_dir or PHASE4_DIR,
        phase5_dir=phase5_dir or PHASE5_DIR,
        phase6_dir=phase6_dir or PHASE6_DIR,
        phase8_dir=phase8_dir or PHASE8_DIR,
    )

    interpretations = ceam["regimes"]

    # Legacy summary table (H4 / Stage 13 / phase7 summary compatibility)
    interp_df = pd.DataFrame(
        [
            {
                "regime": r["regime"],
                "n": r["n"],
                "title": r["title"],
                "interpretive_family": r["interpretive_family"],
                "confidence": r["confidence"],
                "evidence_score": r["evidence_score"],
            }
            for r in interpretations
        ]
    )

    # Figures: fingerprints + membership (unchanged visual contract)
    fig_paths: dict[str, str] = {}
    profiles = regime_profiles
    if profiles is None or not len(profiles):
        # rebuild light profile frame from interpretations' z if needed for plot
        rows = []
        for r in interpretations:
            row = {"regime": r["regime"], "n": r["n"]}
            for k, v in (r.get("z_fingerprint") or {}).items():
                row[f"z__{k}"] = v
            rows.append(row)
        profiles = pd.DataFrame(rows)

    if profiles is not None and len(profiles):
        z_mat = profiles.set_index("regime")
        z_cols = [c for c in z_mat.columns if str(c).startswith("z__")]
        if z_cols:
            plot = z_mat[z_cols].copy()
            plot.columns = [c.replace("z__", "") for c in plot.columns]
            fig, ax = plt.subplots(figsize=(10, 4.5))
            plot.T.plot(kind="bar", ax=ax)
            ax.axhline(0, color="black", lw=0.8)
            ax.set_ylabel("Campaign z-score")
            ax.set_title("Stage 12 / CEAM — Regime environmental fingerprints")
            ax.legend(title="Regime", fontsize=8)
            fig.tight_layout()
            p = fig_dir / "fig_stage12_regime_fingerprints.png"
            fig.savefig(p, dpi=600, bbox_inches="tight")
            plt.close(fig)
            fig_paths["fingerprints"] = str(p)

    df = regime_labels
    if "station" in df.columns and "regime" in df.columns:
        ct = pd.crosstab(df["station"], df["regime"], normalize="index")
        fig, ax = plt.subplots(figsize=(8, 4))
        ct.plot(kind="bar", stacked=True, ax=ax, colormap="tab10")
        ax.set_ylabel("Share of station-days")
        ax.set_title("Stage 12 / CEAM — Regime membership by station")
        fig.tight_layout()
        p2 = fig_dir / "fig_stage12_membership.png"
        fig.savefig(p2, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["membership"] = str(p2)

    # --- Artifacts ---
    interp_df.to_csv(output_dir / "stage12_regime_interpretations.csv", index=False)
    (output_dir / "stage12_interpretation_detail.json").write_text(
        json.dumps(interpretations, indent=2, default=str), encoding="utf-8"
    )

    assessment = {
        "hydrodynamics": ceam["hydrodynamics"],
        "water_quality": ceam["water_quality"],
        "meteorology": ceam["meteorology"],
        "spatial": ceam["spatial"],
        "temporal": ceam["temporal"],
        "ecological": ceam["ecological"],
        "campaign_summary": ceam["campaign_summary"],
        "fusion": ceam["fusion"],
    }
    (output_dir / "stage12_coastal_environmental_assessment.json").write_text(
        json.dumps(assessment, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "stage12_scientific_narrative.md").write_text(ceam["narrative_markdown"], encoding="utf-8")
    (output_dir / "stage12_traceability.json").write_text(
        json.dumps(ceam["traceability"], indent=2, default=str), encoding="utf-8"
    )
    pd.DataFrame(ceam["traceability"]).to_csv(output_dir / "stage12_traceability.csv", index=False)

    report = {
        "n_regimes": int(df["regime"].nunique()) if "regime" in df.columns else len(interpretations),
        "interpretations": interpretations,
        "candidate_families_considered": ceam["candidate_families_considered"],
        "naming_policy": ceam["naming_policy"],
        "ceam": {
            "contract_id": ceam["contract_id"],
            "domain": ceam["domain"],
            "campaign_id": ceam["campaign_id"],
            "n_trace_rows": len(ceam["traceability"]),
            "n_rejected_unsupported": ceam["fusion"].get("n_rejected_unsupported"),
            "assessment_path": str(output_dir / "stage12_coastal_environmental_assessment.json"),
            "narrative_path": str(output_dir / "stage12_scientific_narrative.md"),
            "traceability_path": str(output_dir / "stage12_traceability.json"),
        },
        "campaign_summary": ceam["campaign_summary"],
        "figures": fig_paths,
        "outputs": {"summary_table": str(output_dir / "stage12_regime_interpretations.csv")},
    }
    (output_dir / "stage12_ecological_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    return {"interpretations": interpretations, "summary": interp_df, "report": report, "ceam": ceam}
