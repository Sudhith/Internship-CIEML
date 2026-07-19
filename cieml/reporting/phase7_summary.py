"""Compile Phase 7 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase7_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE7_SUMMARY.md"
    s12 = payload.get("stage_12", {}).get("report", {})
    s13 = payload.get("stage_13", {}).get("report", {})
    lines = [
        "# CIEML 2.0 — Phase 7 Summary",
        "",
        "Phases completed: **Stage 12 (Coastal Environmental Analysis / CEAM)**, **Stage 13 (Decision support)**.",
        "",
        "## Stage 12 — Coastal Environmental Analysis Module",
        f"- Regimes interpreted: {s12.get('n_regimes')}",
        f"- Naming policy: {s12.get('naming_policy')}",
        f"- CEAM domain: {(s12.get('ceam') or {}).get('domain')}",
        f"- Rejected unsupported units: {(s12.get('ceam') or {}).get('n_rejected_unsupported')}",
    ]
    for item in s12.get("interpretations", []):
        lines.append(
            f"- Regime {item.get('regime')}: **{item.get('title')}** "
            f"[{item.get('confidence')}; score={item.get('evidence_score')}]"
        )
    lines += [
        "",
        "## Stage 13 — Decision support",
        f"- Decision rules: {len(s13.get('decision_rules', []))}",
        f"- Early-warning indicators: {len(s13.get('early_warning_indicators', []))}",
        f"- Budget tiers: {json.dumps(s13.get('budget_tiers', []))}",
        f"- Transfer rule: {s13.get('applicability_domain', {}).get('transfer_rule')}",
        "",
        "## Next phase",
        "- Stage 14 Robustness & reproducibility",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
