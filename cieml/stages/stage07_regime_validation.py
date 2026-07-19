"""Stage 7: Validate discovered regimes (stability, consensus, LOSO, LOWO)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import entropy
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from cieml.config import PHASE4_DIR
from cieml.stages.stage06_regime_discovery import _fit_one

RANDOM_STATE = 42


def _variation_of_information(lab_a: np.ndarray, lab_b: np.ndarray) -> float:
    """VI = H(a) + H(b) - 2 I(a;b); use NMI bridge."""
    # VI = H(a)+H(b)-2MI; NMI = MI/sqrt(H(a)H(b)) approx — compute directly
    a = lab_a.astype(int)
    b = lab_b.astype(int)
    # contingency
    fa = pd.Series(a).value_counts(normalize=True)
    fb = pd.Series(b).value_counts(normalize=True)
    ha = float(entropy(fa, base=2))
    hb = float(entropy(fb, base=2))
    joint = pd.crosstab(a, b, normalize=True)
    hj = float(entropy(joint.to_numpy().ravel(), base=2))
    mi = ha + hb - hj
    return float(ha + hb - 2 * mi)


def _jaccard_cluster_match(lab_a: np.ndarray, lab_b: np.ndarray) -> float:
    """Mean best-match Jaccard across clusters in a."""
    scores = []
    for ca in np.unique(lab_a):
        sa = set(np.where(lab_a == ca)[0])
        best = 0.0
        for cb in np.unique(lab_b):
            sb = set(np.where(lab_b == cb)[0])
            inter = len(sa & sb)
            union = len(sa | sb)
            if union:
                best = max(best, inter / union)
        scores.append(best)
    return float(np.mean(scores)) if scores else np.nan


def _fit_best(X: np.ndarray, algorithm: str, k: int) -> np.ndarray:
    lab = _fit_one(X, algorithm, k)
    if lab is None:
        lab = KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE).fit_predict(X)
    return lab


def run_stage07(
    labeled: pd.DataFrame,
    feature_cols: list[str],
    best: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE4_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    algorithm = str(best["algorithm"])
    k = int(best["k"])
    meta = [c for c in ["station", "sample_date"] if c in labeled.columns]

    df = labeled.dropna(subset=feature_cols).reset_index(drop=True)
    X = StandardScaler().fit_transform(df[feature_cols].to_numpy(dtype=float))
    base_labels = df["regime"].to_numpy()

    # --- Bootstrap stability ---
    rng = np.random.default_rng(RANDOM_STATE)
    boot_aris = []
    n = len(X)
    for i in range(50):
        idx = rng.integers(0, n, size=n)
        lab_b = _fit_best(X[idx], algorithm, k)
        # map bootstrap labels to full via nearest centers
        centers = []
        ok = True
        for c in np.unique(lab_b):
            if c < 0:
                ok = False
                break
            centers.append(X[idx][lab_b == c].mean(axis=0))
        if not ok or len(centers) < 2:
            continue
        centers = np.vstack(centers)
        d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        lab_full = d.argmin(axis=1)
        boot_aris.append(adjusted_rand_score(base_labels, lab_full))
    boot_ari_mean = float(np.nanmean(boot_aris)) if boot_aris else np.nan
    boot_ari_std = float(np.nanstd(boot_aris)) if boot_aris else np.nan

    # --- Consensus across algorithms at same k ---
    algos = ["kmeans", "ward", "gmm", "spectral", "agglomerative_average"]
    algo_labels = {}
    for algo in algos:
        try:
            algo_labels[algo] = _fit_best(X, algo, k)
        except Exception:
            continue
    consensus_rows = []
    names = list(algo_labels.keys())
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            la, lb = algo_labels[a], algo_labels[b]
            consensus_rows.append(
                {
                    "a": a,
                    "b": b,
                    "ARI": float(adjusted_rand_score(la, lb)),
                    "NMI": float(normalized_mutual_info_score(la, lb)),
                    "VI": _variation_of_information(la, lb),
                    "Jaccard": _jaccard_cluster_match(la, lb),
                }
            )
    consensus_df = pd.DataFrame(consensus_rows)
    consensus_ari_mean = float(consensus_df["ARI"].mean()) if len(consensus_df) else np.nan

    # Consensus labels via co-association + Ward
    if len(algo_labels) >= 2:
        M = np.zeros((n, n), dtype=float)
        for lab in algo_labels.values():
            for i in range(n):
                M[i] += (lab == lab[i])
        M /= len(algo_labels)
        # Convert similarity to distance
        D = 1 - M
        np.fill_diagonal(D, 0)
        # densify for Agglomerative with precomputed
        cons = AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average")
        consensus_labels = cons.fit_predict(D)
        consensus_vs_best_ari = float(adjusted_rand_score(base_labels, consensus_labels))
    else:
        consensus_labels = base_labels
        consensus_vs_best_ari = 1.0

    # --- Permutation null: ARI of best vs random labels ---
    null_aris = []
    for i in range(100):
        perm = rng.permutation(base_labels)
        null_aris.append(adjusted_rand_score(base_labels, perm))
    # Structure test: bootstrap ARI vs null
    null_mean = float(np.mean(null_aris))
    structure_pvalue = float(np.mean(np.array(boot_aris) <= null_mean)) if boot_aris else np.nan

    # --- Leave-one-station-out ---
    loso_rows = []
    if "station" in df.columns:
        for station in sorted(df["station"].unique()):
            train = df["station"] != station
            test = df["station"] == station
            if train.sum() < k * 3 or test.sum() < 1:
                continue
            lab_train = _fit_best(X[train.to_numpy()], algorithm, k)
            centers = []
            for c in np.unique(lab_train):
                centers.append(X[train.to_numpy()][lab_train == c].mean(axis=0))
            centers = np.vstack(centers)
            d = ((X[test.to_numpy()][:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            pred = d.argmin(axis=1)
            # Compare composition distribution: train regime prior vs held-out assignment entropy etc.
            # ARI not defined vs true labels for held-out; use center-match vs full-model labels
            true_held = base_labels[test.to_numpy()]
            loso_rows.append(
                {
                    "left_out_station": station,
                    "n_test": int(test.sum()),
                    "ARI_vs_full_model": float(adjusted_rand_score(true_held, pred)),
                    "Jaccard_vs_full_model": _jaccard_cluster_match(true_held, pred),
                }
            )
    loso_df = pd.DataFrame(loso_rows)
    loso_ari = float(loso_df["ARI_vs_full_model"].mean()) if len(loso_df) else np.nan

    # --- Leave-one-week-out ---
    lowo_rows = []
    if "sample_date" in df.columns:
        dates = pd.to_datetime(df["sample_date"])
        weeks = dates.dt.isocalendar().week.astype(int)
        df_week = weeks
        for week in sorted(df_week.unique()):
            train = (df_week != week).to_numpy()
            test = (df_week == week).to_numpy()
            if train.sum() < k * 3 or test.sum() < 2:
                continue
            lab_train = _fit_best(X[train], algorithm, k)
            centers = np.vstack([X[train][lab_train == c].mean(axis=0) for c in np.unique(lab_train)])
            d = ((X[test][:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            pred = d.argmin(axis=1)
            true_held = base_labels[test]
            lowo_rows.append(
                {
                    "left_out_week": int(week),
                    "n_test": int(test.sum()),
                    "ARI_vs_full_model": float(adjusted_rand_score(true_held, pred)),
                    "Jaccard_vs_full_model": _jaccard_cluster_match(true_held, pred),
                }
            )
    lowo_df = pd.DataFrame(lowo_rows)
    lowo_ari = float(lowo_df["ARI_vs_full_model"].mean()) if len(lowo_df) else np.nan

    # Decision: genuine structure?
    checks = {
        "bootstrap_ari_ge_0_5": bool(np.isfinite(boot_ari_mean) and boot_ari_mean >= 0.5),
        "consensus_ari_ge_0_4": bool(np.isfinite(consensus_ari_mean) and consensus_ari_mean >= 0.4),
        "loso_ari_ge_0_3": bool(np.isfinite(loso_ari) and loso_ari >= 0.3),
        "lowo_ari_ge_0_3": bool(np.isfinite(lowo_ari) and lowo_ari >= 0.3),
        "beats_permutation_null": bool(np.isfinite(boot_ari_mean) and boot_ari_mean > null_mean + 0.2),
    }
    n_pass = int(sum(checks.values()))
    if n_pass >= 4:
        h4_status, h4_verdict = "PROVISIONAL_SUPPORT", "lean_alternative"
        structure_call = "regimes_supported"
    elif n_pass >= 2:
        h4_status, h4_verdict = "MIXED_EVIDENCE", "exploratory"
        structure_call = "regimes_exploratory"
    else:
        h4_status, h4_verdict = "PROVISIONAL_REJECT_ALTERNATIVE", "lean_null"
        structure_call = "regimes_not_supported"

    # Attach consensus labels
    out = df[meta + ["regime"]].copy()
    out["consensus_regime"] = consensus_labels

    # Figures
    fig_paths = {}
    if len(consensus_df):
        mat = consensus_df.pivot(index="a", columns="b", values="ARI")
        # make symmetric for heatmap
        alg = sorted(set(consensus_df["a"]) | set(consensus_df["b"]))
        M = pd.DataFrame(np.eye(len(alg)), index=alg, columns=alg)
        for _, r in consensus_df.iterrows():
            M.loc[r["a"], r["b"]] = r["ARI"]
            M.loc[r["b"], r["a"]] = r["ARI"]
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(M, annot=True, fmt=".2f", cmap="viridis", vmin=0, vmax=1, ax=ax)
        ax.set_title(f"Stage 7 — Cross-algorithm ARI (k={k})")
        fig.tight_layout()
        p = fig_dir / "fig_stage07_consensus_ari.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["consensus_ari"] = str(p)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(boot_aris, bins=15, color="#1f4e79", alpha=0.85, label="bootstrap ARI")
    ax.axvline(null_mean, color="crimson", ls="--", label=f"perm null mean={null_mean:.2f}")
    ax.axvline(boot_ari_mean, color="black", ls="-", label=f"boot mean={boot_ari_mean:.2f}")
    ax.set_title("Stage 7 — Bootstrap stability vs permutation null")
    ax.set_xlabel("ARI vs full-model labels")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p2 = fig_dir / "fig_stage07_bootstrap_stability.png"
    fig.savefig(p2, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["bootstrap"] = str(p2)

    if len(loso_df):
        fig, ax = plt.subplots(figsize=(7, 4))
        sns.barplot(data=loso_df, x="left_out_station", y="ARI_vs_full_model", ax=ax, color="#2e7d4f")
        ax.set_title("Stage 7 — Leave-one-station-out ARI")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        p3 = fig_dir / "fig_stage07_loso.png"
        fig.savefig(p3, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["loso"] = str(p3)

    if len(lowo_df):
        fig, ax = plt.subplots(figsize=(7, 4))
        sns.barplot(data=lowo_df, x="left_out_week", y="ARI_vs_full_model", ax=ax, color="#6a3d9a")
        ax.set_title("Stage 7 — Leave-one-week-out ARI")
        fig.tight_layout()
        p4 = fig_dir / "fig_stage07_lowo.png"
        fig.savefig(p4, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["lowo"] = str(p4)

    report = {
        "best_algorithm": algorithm,
        "best_k": k,
        "bootstrap_ari_mean": boot_ari_mean,
        "bootstrap_ari_std": boot_ari_std,
        "consensus_ari_mean": consensus_ari_mean,
        "consensus_vs_best_ari": consensus_vs_best_ari,
        "loso_ari_mean": loso_ari,
        "lowo_ari_mean": lowo_ari,
        "permutation_null_ari_mean": null_mean,
        "structure_checks": checks,
        "n_checks_passed": n_pass,
        "structure_call": structure_call,
        "discovery_validation_pipeline": [
            "bootstrap_stability",
            "cross_algorithm_consensus",
            "leave_one_station_out",
            "leave_one_week_out",
            "permutation_null",
        ],
        "h4_update": {
            "hypothesis": "H4_environmental_regimes",
            "status": h4_status,
            "verdict_lean": h4_verdict,
            "note": "Structure call is algorithm/K-agnostic; interpretation deferred to Stage 12. Stage 14 stress-tests the selected solution.",
        },
        "figures": fig_paths,
    }

    consensus_df.to_csv(output_dir / "stage07_cross_algorithm_agreement.csv", index=False)
    loso_df.to_csv(output_dir / "stage07_loso.csv", index=False)
    lowo_df.to_csv(output_dir / "stage07_lowo.csv", index=False)
    out.to_csv(output_dir / "stage07_validated_regimes.csv", index=False)
    pd.DataFrame({"bootstrap_ari": boot_aris}).to_csv(output_dir / "stage07_bootstrap_ari.csv", index=False)
    report_path = output_dir / "stage07_validation_report.json"
    report["outputs"] = {
        "validated_regimes": str(output_dir / "stage07_validated_regimes.csv"),
        "cross_algorithm": str(output_dir / "stage07_cross_algorithm_agreement.csv"),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {
        "consensus_agreement": consensus_df,
        "loso": loso_df,
        "lowo": lowo_df,
        "validated": out,
        "report": report,
    }
