"""Stage 6: Multi-algorithm environmental regime discovery (no assumed K or method)."""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans, SpectralClustering
from sklearn.decomposition import PCA
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from cieml.config import PHASE4_DIR
from cieml.failure import build_failure_report
from cieml.discovery.api import build_selection_trace, discovery_contract_block

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import hdbscan  # type: ignore
    HAS_HDBSCAN = True
except Exception:
    HAS_HDBSCAN = False

K_RANGE = range(2, 9)
RANDOM_STATE = 42
N_STABILITY = 20


def _valid_labels(labels: np.ndarray) -> bool:
    labs = labels[labels >= 0]
    return len(np.unique(labs)) >= 2 and len(labs) >= 10


def _scores(X: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    if not _valid_labels(labels):
        return {"silhouette": np.nan, "davies_bouldin": np.nan, "calinski_harabasz": np.nan, "n_clusters": 0, "noise_frac": 1.0}
    mask = labels >= 0
    lab = labels[mask]
    Xm = X[mask]
    n_clust = int(len(np.unique(lab)))
    if n_clust < 2 or len(Xm) < n_clust + 1:
        return {"silhouette": np.nan, "davies_bouldin": np.nan, "calinski_harabasz": np.nan, "n_clusters": n_clust, "noise_frac": float((labels < 0).mean())}
    return {
        "silhouette": float(silhouette_score(Xm, lab)),
        "davies_bouldin": float(davies_bouldin_score(Xm, lab)),
        "calinski_harabasz": float(calinski_harabasz_score(Xm, lab)),
        "n_clusters": n_clust,
        "noise_frac": float((labels < 0).mean()),
    }


def _gap_statistic(X: np.ndarray, labels: np.ndarray, n_refs: int = 10) -> float:
    """Simplified gap statistic vs uniform reference in bounding box."""
    if not _valid_labels(labels):
        return np.nan
    mask = labels >= 0
    Xm, lab = X[mask], labels[mask]
    try:
        from sklearn.metrics import pairwise_distances
    except Exception:
        return np.nan

    def wk(data, labs):
        tot = 0.0
        for k in np.unique(labs):
            pts = data[labs == k]
            if len(pts) < 2:
                continue
            d = pairwise_distances(pts)
            tot += np.sum(d) / (2.0 * len(pts))
        return tot

    w_obs = wk(Xm, lab)
    mins, maxs = Xm.min(axis=0), Xm.max(axis=0)
    ref_logs = []
    rng = np.random.default_rng(RANDOM_STATE)
    k = len(np.unique(lab))
    for i in range(n_refs):
        ref = rng.uniform(mins, maxs, size=Xm.shape)
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE + i)
        ref_lab = km.fit_predict(ref)
        ref_logs.append(np.log(wk(ref, ref_lab) + 1e-12))
    return float(np.mean(ref_logs) - np.log(w_obs + 1e-12))


def _fit_candidates(X: np.ndarray) -> list[dict[str, Any]]:
    results = []

    for k in K_RANGE:
        # KMeans
        lab = KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE).fit_predict(X)
        sc = _scores(X, lab)
        results.append({"algorithm": "kmeans", "k": k, "labels": lab, **sc, "bic": np.nan, "gap": _gap_statistic(X, lab)})

        # Ward hierarchical via sklearn
        lab = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)
        sc = _scores(X, lab)
        results.append({"algorithm": "ward", "k": k, "labels": lab, **sc, "bic": np.nan, "gap": _gap_statistic(X, lab)})

        # Average linkage agglomerative
        lab = AgglomerativeClustering(n_clusters=k, linkage="average", metric="euclidean").fit_predict(X)
        sc = _scores(X, lab)
        results.append({"algorithm": "agglomerative_average", "k": k, "labels": lab, **sc, "bic": np.nan, "gap": np.nan})

        # GMM
        gmm = GaussianMixture(n_components=k, covariance_type="full", random_state=RANDOM_STATE, n_init=5)
        lab = gmm.fit_predict(X)
        sc = _scores(X, lab)
        results.append({"algorithm": "gmm", "k": k, "labels": lab, **sc, "bic": float(gmm.bic(X)), "gap": np.nan})

        # Spectral
        try:
            lab = SpectralClustering(
                n_clusters=k, affinity="nearest_neighbors", random_state=RANDOM_STATE, n_neighbors=min(10, len(X) - 1)
            ).fit_predict(X)
            sc = _scores(X, lab)
            results.append({"algorithm": "spectral", "k": k, "labels": lab, **sc, "bic": np.nan, "gap": np.nan})
        except Exception:
            pass

    # DBSCAN: choose eps from k-distance elbow heuristic
    nn = NearestNeighbors(n_neighbors=min(5, len(X) - 1)).fit(X)
    dists, _ = nn.kneighbors(X)
    kdist = np.sort(dists[:, -1])
    # candidate eps at percentiles
    for pct in [70, 80, 90]:
        eps = float(np.percentile(kdist, pct))
        lab = DBSCAN(eps=eps, min_samples=5).fit_predict(X)
        sc = _scores(X, lab)
        results.append({"algorithm": "dbscan", "k": sc["n_clusters"], "labels": lab, **sc, "bic": np.nan, "gap": np.nan, "eps": eps, "eps_pct": pct})

    if HAS_HDBSCAN:
        for mcs in [5, 10, 15]:
            clusterer = hdbscan.HDBSCAN(min_cluster_size=mcs, min_samples=5)
            lab = clusterer.fit_predict(X)
            sc = _scores(X, lab)
            results.append({"algorithm": "hdbscan", "k": sc["n_clusters"], "labels": lab, **sc, "bic": np.nan, "gap": np.nan, "min_cluster_size": mcs})

    return results


