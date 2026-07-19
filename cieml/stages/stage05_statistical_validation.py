"""Stage 5: Statistical validation, redundancy analysis, and feature retention."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor

from cieml.config import PHASE3_DIR
from cieml.stats.method_selection import select_statistical_methods

try:
    from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity, calculate_kmo
    HAS_FACTOR = True
except Exception:
    HAS_FACTOR = False


def _kmo_bartlett_fallback(X: np.ndarray) -> dict[str, Any]:
    """Lightweight KMO/Bartlett if factor_analyzer is unavailable."""
    # Bartlett via correlation determinant pathway (statsmodels-like)
    corr = np.corrcoef(X, rowvar=False)
    n, p = X.shape
    corr = np.nan_to_num(corr, nan=0.0)
    # Ensure PSD-ish for det
    sign, logdet = np.linalg.slogdet(corr)
    det = float(sign * np.exp(logdet)) if np.isfinite(logdet) else 0.0
    chi2 = -((n - 1) - (2 * p + 5) / 6) * np.log(max(det, 1e-300))
    df = p * (p - 1) / 2
    pval = float(stats.chi2.sf(chi2, df))

    # Kaiser KMO approximation
    inv = np.linalg.pinv(corr)
    # partial correlations
    kmo_num = 0.0
    kmo_den = 0.0
    for i in range(p):
        for j in range(i + 1, p):
            r = corr[i, j]
            pr = -inv[i, j] / np.sqrt(inv[i, i] * inv[j, j] + 1e-12)
            kmo_num += r ** 2
            kmo_den += r ** 2 + pr ** 2
    kmo = float(kmo_num / (kmo_den + 1e-12))
    return {"kmo_model": kmo, "bartlett_chi2": float(chi2), "bartlett_p": pval, "corr_det": det}


def run_stage05(
    feature_matrix: pd.DataFrame,
    analysis_features: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE3_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    meta = [c for c in ["station", "sample_date"] if c in feature_matrix.columns]
    if analysis_features is None:
        analysis_features = [c for c in feature_matrix.columns if c not in meta]

    # Prefer a compact candidate set for VIF/PCA: daily means + indices + key anomalies
    means = [c for c in analysis_features if c.endswith("__mean")]
    indices = [c for c in analysis_features if c.startswith("idx_")]
    anoms = [c for c in analysis_features if c.endswith("__anom_station")]
    # Stage 5 primary block = means + indices (physically primary); anomalies assessed separately
    primary = means + indices
    primary = [c for c in primary if c in feature_matrix.columns]

    Xdf = feature_matrix[primary].apply(pd.to_numeric, errors="coerce")
    # Drop columns with too many NaNs or zero variance
    keep = []
    drop_notes = []
    for c in primary:
        s = Xdf[c]
        if s.notna().sum() < max(20, int(0.7 * len(Xdf))):
            drop_notes.append({"feature": c, "decision": "remove", "reason": "excessive_missing"})
            continue
        if s.var(ddof=0) == 0 or s.nunique(dropna=True) < 2:
            drop_notes.append({"feature": c, "decision": "remove", "reason": "zero_variance"})
            continue
        keep.append(c)
    Xdf = Xdf[keep].dropna()
    n, p = Xdf.shape

    # Descriptive + normality (D'Agostino for large n)
    desc_rows = []
    for c in keep:
        s = Xdf[c]
        if len(s) >= 20:
            stat_k, p_k = stats.normaltest(s)
        else:
            stat_k, p_k = np.nan, np.nan
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        outlier_frac = float(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).mean()) if iqr > 0 else 0.0
        desc_rows.append(
            {
                "feature": c,
                "n": int(s.notna().sum()),
                "mean": float(s.mean()),
                "std": float(s.std(ddof=0)),
                "skew": float(s.skew()),
                "kurtosis": float(s.kurtosis()),
                "normaltest_p": float(p_k) if np.isfinite(p_k) else np.nan,
                "nonnormal_at_05": bool(np.isfinite(p_k) and p_k < 0.05),
                "iqr_outlier_frac": outlier_frac,
            }
        )
    desc = pd.DataFrame(desc_rows)

    # Correlation
    corr = Xdf.corr(method="spearman")

    # VIF
    scaler = StandardScaler()
    Xs = scaler.fit_transform(Xdf)
    vif_rows = []
    for i, c in enumerate(keep):
        try:
            vif = float(variance_inflation_factor(Xs, i))
        except Exception:
            vif = np.nan
        vif_rows.append({"feature": c, "VIF": vif})
    vif_df = pd.DataFrame(vif_rows).sort_values("VIF", ascending=False)

    # Mutual information vs salinity mean as environmental target if present, else first feature
    target_name = "salinity_psu__mean" if "salinity_psu__mean" in keep else keep[0]
    y = Xdf[target_name].to_numpy()
    mi_features = [c for c in keep if c != target_name]
    if mi_features:
        mi = mutual_info_regression(Xdf[mi_features], y, random_state=42)
        mi_df = pd.DataFrame({"feature": mi_features, "MI_vs_target": mi, "target": target_name}).sort_values(
            "MI_vs_target", ascending=False
        )
    else:
        mi_df = pd.DataFrame(columns=["feature", "MI_vs_target", "target"])

    # KMO / Bartlett
    if HAS_FACTOR:
        try:
            chi2, p_b = calculate_bartlett_sphericity(Xdf)
            kmo_per, kmo_model = calculate_kmo(Xdf)
            factor_stats = {
                "kmo_model": float(kmo_model),
                "bartlett_chi2": float(chi2),
                "bartlett_p": float(p_b),
                "method": "factor_analyzer",
            }
        except Exception:
            factor_stats = _kmo_bartlett_fallback(Xdf.to_numpy())
            factor_stats["method"] = "fallback"
    else:
        factor_stats = _kmo_bartlett_fallback(Xdf.to_numpy())
        factor_stats["method"] = "fallback"

    # PCA suitability / variance explained
    pca = PCA()
    pca.fit(Xs)
    evr = pca.explained_variance_ratio_
    cum = np.cumsum(evr)
    n_90 = int(np.searchsorted(cum, 0.90) + 1)
    pca_df = pd.DataFrame(
        {
            "PC": [f"PC{i+1}" for i in range(len(evr))],
            "explained_variance_ratio": evr,
            "cumulative": cum,
        }
    )

    # Redundancy decisions
    decisions = list(drop_notes)
    # Pairwise |rho| > 0.95 among means => mark redundant
    redundant_pairs = []
    for i, a in enumerate(keep):
        for b in keep[i + 1 :]:
            rho = corr.loc[a, b]
            if abs(rho) >= 0.95:
                redundant_pairs.append((a, b, float(rho)))

    retain = set(keep)
    merge_map = {}
    # Prefer retaining salinity over spcond/tds/conductivity when redundant
    priority = [
        "salinity_psu__mean",
        "temperature_c__mean",
        "do_mg_l__mean",
        "do_sat_pct__mean",
        "ph__mean",
        "turbidity_fnu__mean",
        "barometer_mmhg__mean",
        "spcond_us_cm__mean",
        "conductivity_us_cm__mean",
        "tds_mg_l__mean",
    ]
    for a, b, rho in redundant_pairs:
        # drop the lower-priority feature
        try:
            pa = priority.index(a) if a in priority else 999
            pb = priority.index(b) if b in priority else 999
        except Exception:
            pa, pb = 999, 999
        drop, keep_f = (a, b) if pa > pb else (b, a)
        if drop in retain:
            retain.discard(drop)
            decisions.append(
                {
                    "feature": drop,
                    "decision": "remove_redundant",
                    "reason": f"|spearman|={rho:.3f} with {keep_f}; lower oceanographic priority",
                    "merged_into": keep_f,
                }
            )
            merge_map[drop] = keep_f

    # Iterative VIF pruning: the pairwise |rho|>=0.95 rule above only catches two-way
    # redundancy. It misses exact/near-exact linear combinations spanning 3+ retained
    # features (e.g. idx_do_sat_gap is defined as do_sat_pct__mean minus a linear fit on
    # do_mg_l__mean, so keeping all three together drives VIF to infinity even though no
    # single pairwise |rho| reaches 0.95). Recompute VIF on the shrinking retained set and
    # drop the worst non-core offender until nothing exceeds VIF_DROP_THRESHOLD.
    VIF_DROP_THRESHOLD = 20.0
    CORE_PROTECTED = {
        "salinity_psu__mean", "temperature_c__mean", "do_mg_l__mean", "ph__mean", "turbidity_fnu__mean",
    }

    def _vif_on(cols: list[str]) -> pd.DataFrame:
        if len(cols) < 2:
            return pd.DataFrame({"feature": cols, "VIF": [1.0] * len(cols)})
        sub = StandardScaler().fit_transform(Xdf[cols])
        rows = []
        for i, c in enumerate(cols):
            try:
                v = float(variance_inflation_factor(sub, i))
            except Exception:
                v = np.nan
            rows.append({"feature": c, "VIF": v})
        return pd.DataFrame(rows)

    while True:
        current = sorted(retain)
        vif_now = _vif_on(current)
        candidates = vif_now[
            (vif_now["VIF"] >= VIF_DROP_THRESHOLD) & (~vif_now["feature"].isin(CORE_PROTECTED))
        ].copy()
        if not len(candidates):
            break
        # Among tied/near-infinite VIFs, prefer dropping the raw variable over an
        # engineered index (indices are built to carry the non-redundant residual signal).
        candidates["_is_index"] = candidates["feature"].str.startswith("idx_")
        candidates = candidates.sort_values(["VIF", "_is_index"], ascending=[False, True])
        worst = candidates.iloc[0]
        drop_feat = str(worst["feature"])
        retain.discard(drop_feat)
        decisions.append(
            {
                "feature": drop_feat,
                "decision": "remove_redundant",
                "reason": f"VIF={worst['VIF']:.1f} (>= {VIF_DROP_THRESHOLD:.0f}) within retained set after redundancy pass",
                "merged_into": None,
            }
        )

    for feat in sorted(retain):
        if not any(d.get("feature") == feat for d in decisions):
            decisions.append(
                {
                    "feature": feat,
                    "decision": "retain",
                    "reason": "passes variance/missing filters; not removed by redundancy rule",
                }
            )

    decisions_df = pd.DataFrame(decisions)
    retained = sorted([d["feature"] for d in decisions if d["decision"] == "retain"])
    removed = [d for d in decisions if d["decision"] != "retain"]

    # Partial correlation example: temp vs DO controlling salinity (if all present)
    partial_rows = []
    need = ["temperature_c__mean", "do_mg_l__mean", "salinity_psu__mean"]
    if all(c in Xdf.columns for c in need):
        # residualize
        def _resid(y, controls):
            A = np.column_stack([np.ones(len(controls))] + [controls[c].to_numpy() for c in controls.columns])
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            return y - A @ coef

        controls = Xdf[["salinity_psu__mean"]]
        r_t = _resid(Xdf["temperature_c__mean"].to_numpy(), controls)
        r_d = _resid(Xdf["do_mg_l__mean"].to_numpy(), controls)
        rho, p = stats.spearmanr(r_t, r_d)
        partial_rows.append(
            {
                "pair": "temperature_c__mean ~ do_mg_l__mean",
                "control": "salinity_psu__mean",
                "partial_spearman": float(rho),
                "p": float(p),
            }
        )
    partial_df = pd.DataFrame(partial_rows)

    # H3 update
    n_removed = len([d for d in decisions if str(d["decision"]).startswith("remove")])
    if n_removed > 0 and len(retained) >= 4:
        h3_status, h3_verdict = "PROVISIONAL_SUPPORT", "lean_alternative"
    elif n_removed == 0:
        h3_status, h3_verdict = "MIXED_EVIDENCE", "exploratory"
    else:
        h3_status, h3_verdict = "MIXED_EVIDENCE", "exploratory"

    # Figures
    fig_paths = {}
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(corr, cmap="RdBu_r", center=0, vmin=-1, vmax=1, ax=ax, square=True)
    ax.set_title("Stage 5 — Spearman correlation (primary feature block)")
    fig.tight_layout()
    p = fig_dir / "fig_stage05_correlation.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["correlation"] = str(p)

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=vif_df, x="feature", y="VIF", ax=ax, color="#1f4e79")
    ax.axhline(10, color="crimson", ls="--", lw=1, label="VIF=10")
    ax.set_title("Stage 5 — Variance Inflation Factors")
    ax.tick_params(axis="x", rotation=40)
    ax.legend()
    fig.tight_layout()
    p2 = fig_dir / "fig_stage05_vif.png"
    fig.savefig(p2, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["vif"] = str(p2)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(range(1, len(cum) + 1), cum, marker="o", color="#1f4e79")
    ax.axhline(0.9, color="crimson", ls="--", lw=1)
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Cumulative explained variance")
    ax.set_title("Stage 5 — PCA cumulative variance")
    fig.tight_layout()
    p3 = fig_dir / "fig_stage05_pca_cumulative.png"
    fig.savefig(p3, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["pca"] = str(p3)

    if len(mi_df):
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.barplot(data=mi_df, x="feature", y="MI_vs_target", ax=ax, color="#2e7d4f")
        ax.set_title(f"Stage 5 — Mutual information vs {target_name}")
        ax.tick_params(axis="x", rotation=40)
        fig.tight_layout()
        p4 = fig_dir / "fig_stage05_mutual_information.png"
        fig.savefig(p4, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["mutual_information"] = str(p4)

    pca_suitable = bool(factor_stats.get("bartlett_p", 1) < 0.05 and factor_stats.get("kmo_model", 0) >= 0.5)

    nonnormal_count = int(desc["nonnormal_at_05"].sum()) if len(desc) else 0
    nonnormal_frac = float(nonnormal_count / max(len(desc), 1)) if len(desc) else 0.0
    max_vif = float("nan")
    if len(vif_df) and "VIF" in vif_df.columns:
        vmax = pd.to_numeric(vif_df["VIF"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if vmax.notna().any():
            max_vif = float(vmax.max())
    method_selection = select_statistical_methods(
        n_rows=int(n),
        n_features=len(keep),
        nonnormal_frac=nonnormal_frac,
        kmo_model=factor_stats.get("kmo_model"),
        bartlett_p=factor_stats.get("bartlett_p"),
        max_vif=max_vif,
        n_pcs_for_90pct=n_90,
        pca_suitable=pca_suitable,
    )
    (output_dir / "stage05_method_selection.json").write_text(
        json.dumps(method_selection, indent=2, default=str), encoding="utf-8"
    )

    report = {
        "n_rows_complete": int(n),
        "n_primary_features_started": len(primary),
        "n_primary_features_kept_for_tests": len(keep),
        "n_retained_for_downstream": len(retained),
        "retained_features": retained,
        "n_removed": n_removed,
        "redundant_pairs_abs_rho_ge_0_95": [
            {"a": a, "b": b, "rho": r} for a, b, r in redundant_pairs
        ],
        "factorability": {**factor_stats, "pca_suitable": pca_suitable, "n_pcs_for_90pct": n_90},
        "normality_nonnormal_count": nonnormal_count,
        "method_selection": method_selection,
        "h3_update": {
            "hypothesis": "H3_information_redundancy",
            "status": h3_status,
            "verdict_lean": h3_verdict,
            "note": "Redundancy evidenced among ionic/salinity family; reduced set retained for regimes.",
        },
        "figures": fig_paths,
    }

    # Persist
    desc.to_csv(output_dir / "stage05_descriptive_stats.csv", index=False)
    corr.to_csv(output_dir / "stage05_correlation.csv")
    vif_df.to_csv(output_dir / "stage05_vif.csv", index=False)
    mi_df.to_csv(output_dir / "stage05_mutual_information.csv", index=False)
    decisions_df.to_csv(output_dir / "stage05_feature_decisions.csv", index=False)
    pca_df.to_csv(output_dir / "stage05_pca_variance.csv", index=False)
    partial_df.to_csv(output_dir / "stage05_partial_correlation.csv", index=False)
    retained_matrix = feature_matrix[meta + [c for c in retained if c in feature_matrix.columns]].copy()
    retained_matrix.to_csv(output_dir / "stage05_retained_feature_matrix.csv", index=False)

    report_path = output_dir / "stage05_statistical_report.json"
    report["outputs"] = {
        "descriptive": str(output_dir / "stage05_descriptive_stats.csv"),
        "decisions": str(output_dir / "stage05_feature_decisions.csv"),
        "retained_matrix": str(output_dir / "stage05_retained_feature_matrix.csv"),
        "method_selection": str(output_dir / "stage05_method_selection.json"),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {
        "descriptive": desc,
        "correlation": corr,
        "vif": vif_df,
        "mi": mi_df,
        "decisions": decisions_df,
        "retained_features": retained,
        "retained_matrix": retained_matrix,
        "pca": pca_df,
        "partial": partial_df,
        "report": report,
    }
