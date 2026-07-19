"""Stage -1: Research Question and Claim Register (legacy: Hypothesis Layer).

Phase J loads an open claim pack (`configs/claims/*.yaml`) instead of treating
H1–H6 as engine constants. Artifact filename stays
`stage_m1_hypothesis_register.json` for interchange compatibility; the register
body now also exposes `claims` / `claim_pack_id`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cieml.claims import load_claim_pack, resolve_pack_path
from cieml.config import DEFAULT_CLAIM_PACK, PHASE1_DIR


def run_stage_m1(
    hypotheses_path: Path | None = None,
    output_dir: Path | None = None,
    *,
    claim_pack: str | Path | None = None,
) -> dict[str, Any]:
    """Build the Stage -1 claim/hypothesis register from the active claim pack.

    `hypotheses_path` is accepted for backward compatibility but ignored when a
    claim pack is available (Phase J source of truth).
    """
    output_dir = Path(output_dir or PHASE1_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    pack_ref = claim_pack or DEFAULT_CLAIM_PACK
    # Optional: if caller still passes legacy hypotheses.yaml path as first arg
    # and no claim_pack, prefer the default pack unless the path is itself a pack.
    if hypotheses_path is not None and claim_pack is None:
        hp = Path(hypotheses_path)
        if hp.name.endswith(".yaml") and "claims" in str(hp).replace("\\", "/"):
            pack_ref = hp

    pack = load_claim_pack(str(pack_ref))
    questions = pack.scientific_questions
    hypotheses = pack.as_hypotheses_dict()

    register = {
        "framework": "CIEML-2.0",
        "version": pack.version,
        "claim_pack_id": pack.pack_id,
        "claim_pack_version": pack.version,
        "campaign_agnostic": pack.campaign_agnostic,
        "n_questions": len(questions),
        "n_hypotheses": len(hypotheses),
        "n_claims": len(hypotheses),
        "four_pillars": pack.four_pillars,
        "definitive_rule": pack.classification_rule,
        "forbidden_a_priori_assumptions": pack.assumptions_to_test_not_assume,
        "questions": questions,
        # Artifact-stable key
        "hypotheses": {
            hid: {
                "null": h.get("null"),
                "alternative": h.get("alternative"),
                "status": "UNTESTED",
                "linked_questions": h.get("linked_questions", []),
                "evidence": [],
                "verdict": None,
                "title": h.get("title"),
                "description": h.get("description"),
                "validator": h.get("validator"),
                "applicability": h.get("applicability") or {},
            }
            for hid, h in hypotheses.items()
        },
        # Phase J alias (same entries)
        "claims": {},
        "notes": [
            "Claim pack is configuration; pillar scoring stays in cieml.evidence.",
            "No prior numerical results, exclusion windows, K, or site thresholds are assumed.",
            "Each later stage must append evidence objects to claim/hypothesis records.",
            "Verdicts become DEFINITIVE only if all four pillars pass (weakest-pillar rule).",
            f"Loaded from claim pack: {resolve_pack_path(pack.pack_id)}",
        ],
    }
    register["claims"] = dict(register["hypotheses"])

    out_json = output_dir / "stage_m1_hypothesis_register.json"
    out_md = output_dir / "stage_m1_hypothesis_register.md"
    out_json.write_text(json.dumps(register, indent=2), encoding="utf-8")

    lines = [
        "# CIEML 2.0 — Stage -1 Claim Register",
        "",
        f"Framework: **CIEML-2.0** | Claim pack: `{pack.pack_id}` `{pack.version}`",
        "",
        "## Scientific questions",
    ]
    for qid, q in questions.items():
        lines.append(f"- **{qid}**: {q.get('text')}")
        lines.append(f"  - Tested by: {', '.join(q.get('tested_by', []))}")
    lines += ["", "## Claims (all UNTESTED at start)", ""]
    for hid, h in register["hypotheses"].items():
        title = h.get("title") or hid
        lines.append(f"### {hid} — {title}")
        lines.append(f"- H0: {h['null']}")
        lines.append(f"- H1: {h['alternative']}")
        lines.append(f"- Status: `{h['status']}`")
        lines.append("")
    lines += [
        "## Four-pillar rule",
        register.get("definitive_rule") or "",
        "",
        "## Must rediscover (never assume)",
    ]
    for item in register["forbidden_a_priori_assumptions"]:
        lines.append(f"- {item}")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    return {
        "register": register,
        "claim_pack_id": pack.pack_id,
        "outputs": {"json": str(out_json), "markdown": str(out_md)},
    }
