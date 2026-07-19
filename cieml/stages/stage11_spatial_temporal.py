"""Stage 11: Spatial similarity, temporal evolution, and coastline dynamics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from scipy import stats
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from cieml.config import CONFIG_DIR, PHASE6_DIR


def _campaign_region() -> dict:
    try:
        from cieml.domain import load_campaign
        camp = load_campaign()
        region = dict(camp.region or {})
        if region.get('latitude') is not None:
            return region
    except Exception:
        pass
    path = CONFIG_DIR / "stations.yaml"
    if path.exists():
        import yaml
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return dict(raw.get("campaign_region") or {})
    return {"latitude": 17.72, "longitude": 83.30}


def _feat_cols(df: pd.DataFrame) -> list[str]:
    skip = {"station", "sample_date", "regime", "regime_algorithm", "regime_k", "pc1", "pc2", "consensus_regime"}
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]


def _load_station_coords() -> pd.DataFrame:
    """Prefer campaign profile stations; fall back to legacy stations.yaml."""
    stations: dict = {}
    try:
        from cieml.domain import load_campaign

        stations = dict(load_campaign().stations or {})
    except Exception:
        stations = {}
    if not stations:
        path = CONFIG_DIR / "stations.yaml"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
            stations = dict(meta.get("stations") or {})
    rows = []
    for name, info in stations.items():
        info = info or {}
        rows.append({"station": name, "latitude": info.get("latitude"), "longitude": info.get("longitude")})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["station", "latitude", "longitude"])


def run_stage11(regime_labels: pd.DataFrame, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE6_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = regime_labels.copy()
    df["sample_date"] = pd.to_datetime(df["sample_date"])
    feat_cols = _feat_cols(df)

    # --- Station fingerprints (campaign mean profile, z-scored) ---
    station_mean = df.groupby("station")[feat_cols].mean()
    z = (station_mean - station_mean.mean()) / (station_mean.std(ddof=0) + 1e-12)
    fingerprints = z.reset_index()

    # --- Station similarity (1 - corr of mean profiles; also euclidean on z) ---
    corr = station_mean.T.corr()
    sim = corr.copy()
    dist = 1 - corr
    np.fill_diagonal(dist.values, 0)

    # Hierarchical clustering of stations
    condensed = squareform(dist.values, checks=False)
    Z = linkage(condensed, method="average")

    # --- Network edges from similarity threshold: campaign mean pairwise similarity ---
    thr = float(sim.values[np.triu_indices_from(sim.values, k=1)].mean())
    edges = []
    stations = list(sim.index)
    for i, a in enumerate(stations):
        for b in stations[i + 1 :]:
            w = float(sim.loc[a, b])
            if w >= thr:
                edges.append({"source": a, "target": b, "weight": w})
    edges_df = pd.DataFrame(edges)

    # --- Temporal regime transitions ---
    trans_rows = []
    if "regime" in df.columns:
        for station, g in df.sort_values("sample_date").groupby("station"):
            regs = g["regime"].to_numpy()
            dates = g["sample_date"].to_numpy()
            for i in range(1, len(regs)):
                if regs[i] != regs[i - 1]:
                    trans_rows.append(
                        {
                            "station": station,
                            "date_from": pd.Timestamp(dates[i - 1]).strftime("%Y-%m-%d"),
                            "date_to": pd.Timestamp(dates[i]).strftime("%Y-%m-%d"),
                            "regime_from": int(regs[i - 1]),
                            "regime_to": int(regs[i]),
                        }
                    )
        # Transition matrix overall
        labs = sorted(df["regime"].dropna().unique())
        mat = pd.DataFrame(0, index=labs, columns=labs, dtype=float)
        for station, g in df.sort_values("sample_date").groupby("station"):
            regs = g["regime"].to_list()
            for a, b in zip(regs[:-1], regs[1:]):
                mat.loc[a, b] += 1
        # row-normalize
        trans_mat = mat.div(mat.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    else:
        trans_mat = pd.DataFrame()
    transitions = pd.DataFrame(trans_rows)

    # --- Environmental trajectories in PCA ---
    X = StandardScaler().fit_transform(df[feat_cols].to_numpy(dtype=float))
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(X)
    traj = df[["station", "sample_date"]].copy()
    if "regime" in df.columns:
        traj["regime"] = df["regime"].values
    traj["pc1"] = xy[:, 0]
    traj["pc2"] = xy[:, 1]

    # Spatial gradient proxy: correlate station mean features with latitude/longitude.
    # Every other correlation in this codebase (stage03, stage05, stage10) reports a
    # p-value alongside rho; this one previously didn't, and with only as many points as
    # there are stations (6 here), |rho| can swing close to 1 from sampling noise alone —
    # so an unpaired rho ranking invites over-reading a "coastline gradient" from noise.
    coords = _load_station_coords()
    gradient_rows = []
    if len(coords):
        merged = station_mean.reset_index().merge(coords, on="station", how="inner")
        n_stations_with_coords = int(len(merged))
        for c in feat_cols:
            for axis in ["latitude", "longitude"]:
                if merged[axis].nunique() < 2:
                    continue
                rho, p = stats.spearmanr(merged[c], merged[axis])
                gradient_rows.append(
                    {
                        "feature": c,
                        "axis": axis,
                        "spearman_rho": float(rho),
                        "p": float(p),
                        "n": n_stations_with_coords,
                        "significant_05": bool(p < 0.05),
                    }
                )
    gradients = pd.DataFrame(gradient_rows)

    # Figures
    fig_paths: dict[str, str] = {}

    fig, ax = plt.subplots(figsize=(7, 5))
    sns.heatmap(sim, annot=True, fmt=".2f", cmap="viridis", vmin=0, vmax=1, ax=ax)
    ax.set_title("Stage 11 — Station similarity (profile correlation)")
    fig.tight_layout()
    p = fig_dir / "fig_stage11_station_similarity.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["station_similarity"] = str(p)

    fig, ax = plt.subplots(figsize=(8, 4))
    dendrogram(Z, labels=list(sim.index), leaf_rotation=30, ax=ax)
    ax.set_title("Stage 11 — Station hierarchical clustering")
    fig.tight_layout()
    p2 = fig_dir / "fig_stage11_station_dendrogram.png"
    fig.savefig(p2, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["dendrogram"] = str(p2)

    # Fingerprint heatmap
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sns.heatmap(z, cmap="RdBu_r", center=0, ax=ax)
    ax.set_title("Stage 11 — Station environmental fingerprints (z-scores)")
    fig.tight_layout()
    p3 = fig_dir / "fig_stage11_station_fingerprints.png"
    fig.savefig(p3, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["fingerprints"] = str(p3)

    # Trajectories by station
    fig, ax = plt.subplots(figsize=(8, 6))
    for station, g in traj.sort_values("sample_date").groupby("station"):
        ax.plot(g["pc1"], g["pc2"], alpha=0.35, lw=1, label=None)
        ax.scatter(g["pc1"], g["pc2"], s=18, label=station)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title("Stage 11 — Environmental trajectories (PCA)")
    ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    p4 = fig_dir / "fig_stage11_trajectories.png"
    fig.savefig(p4, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["trajectories"] = str(p4)

    if len(trans_mat):
        fig, ax = plt.subplots(figsize=(5, 4))
        sns.heatmap(trans_mat, annot=True, fmt=".2f", cmap="Blues", ax=ax)
        ax.set_title("Stage 11 — Regime transition probabilities")
        ax.set_xlabel("To regime")
        ax.set_ylabel("From regime")
        fig.tight_layout()
        p5 = fig_dir / "fig_stage11_regime_transitions.png"
        fig.savefig(p5, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["transitions"] = str(p5)

    # Temporal heatmap: salinity or DO by station×date
    for var, label in [("salinity_psu__mean", "salinity"), ("do_mg_l__mean", "do"), ("turbidity_fnu__mean", "turbidity")]:
        if var not in df.columns:
            continue
        pivot = df.pivot_table(index="sample_date", columns="station", values=var, aggfunc="mean")
        fig, ax = plt.subplots(figsize=(9, 6))
        sns.heatmap(pivot, cmap="viridis", ax=ax)
        ax.set_title(f"Stage 11 — Temporal field: {label}")
        fig.tight_layout()
        fp = fig_dir / f"fig_stage11_heatmap_{label}.png"
        fig.savefig(fp, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths[f"heatmap_{label}"] = str(fp)

    # Network-style layout using coords if available
    if len(coords) and len(edges_df):
        fig, ax = plt.subplots(figsize=(7, 6))
        c = coords.set_index("station")
        for _, e in edges_df.iterrows():
            if e["source"] in c.index and e["target"] in c.index:
                ax.plot(
                    [c.loc[e["source"], "longitude"], c.loc[e["target"], "longitude"]],
                    [c.loc[e["source"], "latitude"], c.loc[e["target"], "latitude"]],
                    color="steelblue",
                    lw=1 + 3 * e["weight"],
                    alpha=0.6,
                )
        ax.scatter(c["longitude"], c["latitude"], s=80, c="#c62828", zorder=5)
        for st, row in c.iterrows():
            ax.text(row["longitude"], row["latitude"], st, fontsize=7, ha="left", va="bottom")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("Stage 11 — Station similarity network")
        fig.tight_layout()
        p6 = fig_dir / "fig_stage11_similarity_network.png"
        fig.savefig(p6, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["network"] = str(p6)

    report = {
        "n_stations": int(df["station"].nunique()),
        "n_days": int(df["sample_date"].nunique()),
        "similarity_threshold_used": thr,
        "n_network_edges": int(len(edges_df)),
        "n_regime_transitions": int(len(transitions)),
        "pca_var_explained": [float(x) for x in pca.explained_variance_ratio_],
        "strongest_spatial_gradients": gradients.reindex(gradients["spearman_rho"].abs().sort_values(ascending=False).index).head(6).to_dict(orient="records") if len(gradients) else [],
        "spatial_gradient_caveat": (
            f"Correlated against n={int(df['station'].nunique())} stations only — |rho| can swing "
            "close to 1 from sampling noise alone at this sample size; treat unsignificant rows "
            "(significant_05=false) as not distinguishable from noise, not as a real gradient."
        ),
        "figures": fig_paths,
    }

    fingerprints.to_csv(output_dir / "stage11_station_fingerprints.csv", index=False)
    sim.to_csv(output_dir / "stage11_station_similarity.csv")
    edges_df.to_csv(output_dir / "stage11_similarity_network_edges.csv", index=False)
    transitions.to_csv(output_dir / "stage11_regime_transitions.csv", index=False)
    if len(trans_mat):
        trans_mat.to_csv(output_dir / "stage11_transition_matrix.csv")
    traj.to_csv(output_dir / "stage11_pca_trajectories.csv", index=False)
    if len(gradients):
        gradients.to_csv(output_dir / "stage11_spatial_gradients.csv", index=False)
    report_path = output_dir / "stage11_spatial_temporal_report.json"
    report["outputs"] = {"fingerprints": str(output_dir / "stage11_station_fingerprints.csv")}
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {
        "fingerprints": fingerprints,
        "similarity": sim,
        "edges": edges_df,
        "transitions": transitions,
        "trajectories": traj,
        "gradients": gradients,
        "report": report,
    }
