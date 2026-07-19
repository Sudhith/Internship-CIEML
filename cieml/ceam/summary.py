"""Campaign-level coastal environmental summary."""
from __future__ import annotations

from typing import Any


def build_campaign_summary(
    *,
    regimes: list[dict[str, Any]],
    hydro: list[dict[str, Any]],
    wq: list[dict[str, Any]],
    meteo: list[dict[str, Any]],
    spatial: list[dict[str, Any]],
    temporal: list[dict[str, Any]],
    ecological: list[dict[str, Any]],
    fusion: dict[str, Any],
) -> dict[str, Any]:
    families = [r.get("interpretive_family") for r in regimes]
    dominant = max(regimes, key=lambda r: int(r.get("n") or 0)) if regimes else {}

    rain = next((u for u in meteo if u.get("topic") == "rainfall_influence"), {})
    harbour = next((u for u in spatial if u.get("topic") == "harbour_vs_open_coast"), {})
    hyp = next((u for u in ecological if u.get("topic") == "hypoxia_risk"), {})

    overview = (
        f"The campaign organizes into {len(regimes)} environmental regimes. "
        f"The dominant state is '{dominant.get('title')}' "
        f"({dominant.get('n')} station-days; family `{dominant.get('interpretive_family')}`). "
        f"Families present: {', '.join(sorted({f for f in families if f}))}."
    )

    overall = (
        f"Spatial structure: {harbour.get('interpretation', 'n/a')} "
        f"Meteorology: {rain.get('interpretation', 'n/a')} "
        f"Ecological: {hyp.get('interpretation', 'n/a')} "
        f"Rejected unsupported units: {fusion.get('n_rejected_unsupported', 0)}."
    )

    return {
        "dominant_coastal_processes": sorted({f for f in families if f and f != "insufficient_evidence_for_named_regime"}),
        "environmental_stability": {
            "dominant_regime": dominant.get("regime"),
            "dominant_title": dominant.get("title"),
            "dominant_fraction_hint": dominant.get("n"),
        },
        "spatial_heterogeneity": harbour.get("interpretation"),
        "water_quality_overview": [u.get("topic") + ": " + str(u.get("interpretation")) for u in wq if not u.get("rejected")],
        "meteorological_influences": rain.get("interpretation"),
        "key_anomalies": next((u.get("observation") for u in temporal if u.get("topic") == "recurring_anomalies"), None),
        "major_ecological_observations": [u for u in ecological if not u.get("rejected")],
        "overall_condition": overall,
        "overview_paragraph": overview,
        "hydrodynamics_bullets": [u.get("interpretation") for u in hydro if not u.get("rejected")],
        "temporal_behaviour": next((u.get("interpretation") for u in temporal if u.get("topic") == "transient_events_and_transitions"), None),
    }
