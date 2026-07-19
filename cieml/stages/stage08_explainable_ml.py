"""Stage 8: Explainable ML for regime interpretation (not accuracy chasing)."""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.inspection import PartialDependenceDisplay, permutation_importance
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from scipy.stats import spearmanr

from cieml.config import PHASE5_DIR
from cieml.explain.consensus import build_driver_consensus
from cieml.failure import build_failure_report

warnings.filterwarnings("ignore", category=FutureWarning)
RANDOM_STATE = 42

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except Exception:
    HAS_XGB = False

try:
    from lightgbm import LGBMClassifier
    HAS_LGBM = True
except Exception:
    HAS_LGBM = False


def _meta_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in ["station", "sample_date", "regime", "regime_algorithm", "regime_k", "pc1", "pc2", "consensus_regime"] if c in df.columns]


def _feature_cols(df: pd.DataFrame) -> list[str]:
    skip = set(_meta_cols(df))
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]


def _build_models(n_classes: int) -> dict[str, Any]:
    models: dict[str, Any] = {
        "random_forest": RandomForestClassifier(
            n_estimators=400, max_depth=None, min_samples_leaf=2, random_state=RANDOM_STATE, class_weight="balanced_subsample"
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=2, random_state=RANDOM_STATE, class_weight="balanced_subsample"
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
    }
    if HAS_XGB:
        models["xgboost"] = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob" if n_classes > 2 else "binary:logistic",
            eval_metric="mlogloss" if n_classes > 2 else "logloss",
            random_state=RANDOM_STATE,
            n_jobs=2,
        )
    if HAS_LGBM:
        models["lightgbm"] = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=31,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            verbose=-1,
        )
    return models


def _rank_drivers(mean_abs_shap: pd.Series) -> pd.DataFrame:
    s = mean_abs_shap.sort_values(ascending=False)
    total = float(s.sum()) + 1e-12
    share = s / total
    cum = share.cumsum()
    rows = []
    for feat, val in s.items():
        sh = float(share.loc[feat])
        if cum.loc[feat] <= 0.60 or sh >= 0.15:
            tier = "Dominant"
        elif cum.loc[feat] <= 0.90 or sh >= 0.05:
            tier = "Secondary"
        else:
            tier = "Negligible"
        rows.append({"feature": feat, "mean_abs_shap": float(val), "share": sh, "tier": tier})
    return pd.DataFrame(rows)


