"""Probable-origin classification for consensus anomalies (Phase I).

Taxonomy: sensor | environmental | temporal | multivariate | contextual | novel_state
Origin labels are probabilistic heuristics, not courtroom proof.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


ORIGIN_TYPES = (
    "sensor",
    "environmental",
    "temporal",
    "multivariate",
    "contextual",
    "novel_state",
)


def assign_probable_origins(cat_df: pd.DataFrame) -> pd.DataFrame:
    """Add origin_primary, origin_confidence, origin_rationale from existing class fields."""
    if cat_df is None or not len(cat_df):
        return pd.DataFrame()

    rows = []
    for _, r in cat_df.iterrows():
        physical = str(r.get("physical_class") or "")
        temporal = str(r.get("temporal_class") or "")
        spatial = str(r.get("spatial_class") or "")
        n_methods = int(r.get("n_methods_flagged") or 0)
        top_z = abs(float(r.get("top_feature_z") or 0.0))
        top_feat = str(r.get("top_feature") or "")

        scores = {o: 0.0 for o in ORIGIN_TYPES}

        # Detector agreement → multivariate trust
        if n_methods >= 3:
            scores["multivariate"] += 0.35
        elif n_methods >= 2:
            scores["multivariate"] += 0.20

        # Temporal clustering of anomalies
        if temporal == "temporal_event":
            scores["temporal"] += 0.45
            scores["environmental"] += 0.15
        elif temporal == "isolated_in_time":
            scores["novel_state"] += 0.10

        # Station-specific elevation → contextual / local process
        if spatial == "station_specific":
            scores["contextual"] += 0.40
        else:
            scores["environmental"] += 0.10

        # Physical heuristics
        if physical == "environmental_or_optical_spike":
            # extreme optical spikes can be sensor fouling OR sediment event
            if top_z >= 5:
                scores["sensor"] += 0.35
                scores["environmental"] += 0.25
            else:
                scores["environmental"] += 0.40
        elif physical in {"oxygen_regime_excursion", "salinity_mixing_excursion", "carbonate_ph_excursion"}:
            scores["environmental"] += 0.45
            if spatial == "station_specific":
                scores["contextual"] += 0.15
        elif physical == "multivariate_outlier":
            scores["multivariate"] += 0.35
            scores["novel_state"] += 0.20

        # Very extreme single-feature z with weak multi-method → lean sensor
        if top_z >= 6 and n_methods <= 2:
            scores["sensor"] += 0.25

        primary = max(scores, key=scores.get)
        total = float(sum(scores.values()) + 1e-12)
        conf = float(scores[primary] / total)
        # scale confidence by detector agreement
        conf = float(np.clip(conf * (0.6 + 0.1 * n_methods), 0.05, 0.95))

        rationale = (
            f"primary={primary} from spatial={spatial}, temporal={temporal}, "
            f"physical={physical}, top={top_feat} (z={top_z:+.2f}), detectors={n_methods}"
        )
        rows.append(
            {
                **r.to_dict(),
                "origin_primary": primary,
                "origin_confidence": round(conf, 3),
                "origin_scores": {k: round(v, 3) for k, v in scores.items()},
                "origin_rationale": rationale,
            }
        )

    out = pd.DataFrame(rows)
    # Flatten origin_scores for CSV friendliness
    if len(out):
        for o in ORIGIN_TYPES:
            out[f"origin_score_{o}"] = out["origin_scores"].apply(lambda d, k=o: float((d or {}).get(k, 0.0)))
        out = out.drop(columns=["origin_scores"])
    return out
