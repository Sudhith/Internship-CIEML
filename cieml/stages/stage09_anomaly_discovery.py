"""Stage 9: Multi-method anomaly discovery with physical categorization."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import DBSCAN
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor, NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from cieml.config import PHASE5_DIR
from cieml.anomalies.origin import assign_probable_origins
from cieml.failure import build_failure_report

RANDOM_STATE = 42
CONTAMINATION_GRID = [0.03, 0.05, 0.07, 0.08, 0.10, 0.12, 0.15]


def _feature_cols(df: pd.DataFrame) -> list[str]:
    skip = {
        "station", "sample_date", "regime", "regime_algorithm", "regime_k",
        "pc1", "pc2", "consensus_regime",
    }
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]


def _detector_agreement(X: np.ndarray, contamination: float, n: int) -> float:
    """Mean pairwise label agreement among independent detectors at this contamination."""
    labels = []
    try:
        labels.append(
            IsolationForest(n_estimators=200, contamination=contamination, random_state=RANDOM_STATE).fit_predict(X)
        )
    except Exception:
        pass
    try:
        labels.append(
            LocalOutlierFactor(n_neighbors=min(20, max(5, n // 10)), contamination=contamination).fit_predict(X)
        )
    except Exception:
        pass
    try:
        labels.append(EllipticEnvelope(contamination=contamination, random_state=RANDOM_STATE).fit_predict(X))
    except Exception:
        pass
    if len(labels) < 2:
        return float("nan")
    pairs = [float((labels[i] == labels[j]).mean()) for i in range(len(labels)) for j in range(i + 1, len(labels))]
    return float(np.mean(pairs))


def run_stage09(labeled: pd.DataFrame, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE5_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    feat_cols = _feature_cols(labeled)
    df = labeled.dropna(subset=feat_cols).reset_index(drop=True).copy()
    X = StandardScaler().fit_transform(df[feat_cols].to_numpy(dtype=float))
    n = len(df)

    # Contamination genuinely rediscovered from data: search a small grid and pick the
    # value where independent detectors (Isolation Forest, LOF, Elliptic Envelope) agree
    # most on which points are anomalous. A "fraction of scores above the 90th percentile"
    # trick always returns ~10% by construction regardless of the data, so it doesn't
    # actually discover anything about this dataset — cross-detector agreement does.
    grid_scores = {c: _detector_agreement(X, c, n) for c in CONTAMINATION_GRID}
    valid = {c: s for c, s in grid_scores.items() if np.isfinite(s)}
    contamination = max(valid, key=valid.get) if valid else 0.05

    methods = {}
    methods["isolation_forest"] = IsolationForest(
        n_estimators=400, contamination=contamination, random_state=RANDOM_STATE
    ).fit_predict(X)
    methods["lof"] = LocalOutlierFactor(n_neighbors=min(20, max(5, n // 10)), contamination=contamination).fit_predict(X)
    methods["one_class_svm"] = OneClassSVM(kernel="rbf", gamma="scale", nu=contamination).fit_predict(X)
    try:
        methods["elliptic_envelope"] = EllipticEnvelope(
            contamination=contamination, random_state=RANDOM_STATE
        ).fit_predict(X)
    except Exception:
        methods["elliptic_envelope"] = np.ones(n, dtype=int)

    # DBSCAN eps from k-distance percentile
    nn = NearestNeighbors(n_neighbors=min(5, n - 1)).fit(X)
    dists, _ = nn.kneighbors(X)
    eps = float(np.percentile(np.sort(dists[:, -1]), 85))
    db = DBSCAN(eps=eps, min_samples=5).fit_predict(X)
    methods["dbscan_noise"] = np.where(db == -1, -1, 1)

    # Convert to anomaly boolean (sklearn: -1 = anomaly)
    flag_df = df[["station", "sample_date"]].copy() if set(["station", "sample_date"]).issubset(df.columns) else pd.DataFrame(index=df.index)
    if "regime" in df.columns:
        flag_df["regime"] = df["regime"].values
    for name, labels in methods.items():
        flag_df[f"anom_{name}"] = (np.asarray(labels) == -1).astype(int)

    method_cols = [c for c in flag_df.columns if c.startswith("anom_")]
    flag_df["n_methods_flagged"] = flag_df[method_cols].sum(axis=1)
    # Consensus: flagged by >= 2 methods
    flag_df["anomaly_consensus"] = (flag_df["n_methods_flagged"] >= 2).astype(int)

    # Categorize consensus anomalies
    categories = []
    global_z = (df[feat_cols] - df[feat_cols].mean()) / (df[feat_cols].std(ddof=0) + 1e-12)
    for idx in flag_df.index[flag_df["anomaly_consensus"] == 1]:
        row = df.loc[idx]
        zrow = global_z.loc[idx]
        top = zrow.abs().sort_values(ascending=False).head(3)
        station = str(row["station"]) if "station" in df.columns else "UNKNOWN"
        date = str(row["sample_date"]) if "sample_date" in df.columns else None
        regime = int(row["regime"]) if "regime" in df.columns else None

        # Station-specific if this station has elevated anomaly rate
        station_rate = float(flag_df.loc[flag_df["station"] == station, "anomaly_consensus"].mean()) if "station" in flag_df.columns else np.nan
        campaign_rate = float(flag_df["anomaly_consensus"].mean())
        if np.isfinite(station_rate) and station_rate >= max(0.15, 2 * campaign_rate):
            spatial = "station_specific"
        else:
            spatial = "global"

        # Temporal: day with many anomalies
        if "sample_date" in flag_df.columns:
            day_rate = float(flag_df.loc[flag_df["sample_date"] == date, "anomaly_consensus"].mean())
            temporal = "temporal_event" if day_rate >= max(0.25, 2 * campaign_rate) else "isolated_in_time"
        else:
            temporal = "unknown"

        # Sensor vs environmental heuristic: extreme turbidity/zeros with QA-like patterns
        dominant = str(top.index[0])
        if "turbidity" in dominant and abs(float(top.iloc[0])) >= 3:
            nature = "environmental_or_optical_spike"
        elif "do_" in dominant and abs(float(top.iloc[0])) >= 3:
            nature = "oxygen_regime_excursion"
        elif "salinity" in dominant or "spcond" in dominant:
            nature = "salinity_mixing_excursion"
        elif "ph" in dominant:
            nature = "carbonate_ph_excursion"
        else:
            nature = "multivariate_outlier"

        categories.append(
            {
                "station": station,
                "sample_date": date,
                "regime": regime,
                "n_methods_flagged": int(flag_df.loc[idx, "n_methods_flagged"]),
                "spatial_class": spatial,
                "temporal_class": temporal,
                "physical_class": nature,
                "top_feature": dominant,
                "top_feature_z": float(top.iloc[0]),
                "top3_features": ", ".join([f"{k}:{float(v):+.2f}" for k, v in top.items()]),
                "interpretation": (
                    f"{spatial}/{temporal}: {nature} driven mainly by {dominant} "
                    f"(z={float(top.iloc[0]):+.2f}). Consensus of {int(flag_df.loc[idx, 'n_methods_flagged'])} detectors."
                ),
            }
        )
    cat_df = pd.DataFrame(categories)
    # Phase I — probable origin taxonomy (sensor/environmental/temporal/...)
    if len(cat_df):
        cat_df = assign_probable_origins(cat_df)

    # H5 provisional: anomalies exist with multi-method consensus; external validation is Stage 10
    n_consensus = int(flag_df["anomaly_consensus"].sum())
    if n_consensus > 0 and len(cat_df):
        h5_status, h5_verdict = "PROVISIONAL_SUPPORT", "lean_alternative_pending_external_validation"
    else:
        h5_status, h5_verdict = "MIXED_EVIDENCE", "exploratory"

    # Figures
    fig_paths = {}
    rates = {c.replace("anom_", ""): float(flag_df[c].mean()) for c in method_cols}
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(x=list(rates.keys()), y=list(rates.values()), ax=ax, color="#1f4e79")
    ax.set_ylabel("Anomaly fraction")
    ax.set_title(f"Stage 9 — Detector rates (contamination≈{contamination:.2f})")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = fig_dir / "fig_stage09_detector_rates.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["detector_rates"] = str(p)

    if "pc1" in df.columns and "pc2" in df.columns:
        plot_df = df.copy()
        plot_df["anomaly_consensus"] = flag_df["anomaly_consensus"].values
        fig, ax = plt.subplots(figsize=(7, 5))
        sns.scatterplot(
            data=plot_df, x="pc1", y="pc2", hue="anomaly_consensus",
            style="station" if "station" in plot_df.columns else None,
            palette={0: "#9aa0a6", 1: "#c62828"}, ax=ax, s=45
        )
        ax.set_title("Stage 9 — Consensus anomalies in PCA space")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        fig.tight_layout()
        p2 = fig_dir / "fig_stage09_pca_anomalies.png"
        fig.savefig(p2, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["pca_anomalies"] = str(p2)

    if len(cat_df) and "station" in cat_df.columns:
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.countplot(data=cat_df, x="station", hue="physical_class", ax=ax)
        ax.set_title("Stage 9 — Consensus anomaly physical classes by station")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        p3 = fig_dir / "fig_stage09_anomaly_classes.png"
        fig.savefig(p3, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["anomaly_classes"] = str(p3)

    if "sample_date" in flag_df.columns:
        daily = flag_df.groupby("sample_date")["anomaly_consensus"].mean().reset_index()
        fig, ax = plt.subplots(figsize=(9, 3.5))
        ax.plot(pd.to_datetime(daily["sample_date"]), daily["anomaly_consensus"], marker="o", color="#c62828")
        ax.set_ylabel("Consensus anomaly rate")
        ax.set_title("Stage 9 — Temporal anomaly rate")
        fig.autofmt_xdate()
        fig.tight_layout()
        p4 = fig_dir / "fig_stage09_temporal_rate.png"
        fig.savefig(p4, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["temporal_rate"] = str(p4)

    # SC-FMF: Anomaly Intelligence failure assessment. anom_zero_consensus is
    # locally evaluable here; anom_no_external_validation needs Stage 10's
    # anomaly_external_support_frac (not yet computed — Stage 10 runs after
    # Stage 9) and is soft-skipped here. Stage 10 runs a supplementary check
    # once that evidence exists and Stage 14 consolidates both into one
    # final anomaly_intelligence failure report.
    failure_bundle = {"n_consensus_anomalies": n_consensus}
    failure_report = build_failure_report("anomaly_intelligence", failure_bundle)

    report = {
        "n_samples": int(n),
        "contamination_used": contamination,
        "contamination_selection": "grid search maximizing cross-detector agreement (Isolation Forest / LOF / Elliptic Envelope)",
        "contamination_grid_scores": {str(c): (s if np.isfinite(s) else None) for c, s in grid_scores.items()},
        "method_rates": rates,
        "n_consensus_anomalies": n_consensus,
        "consensus_rate": float(flag_df["anomaly_consensus"].mean()),
        "category_counts": cat_df["physical_class"].value_counts().to_dict() if len(cat_df) else {},
        "origin_primary_counts": cat_df["origin_primary"].value_counts().to_dict() if len(cat_df) and "origin_primary" in cat_df.columns else {},
        "h5_update": {
            "hypothesis": "H5_anomaly_reality",
            "status": h5_status,
            "verdict_lean": h5_verdict,
            "note": "Multi-method consensus anomalies identified; Stage 10 external drivers required for definitive environmental validation.",
        },
        "failure_report": failure_report,
        "figures": fig_paths,
    }

    flag_df.to_csv(output_dir / "stage09_anomaly_flags.csv", index=False)
    cat_df.to_csv(output_dir / "stage09_anomaly_catalog.csv", index=False)
    report_path = output_dir / "stage09_anomaly_report.json"
    report["outputs"] = {
        "flags": str(output_dir / "stage09_anomaly_flags.csv"),
        "catalog": str(output_dir / "stage09_anomaly_catalog.csv"),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (output_dir / "stage09_failure_report.json").write_text(
        json.dumps(failure_report, indent=2, default=str), encoding="utf-8"
    )

    return {"flags": flag_df, "catalog": cat_df, "report": report, "failure_report": failure_report}


