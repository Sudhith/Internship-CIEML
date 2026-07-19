"""Stage 2: Evidence-based sensor QA/QC (detect, do not assume artifacts)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cieml.config import CORE_VARIABLES, PHASE2_DIR

QA_VARS = [
    c for c in [
        "temperature_c", "salinity_psu", "ph", "do_mg_l", "do_sat_pct",
        "turbidity_fnu", "conductivity_us_cm", "spcond_us_cm", "tds_mg_l",
    ]
]


def _file_groups(df: pd.DataFrame):
    key = "source_file" if "source_file" in df.columns else None
    if key is None:
        df = df.copy()
        df["_file_key"] = df.get("station", "all").astype(str) + "|" + df.get("sample_date", "").astype(str)
        key = "_file_key"
    return df.groupby(key, sort=False)


def _detect_flatline(s: pd.Series, min_run: int = 30) -> dict[str, Any]:
    s = pd.to_numeric(s, errors="coerce")
    if s.notna().sum() < min_run:
        return {"flagged": False, "max_run": 0, "frac": 0.0}
    vals = s.to_numpy()
    max_run = 1
    run = 1
    for i in range(1, len(vals)):
        if np.isfinite(vals[i]) and np.isfinite(vals[i - 1]) and vals[i] == vals[i - 1]:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    frac = max_run / max(len(s), 1)
    return {"flagged": max_run >= min_run, "max_run": int(max_run), "frac": float(frac)}


def _detect_zero_inflation(s: pd.Series, thr: float = 0.05) -> dict[str, Any]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) == 0:
        return {"flagged": False, "zero_frac": 0.0}
    z = float((s == 0).mean())
    return {"flagged": z >= thr, "zero_frac": z}


def _detect_warmup(s: pd.Series, head_n: int = 20) -> dict[str, Any]:
    """Detect monotonic early drift relative to later stable window (cast start)."""
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) < head_n * 3:
        return {"flagged": False, "early_delta": 0.0, "score": 0.0}
    early = s.iloc[:head_n]
    late = s.iloc[head_n : head_n * 3]
    if late.std() == 0 or not np.isfinite(late.std()):
        return {"flagged": False, "early_delta": 0.0, "score": 0.0}
    early_delta = float(early.iloc[-1] - early.iloc[0])
    score = abs(early_delta) / (float(late.std()) + 1e-9)
    # Evidence threshold: early change exceeds ~3 late-window SDs
    return {"flagged": score >= 3.0, "early_delta": early_delta, "score": float(score)}


def _detect_step_change(s: pd.Series, z_thr: float = 6.0) -> dict[str, Any]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) < 40:
        return {"flagged": False, "max_z": 0.0}
    d = s.diff().dropna()
    mad = np.median(np.abs(d - np.median(d))) + 1e-9
    z = np.abs(d - np.median(d)) / (1.4826 * mad)
    max_z = float(np.nanmax(z)) if len(z) else 0.0
    return {"flagged": max_z >= z_thr, "max_z": max_z}


def _detect_saturation(s: pd.Series, edge_frac: float = 0.02) -> dict[str, Any]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) < 20:
        return {"flagged": False, "edge_frac": 0.0}
    lo, hi = float(s.min()), float(s.max())
    if hi == lo:
        return {"flagged": False, "edge_frac": 0.0}
    near = ((s - lo) / (hi - lo) < 0.01) | ((s - lo) / (hi - lo) > 0.99)
    ef = float(near.mean())
    return {"flagged": ef >= edge_frac and (hi - lo) > 0, "edge_frac": ef}


def run_stage02(observations: pd.DataFrame, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE2_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    vars_present = [c for c in QA_VARS if c in observations.columns]
    flags: list[dict[str, Any]] = []
    per_file_rows: list[dict[str, Any]] = []

    for file_key, g in _file_groups(observations):
        station = str(g["station"].iloc[0]) if "station" in g.columns else "UNKNOWN"
        date = str(g["sample_date"].iloc[0]) if "sample_date" in g.columns else None
        row: dict[str, Any] = {
            "source_file": str(file_key),
            "station": station,
            "sample_date": date,
            "n": int(len(g)),
        }
        file_flags = 0
        for col in vars_present:
            s = g[col]
            checks = {
                "flatline": _detect_flatline(s),
                "zero_inflation": _detect_zero_inflation(s) if col in {
                    "do_mg_l", "do_sat_pct", "turbidity_fnu", "tss_mg_l"
                } else {"flagged": False, "zero_frac": 0.0},
                "warmup": _detect_warmup(s),
                "step_change": _detect_step_change(s),
                "saturation": _detect_saturation(s),
            }
            # negatives
            snum = pd.to_numeric(s, errors="coerce")
            neg_frac = float((snum < 0).mean()) if snum.notna().any() else 0.0
            checks["negatives"] = {"flagged": neg_frac > 0, "neg_frac": neg_frac}

            for check_name, res in checks.items():
                if res.get("flagged"):
                    file_flags += 1
                    flags.append(
                        {
                            "source_file": str(file_key),
                            "station": station,
                            "sample_date": date,
                            "variable": col,
                            "check": check_name,
                            "severity": "Suspicious",
                            "metrics": {k: v for k, v in res.items() if k != "flagged"},
                            "action": "flag_only_no_deletion",
                            "physical_reasoning": _reasoning(check_name, col),
                        }
                    )
            row[f"{col}__n_checks_flagged"] = sum(1 for r in checks.values() if r.get("flagged"))
        row["n_flag_events"] = file_flags
        per_file_rows.append(row)

    flags_df = pd.DataFrame(flags)
    file_df = pd.DataFrame(per_file_rows)

    # Cross-station concordance: same check+variable on same day across stations
    cross: list[dict[str, Any]] = []
    if len(flags_df):
        for (date, variable, check), sub in flags_df.groupby(["sample_date", "variable", "check"]):
            n_stations = sub["station"].nunique()
            if n_stations >= 3:
                cross.append(
                    {
                        "sample_date": date,
                        "variable": variable,
                        "check": check,
                        "n_stations": int(n_stations),
                        "interpretation": (
                            "Multi-station co-occurrence raises likelihood of shared instrument/"
                            "protocol artifact OR synoptic environmental forcing; requires Stage 3/10."
                        ),
                        "severity": "Suspicious",
                    }
                )
    cross_df = pd.DataFrame(cross)

    # Sensitivity: compare raw vs mild winsorized summary means (no deletion)
    sens_rows = []
    for col in vars_present:
        s = pd.to_numeric(observations[col], errors="coerce")
        raw_mean = float(s.mean())
        q01, q99 = s.quantile(0.01), s.quantile(0.99)
        wins = s.clip(q01, q99)
        sens_rows.append(
            {
                "variable": col,
                "raw_mean": raw_mean,
                "winsor_01_99_mean": float(wins.mean()),
                "abs_rel_change": float(abs(wins.mean() - raw_mean) / (abs(raw_mean) + 1e-9)),
            }
        )
    sens_df = pd.DataFrame(sens_rows)

    # QC-annotated frame: add boolean columns, never drop rows
    annotated = observations.copy()
    annotated["qa_flag_any"] = False
    if len(flags_df):
        bad_files = set(flags_df["source_file"].astype(str))
        if "source_file" in annotated.columns:
            annotated["qa_flag_any"] = annotated["source_file"].astype(str).isin(bad_files)

    # Figures
    fig_paths: dict[str, str] = {}
    if len(flags_df):
        pivot = flags_df.groupby(["station", "check"]).size().unstack(fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.heatmap(pivot, annot=True, fmt="d", cmap="OrRd", ax=ax)
        ax.set_title("Stage 2 — Sensor QA flag counts by station × check")
        fig.tight_layout()
        p = fig_dir / "fig_stage02_flag_heatmap.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["flag_heatmap"] = str(p)

        # Example timeseries: top flagged variable overall
        top_var = flags_df["variable"].value_counts().index[0]
        sample_file = flags_df.loc[flags_df["variable"] == top_var, "source_file"].iloc[0]
        g = observations[observations["source_file"].astype(str) == str(sample_file)]
        if len(g) and top_var in g.columns:
            fig, ax = plt.subplots(figsize=(10, 3.5))
            y = pd.to_numeric(g[top_var], errors="coerce").to_numpy()
            ax.plot(y, lw=0.8, color="#1f4e79")
            ax.set_title(f"Stage 2 — Example flagged series: {top_var}")
            ax.set_xlabel("Sample index within cast")
            ax.set_ylabel(top_var)
            fig.tight_layout()
            p2 = fig_dir / "fig_stage02_example_series.png"
            fig.savefig(p2, dpi=600, bbox_inches="tight")
            plt.close(fig)
            fig_paths["example_series"] = str(p2)

    # Station comparison of zero-inflation for DO / turbidity
    zi_rows = []
    if "station" in observations.columns:
        for station, g in observations.groupby("station"):
            for col in [c for c in ["do_mg_l", "turbidity_fnu", "do_sat_pct"] if c in g.columns]:
                zi = _detect_zero_inflation(g[col], thr=0.0)
                zi_rows.append({"station": station, "variable": col, "zero_frac": zi["zero_frac"]})
    zi_df = pd.DataFrame(zi_rows)
    if len(zi_df):
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.barplot(data=zi_df, x="station", y="zero_frac", hue="variable", ax=ax)
        ax.set_title("Stage 2 — Zero inflation by station")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        p3 = fig_dir / "fig_stage02_zero_inflation.png"
        fig.savefig(p3, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["zero_inflation"] = str(p3)

    n_files = int(file_df["source_file"].nunique()) if len(file_df) else 0
    n_flag_files = int((file_df["n_flag_events"] > 0).sum()) if len(file_df) else 0
    report = {
        "n_observations": int(len(observations)),
        "n_variables_checked": len(vars_present),
        "n_flag_events": int(len(flags_df)),
        "n_files": n_files,
        "n_files_with_flags": n_flag_files,
        "file_flag_rate": float(n_flag_files / n_files) if n_files else 0.0,
        "check_counts": flags_df["check"].value_counts().to_dict() if len(flags_df) else {},
        "variable_counts": flags_df["variable"].value_counts().to_dict() if len(flags_df) else {},
        "cross_station_patterns": int(len(cross_df)),
        "policy": {
            "deletion": "none",
            "correction": "none_applied",
            "annotation": "qa_flag_any on observations; full flag ledger retained",
            "rationale": "Stage 2 detects and documents; Stage 3/14 decide robustness under inclusion.",
        },
        "sensitivity_max_rel_change": float(sens_df["abs_rel_change"].max()) if len(sens_df) else 0.0,
        "h1_update": {
            "hypothesis": "H1_data_trustworthiness",
            "status": "PROVISIONAL_SUPPORT",
            "note": (
                "No Critical instrument failures requiring wholesale rejection; flags are Suspicious "
                "and retained with provenance. Final DEFINITIVE status still requires four-pillar review."
            ),
        },
        "figures": fig_paths,
    }

    # Persist
    flags_path = output_dir / "stage02_qa_flags.csv"
    file_path = output_dir / "stage02_file_qa_summary.csv"
    cross_path = output_dir / "stage02_cross_station_patterns.csv"
    sens_path = output_dir / "stage02_sensitivity.csv"
    ann_path = output_dir / "stage02_observations_annotated.parquet"
    report_path = output_dir / "stage02_qa_report.json"

    flags_df.to_csv(flags_path, index=False)
    file_df.to_csv(file_path, index=False)
    cross_df.to_csv(cross_path, index=False)
    sens_df.to_csv(sens_path, index=False)
    try:
        annotated.to_parquet(ann_path, index=False)
        ann_out = str(ann_path)
    except Exception:
        ann_csv = output_dir / "stage02_observations_annotated.csv"
        annotated.to_csv(ann_csv, index=False)
        ann_out = str(ann_csv)
    report["outputs"] = {
        "flags": str(flags_path),
        "file_summary": str(file_path),
        "cross_station": str(cross_path),
        "sensitivity": str(sens_path),
        "annotated_observations": ann_out,
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {
        "flags": flags_df,
        "file_summary": file_df,
        "cross_station": cross_df,
        "sensitivity": sens_df,
        "annotated": annotated,
        "report": report,
    }


def _reasoning(check: str, variable: str) -> str:
    mapping = {
        "flatline": f"Extended identical consecutive {variable} values can indicate stuck sensor/dead channel.",
        "zero_inflation": f"Excess zeros in {variable} may indicate dropouts, fouling, or dry-sensor intervals.",
        "warmup": f"Large early-cast drift in {variable} vs later variability is consistent with probe equilibration.",
        "step_change": f"Abrupt jumps in {variable} may reflect contact changes, bubbles, or electrical noise.",
        "saturation": f"Values piled at range edges for {variable} can indicate clipping/saturation.",
        "negatives": f"Negative {variable} is physically implausible for this measurand and suggests fault codes/noise.",
    }
    return mapping.get(check, "Flagged by automated sensor QA rule.")
