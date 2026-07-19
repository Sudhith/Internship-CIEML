"""Compile Phase 4 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase4_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE4_SUMMARY.md"
    s6 = payload.get("stage_06", {}).get("report", {})
    s7 = payload.get("stage_07", {}).get("report", {})
    best = s6.get("best", {})
    lines = [
        "# CIEML 2.0 — Phase 4 Summary",
        "",
        "Phases completed: **Stage 6 (Regime discovery)**, **Stage 7 (Regime validation)**.",
        "",
        "## Stage 6 — Regime discovery",
        f"- Samples: {s6.get('n_samples')} | Features: {s6.get('n_features')}",
        f"- Candidates evaluated: {s6.get('n_candidates_evaluated')}",
        f"- Selected: **{best.get('algorithm')}** with **k={best.get('k')}**",
        f"- Silhouette: {best.get('silhouette')}",
        f"- Davies-Bouldin: {best.get('davies_bouldin')}",
        f"- Calinski-Harabasz: {best.get('calinski_harabasz')}",
        f"- Stability ARI: {best.get('stability_ari')}",
        f"- Composite score: {best.get('composite')}",
        "",
        "## Stage 7 — Regime validation",
        f"- Bootstrap ARI: {s7.get('bootstrap_ari_mean')} ± {s7.get('bootstrap_ari_std')}",
        f"- Cross-algorithm consensus ARI: {s7.get('consensus_ari_mean')}",
        f"- Consensus vs selected ARI: {s7.get('consensus_vs_best_ari')}",
        f"- LOSO ARI: {s7.get('loso_ari_mean')}",
        f"- LOWO ARI: {s7.get('lowo_ari_mean')}",
        f"- Checks passed: {s7.get('n_checks_passed')} / 5",
        f"- Structure call: **{s7.get('structure_call')}**",
        f"- H4 update: {s7.get('h4_update', {}).get('status')} ({s7.get('h4_update', {}).get('verdict_lean')})",
        f"- Check detail: {json.dumps(s7.get('structure_checks', {}))}",
        "",
        "## Next phase",
        "- Stage 8 Explainable ML (SHAP / importance)",
        "- Stage 9 Anomaly discovery",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
