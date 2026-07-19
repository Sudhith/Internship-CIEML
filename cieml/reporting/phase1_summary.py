"""Compile Phase 1 executive summary for manuscript drafting."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase1_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE1_SUMMARY.md"
    m1 = payload.get("stage_m1", {})
    s0 = payload.get("stage_00", {})
    s1 = payload.get("stage_01", {})

    rep0 = s0.get("report", {})
    rep1 = s1.get("report", {})

    lines = [
        "# CIEML 2.0 — Phase 1 Summary",
        "",
        "Phases completed: **Stage -1**, **Stage 0**, **Stage 1**.",
        "",
        "## Stage -1 — Hypothesis layer",
        f"- Questions registered: {m1.get('register', {}).get('n_questions')}",
        f"- Hypotheses registered: {m1.get('register', {}).get('n_hypotheses')} (all start UNTESTED)",
        "",
        "## Stage 0 — Ingestion",
        f"- Files discovered: {rep0.get('n_files_discovered')}",
        f"- Files loaded: {rep0.get('n_files_loaded')}",
        f"- Failures: {rep0.get('n_files_failed')}",
        f"- Observations: {rep0.get('n_observations')}",
        f"- Stations: {', '.join(rep0.get('stations', []))}",
        f"- Date range: {rep0.get('date_range', {}).get('min')} → {rep0.get('date_range', {}).get('max')}",
        f"- Core variables present: {', '.join(rep0.get('canonical_variables_present', []))}",
        "",
        "## Stage 1 — Scientific audit",
        f"- Issues flagged: {rep1.get('n_issues')}",
        f"- Severity counts: {json.dumps(rep1.get('severity_counts', {}))}",
        f"- H1 provisional status: {rep1.get('h1_provisional', {}).get('status')}",
        "",
        "## Evidence discipline",
        "- No prior-paper numbers reused.",
        "- No exclusion windows, K, or rainfall effects assumed.",
        "- Literature plausibility bands used only for QA screening, not as site truth.",
        "",
        "## Next phase",
        "- Stage 2 Sensor QA/QC",
        "- Stage 3 Physical oceanographic validation",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
