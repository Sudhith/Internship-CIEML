"""Publication-oriented scientific narratives from CEAM packets."""
from __future__ import annotations

from typing import Any


def _fmt_unit(u: dict[str, Any]) -> list[str]:
    if u.get("rejected"):
        return [
            f"### {u.get('topic')} — REJECTED",
            f"- **Observation:** {u.get('observation')}",
            f"- **Reject reason:** {u.get('reject_reason')}",
            "",
        ]
    lines = [
        f"### {u.get('topic')}",
        f"- **Observation:** {u.get('observation')}",
        f"- **Interpretation:** {u.get('interpretation')}",
        f"- **Level:** {u.get('level')} | **Confidence:** {u.get('confidence')}",
    ]
    if u.get("uncertainty"):
        lines.append(f"- **Uncertainty:** {u.get('uncertainty')}")
    if u.get("alternatives"):
        lines.append("- **Alternatives:** " + "; ".join(u.get("alternatives") or []))
    if u.get("limitations"):
        lines.append("- **Limitations:** " + "; ".join(u.get("limitations") or []))
    ev = u.get("supporting_evidence") or []
    if ev:
        lines.append("- **Supporting evidence:**")
        for e in ev[:6]:
            lines.append(
                f"  - [{e.get('stage')}] {e.get('artifact')} · {e.get('variable')}={e.get('value')} — {e.get('note')} ({e.get('strength')})"
            )
    lines.append("")
    return lines


def build_scientific_narrative(
    *,
    campaign_id: str,
    domain: str,
    regimes: list[dict[str, Any]],
    hydro: list[dict[str, Any]],
    wq: list[dict[str, Any]],
    meteo: list[dict[str, Any]],
    spatial: list[dict[str, Any]],
    temporal: list[dict[str, Any]],
    ecological: list[dict[str, Any]],
    fusion: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    lines = [
        f"# Coastal Environmental Analysis — {campaign_id}",
        "",
        f"**Domain profile:** `{domain}`",
        "",
        "This narrative is produced by the CIEML Coastal Environmental Analysis Module (Stage 12 / CEAM). "
        "It interprets upstream framework artifacts and does not re-run QA, discovery, SHAP, anomaly detection, or EBSVE scoring.",
        "",
        "## Campaign overview",
        "",
        summary.get("overview_paragraph") or "",
        "",
        "## Environmental regimes",
        "",
    ]
    for r in regimes:
        lines += [
            f"### Regime {r.get('regime')}: {r.get('title')}",
            f"- **Family:** `{r.get('interpretive_family')}` | **Confidence:** {r.get('confidence')} | **Evidence score:** {r.get('evidence_score')}",
            f"- **n station-days:** {r.get('n')} | **Harbour-role share:** {r.get('harbour_role_membership_share')}",
            "- **Evidence:**",
        ]
        for e in r.get("evidence") or []:
            lines.append(f"  - {e}")
        lines.append("- **Speculation excluded:** " + "; ".join(r.get("speculation_excluded") or []))
        lines.append("")

    for section, block in [
        ("Hydrodynamic interpretation", hydro),
        ("Water quality assessment", wq),
        ("Meteorological interpretation", meteo),
        ("Spatial interpretation", spatial),
        ("Temporal interpretation", temporal),
        ("Ecological interpretation", ecological),
    ]:
        lines += [f"## {section}", ""]
        for u in block:
            lines.extend(_fmt_unit(u))

    lines += [
        "## Multi-source evidence fusion",
        "",
    ]
    lines.extend(_fmt_unit(fusion.get("fusion_packet") or {}))
    if fusion.get("ebsve_campaign_closure"):
        lines += [
            f"- **EBSVE campaign closure:** {fusion.get('ebsve_campaign_closure')} "
            f"(mean confidence={fusion.get('ebsve_mean_confidence')})",
            "",
        ]
    lines += [
        "## Overall environmental condition",
        "",
        summary.get("overall_condition") or "",
        "",
        "---",
        "",
        "*CEAM distinguishes Observation, Interpretation, Hypothesis, and Evidence. Unsupported causal claims are rejected.*",
        "",
    ]
    return "\n".join(lines)
