"""Multi-method driver consensus (Phase H).

SHAP tiers remain the legacy `tier` field for downstream compatibility.
Consensus adds method-agreement fields without silently dropping disputed drivers.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _top_set(series: pd.Series, frac: float = 0.60, min_share: float = 0.05) -> set[str]:
    s = series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if float(s.sum()) <= 0:
        return set()
    share = s / s.sum()
    share = share.sort_values(ascending=False)
    cum = share.cumsum()
    out = set()
    for feat, sh in share.items():
        if cum.loc[feat] <= frac or sh >= min_share:
            out.add(str(feat))
        else:
            break
    # always include the single top feature
    if len(share):
        out.add(str(share.index[0]))
    return out


def build_driver_consensus(
    shap_ranks: pd.DataFrame,
    perm_df: pd.DataFrame,
    native_df: pd.DataFrame | None = None,
    *,
    primary_model: str = "random_forest",
    min_methods: int = 2,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attach consensus columns to SHAP rank table; return summary dict."""
    ranks = shap_ranks.copy()
    methods: dict[str, set[str]] = {}

    if "mean_abs_shap" in ranks.columns:
        methods["shap"] = _top_set(ranks.set_index("feature")["mean_abs_shap"])
    if len(perm_df) and "perm_importance_mean" in perm_df.columns:
        methods["permutation"] = _top_set(perm_df.set_index("feature")["perm_importance_mean"])
    if native_df is not None and len(native_df) and "importance" in native_df.columns:
        sub = native_df[native_df.get("model") == primary_model] if "model" in native_df.columns else native_df
        if not len(sub):
            sub = native_df
        # mean across models if multiple
        g = sub.groupby("feature")["importance"].mean()
        methods["native_importance"] = _top_set(g)

    n_methods = len(methods)
    support_counts = []
    supporting = []
    for feat in ranks["feature"].astype(str):
        supporters = [m for m, s in methods.items() if feat in s]
        support_counts.append(len(supporters))
        supporting.append(",".join(supporters) if supporters else "")

    ranks["n_methods_supporting"] = support_counts
    ranks["methods_supporting"] = supporting
    ranks["consensus_supported"] = ranks["n_methods_supporting"] >= min(min_methods, max(1, n_methods))

    # Consensus tier: SHAP's own tier is the starting point, but multi-method
    # agreement can move it in either direction — a Dominant SHAP driver that no
    # other method corroborates is Disputed, and (the case the previous version
    # missed) a Negligible-per-SHAP feature that permutation *and* native
    # importance both independently rank highly is promoted to Secondary rather
    # than silently reported as still-Negligible. Only Dominant/Secondary keep
    # their SHAP label unconditionally when consensus agrees with SHAP already.
    def _consensus_tier(row) -> str:
        tier = row.get("tier")
        supported = bool(row["consensus_supported"])
        if tier == "Dominant":
            return "Dominant" if supported else "Disputed"
        if tier == "Secondary":
            return "Secondary" if supported else "Unconfirmed"
        # tier is Negligible (or an unrecognized value)
        if supported:
            return "Secondary"
        return "Negligible" if tier == "Negligible" else "Unconfirmed"

    ranks["consensus_tier"] = ranks.apply(_consensus_tier, axis=1)

    disputed = ranks.loc[ranks["consensus_tier"] == "Disputed", "feature"].tolist()
    consensus_dominant = ranks.loc[ranks["consensus_tier"] == "Dominant", "feature"].tolist()
    consensus_secondary = ranks.loc[ranks["consensus_tier"] == "Secondary", "feature"].tolist()

    summary = {
        "methods_used": sorted(methods.keys()),
        "min_methods_for_consensus": min(min_methods, max(1, n_methods)),
        "consensus_dominant": consensus_dominant,
        "consensus_secondary": consensus_secondary,
        "disputed_drivers": disputed,
        "rule": (
            "A driver is consensus_supported if it appears in the high-share set of "
            f">={min(min_methods, max(1, n_methods))} explanation methods (SHAP / permutation / native)."
        ),
        "legacy_tier_field": "tier remains SHAP-only for downstream compatibility; prefer consensus_tier for reporting",
    }
    return ranks, summary
