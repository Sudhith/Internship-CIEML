"""Compile Phase 2 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase2_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE2_SUMMARY.md"
    s2 = payload.get("stage_02", {}).get("report", {})
    s3 = payload.get("stage_03", {}).get("report", {})

    lines = [
        "# CIEML 2.0 — Phase 2 Summary",
        "",
        "Phases completed: **Stage 2 (Sensor QA/QC)**, **Stage 3 (Physical validation)**.",
        "",
        "## Stage 2 — Sensor QA/QC",
        f"- Flag events: {s2.get('n_flag_events')}",
        f"- Files with flags: {s2.get('n_files_with_flags')} / {s2.get('n_files')} ({s2.get('file_flag_rate')})",
        f"- Cross-station co-occurrence patterns: {s2.get('cross_station_patterns')}",
        f"- Deletion policy: {s2.get('policy', {}).get('deletion')}",
        f"- H1 update: {s2.get('h1_update', {}).get('status')}",
        f"- Check counts: {json.dumps(s2.get('check_counts', {}))}",
        "",
        "## Stage 3 — Physical oceanographic validation",
        f"- Data-driven |rho| threshold: {s3.get('effect_threshold_abs_rho')}",
        f"- Required pairs supported: {s3.get('n_required_supported')} / {s3.get('n_required_pairs')}",
        f"- Required pairs broken: {s3.get('n_required_broken')}",
        f"- Support rate: {s3.get('support_rate_required')}",
        f"- Status counts: {json.dumps(s3.get('status_counts', {}))}",
        f"- H2 update: {s3.get('h2_update', {}).get('status')} ({s3.get('h2_update', {}).get('verdict_lean')})",
        "",
        "## Scientific discipline",
        "- No data deleted; flags retained with provenance.",
        "- Relationship magnitudes rediscovered from this dataset.",
        "- Conclusions remain provisional until Stage 14 four-pillar closure.",
        "",
        "## Next phase",
        "- Stage 4 Feature engineering",
        "- Stage 5 Statistical validation / redundancy",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