def run_stage08(labeled: pd.DataFrame, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE5_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    if "regime" not in labeled.columns:
        raise ValueError("labeled frame must include regime column from Stage 6/7")

    feat_cols = _feature_cols(labeled)
    df = labeled.dropna(subset=feat_cols + ["regime"]).copy()
    X = df[feat_cols].to_numpy(dtype=float)
    y = df["regime"].astype(int).to_numpy()
    classes = np.sort(np.unique(y))
    n_classes = len(classes)

    models = _build_models(n_classes)
    cv = StratifiedKFold(n_splits=min(5, max(2, int(np.min(np.bincount(y))))), shuffle=True, random_state=RANDOM_STATE)

    perf_rows = []
    fitted = {}
    for name, model in models.items():
        try:
            # XGBoost prefers 0..K-1 contiguous labels
            y_fit = y.copy()
            if name == "xgboost":
                # remap
                mapping = {c: i for i, c in enumerate(classes)}
                y_fit = np.vectorize(mapping.get)(y)
            pred = cross_val_predict(model, X, y_fit, cv=cv)
            if name == "xgboost":
                inv = {i: c for c, i in mapping.items()}
                pred = np.vectorize(inv.get)(pred)
            perf_rows.append(
                {
                    "model": name,
                    "accuracy": float(accuracy_score(y, pred)),
                    "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
                    "macro_f1": float(f1_score(y, pred, average="macro")),
                    "purpose": "interpretation_proxy_not_deployment",
                }
            )
            model.fit(X, y_fit if name == "xgboost" else y)
            fitted[name] = {"model": model, "y_mapping": mapping if name == "xgboost" else None}
        except Exception as exc:  # noqa: BLE001
            perf_rows.append({"model": name, "error": str(exc)})

    perf_df = pd.DataFrame(perf_rows)
    # Prefer random_forest as primary explainer (stable TreeSHAP)
    primary_name = "random_forest" if "random_forest" in fitted else next(iter(fitted))
    primary = fitted[primary_name]["model"]

    # Permutation importance on primary
    perm = permutation_importance(primary, X, y if primary_name != "xgboost" else np.vectorize(fitted[primary_name]["y_mapping"].get)(y),
                                  n_repeats=30, random_state=RANDOM_STATE, scoring="balanced_accuracy")
    perm_df = pd.DataFrame(
        {
            "feature": feat_cols,
            "perm_importance_mean": perm.importances_mean,
            "perm_importance_std": perm.importances_std,
        }
    ).sort_values("perm_importance_mean", ascending=False)

    # SHAP
    explainer = shap.TreeExplainer(primary)
    shap_values = explainer.shap_values(X)
    # Handle binary vs multiclass shapes
    if isinstance(shap_values, list):
        # list of arrays (n_samples, n_features) per class
        abs_stack = np.stack([np.abs(sv) for sv in shap_values], axis=0)  # (C, N, F)
        mean_abs = abs_stack.mean(axis=(0, 1))
        # for summary use class with largest mean
        class_means = abs_stack.mean(axis=(1, 2))
        focus_class = int(np.argmax(class_means))
        shap_focus = shap_values[focus_class]
    else:
        sv = np.asarray(shap_values)
        if sv.ndim == 3:
            # (N, F, C) or (C, N, F) depending on shap version
            if sv.shape[0] == len(X):
                mean_abs = np.abs(sv).mean(axis=(0, 2))
                focus_class = int(np.argmax(np.abs(sv).mean(axis=(0, 1))))
                shap_focus = sv[:, :, focus_class]
            else:
                mean_abs = np.abs(sv).mean(axis=(0, 1))
                focus_class = int(np.argmax(np.abs(sv).mean(axis=(1, 2))))
                shap_focus = sv[focus_class]
        else:
            mean_abs = np.abs(sv).mean(axis=0)
            focus_class = 0
            shap_focus = sv

    shap_imp = pd.Series(mean_abs, index=feat_cols, name="mean_abs_shap")
    driver_ranks = _rank_drivers(shap_imp)

    # Native importances across tree models
    native_rows = []
    for name, pack in fitted.items():
        model = pack["model"]
        if hasattr(model, "feature_importances_"):
            for f, v in zip(feat_cols, model.feature_importances_):
                native_rows.append({"model": name, "feature": f, "importance": float(v)})
    native_df = pd.DataFrame(native_rows)

    shap_df_full = pd.DataFrame(np.asarray(shap_focus), columns=feat_cols)
    interaction_rows = []
    top_feats = driver_ranks.head(6)["feature"].tolist()
    shap_df = shap_df_full[top_feats]
    for i, a in enumerate(top_feats):
        for b in top_feats[i + 1 :]:
            interaction_rows.append(
                {
                    "feature_a": a,
                    "feature_b": b,
                    "shap_attr_corr": float(shap_df[a].corr(shap_df[b])),
                    "note": "attribution_correlation_proxy_not_full_shap_interaction",
                    "focus_regime": int(classes[focus_class]) if n_classes > 2 else None,
                }
            )
    interaction_df = pd.DataFrame(interaction_rows)

    # Figures
    fig_paths: dict[str, str] = {}
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=driver_ranks, x="mean_abs_shap", y="feature", hue="tier", dodge=False, ax=ax)
    ax.set_title(f"Stage 8 — SHAP mean |value| ({primary_name})")
    fig.tight_layout()
    p = fig_dir / "fig_stage08_shap_importance.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["shap_importance"] = str(p)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=perm_df, x="perm_importance_mean", y="feature", ax=ax, color="#1f4e79")
    ax.set_title(f"Stage 8 — Permutation importance ({primary_name})")
    fig.tight_layout()
    p2 = fig_dir / "fig_stage08_permutation_importance.png"
    fig.savefig(p2, dpi=600, bbox_inches="tight")
    plt.close(fig)
    fig_paths["permutation_importance"] = str(p2)

    # SHAP beeswarm-like summary via scatter of shap vs feature for top 4
    top4 = driver_ranks.head(4)["feature"].tolist()
    if top4:
        fig, axes = plt.subplots(2, 2, figsize=(9, 7))
        axes = axes.ravel()
        for ax, feat in zip(axes, top4):
            ax.scatter(df[feat], shap_df_full[feat], c=y, cmap="tab10", s=18, alpha=0.75)
            ax.set_xlabel(feat)
            ax.set_ylabel("SHAP value")
            ax.set_title(feat)
        title = "Stage 8 — SHAP dependence (top drivers)"
        if n_classes > 2:
            title += f" — focus regime {int(classes[focus_class])} (largest mean |SHAP|)"
        fig.suptitle(title, y=1.02)
        fig.tight_layout()
        p3 = fig_dir / "fig_stage08_shap_dependence.png"
        fig.savefig(p3, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["shap_dependence"] = str(p3)

    # PDP for top 3 features. Sklearn requires an explicit target class once there are
    # 3+ regimes (a bare call raises "target must be specified for multi-class") — produce
    # one panel per regime so Stage 8 actually explains each regime's membership, rather
    # than silently picking one arbitrary class. Any failure is recorded in the report
    # instead of swallowed, so a broken figure is never invisible to whoever reads this.
    pdp_warnings: list[str] = []
    top3 = driver_ranks.head(3)["feature"].tolist()
    if n_classes > 2:
        for cls in classes:
            try:
                fig, ax = plt.subplots(figsize=(9, 4))
                PartialDependenceDisplay.from_estimator(
                    primary, df[feat_cols], features=top3, target=int(cls), ax=ax
                )
                fig.suptitle(f"Stage 8 — Partial dependence ({primary_name}), regime {int(cls)}")
                fig.tight_layout()
                pk = fig_dir / f"fig_stage08_pdp_regime{int(cls)}.png"
                fig.savefig(pk, dpi=600, bbox_inches="tight")
                plt.close(fig)
                fig_paths[f"pdp_regime_{int(cls)}"] = str(pk)
            except Exception as exc:
                pdp_warnings.append(f"regime {int(cls)}: {type(exc).__name__}: {exc}")
    else:
        try:
            fig, ax = plt.subplots(figsize=(9, 4))
            PartialDependenceDisplay.from_estimator(primary, df[feat_cols], features=top3, ax=ax)
            fig.suptitle(f"Stage 8 — Partial dependence ({primary_name})")
            fig.tight_layout()
            p4 = fig_dir / "fig_stage08_pdp.png"
            fig.savefig(p4, dpi=600, bbox_inches="tight")
            plt.close(fig)
            fig_paths["pdp"] = str(p4)
        except Exception as exc:
            pdp_warnings.append(f"{type(exc).__name__}: {exc}")

    if len(native_df):
        fig, ax = plt.subplots(figsize=(9, 5))
        sns.barplot(data=native_df, x="importance", y="feature", hue="model", ax=ax)
        ax.set_title("Stage 8 — Native feature importances across models")
        fig.tight_layout()
        p5 = fig_dir / "fig_stage08_native_importances.png"
        fig.savefig(p5, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["native_importances"] = str(p5)

    # Counterfactual-ish: for each regime, mean profile vs global mean (standardized)
    profiles = []
    global_mean = df[feat_cols].mean()
    global_std = df[feat_cols].std(ddof=0).replace(0, 1)
    for reg, g in df.groupby("regime"):
        z = ((g[feat_cols].mean() - global_mean) / global_std).to_dict()
        profiles.append({"regime": int(reg), "n": int(len(g)), **{f"z__{k}": float(v) for k, v in z.items()}})
    profile_df = pd.DataFrame(profiles)

    # Phase H — multi-method consensus (SHAP tier kept as legacy `tier`)
    driver_ranks, consensus_summary = build_driver_consensus(
        driver_ranks, perm_df, native_df if len(native_df) else None, primary_model=primary_name
    )
    (output_dir / "stage08_explainability_consensus.json").write_text(
        json.dumps(consensus_summary, indent=2, default=str), encoding="utf-8"
    )

    # SC-FMF: Explainability Engine failure assessment. xai_high_feature_correlation
    # uses RAW feature-value correlation (not SHAP-attribution correlation, which
    # `interaction_df.shap_attr_corr` measures a different thing) among the
    # top-ranked drivers, since the failure concern is that collinear drivers make
    # independent SHAP attribution unstable. xai_method_disagreement uses Spearman
    # rank correlation between the SHAP and permutation-importance orderings.
    top_feats_for_corr = driver_ranks.sort_values("mean_abs_shap", ascending=False).head(6)["feature"].tolist()
    max_abs_driver_corr = 0.0
    if len(top_feats_for_corr) > 1:
        corr_mat = df[top_feats_for_corr].corr().abs().to_numpy()
        np.fill_diagonal(corr_mat, 0.0)
        max_abs_driver_corr = float(np.nanmax(corr_mat)) if corr_mat.size else 0.0

    shap_rank_map = {f: i for i, f in enumerate(driver_ranks.sort_values("mean_abs_shap", ascending=False)["feature"])}
    perm_rank_map = {f: i for i, f in enumerate(perm_df.sort_values("perm_importance_mean", ascending=False)["feature"])}
    common = [f for f in feat_cols if f in shap_rank_map and f in perm_rank_map]
    rho = float("nan")
    if len(common) >= 3:
        rho_val, _ = spearmanr([shap_rank_map[f] for f in common], [perm_rank_map[f] for f in common])
        rho = float(rho_val)
    discord = bool(np.isfinite(rho) and rho < 0.5)

    failure_bundle = {
        "max_abs_driver_corr": max_abs_driver_corr,
        "shap_vs_permutation_discord": discord,
        "shap_vs_permutation_discord_detail": f"spearman_rho={rho:.3f}" if np.isfinite(rho) else "insufficient features for rank comparison",
    }
    failure_report = build_failure_report("explainability", failure_bundle)

    report = {
        "n_samples": int(len(df)),
        "n_features": len(feat_cols),
        "n_regimes": int(n_classes),
        "primary_explainer_model": primary_name,
        "models_trained": list(fitted.keys()),
        "performance": perf_rows,
        "driver_tiers": {
            "Dominant": driver_ranks.loc[driver_ranks["tier"] == "Dominant", "feature"].tolist(),
            "Secondary": driver_ranks.loc[driver_ranks["tier"] == "Secondary", "feature"].tolist(),
            "Negligible": driver_ranks.loc[driver_ranks["tier"] == "Negligible", "feature"].tolist(),
        },
        "explainability_consensus": consensus_summary,
        "purpose_statement": "Models explain regime membership; metrics are sanity checks, not optimization targets.",
        "shap_focus_regime": int(classes[focus_class]) if n_classes > 2 else None,
        "pdp_warnings": pdp_warnings,
        "failure_report": failure_report,
        "figures": fig_paths,
    }

    perf_df.to_csv(output_dir / "stage08_model_performance.csv", index=False)

    driver_ranks.to_csv(output_dir / "stage08_shap_driver_ranks.csv", index=False)
    perm_df.to_csv(output_dir / "stage08_permutation_importance.csv", index=False)
    native_df.to_csv(output_dir / "stage08_native_importances.csv", index=False)
    interaction_df.to_csv(output_dir / "stage08_shap_interaction_proxy.csv", index=False)
    profile_df.to_csv(output_dir / "stage08_regime_z_profiles.csv", index=False)
    report_path = output_dir / "stage08_explainable_report.json"
    report["outputs"] = {
        "driver_ranks": str(output_dir / "stage08_shap_driver_ranks.csv"),
        "consensus": str(output_dir / "stage08_explainability_consensus.json"),
        "permutation": str(output_dir / "stage08_permutation_importance.csv"),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (output_dir / "stage08_failure_report.json").write_text(
        json.dumps(failure_report, indent=2, default=str), encoding="utf-8"
    )

    return {
        "performance": perf_df,
        "drivers": driver_ranks,
        "permutation": perm_df,
        "profiles": profile_df,
        "report": report,
        "feature_cols": feat_cols,
        "failure_report": failure_report,
    }