def _stability_ari(X: np.ndarray, algorithm: str, k: int, n_boot: int = N_STABILITY) -> float:
    from sklearn.metrics import adjusted_rand_score

    rng = np.random.default_rng(RANDOM_STATE)
    aris = []
    n = len(X)
    base = _fit_one(X, algorithm, k)
    if base is None or not _valid_labels(base):
        return np.nan
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        Xb = X[idx]
        lab_b = _fit_one(Xb, algorithm, k)
        if lab_b is None or not _valid_labels(lab_b):
            continue
        # compare on unique bootstrap indices mapped back is messy; compare subsample labels via refit on full with same seed pattern
        # Instead: fit on bootstrap sample, predict nearest centroid assignment for full X when possible
        try:
            if algorithm in {"kmeans", "gmm", "ward", "agglomerative_average", "spectral"}:
                # Refit on bootstrap, assign full data by nearest cluster center from bootstrap fit
                centers = []
                for c in np.unique(lab_b[lab_b >= 0]):
                    centers.append(Xb[lab_b == c].mean(axis=0))
                centers = np.vstack(centers)
                d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
                lab_full = d.argmin(axis=1)
                # align cluster count
                if len(np.unique(lab_full)) < 2:
                    continue
                aris.append(adjusted_rand_score(base, lab_full))
        except Exception:
            continue
    return float(np.nanmean(aris)) if aris else np.nan


def _fit_one(X: np.ndarray, algorithm: str, k: int) -> np.ndarray | None:
    k = int(k)
    if k < 2:
        return None
    if algorithm == "kmeans":
        return KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE).fit_predict(X)
    if algorithm == "ward":
        return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)
    if algorithm == "agglomerative_average":
        return AgglomerativeClustering(n_clusters=k, linkage="average", metric="euclidean").fit_predict(X)
    if algorithm == "gmm":
        return GaussianMixture(n_components=k, covariance_type="full", random_state=RANDOM_STATE, n_init=5).fit_predict(X)
    if algorithm == "spectral":
        return SpectralClustering(
            n_clusters=k, affinity="nearest_neighbors", random_state=RANDOM_STATE, n_neighbors=min(10, len(X) - 1)
        ).fit_predict(X)
    return None


def _composite_rank(df: pd.DataFrame) -> pd.Series:
    """Higher is better composite after normalizing metrics."""
    d = df.copy()
    # silhouette high good, CH high good, DB low good, gap high good, bic low good, stability high good
    def norm_good(s):
        s = s.astype(float)
        if s.notna().sum() < 2 or s.max() == s.min():
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - s.min()) / (s.max() - s.min())

    def norm_bad(s):
        s = s.astype(float)
        if s.notna().sum() < 2 or s.max() == s.min():
            return pd.Series(np.zeros(len(s)), index=s.index)
        return 1 - (s - s.min()) / (s.max() - s.min())

    score = (
        0.30 * norm_good(d["silhouette"])
        + 0.20 * norm_good(d["calinski_harabasz"])
        + 0.20 * norm_bad(d["davies_bouldin"])
        + 0.15 * norm_good(d["stability_ari"])
        + 0.10 * norm_good(d["gap"].fillna(d["gap"].median() if d["gap"].notna().any() else 0))
        + 0.05 * norm_bad(d["bic"].fillna(d["bic"].median() if d["bic"].notna().any() else 0))
    )
    # Penalize noise-heavy density clusters
    score = score - 0.15 * d["noise_frac"].fillna(0)
    return score


