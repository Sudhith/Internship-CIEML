"""Stage 1: Scientific data audit with Acceptable / Suspicious / Critical classification."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cieml.config import CORE_VARIABLES, DEFAULT_DOMAIN, PHASE1_DIR
from cieml.domain import load_domain
from cieml.qa.engine import run_qa_checks


SEVERITY_ORDER = {"Acceptable": 0, "Suspicious": 1, "Critical": 2}


def run_stage01(
    observations: pd.DataFrame,
    inventory: pd.DataFrame,
    output_dir: Path | None = None,
    domain_name: str | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE1_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    domain = load_domain(domain_name or DEFAULT_DOMAIN)
    core_vars = domain.core_variables or list(CORE_VARIABLES)
    plaus = domain.plausibility_ranges

    issues: list[dict[str, Any]] = []
    measure_cols = [c for c in observations.columns if c in core_vars or c in plaus]

    # --- Missingness ---
    miss = observations[measure_cols].isna().mean().sort_values(ascending=False) if measure_cols else pd.Series(dtype=float)
    for col, frac in miss.items():
        sev = "Acceptable"
        if frac > 0.2:
            sev = "Critical"
        elif frac > 0.05:
            sev = "Suspicious"
        elif frac > 0:
            sev = "Suspicious"
        if frac > 0:
            issues.append(
                {
                    "category": "missing_values",
                    "variable": col,
                    "severity": sev,
                    "detail": f"missing_fraction={frac:.4f}",
                }
            )

    # --- Constant / near-constant ---
    for col in measure_cols:
        s = pd.to_numeric(observations[col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        if s.nunique() <= 1:
            issues.append(
                {
                    "category": "constant_column",
                    "variable": col,
                    "severity": "Suspicious",
                    "detail": f"nunique={s.nunique()} value={s.iloc[0]}",
                }
            )
        elif s.nunique() <= 3 and len(s) > 100:
            issues.append(
                {
                    "category": "near_constant_column",
                    "variable": col,
                    "severity": "Suspicious",
                    "detail": f"nunique={s.nunique()}",
                }
            )

    # --- Negatives where impossible ---
    nonneg = list(domain.qa.get("non_negative_variables") or [
        "salinity_psu", "do_mg_l", "do_sat_pct", "turbidity_fnu", "tds_mg_l",
        "conductivity_us_cm", "spcond_us_cm", "tss_mg_l",
    ])
    for col in nonneg:
        if col not in observations.columns:
            continue
        s = pd.to_numeric(observations[col], errors="coerce")
        neg_frac = float((s < 0).mean()) if s.notna().any() else 0.0
        if neg_frac > 0:
            sev = "Critical" if neg_frac > 0.01 else "Suspicious"
            issues.append(
                {
                    "category": "negative_values",
                    "variable": col,
                    "severity": sev,
                    "detail": f"negative_fraction={neg_frac:.4f}",
                }
            )

    # --- Literature plausibility bands + magnitude overshoot (QA registry / Phase D) ---
    issues.extend(run_qa_checks(observations, domain, check_ids=["range_magnitude_overshoot"]))

    # --- Station-day completeness ---
    if {"station", "sample_date"}.issubset(observations.columns):
        stations = sorted(observations["station"].dropna().unique())
        dates = sorted(observations["sample_date"].dropna().unique())
        completeness = (
            observations.groupby(["sample_date", "station"]).size().unstack(fill_value=0)
        )
        # binary presence
        presence = (completeness > 0).astype(int)
        expected = len(stations) * len(dates)
        observed = int(presence.values.sum())
        miss_rate = 1 - observed / expected if expected else 0
        sev = "Acceptable"
        if miss_rate > 0.2:
            sev = "Critical"
        elif miss_rate > 0.05:
            sev = "Suspicious"
        issues.append(
            {
                "category": "station_day_coverage",
                "variable": "matrix",
                "severity": sev,
                "detail": f"observed={observed}/{expected}; missing_rate={miss_rate:.4f}",
            }
        )

        # Heatmap
        fig, ax = plt.subplots(figsize=(12, max(4, len(dates) * 0.22)))
        sns.heatmap(presence, cmap="Greens", cbar_kws={"label": "Present (1) / Absent (0)"}, ax=ax)
        ax.set_title("Stage 1 — Station–day completeness")
        ax.set_xlabel("Station")
        ax.set_ylabel("Sample date")
        fig.tight_layout()
        heat_path = fig_dir / "fig_stage01_completeness_heatmap.png"
        fig.savefig(heat_path, dpi=600, bbox_inches="tight")
        plt.close(fig)
    else:
        presence = pd.DataFrame()
        heat_path = None
        issues.append(
            {
                "category": "metadata",
                "variable": "station/sample_date",
                "severity": "Critical",
                "detail": "cannot build completeness matrix",
            }
        )

    # --- Duplicate observation check ---
    dup_cols = [c for c in ["timestamp", "station"] if c in observations.columns]
    if dup_cols:
        n_dup = int(observations.duplicated(subset=dup_cols).sum())
        if n_dup:
            issues.append(
                {
                    "category": "duplicates",
                    "variable": "+".join(dup_cols),
                    "severity": "Suspicious" if n_dup < 100 else "Critical",
                    "detail": f"n_duplicate_keys={n_dup}",
                }
            )

    # --- File inventory issues ---
    if inventory is not None and len(inventory):
        if "warnings" in inventory.columns:
            n_warn = int(inventory["warnings"].astype(str).str.contains("station_unresolved").sum())
            if n_warn:
                issues.append(
                    {
                        "category": "station_resolution",
                        "variable": "station",
                        "severity": "Suspicious",
                        "detail": f"files_with_unresolved_station={n_warn}",
                    }
                )
        # summary PH NA historically — check computed daily
        if "summary_ph_mean" in inventory.columns:
            na_ph = inventory["summary_ph_mean"].isna().sum()
            if na_ph:
                issues.append(
                    {
                        "category": "summary_stat_gap",
                        "variable": "ph",
                        "severity": "Suspicious",
                        "detail": f"files_with_na_summary_ph={int(na_ph)}",
                    }
                )

    # --- Variable summary table ---
    rows = []
    for col in measure_cols:
        s = pd.to_numeric(observations[col], errors="coerce")
        rows.append(
            {
                "variable": col,
                "n": int(s.notna().sum()),
                "missing_frac": float(s.isna().mean()),
                "mean": float(s.mean()) if s.notna().any() else np.nan,
                "std": float(s.std()) if s.notna().any() else np.nan,
                "min": float(s.min()) if s.notna().any() else np.nan,
                "p50": float(s.median()) if s.notna().any() else np.nan,
                "max": float(s.max()) if s.notna().any() else np.nan,
            }
        )
    var_summary = pd.DataFrame(rows)

    issues_df = pd.DataFrame(issues)
    if len(issues_df):
        counts = issues_df["severity"].value_counts().to_dict()
    else:
        counts = {}

    n_files = int(len(inventory)) if inventory is not None else 0
    n_critical = int((issues_df["severity"] == "Critical").sum()) if len(issues_df) else 0
    # provisional H1 evidence (not a final verdict)
    critical_rate = n_critical / max(len(issues_df), 1)

    qa_report = {
        "n_observations": int(len(observations)),
        "n_issues": int(len(issues_df)),
        "severity_counts": counts,
        "critical_issue_share_of_flags": critical_rate,
        "core_variables_present": [c for c in core_vars if c in observations.columns],
        "domain": domain.name,
        "domain_version": domain.version,
        "h1_provisional": {
            "hypothesis": "H1_data_trustworthiness",
            "status": "EVIDENCE_RECORDED",
            "note": "Final accept/reject deferred until Stage 2 QA/QC remediation paths are evaluated.",
            "signals": {
                "n_critical_flags": n_critical,
                "n_files": n_files,
            },
        },
        "figures": {"completeness_heatmap": str(heat_path) if heat_path else None},
    }

    # Missing-data matrix figure (variable x station)
    if measure_cols and "station" in observations.columns:
        miss_by_station = observations.groupby("station")[measure_cols].apply(lambda x: x.isna().mean())
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.heatmap(miss_by_station.T, cmap="YlOrRd", vmin=0, vmax=max(0.05, float(miss_by_station.max().max() or 0)), ax=ax)
        ax.set_title("Stage 1 — Missing-data fraction by station × variable")
        fig.tight_layout()
        miss_fig = fig_dir / "fig_stage01_missing_matrix.png"
        fig.savefig(miss_fig, dpi=600, bbox_inches="tight")
        plt.close(fig)
        qa_report["figures"]["missing_matrix"] = str(miss_fig)

    # Persist
    issues_path = output_dir / "stage01_qa_issues.csv"
    summary_path = output_dir / "stage01_variable_summary.csv"
    report_path = output_dir / "stage01_qa_report.json"
    presence_path = output_dir / "stage01_completeness_matrix.csv"

    issues_df.to_csv(issues_path, index=False)
    var_summary.to_csv(summary_path, index=False)
    if len(presence):
        presence.to_csv(presence_path)
    report_path.write_text(json.dumps(qa_report, indent=2), encoding="utf-8")

    return {
        "issues": issues_df,
        "variable_summary": var_summary,
        "completeness": presence,
        "report": qa_report,
    }
