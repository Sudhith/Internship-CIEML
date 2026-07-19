"""Assumption-aware statistical method selection (Phase F).

Does not change feature retention; produces an auditable method log so PCA /
parametric defaults are justified (or alternatives recommended) from diagnostics.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def select_statistical_methods(
    *,
    n_rows: int,
    n_features: int,
    nonnormal_frac: float,
    kmo_model: float | None,
    bartlett_p: float | None,
    max_vif: float | None,
    n_pcs_for_90pct: int | None,
    pca_suitable: bool,
) -> dict[str, Any]:
    """Return method choices + rationale for association, reduction, and downstream."""
    decisions: list[dict[str, Any]] = []

    # --- Association ---
    # Spearman is the engine's fixed default for environmental multiparameter data
    # regardless of normality (robust to outliers/nonlinearity that Pearson would
    # mis-score). This is a deliberate standing choice, not a per-dataset branch —
    # earlier code here had an if/else that always resolved to "spearman" on both
    # sides, which looked like a live decision but never actually varied; that was
    # misleading in the method-selection log, so it's now a single assignment with
    # a diagnostic-dependent justification instead of two dead branches.
    association = "spearman"
    if nonnormal_frac >= 0.30 or n_rows < 50:
        assoc_reason = (
            f"nonnormal_frac={nonnormal_frac:.2f} or small n={n_rows}; "
            "rank association (Spearman) required over Pearson."
        )
    else:
        assoc_reason = (
            f"nonnormal_frac={nonnormal_frac:.2f} is moderate; Spearman still used as "
            "the engine's standing default for environmental multiparameter data "
            "(robust to outliers), not because normality was violated here."
        )
    decisions.append({"task": "association", "choice": association, "reason": assoc_reason})

    # --- Dimensionality reduction ---
    kmo = float(kmo_model) if kmo_model is not None and np.isfinite(kmo_model) else float("nan")
    bp = float(bartlett_p) if bartlett_p is not None and np.isfinite(bartlett_p) else float("nan")
    if pca_suitable and (not np.isfinite(kmo) or kmo >= 0.5) and (not np.isfinite(bp) or bp < 0.05):
        dimred = "pca"
        dim_reason = (
            f"PCA suitable (KMO={kmo:.3f}, Bartlett p={bp:.2e}, "
            f"n_pcs_90%={n_pcs_for_90pct}). Linear embedding justified."
        )
        dim_alt = None
    else:
        dimred = "pca_with_caution"
        dim_reason = (
            f"Factorability weak or borderline (KMO={kmo}, Bartlett p={bp}, "
            f"pca_suitable={pca_suitable}). PCA may still be reported for continuity, "
            "but nonlinear embeddings (e.g. UMAP) are recommended for exploratory geometry."
        )
        dim_alt = "umap_recommended"
    decisions.append(
        {
            "task": "dimensionality_reduction",
            "choice": dimred,
            "alternative_recommended": dim_alt,
            "reason": dim_reason,
        }
    )

    # --- Multicollinearity handling ---
    mv = float(max_vif) if max_vif is not None and np.isfinite(max_vif) else float("nan")
    if np.isfinite(mv) and mv >= 10:
        multi = "vif_pruning_required"
        multi_reason = f"max_VIF={mv:.1f} indicates multicollinearity; iterative VIF / redundancy pruning required before discovery."
    else:
        multi = "vif_monitoring"
        multi_reason = f"max_VIF={mv} within tolerable band after filters; continue monitoring."
    decisions.append({"task": "multicollinearity", "choice": multi, "reason": multi_reason})

    # --- Downstream clustering / ML ---
    if n_rows < max(30, 5 * n_features):
        down = "limited_sample_caution"
        down_reason = f"n={n_rows}, p={n_features}: discovery/ML results should be treated as provisional (n/p limited)."
    else:
        down = "standard_discovery_ok"
        down_reason = f"n={n_rows}, p={n_features}: sample size adequate for multi-algorithm discovery with validation."
    decisions.append({"task": "downstream_discovery", "choice": down, "reason": down_reason})

    # Prefer non-parametric tests when non-normal
    testing = "nonparametric_preferred" if nonnormal_frac >= 0.30 else "parametric_ok_with_robustness"
    decisions.append(
        {
            "task": "hypothesis_testing_style",
            "choice": testing,
            "reason": f"nonnormal_frac={nonnormal_frac:.2f}",
        }
    )

    return {
        "engine": "StatisticalIntelligence",
        "phase": "F",
        "diagnostics": {
            "n_rows": n_rows,
            "n_features": n_features,
            "nonnormal_frac": nonnormal_frac,
            "kmo_model": kmo_model,
            "bartlett_p": bartlett_p,
            "max_vif": max_vif,
            "n_pcs_for_90pct": n_pcs_for_90pct,
            "pca_suitable": pca_suitable,
        },
        "decisions": decisions,
        "primary_association": association,
        "dimensionality_reduction": dimred,
        "dimensionality_alternative": dim_alt,
    }
