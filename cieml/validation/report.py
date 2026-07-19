"""Build certification report artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cieml.validation.suite import run_validation_suite

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "outputs" / "framework_validation"

CONTRACTS = [
    "SC-DCL", "SC-ING", "SC-QA", "SC-PHYS", "SC-STAT", "SC-DISC", "SC-XAI",
    "SC-ANOM", "SC-EBSVE", "SC-DSS", "SC-APP", "SC-KB", "SC-MMU", "SC-REL",
    "SC-FMF", "SC-FVE",
]
CATEGORIES = ["V-ARCH", "V-SCI", "V-SOFT", "V-REPRO", "V-ROB", "V-EXT", "V-TRANS", "V-TRACE"]


def build_compliance_matrix(suite_result: dict[str, Any]) -> dict[str, Any]:
    """Sparse matrix: category cells filled from suite results only."""
    by_cat: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for r in suite_result.get("results") or []:
        cat = r.get("category")
        if cat in by_cat:
            by_cat[cat].append(r["status"])

    # Contract-level detail is manual/partial until full mapping; mark from groups.
    matrix = {cid: {c: "n/a" for c in CATEGORIES} for cid in CONTRACTS}
    # Heuristic fill from suite categories present
    cat_status = {}
    for cat, statuses in by_cat.items():
        if not statuses:
            cat_status[cat] = "n/a"
        elif any(s == "fail" for s in statuses):
            cat_status[cat] = "fail"
        elif any(s == "skip" for s in statuses):
            cat_status[cat] = "partial"
        else:
            cat_status[cat] = "pass"

    # Apply category status across all contracts as framework-level signal
    # (per-contract fine mapping is a Phase extension).
    for cid in CONTRACTS:
        for cat, st in cat_status.items():
            matrix[cid][cat] = st

    return {"categories": CATEGORIES, "contracts": CONTRACTS, "cells": matrix, "category_status": cat_status}


def build_certification_report(output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir or OUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    suite_result = run_validation_suite()
    matrix = build_compliance_matrix(suite_result)

    # Framework version from framework.yaml if present
    fw_ver = "unknown"
    fw_path = ROOT / "configs" / "framework.yaml"
    if fw_path.exists():
        import yaml

        fw = yaml.safe_load(fw_path.read_text(encoding="utf-8")) or {}
        fw_ver = str((fw.get("framework") or {}).get("version") or "unknown")

    report = {
        "framework_name": "CIEML",
        "framework_version": fw_ver,
        "certification_status": suite_result["certification_status"],
        "suite_version": suite_result.get("suite_version"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_demonstration": suite_result.get("primary_demonstration"),
        "suite": suite_result,
        "compliance_matrix": matrix,
        "readiness": {
            "critical_fails": suite_result.get("critical_fails") or [],
            "blocker": bool(suite_result.get("critical_fails")),
        },
    }

    (output_dir / "certification_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (output_dir / "compliance_matrix.json").write_text(
        json.dumps(matrix, indent=2), encoding="utf-8"
    )
    (output_dir / "certification_report.md").write_text(
        _to_markdown(report), encoding="utf-8"
    )
    return report


def _to_markdown(report: dict[str, Any]) -> str:
    s = report["suite"]
    lines = [
        "# CIEML Framework Certification Report",
        "",
        f"- **Status:** `{report['certification_status']}`",
        f"- **Framework version:** {report['framework_version']}",
        f"- **Suite version:** {report.get('suite_version')}",
        f"- **Generated (UTC):** {report['generated_at']}",
        f"- **Demonstration:** {report.get('primary_demonstration')}",
        "",
        "## Suite summary",
        "",
        f"Passed: {s['n_pass']} · Failed: {s['n_fail']} · Skipped: {s['n_skip']}",
        "",
        "### Results",
        "",
        "| Test | Group | Critical | Status | Detail |",
        "|------|-------|----------|--------|--------|",
    ]
    for r in s["results"]:
        lines.append(
            f"| `{r['id']}` | {r.get('group')} | {r.get('critical')} | **{r['status']}** | {r.get('detail','')} |"
        )
    lines += [
        "",
        "## Critical failures",
        "",
    ]
    cf = s.get("critical_fails") or []
    if not cf:
        lines.append("_None._")
    else:
        for x in cf:
            lines.append(f"- `{x}`")
    lines += [
        "",
        "## Compliance matrix (category roll-up)",
        "",
        "| Category | Status |",
        "|----------|--------|",
    ]
    for cat, st in (report.get("compliance_matrix") or {}).get("category_status", {}).items():
        lines.append(f"| {cat} | {st} |")
    lines += [
        "",
        "## Notes",
        "",
        "This certifies framework process integrity, not case-study environmental truth.",
        "See `docs/validation/` for methodology, audits, and readiness checklist.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    report = build_certification_report()
    print(f"certification_status={report['certification_status']}")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
