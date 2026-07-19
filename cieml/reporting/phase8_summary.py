"""Compile Phase 8 executive summary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase8_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    path = output_dir / "PHASE8_SUMMARY.md"
    s14 = payload.get("stage_14", {}).get("report", {})
    pillars = payload.get("stage_14", {}).get("pillars", {})
    lines = [
        "# CIEML 2.0 — Phase 8 Summary",
        "",
        "Phase completed: **Stage 14 (Robustness & reproducibility / four-pillar closure)**.",
        "",
        "## Robustness",
        f"- Baseline: {s14.get('baseline')}",
        f"- Tests passed: {s14.get('n_tests_pass')} pass / {s14.get('n_tests_fail')} fail "
        f"(frac={s14.get('robustness_frac_pass')})",
        f"- Critical checks: {s14.get('critical_pass_count')} → {json.dumps(s14.get('critical_checks'))}",
        f"- Regime structure call: **{s14.get('regime_structure_call')}**",
        "",
        "## Four-pillar closure (Evidence-Based Scientific Validation Engine)",
        f"- Campaign closure: **{pillars.get('campaign_closure')}** "
        f"(mean confidence {pillars.get('campaign_mean_confidence')}/100)",
        f"- Weakest evidence campaign-wide: {pillars.get('weakest_evidence')}",
    ]
    for hid, block in pillars.get("hypotheses", {}).items():
        pillar_scores = ", ".join(f"{p}={v['score']:.0f}" for p, v in block.get("pillars", {}).items())
        lines.append(
            f"- {hid}: **{block.get('classification')}** "
            f"(confidence {block.get('overall_confidence')}/100, {block.get('evidence_strength')}) | {pillar_scores}"
        )
    lines += [
        "",
        "## Artifacts",
        "- `stage14_sensitivity_results.csv`",
        "- `stage14_scientific_closure.md`",
        "- `fig_stage14_robustness_bars.png`",
        "",
        "## Framework status",
        "- Phases 1–8 complete for this campaign. Re-run on new data rather than transplanting thresholds.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
