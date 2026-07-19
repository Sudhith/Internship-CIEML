"""Stage 14: Robustness/sensitivity stress-testing plus the Evidence-Based Scientific
Validation Engine (EBSVE) four-pillar closure (see cieml.evidence.*).

This stage's own stress-test battery (seed stability, alternative scaling/clustering/
features/preprocessing, bootstrap, Monte Carlo noise, permutation null, alternative k,
LOSO) still runs exactly as before and feeds live evidence into H4/H6's statistical and
practical pillars. The closure computation itself has moved to cieml.evidence: every
pillar for every hypothesis is now computed from real upstream evidence, never hardcoded.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from cieml.config import PHASE1_DIR, PHASE2_DIR, PHASE3_DIR, PHASE4_DIR, PHASE5_DIR, PHASE6_DIR, PHASE7_DIR, PHASE8_DIR
from cieml.evidence.engine import run_evidence_engine
from cieml.evidence.loaders import build_evidence_bundle, load_csv, load_json
from cieml.evidence.visualize import render_all
from cieml.uncertainty.assemble import build_campaign_uncertainty_ledger
from cieml.uncertainty.visualize import render_uncertainty_figures

RANDOM_STATE = 42
N_SEEDS = 20
N_BOOT = 40
N_PERM = 30
N_MC = 25


def _meta_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in ["station", "sample_date", "regime", "regime_algorithm", "regime_k", "pc1", "pc2"] if c in df.columns]


def _feature_cols(df: pd.DataFrame) -> list[str]:
    skip = set(_meta_cols(df))
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]


def _fit(X: np.ndarray, algorithm: str, k: int, random_state: int = RANDOM_STATE) -> np.ndarray:
    k = int(k)
    if algorithm == "kmeans":
        return KMeans(n_clusters=k, n_init=25, random_state=random_state).fit_predict(X)
    if algorithm == "ward":
        return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)
    if algorithm == "agglomerative_average":
        return AgglomerativeClustering(n_clusters=k, linkage="average", metric="euclidean").fit_predict(X)
    if algorithm == "gmm":
        return GaussianMixture(
            n_components=k, covariance_type="full", random_state=random_state, n_init=5
        ).fit_predict(X)
    if algorithm == "spectral":
        return SpectralClustering(
            n_clusters=k,
            affinity="nearest_neighbors",
            random_state=random_state,
            n_neighbors=min(10, max(2, len(X) - 1)),
        ).fit_predict(X)
    raise ValueError(f"Unknown algorithm: {algorithm}")


def _scale(X: np.ndarray, method: str) -> np.ndarray:
    if method == "standard":
        return StandardScaler().fit_transform(X)
    if method == "robust":
        return RobustScaler().fit_transform(X)
    if method == "minmax":
        return MinMaxScaler().fit_transform(X)
    if method == "none":
        return np.asarray(X, dtype=float)
    raise ValueError(method)


def _ari_safe(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a)
    b = np.asarray(b)
    if len(a) != len(b) or len(a) < 5:
        return float("nan")
    if len(np.unique(a)) < 2 or len(np.unique(b)) < 2:
        return float("nan")
    return float(adjusted_rand_score(a, b))


def _pass_fail(ari: float, threshold: float = 0.5) -> str:
    if np.isnan(ari):
        return "inconclusive"
    return "pass" if ari >= threshold else "fail"


def run_stage14(
    labeled: pd.DataFrame,
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase3_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    phase7_dir: Path | None = None,
    hypothesis_register: dict[str, Any] | None = None,
    output_dir: Path | None = None,
    *,
    knowledge_store_root: Path | None = None,
    update_phase7_applicability: bool = True,
) -> dict[str, Any]:
    """
    `knowledge_store_root` overrides the Phase K Knowledge Base write target
    (default: the real repo `knowledge_base/`) — pass a scratch path for test runs
    so they don't mutate shared project state.

    `update_phase7_applicability` controls whether the enriched applicability
    packet is written back into `phase7_dir` (an *input* directory to this stage)
    so a later standalone evidence-engine run picks up enrichment without
    re-running Stage 13. This is a real side effect on an upstream phase's own
    artifacts, not just this stage's `output_dir` — set False for test/dry runs
    that must not mutate `phase7_dir`.
    """
    phase1_dir = Path(phase1_dir or PHASE1_DIR)
    phase2_dir = Path(phase2_dir or PHASE2_DIR)
    phase3_dir = Path(phase3_dir or PHASE3_DIR)
    phase4_dir = Path(phase4_dir or PHASE4_DIR)
    phase5_dir = Path(phase5_dir or PHASE5_DIR)
    phase6_dir = Path(phase6_dir or PHASE6_DIR)
    phase7_dir = Path(phase7_dir or PHASE7_DIR)
    output_dir = Path(output_dir or PHASE8_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    hypothesis_register = hypothesis_register or {}
    shap_drivers = load_csv(phase5_dir / "stage08_shap_driver_ranks.csv")
    station_day_features = load_csv(phase3_dir / "stage04_station_day_features.csv")
    prior_validation = load_json(phase4_dir / "stage07_validation_report.json")

    df = labeled.copy().reset_index(drop=True)
    feat_cols = _feature_cols(df)
    if not feat_cols:
        raise ValueError("No numeric feature columns found in labeled matrix")

    algorithm = str(df["regime_algorithm"].iloc[0]) if "regime_algorithm" in df.columns else "ward"
    k = int(df["regime_k"].iloc[0]) if "regime_k" in df.columns else int(df["regime"].nunique())
    base = df["regime"].to_numpy()
    X_raw = df[feat_cols].to_numpy(dtype=float)
    X0 = _scale(X_raw, "standard")

    rows: list[dict[str, Any]] = []

    # --- 1. Random seed stability ---
    seed_algos = ["kmeans", "gmm", "spectral"]
    for algo in seed_algos:
        aris = []
        ref = _fit(X0, algo, k, random_state=RANDOM_STATE)
        for s in range(N_SEEDS):
            lab = _fit(X0, algo, k, random_state=s)
            aris.append(_ari_safe(ref, lab))
        rows.append(
            {
                "test_family": "seed_stability",
                "condition": algo,
                "metric": "ari_vs_seed0_ref",
                "value_mean": float(np.nanmean(aris)),
                "value_std": float(np.nanstd(aris)),
                "value_min": float(np.nanmin(aris)),
                "n_reps": N_SEEDS,
                "result": _pass_fail(float(np.nanmean(aris)), 0.7),
            }
        )
    # Ward deterministic check
    w1 = _fit(X0, "ward", k, 0)
    w2 = _fit(X0, "ward", k, 99)
    rows.append(
        {
            "test_family": "seed_stability",
            "condition": "ward_deterministic",
            "metric": "ari_identical",
            "value_mean": _ari_safe(w1, w2),
            "value_std": 0.0,
            "value_min": _ari_safe(w1, w2),
            "n_reps": 2,
            "result": "pass" if _ari_safe(w1, w2) == 1.0 else "fail",
        }
    )

    # --- 2. Alternative scaling ---
    for method in ["standard", "robust", "minmax"]:
        Xs = _scale(X_raw, method)
        lab = _fit(Xs, algorithm, k, RANDOM_STATE)
        ari = _ari_safe(base, lab)
        rows.append(
            {
                "test_family": "alternative_scaling",
                "condition": method,
                "metric": "ari_vs_baseline",
                "value_mean": ari,
                "value_std": np.nan,
                "value_min": ari,
                "n_reps": 1,
                "result": _pass_fail(ari, 0.5),
            }
        )

    # --- 3. Alternative clustering algorithms ---
    for algo in ["ward", "kmeans", "gmm", "spectral", "agglomerative_average"]:
        lab = _fit(X0, algo, k, RANDOM_STATE)
        ari = _ari_safe(base, lab)
        sil = float(silhouette_score(X0, lab)) if len(np.unique(lab)) >= 2 else np.nan
        rows.append(
            {
                "test_family": "alternative_clustering",
                "condition": algo,
                "metric": "ari_vs_baseline",
                "value_mean": ari,
                "value_std": np.nan,
                "value_min": ari,
                "n_reps": 1,
                "result": _pass_fail(ari, 0.4),
                "silhouette": sil,
            }
        )

    # --- 4. Alternative feature selection / ablation ---
    dominant, secondary, negligible = [], [], []
    if shap_drivers is not None and len(shap_drivers):
        for _, r in shap_drivers.iterrows():
            f = r["feature"]
            if f not in feat_cols:
                continue
            tier = r.get("tier", "Negligible")
            if tier == "Dominant":
                dominant.append(f)
            elif tier == "Secondary":
                secondary.append(f)
            else:
                negligible.append(f)

    feature_sets = {
        "full_baseline": feat_cols,
        "drop_negligible": [c for c in feat_cols if c not in negligible] or feat_cols,
        "dominant_secondary": (dominant + secondary) or feat_cols,
        "dominant_only": dominant or feat_cols[: max(2, len(feat_cols) // 2)],
        "raw_means_only": [c for c in feat_cols if not str(c).startswith("idx_")] or feat_cols,
        "indices_only": [c for c in feat_cols if str(c).startswith("idx_")] or feat_cols,
    }
    for name, cols in feature_sets.items():
        if len(cols) < 2:
            continue
        Xs = _scale(df[cols].to_numpy(dtype=float), "standard")
        lab = _fit(Xs, algorithm, k, RANDOM_STATE)
        ari = _ari_safe(base, lab)
        rows.append(
            {
                "test_family": "alternative_features",
                "condition": name,
                "metric": "ari_vs_baseline",
                "value_mean": ari,
                "value_std": np.nan,
                "value_min": ari,
                "n_reps": 1,
                "result": _pass_fail(ari, 0.4 if name != "indices_only" else 0.3),
                "n_features": len(cols),
            }
        )
    for f in dominant:
        cols = [c for c in feat_cols if c != f]
        if len(cols) < 2:
            continue
        Xs = _scale(df[cols].to_numpy(dtype=float), "standard")
        lab = _fit(Xs, algorithm, k, RANDOM_STATE)
        ari = _ari_safe(base, lab)
        rows.append(
            {
                "test_family": "leave_one_dominant",
                "condition": f"drop_{f}",
                "metric": "ari_vs_baseline",
                "value_mean": ari,
                "value_std": np.nan,
                "value_min": ari,
                "n_reps": 1,
                "result": _pass_fail(ari, 0.4),
            }
        )

    # --- 5. Alternative preprocessing: median family if available ---
    if station_day_features is not None and len(station_day_features):
        med_map = {}
        for c in feat_cols:
            if c.endswith("__mean"):
                alt = c.replace("__mean", "__median")
                if alt in station_day_features.columns:
                    med_map[c] = alt
        if len(med_map) >= 3:
            # rebuild matrix: replace means with medians, keep indices from labeled
            tmp = df.copy()
            merge_keys = [c for c in ["station", "sample_date"] if c in df.columns and c in station_day_features.columns]
            if merge_keys:
                m = station_day_features[merge_keys + list(med_map.values())].copy()
                tmp = df.merge(m, on=merge_keys, how="left", suffixes=("", "_medsrc"))
                cols_use = []
                for c in feat_cols:
                    if c in med_map and med_map[c] in tmp.columns:
                        cols_use.append(med_map[c])
                    else:
                        cols_use.append(c)
                Xs = _scale(tmp[cols_use].to_numpy(dtype=float), "standard")
                lab = _fit(Xs, algorithm, k, RANDOM_STATE)
                ari = _ari_safe(base, lab)
                rows.append(
                    {
                        "test_family": "alternative_preprocessing",
                        "condition": "median_core_variables",
                        "metric": "ari_vs_baseline",
                        "value_mean": ari,
                        "value_std": np.nan,
                        "value_min": ari,
                        "n_reps": 1,
                        "result": _pass_fail(ari, 0.5),
                        "n_medians_substituted": len(med_map),
                    }
                )

    # --- 6. Bootstrap stability ---
    boot_aris = []
    rng = np.random.default_rng(RANDOM_STATE)
    n = len(df)
    for i in range(N_BOOT):
        idx = rng.choice(n, size=n, replace=True)
        uniq = np.unique(idx)
        if len(uniq) < max(20, k * 5):
            continue
        Xs = _scale(X_raw[uniq], "standard")
        lab = _fit(Xs, algorithm, k, RANDOM_STATE + i)
        boot_aris.append(_ari_safe(base[uniq], lab))
    rows.append(
        {
            "test_family": "bootstrap",
            "condition": f"{algorithm}_k{k}",
            "metric": "ari_vs_baseline_on_unique",
            "value_mean": float(np.nanmean(boot_aris)) if boot_aris else np.nan,
            "value_std": float(np.nanstd(boot_aris)) if boot_aris else np.nan,
            "value_min": float(np.nanmin(boot_aris)) if boot_aris else np.nan,
            "n_reps": len(boot_aris),
            "result": _pass_fail(float(np.nanmean(boot_aris)) if boot_aris else np.nan, 0.5),
        }
    )

    # --- 7. Monte Carlo noise sensitivity ---
    mc_rows = []
    for noise_sd in [0.05, 0.10, 0.20, 0.40]:
        aris = []
        for i in range(N_MC):
            noise = rng.normal(0.0, noise_sd, size=X0.shape)
            lab = _fit(X0 + noise, algorithm, k, RANDOM_STATE + i)
            aris.append(_ari_safe(base, lab))
        mean_ari = float(np.nanmean(aris))
        rows.append(
            {
                "test_family": "monte_carlo_noise",
                "condition": f"gaussian_sd_{noise_sd}",
                "metric": "ari_vs_baseline",
                "value_mean": mean_ari,
                "value_std": float(np.nanstd(aris)),
                "value_min": float(np.nanmin(aris)),
                "n_reps": N_MC,
                "result": _pass_fail(mean_ari, 0.5 if noise_sd <= 0.2 else 0.3),
            }
        )
        mc_rows.append({"noise_sd": noise_sd, "ari_mean": mean_ari, "ari_std": float(np.nanstd(aris))})

    # --- 8. Permutation null ---
    perm_aris = []
    for i in range(N_PERM):
        Xp = X0.copy()
        for j in range(Xp.shape[1]):
            Xp[:, j] = rng.permutation(Xp[:, j])
        lab = _fit(Xp, algorithm, k, RANDOM_STATE + i)
        perm_aris.append(_ari_safe(base, lab))
    perm_mean = float(np.nanmean(perm_aris))
    rows.append(
        {
            "test_family": "permutation_null",
            "condition": "column_permute_features",
            "metric": "ari_vs_baseline",
            "value_mean": perm_mean,
            "value_std": float(np.nanstd(perm_aris)),
            "value_min": float(np.nanmin(perm_aris)),
            "n_reps": N_PERM,
            "result": "pass" if perm_mean < 0.15 else "fail",
        }
    )

    # --- 9. Alternative k sensitivity ---
    for kk in [2, 3, 4, 5]:
        lab = _fit(X0, algorithm, kk, RANDOM_STATE)
        sil = float(silhouette_score(X0, lab)) if len(np.unique(lab)) >= 2 else np.nan
        ari = _ari_safe(base, lab) if kk == k else np.nan
        rows.append(
            {
                "test_family": "alternative_k",
                "condition": f"k={kk}",
                "metric": "silhouette",
                "value_mean": sil,
                "value_std": np.nan,
                "value_min": sil,
                "n_reps": 1,
                "result": "reference" if kk == k else "exploratory",
                "ari_vs_baseline_if_k_matches": ari,
            }
        )

    # --- 10. Station leave-one-out quick check ---
    if "station" in df.columns:
        loso = []
        for st in sorted(df["station"].unique()):
            mask = df["station"] != st
            if mask.sum() < max(20, k * 5):
                continue
            Xs = _scale(X_raw[mask.to_numpy()], "standard")
            lab = _fit(Xs, algorithm, k, RANDOM_STATE)
            loso.append({"left_out": st, "ari": _ari_safe(base[mask.to_numpy()], lab)})
        if loso:
            loso_df = pd.DataFrame(loso)
            rows.append(
                {
                    "test_family": "loso",
                    "condition": "leave_one_station_out",
                    "metric": "ari_vs_baseline",
                    "value_mean": float(loso_df["ari"].mean()),
                    "value_std": float(loso_df["ari"].std(ddof=0)),
                    "value_min": float(loso_df["ari"].min()),
                    "n_reps": len(loso_df),
                    "result": _pass_fail(float(loso_df["ari"].mean()), 0.4),
                }
            )
            loso_df.to_csv(output_dir / "stage14_loso_detail.csv", index=False)

    sens_df = pd.DataFrame(rows)

    # --- Aggregate robustness score ---
    scored = sens_df[sens_df["result"].isin(["pass", "fail"])]
    n_pass = int((scored["result"] == "pass").sum())
    n_fail = int((scored["result"] == "fail").sum())
    n_scored = n_pass + n_fail
    robustness_frac = float(n_pass / n_scored) if n_scored else np.nan

    # Critical checks for regime conclusion
    critical = {
        "bootstrap_pass": bool(
            ((sens_df["test_family"] == "bootstrap") & (sens_df["result"] == "pass")).any()
        ),
        "permutation_null_pass": bool(
            ((sens_df["test_family"] == "permutation_null") & (sens_df["result"] == "pass")).any()
        ),
        "scaling_majority_pass": bool(
            (sens_df.loc[sens_df["test_family"] == "alternative_scaling", "result"] == "pass").mean() >= 0.66
        ),
        "feature_ablation_majority_pass": bool(
            (
                sens_df.loc[sens_df["test_family"].isin(["alternative_features", "leave_one_dominant"]), "result"]
                == "pass"
            ).mean()
            >= 0.5
        ),
        "noise_0.1_pass": bool(
            (
                (sens_df["test_family"] == "monte_carlo_noise")
                & (sens_df["condition"] == "gaussian_sd_0.1")
                & (sens_df["result"] == "pass")
            ).any()
        ),
        "prior_stage07_regimes_supported": prior_validation.get("structure_call") == "regimes_supported",
    }
    critical_pass = int(sum(critical.values()))
    critical_total = len(critical)

    # --- Evidence-Based Scientific Validation Engine (four-pillar closure) ---
    # Every pillar for every hypothesis (H1-H6) is computed from real upstream
    # artifacts by cieml.evidence — none is hardcoded here. The live sensitivity
    # battery just run above (sens_df, critical) is injected into the evidence bundle
    # so H4/H6 can use it as real statistical/practical evidence.
    evidence_bundle = build_evidence_bundle(phase1_dir, phase2_dir, phase3_dir, phase4_dir, phase5_dir, phase6_dir, phase7_dir)
    evidence_bundle["stage14_sensitivity_results"] = sens_df
    evidence_bundle["stage14_critical_checks"] = critical
    pillars = run_evidence_engine(evidence_bundle, hypothesis_register)
    pillars.pop("_assessments", None)
    pillars.pop("_claim_pack", None)
    support_frac = evidence_bundle.get("stage10_external_report", {}).get("anomaly_external_support_frac")
    evidence_fig_paths = render_all(pillars, fig_dir)

    # --- Phase K: Applicability enrichment + DSS gate + KB propose (SC-APP/DSS/KB) ---
    from cieml.applicability import enrich_with_claims
    from cieml.decision import gate_recommendations
    from cieml.knowledge import load_store, propose_from_campaign

    claim_classes = {
        hid: block.get("classification")
        for hid, block in (pillars.get("hypotheses") or {}).items()
    }
    base_applicability = load_json(phase7_dir / "stage13_applicability_domain.json")
    if not base_applicability:
        base_applicability = {
            "applies_to": ["Monitoring design for multiparameter sonde campaigns"],
            "does_not_apply_to": ["Universal numeric threshold transfer without re-analysis"],
            "transfer_rule": (
                "Re-run CIEML Stages 4–9 on the new campaign; reuse framework logic, "
                "not site-specific cutoffs."
            ),
        }
    post_gate = gate_recommendations(
        claim_classes,
        pillars.get("campaign_mean_confidence"),
        applicability_domain=base_applicability,
    )
    (output_dir / "stage14_decision_gate.json").write_text(
        json.dumps(post_gate, indent=2, default=str), encoding="utf-8"
    )

    enriched_app = enrich_with_claims(base_applicability, pillars.get("hypotheses") or {})
    (output_dir / "stage14_applicability_domain.json").write_text(
        json.dumps(enriched_app, indent=2, default=str), encoding="utf-8"
    )
    # Keep Stage 13 artifact current for loaders / H6 re-reads. This mutates an
    # *input* directory to this stage (not just output_dir), so it is gated by
    # update_phase7_applicability — callers doing test/dry runs against a real
    # phase7_dir (rather than a scratch copy) should pass False.
    if update_phase7_applicability:
        (phase7_dir / "stage13_applicability_domain.json").write_text(
            json.dumps(enriched_app, indent=2, default=str), encoding="utf-8"
        )

    try:
        from cieml.domain import load_campaign

        _camp = load_campaign()
        _campaign_id, _domain = _camp.campaign_id, _camp.domain
    except FileNotFoundError:
        _campaign_id, _domain = "visakhapatnam_may2026", "coastal"

    kb_store = load_store(knowledge_store_root) if knowledge_store_root is not None else None
    kb_summary = propose_from_campaign(
        campaign_id=_campaign_id,
        domain=_domain,
        pillars=pillars,
        applicability=enriched_app,
        physical_report=evidence_bundle.get("stage03_physical_report") or {},
        anomaly_report=evidence_bundle.get("stage09_anomaly_report") or {},
        store=kb_store,
        output_summary_path=output_dir / "stage14_kb_propose_summary.json",
    )

    # --- SC-FMF: consolidated cross-stage failure dossier (Task: campaign-wide) ---
    # Discovery and Anomaly Intelligence each ran a LOCAL failure check at their
    # own stage (06 and 09/10 respectively) using whatever evidence existed at
    # that point in the pipeline; disc_high_noise and the environmental half of
    # anom_no_external_validation needed evidence that only exists once Stage 14's
    # own robustness battery / Stage 10's external report have run. This block
    # re-evaluates both engines ONE FINAL TIME with the complete evidence set,
    # producing the authoritative report that feeds the uncertainty ledger below
    # and the campaign-wide dossier -- it supersedes, not duplicates, the earlier
    # local reports (both are retained on disk for audit; see stageNN_failure_report.json).
    from cieml.failure import build_failure_report
    from cieml.validation.suite import run_validation_suite

    n_stations_for_discovery = int(labeled["station"].nunique()) if "station" in labeled.columns else None
    disc_best = (evidence_bundle.get("stage06_regime_discovery_report") or {}).get("best") or {}
    noise_flag = bool(np.isfinite(robustness_frac) and robustness_frac < 0.70)
    discovery_failure_report = build_failure_report(
        "discovery",
        {
            "n_stations": n_stations_for_discovery,
            "selected_silhouette": disc_best.get("silhouette"),
            "stage14_noise_or_stability": noise_flag,
            "stage14_noise_or_stability_detail": (
                f"robustness_frac_pass={robustness_frac:.3f} (< 0.70 flags high noise/instability)"
                if np.isfinite(robustness_frac) else "robustness_frac_pass unavailable"
            ),
        },
    )
    anomaly_failure_report = build_failure_report(
        "anomaly_intelligence",
        {
            "n_consensus_anomalies": (evidence_bundle.get("stage09_anomaly_report") or {}).get("n_consensus_anomalies"),
            "anomaly_external_support_frac": support_frac,
        },
    )
    explainability_failure_report = (evidence_bundle.get("stage08_explainable_report") or {}).get("failure_report") \
        or build_failure_report("explainability", {})
    ebsve_failure_report = pillars.get("failure_report") or build_failure_report("ebsve", {})
    decision_support_failure_report = build_failure_report(
        "decision_support",
        {
            "claim_classifications": claim_classes,
            "campaign_mean_confidence": pillars.get("campaign_mean_confidence"),
            "applicability_domain": base_applicability,
        },
    )
    fve_result = run_validation_suite()
    framework_validation_failure_report = fve_result.get("failure_report") or build_failure_report("framework_validation", {})

    failure_reports_by_engine = {
        "discovery": discovery_failure_report,
        "explainability": explainability_failure_report,
        "anomaly_intelligence": anomaly_failure_report,
        "ebsve": ebsve_failure_report,
        "decision_support": decision_support_failure_report,
        "framework_validation": framework_validation_failure_report,
    }
    failure_dossier = {
        "campaign_id": _campaign_id,
        "engines": failure_reports_by_engine,
        "n_engines_ok": sum(1 for fr in failure_reports_by_engine.values() if fr.get("severity") == "NONE"),
        "n_engines_degraded_or_worse": sum(
            1 for fr in failure_reports_by_engine.values() if fr.get("severity") in {"DEGRADED", "CRITICAL", "FATAL"}
        ),
        "n_engines_blocking": sum(1 for fr in failure_reports_by_engine.values() if fr.get("blocking_status")),
        "worst_severity": max(
            (fr.get("severity", "NONE") for fr in failure_reports_by_engine.values()),
            key=lambda s: {"NONE": -1, "INFO": 0, "WARNING": 1, "DEGRADED": 2, "CRITICAL": 3, "FATAL": 4}.get(s, -1),
            default="NONE",
        ),
    }
    (output_dir / "stage14_failure_dossier.json").write_text(
        json.dumps(failure_dossier, indent=2, default=str), encoding="utf-8"
    )

    # Computed here (not after the uncertainty block) because the DiscoveryEngine
    # uncertainty packet's confidence directly depends on regime_structure_call
    # (85.0 if "robust_support" else 60.0) — building the ledger before this was
    # known meant that packet could never reflect a genuine robust_support H4
    # classification; it was permanently pinned to the pessimistic branch.
    h4_classification = pillars["hypotheses"].get("H4_environmental_regimes", {}).get("classification")
    regime_structure_call = {
        "DEFINITIVE": "robust_support",
        "PROVISIONAL": "provisional_support",
        "EXPLORATORY": "fragile",
    }.get(h4_classification, "fragile")

    # --- Uncertainty Model v2 (SC-MMU + SC-REL): ledger + figures ---
    interim_robustness = {
        "robustness_frac_pass": robustness_frac,
        "critical_checks": critical,
        "regime_structure_call": regime_structure_call,
    }
    uncertainty_ledger = build_campaign_uncertainty_ledger(
        phase1_dir=phase1_dir,
        phase2_dir=phase2_dir,
        phase3_dir=phase3_dir,
        phase4_dir=phase4_dir,
        phase5_dir=phase5_dir,
        phase6_dir=phase6_dir,
        phase7_dir=phase7_dir,
        pillars=pillars,
        robustness_report=interim_robustness,
        failure_reports=failure_reports_by_engine,
    )
    uncertainty_fig_paths = render_uncertainty_figures(uncertainty_ledger, fig_dir)
    (output_dir / "stage14_uncertainty_ledger.json").write_text(
        json.dumps(uncertainty_ledger, indent=2, default=str), encoding="utf-8"
    )

    # --- Figures ---
    fig_paths = {}
    plot_df = sens_df[sens_df["test_family"].isin(
        ["alternative_scaling", "alternative_clustering", "alternative_features", "seed_stability", "bootstrap", "loso", "permutation_null"]
    )].copy()
    if len(plot_df):
        fig, ax = plt.subplots(figsize=(10, 5.5))
        plot_df["label"] = plot_df["test_family"] + " | " + plot_df["condition"].astype(str)
        plot_df = plot_df.sort_values("value_mean")
        colors = plot_df["result"].map({"pass": "#2e7d32", "fail": "#c62828", "inconclusive": "#9e9e9e", "reference": "#1565c0", "exploratory": "#6a1b9a"})
        ax.barh(plot_df["label"], plot_df["value_mean"], color=colors.fillna("#607d8b"))
        ax.axvline(0.5, color="black", ls="--", lw=0.8)
        ax.set_xlabel("ARI / metric value")
        ax.set_title("Stage 14 — Robustness stress tests")
        fig.tight_layout()
        p = fig_dir / "fig_stage14_robustness_bars.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["robustness_bars"] = str(p)

    if mc_rows:
        mc = pd.DataFrame(mc_rows)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.errorbar(mc["noise_sd"], mc["ari_mean"], yerr=mc["ari_std"], marker="o", color="#1f4e79")
        ax.set_xlabel("Gaussian noise SD (on standardized features)")
        ax.set_ylabel("Mean ARI vs baseline")
        ax.set_title("Stage 14 — Monte Carlo noise sensitivity")
        ax.set_ylim(-0.05, 1.05)
        fig.tight_layout()
        p = fig_dir / "fig_stage14_noise_sensitivity.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["noise"] = str(p)

    # Four-pillar visuals (radar/confidence/heatmap/dashboard/table) are rendered by
    # cieml.evidence.visualize.render_all above and merged into fig_paths below —
    # no separate ad-hoc heatmap needed here.
    fig_paths.update(evidence_fig_paths)
    fig_paths.update({f"uncertainty_{k}": v for k, v in uncertainty_fig_paths.items()})

    report = {
        "baseline": {"algorithm": algorithm, "k": k, "n_samples": int(len(df)), "n_features": len(feat_cols)},
        "robustness_frac_pass": robustness_frac,
        "n_tests_pass": n_pass,
        "n_tests_fail": n_fail,
        "critical_checks": critical,
        "critical_pass_count": f"{critical_pass}/{critical_total}",
        "regime_structure_call": regime_structure_call,
        "four_pillar": pillars,
        "uncertainty_ledger_summary": uncertainty_ledger.get("summary"),
        "prior_stage07": {
            "structure_call": prior_validation.get("structure_call"),
            "bootstrap_ari_mean": prior_validation.get("bootstrap_ari_mean"),
            "permutation_null_ari_mean": prior_validation.get("permutation_null_ari_mean"),
        },
        "anomaly_external_support_frac": support_frac,
        "phase_k": {
            "decision_gate": post_gate,
            "applicability_enriched": True,
            "kb_propose": {
                "entries_written": kb_summary.get("entries_written"),
                "domain_profile_mutated": kb_summary.get("domain_profile_mutated"),
                "domain_proposal": kb_summary.get("domain_proposal"),
            },
        },
        "sc_fmf": {
            "worst_severity": failure_dossier["worst_severity"],
            "n_engines_ok": failure_dossier["n_engines_ok"],
            "n_engines_degraded_or_worse": failure_dossier["n_engines_degraded_or_worse"],
            "n_engines_blocking": failure_dossier["n_engines_blocking"],
            "dossier_path": str(output_dir / "stage14_failure_dossier.json"),
        },
        "figures": fig_paths,
        "limitations": [
            "Campaign is one month (May) at six Visakhapatnam stations — seasonal and geographic transfer untested.",
            "Ward clustering is deterministic; seed tests apply mainly to stochastic algorithms.",
            "External meteo validation uses a single regional Open-Meteo point, not station-resolved forcing.",
            "Four-pillar 'DEFINITIVE' requires every pillar >=90/100 for every hypothesis; 'PROVISIONAL' "
            "requires the weakest pillar per hypothesis >=70/100; see cieml.evidence for the full, "
            "reproducible per-pillar evidence trail behind every score (no hardcoded pillar values remain).",
        ],
    }

    sens_df.to_csv(output_dir / "stage14_sensitivity_results.csv", index=False)
    pd.DataFrame(mc_rows).to_csv(output_dir / "stage14_monte_carlo_noise.csv", index=False)
    (output_dir / "stage14_robustness_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "stage14_four_pillar_closure.json").write_text(
        json.dumps(pillars, indent=2, default=str), encoding="utf-8"
    )

    # Scientific closure markdown
    _write_closure_md(output_dir, report, sens_df, pillars)

    return {"sensitivity": sens_df, "report": report, "pillars": pillars}


def _write_closure_md(output_dir: Path, report: dict, sens_df: pd.DataFrame, pillars: dict) -> None:
    lines = [
        "# CIEML 2.0 — Stage 14 Scientific Closure",
        "",
        "## Observed evidence",
        f"- Baseline solution: `{report['baseline']['algorithm']}` k={report['baseline']['k']} "
        f"(n={report['baseline']['n_samples']}, p={report['baseline']['n_features']})",
        f"- Robustness tests passed: {report['n_tests_pass']} / "
        f"{report['n_tests_pass'] + report['n_tests_fail']} (frac={report['robustness_frac_pass']})",
        f"- Critical checks: {report['critical_pass_count']}",
        f"- Regime structure call after Stage 14: **{report['regime_structure_call']}**",
        f"- Campaign four-pillar closure: **{pillars.get('campaign_closure')}** "
        f"(mean confidence {pillars.get('campaign_mean_confidence')}/100)",
        f"- Weakest evidence campaign-wide: {pillars.get('weakest_evidence')}",
        "",
        "## Evidence-Based Scientific Validation Engine — per hypothesis",
        "Every pillar score below is computed from named upstream evidence (see "
        "`stage14_four_pillar_closure.json` for the full evidence trail); none is hardcoded.",
    ]
    for hid, block in pillars.get("hypotheses", {}).items():
        pillar_scores = ", ".join(f"{p}={v['score']:.0f}" for p, v in block["pillars"].items())
        lines.append(
            f"- `{hid}`: **{block['classification']}** (confidence {block['overall_confidence']:.0f}/100, "
            f"{block['evidence_strength']} evidence) | {pillar_scores}"
        )
        lines.append(f"  - {block['reasoning_summary']}")
        if block.get("limitations"):
            lines.append(f"  - Limitations: {'; '.join(block['limitations'])}")
    lines += [
        "",
        "## Speculation excluded",
        "- No universal DO/pH/turbidity thresholds claimed for other coasts.",
        "- No causal pollutant-source attribution beyond water-quality fingerprints + partial meteo support.",
        "",
        "## Limitations",
    ]
    for lim in report.get("limitations", []):
        lines.append(f"- {lim}")
    lines += [
        "",
        "## Future hypotheses",
        "- Multi-season replication at Visakhapatnam to test regime seasonality.",
        "- Station-resolved forcing (local rainfall, tides, harbour operations) for stronger H5 tests.",
        "- Independent TSS / chlorophyll tracers if instrumented.",
    ]
    (output_dir / "stage14_scientific_closure.md").write_text("\n".join(lines), encoding="utf-8")
