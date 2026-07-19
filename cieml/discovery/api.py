"""Discovery Engine API helpers — algorithm/K agnostic."""
from __future__ import annotations

from typing import Any

import pandas as pd


def build_selection_trace(
    ranked: pd.DataFrame,
    best: dict[str, Any],
    *,
    k_range: range | list[int],
    candidate_algorithms: list[str],
) -> dict[str, Any]:
    """Document candidate → compare → select without assuming ward/k=3."""
    top = ranked.head(5).copy() if len(ranked) else pd.DataFrame()
    return {
        "pipeline": [
            "generate_candidates",
            "score_internal_indices",
            "bootstrap_stability",
            "composite_rank",
            "select_best",
            "validate_externally",  # Stage 7
        ],
        "candidate_algorithms": candidate_algorithms,
        "k_range": list(k_range),
        "n_candidates_ranked": int(len(ranked)),
        "selected": {
            "algorithm": best.get("algorithm"),
            "k": int(best["k"]) if best.get("k") is not None else None,
            "composite": best.get("composite"),
            "silhouette": best.get("silhouette"),
            "stability_ari": best.get("stability_ari"),
        },
        "top5": top.to_dict(orient="records") if len(top) else [],
        "guarantee": "No predetermined K or algorithm; selection is data-driven under declared candidates.",
    }


def discovery_contract_block() -> dict[str, Any]:
    return {
        "contract_id": "SC-DISC",
        "semantic_labels": "out_of_scope",
        "note": "Regime IDs are unlabeled integers until process-labeling (Stage 12 / domain vocab).",
    }
