"""Compile Phase 6 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase6_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE6_SUMMARY.md"
    s10 = payload.get("stage_10", {}).get("report", {})
    s11 = payload.get("stage_11", {}).get("report", {})
    lines = [
        "# CIEML 2.0 — Phase 6 Summary",
        "",
        "Phases completed: **Stage 10 (External validation)**, **Stage 11 (Spatial & temporal)**.",
        "",
        "## Stage 10 — External environmental validation",
        f"- Region: {s10.get('region')}",
        f"- Date range: {s10.get('date_range')}",
        f"- Fetch notes: {s10.get('fetch_notes')}",
        f"- Meteo days: {s10.get('n_meteo_days')}",
        f"- Significant cross-correlations (p<0.05 uncorrected): {s10.get('n_significant_crosscorr_05')} / {s10.get('n_crosscorr_tests')}",
        f"- Significant cross-correlations (FDR-corrected, q<0.05): {s10.get('n_significant_crosscorr_fdr_05')} / {s10.get('n_crosscorr_tests')}",
        f"- Anomaly external support fraction: {s10.get('anomaly_external_support_frac')}",
        f"- H5 update: {s10.get('h5_update', {}).get('status')} ({s10.get('h5_update', {}).get('verdict_lean')})",
        f"- Limitations: {'; '.join(s10.get('limitations', []))}",
        "",
        "## Stage 11 — Spatial & temporal analysis",
        f"- Stations: {s11.get('n_stations')} | Days: {s11.get('n_days')}",
        f"- Network edges: {s11.get('n_network_edges')}",
        f"- Regime transitions observed: {s11.get('n_regime_transitions')}",
        f"- PCA variance: {s11.get('pca_var_explained')}",
        f"- Strongest spatial gradients: {json.dumps(s11.get('strongest_spatial_gradients', [])[:3])}",
        "",
        "## Next phase",
        "- Stage 12 Ecological interpretation",
        "- Stage 13 Decision support",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
