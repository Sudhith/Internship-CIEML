"""Stage 3: Physical relationship validation (Physical Knowledge Engine — Phase E)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cieml.config import DEFAULT_DOMAIN, PHASE2_DIR
from cieml.domain import load_domain
from cieml.physics.engine import _spearman, evaluate_physical_relationships


def run_stage03(
    observations: pd.DataFrame,
    output_dir: Path | None = None,
    domain_name: str | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE2_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    domain = load_domain(domain_name or DEFAULT_DOMAIN)
    phys = evaluate_physical_relationships(observations, domain)
    data_driven_thr = float(phys["data_driven_abs_rho_threshold"])
    pair_rows = []
    for row in phys["pairs"]:
        pair_rows.append({**row, "effect_threshold": data_driven_thr})
    pairs_df = pd.DataFrame(pair_rows)

    catalog_vars = sorted({v for rel in domain.relationship_catalog() for v in (rel["x"], rel["y"])})
    num_cols = [c for c in catalog_vars if c in observations.columns]
    if not num_cols:
        num_cols = [c for c in domain.core_variables if c in observations.columns]

    corr = observations[num_cols].apply(pd.to_numeric, errors="coerce").corr(method="spearman") if num_cols else pd.DataFrame()

    key_pairs = [
        ("salinity_psu", "spcond_us_cm"),
        ("temperature_c", "do_mg_l"),
        ("do_mg_l", "do_sat_pct"),
    ]
    station_rows = []
    if "station" in observations.columns:
        for station, g in observations.groupby("station"):
            for x, y in key_pairs:
                if x in g.columns and y in g.columns:
                    r = _spearman(g[x], g[y])
                    station_rows.append(
                        {"station": station, "pair": f"{x}~{y}", "rho": r["rho"], "p": r["p"], "n": r["n"]}
                    )
    station_df = pd.DataFrame(station_rows)

    fig_paths: dict[str, str] = {}
    if len(corr):
        fig, ax = plt.subplots(figsize=(9, 7))
        sns.heatmap(corr, cmap="RdBu_r", center=0, vmin=-1, vmax=1, ax=ax, square=True)
        ax.set_title("Stage 3 — Spearman correlation matrix")
        fig.tight_layout()
        p = fig_dir / "fig_stage03_correlation_matrix.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["correlation_matrix"] = str(p)

    required = [r for r in pair_rows if not r.get("optional") and r.get("status") != "Missing_variable"]
    n = len(required)
    if n:
        ncols = 3
        nrows = int(np.ceil(n / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3.6 * nrows))
        axes = np.array(axes).reshape(-1)
        for ax, row in zip(axes, required):
            x, y = row["x"], row["y"]
            sub = observations[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(sub) > 4000:
                sub = sub.sample(4000, random_state=42)
            ax.scatter(sub[x], sub[y], s=4, alpha=0.25, c="#1f4e79", linewidths=0)
            ax.set_xlabel(x)
            ax.set_ylabel(y)
            ax.set_title(f"{row['status']}  rho={row['rho']:.2f}" if np.isfinite(row["rho"]) else row["status"])
        for ax in axes[n:]:
            ax.axis("off")
        fig.suptitle("Stage 3 — Expected physical relationships", y=1.01)
        fig.tight_layout()
        p2 = fig_dir / "fig_stage03_expected_pairs.png"
        fig.savefig(p2, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["expected_pairs"] = str(p2)

    if len(station_df):
        fig, ax = plt.subplots(figsize=(9, 4.5))
        sns.barplot(data=station_df, x="station", y="rho", hue="pair", ax=ax)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title("Stage 3 — Key-pair Spearman rho by station")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        p3 = fig_dir / "fig_stage03_station_pair_stability.png"
        fig.savefig(p3, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["station_stability"] = str(p3)

    scored = pairs_df[~pairs_df["optional"].fillna(False) & ~pairs_df["status"].isin(["Missing_variable", "Not_testable"])]
    n_req = int(len(scored))
    n_ok = int(scored["status"].isin(["Expected", "Expected_weak"]).sum()) if n_req else 0
    n_broken = int(scored["status"].eq("Broken").sum()) if n_req else 0
    support_rate = float(n_ok / n_req) if n_req else 0.0

    if n_req and support_rate >= 0.75 and n_broken == 0:
        h2_status, h2_verdict = "PROVISIONAL_SUPPORT", "lean_alternative"
    elif n_broken >= max(1, n_req // 2):
        h2_status, h2_verdict = "PROVISIONAL_REJECT_ALTERNATIVE", "lean_null"
    else:
        h2_status, h2_verdict = "MIXED_EVIDENCE", "exploratory"

    explanations = []
    for _, row in pairs_df.iterrows():
        if row["status"] in {"Broken", "Unexpected", "Missing_variable", "Not_testable"}:
            explanations.append(
                {
                    "pair": f"{row['x']}~{row['y']}",
                    "status": row["status"],
                    "environmental_note": _explain_deviation(row),
                }
            )

    report = {
        "effect_threshold_abs_rho": data_driven_thr,
        "n_pairs_evaluated": int(len(pairs_df)),
        "n_required_pairs": n_req,
        "n_required_supported": n_ok,
        "n_required_broken": n_broken,
        "support_rate_required": support_rate,
        "status_counts": pairs_df["status"].value_counts().to_dict() if len(pairs_df) else {},
        "domain": domain.name,
        "domain_version": domain.version,
        "h2_update": {
            "hypothesis": "H2_physical_coherence",
            "status": h2_status,
            "verdict_lean": h2_verdict,
            "note": (
                "Verdict is provisional pending Stage 14 robustness; "
                "DEFINITIVE requires all four pillars. Relationships sourced from domain profile."
            ),
        },
        "deviations": explanations,
        "figures": fig_paths,
    }

    pairs_path = output_dir / "stage03_physical_pairs.csv"
    corr_path = output_dir / "stage03_correlation_matrix.csv"
    station_path = output_dir / "stage03_station_pair_stability.csv"
    report_path = output_dir / "stage03_physical_report.json"

    pairs_df.to_csv(pairs_path, index=False)
    corr.to_csv(corr_path)
    station_df.to_csv(station_path, index=False)
    report["outputs"] = {
        "pairs": str(pairs_path),
        "correlation_matrix": str(corr_path),
        "station_stability": str(station_path),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {
        "pairs": pairs_df,
        "correlation": corr,
        "station_stability": station_df,
        "report": report,
    }


def _explain_deviation(row: pd.Series) -> str:
    status = row.get("status")
    x, y = row.get("x"), row.get("y")
    if status == "Missing_variable":
        return f"{x} or {y} absent; relationship cannot be tested in this campaign export."
    if status == "Not_testable":
        return (
            f"{x}-{y} cannot be tested because at least one variable lacks dynamic range "
            f"(for example TSS exported as zeros). This is a data-product limitation, not a falsified mechanism."
        )
    if status == "Broken":
        return (
            f"Observed association between {x} and {y} conflicts with the expected domain mechanism "
            f"({row.get('mechanism')}). Possible causes: sensor cross-talk, unit mismatch, "
            f"short-cast mixing artifacts, or true local biogeochemical override — needs QA context."
        )
    if status == "Unexpected":
        return (
            f"No statistically reliable {x}–{y} link at the data-driven effect size; "
            f"may reflect limited dynamic range within short casts."
        )
    return "See pair metrics."