def run_stage06(feature_matrix: pd.DataFrame, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE4_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    meta = [c for c in ["station", "sample_date"] if c in feature_matrix.columns]
    feat_cols = [c for c in feature_matrix.columns if c not in meta]
    df = feature_matrix.dropna(subset=feat_cols).reset_index(drop=True)
    X_raw = df[feat_cols].to_numpy(dtype=float)
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    print(f"  [stage06] fitting candidates on n={len(X)}, p={X.shape[1]}")
    candidates = _fit_candidates(X)

    rows = []
    for c in candidates:
        row = {k: v for k, v in c.items() if k != "labels"}
        rows.append(row)
    metrics_df = pd.DataFrame(rows)

    # Stability for top silhouette candidates per algorithm family (parametric only)
    print("  [stage06] bootstrap stability")
    stab = []
    parametric = metrics_df[metrics_df["algorithm"].isin(["kmeans", "ward", "gmm", "spectral", "agglomerative_average"])]
    # evaluate stability for each unique algo-k with finite silhouette
    for _, r in parametric.dropna(subset=["silhouette"]).iterrows():
        ari = _stability_ari(X, r["algorithm"], int(r["k"]))
        stab.append({"algorithm": r["algorithm"], "k": int(r["k"]), "stability_ari": ari})
    stab_df = pd.DataFrame(stab).drop_duplicates(subset=["algorithm", "k"])
    metrics_df = metrics_df.merge(stab_df, on=["algorithm", "k"], how="left")

    # Density methods: stability_ari NaN
    metrics_df["stability_ari"] = metrics_df["stability_ari"].astype(float)

    # Keep only valid cluster solutions
    valid = metrics_df[metrics_df["n_clusters"] >= 2].copy()
    valid["composite"] = _composite_rank(valid)
    valid = valid.sort_values("composite", ascending=False).reset_index(drop=True)

    best = valid.iloc[0].to_dict()
    best_algo, best_k = best["algorithm"], int(best["k"])

    # Retrieve labels for best
    best_labels = None
    for c in candidates:
        if c["algorithm"] == best_algo and int(c.get("k", -1)) == best_k:
            # for dbscan match eps if present
            if best_algo == "dbscan" and "eps" in best:
                if abs(c.get("eps", -1) - best.get("eps", -2)) < 1e-12:
                    best_labels = c["labels"]
                    break
            elif best_algo == "hdbscan" and "min_cluster_size" in best:
                if c.get("min_cluster_size") == best.get("min_cluster_size"):
                    best_labels = c["labels"]
                    break
            else:
                best_labels = c["labels"]
                break
    if best_labels is None:
        best_labels = _fit_one(X, best_algo, best_k)

    labeled = df[meta].copy()
    labeled["regime"] = best_labels
    labeled["regime_algorithm"] = best_algo
    labeled["regime_k"] = best_k
    for c in feat_cols:
        labeled[c] = df[c].values

    # PCA embedding for visualization
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    xy = pca.fit_transform(X)
    labeled["pc1"] = xy[:, 0]
    labeled["pc2"] = xy[:, 1]

    # Figures
    fig_paths = {}
    fig, ax = plt.subplots(figsize=(8, 5))
    plot = valid.copy()
    plot["label"] = plot["algorithm"] + "_k" + plot["k"].astype(int).astype(str)
    top = plot.head(20)
    sns.barplot(data=top, x="composite", y="label", ax=ax, color="#1f4e79")
    ax.set_title("Stage 6 — Top clustering solutions by composite score")
    fig.tight_layout()
    p = fig_dir / "fig_stage06_model_selection.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["model_selection"] = str(p)

    fig, ax = plt.subplots(figsize=(7, 5))
    sns.scatterplot(data=labeled, x="pc1", y="pc2", hue="regime", style="station", palette="tab10", ax=ax, s=45)
    ax.set_title(f"Stage 6 — Regimes ({best_algo}, k={best_k}) in PCA space")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    p2 = fig_dir / "fig_stage06_pca_regimes.png"
    fig.savefig(p2, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["pca_regimes"] = str(p2)

    # Silhouette vs k for kmeans/ward/gmm
    fig, ax = plt.subplots(figsize=(7, 4))
    for algo in ["kmeans", "ward", "gmm"]:
        sub = metrics_df[metrics_df["algorithm"] == algo].dropna(subset=["silhouette"])
        ax.plot(sub["k"], sub["silhouette"], marker="o", label=algo)
    ax.set_xlabel("k")
    ax.set_ylabel("Silhouette")
    ax.set_title("Stage 6 — Silhouette vs k")
    ax.legend()
    fig.tight_layout()
    p3 = fig_dir / "fig_stage06_silhouette_curves.png"
    fig.savefig(p3, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["silhouette_curves"] = str(p3)

    # Regime size / station composition
    comp = pd.crosstab(labeled["station"], labeled["regime"])
    fig, ax = plt.subplots(figsize=(8, 4))
    comp.plot(kind="bar", stacked=True, ax=ax, colormap="tab10")
    ax.set_title("Stage 6 — Regime membership by station")
    ax.set_xlabel("Station")
    ax.set_ylabel("Station-days")
    fig.tight_layout()
    p4 = fig_dir / "fig_stage06_regime_by_station.png"
    fig.savefig(p4, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["regime_by_station"] = str(p4)

    selection_trace = build_selection_trace(
        valid,
        best,
        k_range=K_RANGE,
        candidate_algorithms=sorted(valid["algorithm"].dropna().unique().tolist()) if len(valid) else [],
    )

    # SC-FMF: Discovery Engine failure assessment (Sec "Run engine -> evaluate
    # failure modes -> ... -> pass structured failure report downstream").
    # disc_too_few_stations / disc_poor_silhouette are locally evaluable here;
    # disc_high_noise needs Stage 14's noise-sensitivity battery (not yet run)
    # and is soft-skipped (no bundle key) — Stage 14 runs a consolidated,
    # final Discovery failure report once that evidence exists (see
    # stage14_robustness.py), which supersedes this one for that mode only.
    n_stations = int(labeled["station"].nunique()) if "station" in labeled.columns else None
    failure_bundle = {"n_stations": n_stations, "selected_silhouette": best.get("silhouette")}
    failure_report = build_failure_report("discovery", failure_bundle)

    report = {
        "n_samples": int(len(df)),
        "n_features": len(feat_cols),
        "features": feat_cols,
        "selection_trace": selection_trace,
        "discovery_contract": discovery_contract_block(),
        "n_candidates_evaluated": int(len(metrics_df)),
        "best": {
            "algorithm": best_algo,
            "k": best_k,
            "silhouette": best.get("silhouette"),
            "davies_bouldin": best.get("davies_bouldin"),
            "calinski_harabasz": best.get("calinski_harabasz"),
            "stability_ari": best.get("stability_ari"),
            "gap": best.get("gap"),
            "bic": best.get("bic"),
            "composite": best.get("composite"),
            "noise_frac": best.get("noise_frac"),
        },
        "hdbscan_available": HAS_HDBSCAN,
        "selection_rule": "composite of silhouette, CH, DB, stability ARI, gap, BIC with noise penalty (no predetermined K/algorithm)",
        "failure_report": failure_report,
        "figures": fig_paths,
    }

    metrics_path = output_dir / "stage06_clustering_metrics.csv"
    labels_path = output_dir / "stage06_regime_labels.csv"
    valid_path = output_dir / "stage06_ranked_solutions.csv"
    report_path = output_dir / "stage06_regime_discovery_report.json"
    failure_report_path = output_dir / "stage06_failure_report.json"

    # Save metrics without giant objects
    metrics_df.to_csv(metrics_path, index=False)
    valid.drop(columns=[c for c in valid.columns if c == "labels"], errors="ignore").to_csv(valid_path, index=False)
    labeled.to_csv(labels_path, index=False)
    report["outputs"] = {"metrics": str(metrics_path), "labels": str(labels_path), "ranked": str(valid_path)}
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    failure_report_path.write_text(json.dumps(failure_report, indent=2, default=str), encoding="utf-8")

    # Persist scaler info indirectly via labeled features already unscaled in CSV
    return {
        "metrics": metrics_df,
        "ranked": valid,
        "labeled": labeled,
        "best": report["best"],
        "X_scaled": X,
        "feature_cols": feat_cols,
        "scaler": scaler,
        "report": report,
        "failure_report": failure_report,
    }
