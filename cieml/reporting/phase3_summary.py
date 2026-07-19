"""Compile Phase 3 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase3_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE3_SUMMARY.md"
    s4 = payload.get("stage_04", {}).get("report", {})
    s5 = payload.get("stage_05", {}).get("report", {})
    lines = [
        "# CIEML 2.0 — Phase 3 Summary",
        "",
        "Phases completed: **Stage 4 (Feature engineering)**, **Stage 5 (Statistical validation)**.",
        "",
        "## Stage 4 — Feature engineering",
        f"- Station-days: {s4.get('n_station_days')}",
        f"- Base variables used: {', '.join(s4.get('base_variables_used', []))}",
        f"- Catalog features: {s4.get('n_catalog_features')}",
        f"- Analysis features: {s4.get('n_analysis_features')}",
        f"- Indices: {', '.join(s4.get('index_features', []))}",
        f"- Family counts: {json.dumps(s4.get('family_counts', {}))}",
        "",
        "## Stage 5 — Statistical validation",
        f"- Primary features tested: {s5.get('n_primary_features_kept_for_tests')}",
        f"- Retained for downstream: {s5.get('n_retained_for_downstream')}",
        f"- Retained set: {', '.join(s5.get('retained_features', []))}",
        f"- Removed: {s5.get('n_removed')}",
        f"- KMO: {s5.get('factorability', {}).get('kmo_model')}",
        f"- Bartlett p: {s5.get('factorability', {}).get('bartlett_p')}",
        f"- PCA suitable: {s5.get('factorability', {}).get('pca_suitable')}",
        f"- PCs for 90% variance: {s5.get('factorability', {}).get('n_pcs_for_90pct')}",
        f"- H3 update: {s5.get('h3_update', {}).get('status')} ({s5.get('h3_update', {}).get('verdict_lean')})",
        "",
        "## Next phase",
        "- Stage 6 Environmental regime discovery (multi-algorithm clustering)",
        "- Stage 7 Regime validation",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
