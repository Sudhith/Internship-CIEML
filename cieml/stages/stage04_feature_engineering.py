"""Stage 4: Physically interpretable feature engineering."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cieml.config import CORE_VARIABLES, PHASE3_DIR

# Base environmental drivers retained for engineering (exclude known dead/redundant channels later in Stage 5)
BASE_VARS = [
    "temperature_c",
    "salinity_psu",
    "ph",
    "do_mg_l",
    "do_sat_pct",
    "turbidity_fnu",
    "spcond_us_cm",
    "barometer_mmhg",
]

FEATURE_DICTIONARY: dict[str, str] = {
    "daily_mean": "Station-day mean of a sonde variable (cast-central tendency).",
    "daily_median": "Station-day median; spike-robust alternative to the mean for sanity-checking outlier pull.",
    "daily_std": "Within-cast variability; high values imply mixing/noise/heterogeneity.",
    "daily_range": "Within-cast max-min; physical excursion during the cast.",
    "anom_station": "Departure from that station's campaign mean (local anomaly).",
    "anom_campaign": "Departure from coastline-wide campaign mean (synoptic anomaly).",
    "z_station": "Station-standardized score (comparability across variables).",
    "roll3_mean": "3-day rolling mean by station (short persistence / weather memory).",
    "roll3_std": "3-day rolling std by station (recent volatility).",
    "d1": "Day-to-day change at a station (temporal derivative / event onset).",
    "lag1": "Previous day value at the station (short-term autocorrelation structure).",
    "do_solubility_stress": "Warm + low DO coincidence index (hypoxia risk proxy).",
    "mixing_contrast": "Salinity x turbidity interaction (freshwater/sediment pulse proxy).",
    "carbonate_thermal": "pH x temperature interaction (carbonate-system thermal coupling proxy).",
    "do_sat_gap": "DO% - expected coupling residual vs DO mg/L (sensor/process mismatch hint).",
}


def _present(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def run_stage04(observations: pd.DataFrame, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE3_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    vars_ = _present(observations, BASE_VARS)
    # Drop near-constant base vars (no physical information for engineering)
    usable = []
    dropped_constant = []
    for c in vars_:
        s = pd.to_numeric(observations[c], errors="coerce")
        if s.nunique(dropna=True) < 2:
            dropped_constant.append(c)
        else:
            usable.append(c)

    obs = observations.copy()
    for c in usable:
        obs[c] = pd.to_numeric(obs[c], errors="coerce")

    # --- Station-day aggregates ---
    gcols = ["station", "sample_date"]
    # median alongside mean: a spike-robust aggregate so downstream stages / manuscript
    # authors can check how much a mean-based feature is being pulled by a handful of
    # extreme readings (coastal sondes intermittently spike from biofouling, bubbles, wave slap).
    aggs = {c: ["mean", "median", "std", "min", "max", "count"] for c in usable}
    daily = obs.groupby(gcols, dropna=False).agg(aggs)
    daily.columns = [f"{v}__{stat}" for v, stat in daily.columns]
    daily = daily.reset_index()
    daily["sample_date"] = pd.to_datetime(daily["sample_date"])
    daily = daily.sort_values(["station", "sample_date"]).reset_index(drop=True)

    for c in usable:
        daily[f"{c}__range"] = daily[f"{c}__max"] - daily[f"{c}__min"]
        # Relative pull of the mean away from the median: large values flag station-days
        # where a spike-sensitive mean feature may not represent the typical cast reading.
        # Symmetric (mean+median)/2 denominator avoids blow-up when the median is ~0 but
        # the mean is small-and-nonzero (a lone spike among otherwise-zero readings) —
        # a plain |median| denominator would report an uninterpretable ratio there.
        denom = (daily[f"{c}__mean"].abs() + daily[f"{c}__median"].abs()) / 2 + 1e-9
        daily[f"{c}__mean_median_rel_gap"] = (daily[f"{c}__mean"] - daily[f"{c}__median"]).abs() / denom

    # QA flags (Stage 2) carried through as an informational, non-filtering signal: what
    # fraction of readings behind each station-day mean were flagged Suspicious upstream.
    if "qa_flag_any" in obs.columns:
        qa_frac = obs.groupby(gcols, dropna=False)["qa_flag_any"].mean().rename("qa_flagged_frac").reset_index()
        qa_frac["sample_date"] = pd.to_datetime(qa_frac["sample_date"])
        daily = daily.merge(qa_frac, on=gcols, how="left")
    else:
        daily["qa_flagged_frac"] = np.nan

    mean_cols = [f"{c}__mean" for c in usable]

    # Campaign and station anomalies / z-scores on daily means
    for c in usable:
        mcol = f"{c}__mean"
        camp_mean = daily[mcol].mean()
        camp_std = daily[mcol].std(ddof=0) + 1e-12
        daily[f"{c}__anom_campaign"] = daily[mcol] - camp_mean
        daily[f"{c}__z_campaign"] = daily[f"{c}__anom_campaign"] / camp_std
        daily[f"{c}__anom_station"] = daily.groupby("station")[mcol].transform(lambda s: s - s.mean())
        daily[f"{c}__z_station"] = daily.groupby("station")[mcol].transform(
            lambda s: (s - s.mean()) / (s.std(ddof=0) + 1e-12)
        )

    # Rolling 3-day and lag/diff by station
    for c in usable:
        mcol = f"{c}__mean"
        daily[f"{c}__roll3_mean"] = daily.groupby("station")[mcol].transform(
            lambda s: s.rolling(3, min_periods=1).mean()
        )
        daily[f"{c}__roll3_std"] = daily.groupby("station")[mcol].transform(
            lambda s: s.rolling(3, min_periods=1).std()
        )
        daily[f"{c}__lag1"] = daily.groupby("station")[mcol].shift(1)
        daily[f"{c}__d1"] = daily.groupby("station")[mcol].diff(1)

    # Physically motivated indices (only if ingredients exist)
    index_cols: list[str] = []
    if {"temperature_c__mean", "do_mg_l__mean"}.issubset(daily.columns):
        # Higher when warm and oxygen-poor (both z-scored)
        daily["idx_do_solubility_stress"] = daily["temperature_c__z_station"] - daily["do_mg_l__z_station"]
        index_cols.append("idx_do_solubility_stress")
    if {"salinity_psu__mean", "turbidity_fnu__mean"}.issubset(daily.columns):
        daily["idx_mixing_contrast"] = daily["salinity_psu__z_station"] * daily["turbidity_fnu__z_station"]
        index_cols.append("idx_mixing_contrast")
    if {"ph__mean", "temperature_c__mean"}.issubset(daily.columns):
        daily["idx_carbonate_thermal"] = daily["ph__z_station"] * daily["temperature_c__z_station"]
        index_cols.append("idx_carbonate_thermal")
    if {"do_mg_l__mean", "do_sat_pct__mean"}.issubset(daily.columns):
        # Residual of DO% after linear coupling to DO mg/L (campaign fit)
        x = daily["do_mg_l__mean"].to_numpy()
        y = daily["do_sat_pct__mean"].to_numpy()
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() >= 10:
            coef = np.polyfit(x[mask], y[mask], 1)
            yhat = coef[0] * daily["do_mg_l__mean"] + coef[1]
            daily["idx_do_sat_gap"] = daily["do_sat_pct__mean"] - yhat
            index_cols.append("idx_do_sat_gap")

    # Feature catalog
    catalog_rows = []
    for c in usable:
        for kind, note in [
            ("mean", FEATURE_DICTIONARY["daily_mean"]),
            ("median", FEATURE_DICTIONARY["daily_median"]),
            ("std", FEATURE_DICTIONARY["daily_std"]),
            ("range", FEATURE_DICTIONARY["daily_range"]),
            ("anom_station", FEATURE_DICTIONARY["anom_station"]),
            ("anom_campaign", FEATURE_DICTIONARY["anom_campaign"]),
            ("z_station", FEATURE_DICTIONARY["z_station"]),
            ("roll3_mean", FEATURE_DICTIONARY["roll3_mean"]),
            ("roll3_std", FEATURE_DICTIONARY["roll3_std"]),
            ("d1", FEATURE_DICTIONARY["d1"]),
            ("lag1", FEATURE_DICTIONARY["lag1"]),
        ]:
            catalog_rows.append(
                {
                    "feature": f"{c}__{kind}" if kind != "mean" else f"{c}__mean",
                    "base_variable": c,
                    "family": kind if kind != "mean" else "daily_mean",
                    "physical_interpretation": note,
                    "level": "station_day",
                }
            )
    for ic in index_cols:
        key = ic.replace("idx_", "")
        catalog_rows.append(
            {
                "feature": ic,
                "base_variable": "interaction",
                "family": "environmental_index",
                "physical_interpretation": FEATURE_DICTIONARY.get(key, "Environmental index"),
                "level": "station_day",
            }
        )
    catalog = pd.DataFrame(catalog_rows)

    # Analysis matrix for Stage 5/6: prefer stationary, comparable features
    analysis_cols = (
        [f"{c}__mean" for c in usable]
        + [f"{c}__std" for c in usable]
        + [f"{c}__anom_station" for c in usable]
        + [f"{c}__d1" for c in usable]
        + index_cols
    )
    analysis_cols = [c for c in analysis_cols if c in daily.columns]
    feature_matrix = daily[["station", "sample_date"] + analysis_cols].copy()

    # Figures
    fig_paths: dict[str, str] = {}
    # Heatmap of station-day means for salinity/temp/do/turbidity
    show_vars = [c for c in ["salinity_psu", "temperature_c", "do_mg_l", "turbidity_fnu", "ph"] if c in usable]
    if show_vars:
        fig, axes = plt.subplots(1, len(show_vars), figsize=(3.2 * len(show_vars), 6), sharey=True)
        if len(show_vars) == 1:
            axes = [axes]
        for ax, c in zip(axes, show_vars):
            pivot = daily.pivot(index="sample_date", columns="station", values=f"{c}__mean")
            sns.heatmap(pivot, ax=ax, cmap="viridis", cbar_kws={"label": c})
            ax.set_title(c)
            ax.set_xlabel("")
        fig.suptitle("Stage 4 — Daily mean environmental fields", y=1.02)
        fig.tight_layout()
        p = fig_dir / "fig_stage04_daily_mean_heatmaps.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["daily_mean_heatmaps"] = str(p)

    if index_cols:
        fig, ax = plt.subplots(figsize=(9, 4))
        plot_df = daily.melt(
            id_vars=["station", "sample_date"],
            value_vars=index_cols,
            var_name="index",
            value_name="value",
        )
        sns.boxplot(data=plot_df, x="index", y="value", hue="station", ax=ax)
        ax.tick_params(axis="x", rotation=20)
        ax.set_title("Stage 4 — Environmental indices by station")
        fig.tight_layout()
        p2 = fig_dir / "fig_stage04_indices_by_station.png"
        fig.savefig(p2, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["indices"] = str(p2)

    # Family counts
    family_counts = catalog["family"].value_counts().to_dict()

    # Mean-vs-median divergence diagnostic: flags station-days where a mean-based
    # feature is likely being pulled by a small number of extreme readings (spikes),
    # so this is visible before it silently shapes Stage 5/6 downstream results.
    rel_gap_cols = [f"{c}__mean_median_rel_gap" for c in usable if f"{c}__mean_median_rel_gap" in daily.columns]
    spike_sensitive_station_days = []
    if rel_gap_cols:
        worst_gap = daily[rel_gap_cols].max(axis=1)
        flagged = worst_gap[worst_gap >= 0.20]
        for idx in flagged.index:
            row = daily.loc[idx]
            worst_var = daily.loc[idx, rel_gap_cols].astype(float).idxmax().replace("__mean_median_rel_gap", "")
            spike_sensitive_station_days.append(
                {
                    "station": str(row["station"]),
                    "sample_date": str(row["sample_date"]),
                    "variable": worst_var,
                    "mean": float(row[f"{worst_var}__mean"]),
                    "median": float(row[f"{worst_var}__median"]),
                    "rel_gap": float(row[f"{worst_var}__mean_median_rel_gap"]),
                }
            )

    qa_flagged_frac_mean = float(daily["qa_flagged_frac"].mean()) if daily["qa_flagged_frac"].notna().any() else None

    report = {
        "n_station_days": int(len(daily)),
        "n_base_variables_used": len(usable),
        "base_variables_used": usable,
        "base_variables_dropped_constant": dropped_constant,
        "n_catalog_features": int(len(catalog)),
        "n_analysis_features": len(analysis_cols),
        "analysis_features": analysis_cols,
        "index_features": index_cols,
        "family_counts": family_counts,
        "n_spike_sensitive_station_days": len(spike_sensitive_station_days),
        "spike_sensitive_station_days": spike_sensitive_station_days,
        "qa_flagged_frac_campaign_mean": qa_flagged_frac_mean,
        "design_rules": [
            "Every engineered feature has an explicit physical interpretation in the catalog.",
            "No rainfall/tide/external drivers invented; those belong to Stage 10 if available.",
            "Constant channels are not engineered.",
            "Analysis matrix emphasizes means, within-cast std, station anomalies, day-to-day changes, and indices.",
            "Median and mean-vs-median relative gap are computed for every base variable as a "
            "spike-robustness diagnostic, but the analysis matrix still uses the mean family "
            "for continuity with Stage 5/6; see spike_sensitive_station_days before trusting "
            "mean-based features on days with a large gap.",
        ],
        "figures": fig_paths,
    }

    daily_path = output_dir / "stage04_station_day_features.csv"
    matrix_path = output_dir / "stage04_feature_matrix.csv"
    catalog_path = output_dir / "stage04_feature_catalog.csv"
    report_path = output_dir / "stage04_feature_report.json"
    parquet_path = output_dir / "stage04_station_day_features.parquet"

    daily.to_csv(daily_path, index=False)
    feature_matrix.to_csv(matrix_path, index=False)
    catalog.to_csv(catalog_path, index=False)
    try:
        daily.to_parquet(parquet_path, index=False)
        report["outputs_parquet"] = str(parquet_path)
    except Exception:
        report["outputs_parquet"] = None
    report["outputs"] = {
        "station_day_features": str(daily_path),
        "feature_matrix": str(matrix_path),
        "catalog": str(catalog_path),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {
        "daily_features": daily,
        "feature_matrix": feature_matrix,
        "catalog": catalog,
        "analysis_features": analysis_cols,
        "report": report,
    }
