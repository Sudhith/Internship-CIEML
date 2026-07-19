"""Compile Phase 5 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase5_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE5_SUMMARY.md"
    s8 = payload.get("stage_08", {}).get("report", {})
    s9 = payload.get("stage_09", {}).get("report", {})
    lines = [
        "# CIEML 2.0 — Phase 5 Summary",
        "",
        "Phases completed: **Stage 8 (Explainable ML)**, **Stage 9 (Anomaly discovery)**.",
        "",
        "## Stage 8 — Explainable ML",
        f"- Samples: {s8.get('n_samples')} | Features: {s8.get('n_features')} | Regimes: {s8.get('n_regimes')}",
        f"- Primary explainer: {s8.get('primary_explainer_model')}",
        f"- Models trained: {', '.join(s8.get('models_trained', []))}",
        f"- Dominant drivers: {', '.join(s8.get('driver_tiers', {}).get('Dominant', []))}",
        f"- Secondary drivers: {', '.join(s8.get('driver_tiers', {}).get('Secondary', []))}",
        f"- Negligible drivers: {', '.join(s8.get('driver_tiers', {}).get('Negligible', []))}",
        f"- Note: {s8.get('purpose_statement')}",
        "",
        "## Stage 9 — Anomaly discovery",
        f"- Contamination used: {s9.get('contamination_used')}",
        f"- Consensus anomalies: {s9.get('n_consensus_anomalies')} ({s9.get('consensus_rate')})",
        f"- Detector rates: {json.dumps(s9.get('method_rates', {}))}",
        f"- Physical class counts: {json.dumps(s9.get('category_counts', {}))}",
        f"- H5 update: {s9.get('h5_update', {}).get('status')} ({s9.get('h5_update', {}).get('verdict_lean')})",
        "",
        "## Next phase",
        "- Stage 10 External environmental validation",
        "- Stage 11 Spatial & temporal analysis",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
