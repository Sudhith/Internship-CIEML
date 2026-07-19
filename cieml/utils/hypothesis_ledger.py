"""Append evidence and provisional verdicts to the Stage -1 hypothesis register."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_register(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_register(path: Path, register: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(register, indent=2, default=str), encoding="utf-8")


def append_evidence(
    register: dict[str, Any],
    hypothesis_id: str,
    stage: str,
    evidence: dict[str, Any],
    status: str | None = None,
    verdict: str | None = None,
) -> dict[str, Any]:
    hyps = register.setdefault("hypotheses", {})
    if hypothesis_id not in hyps:
        hyps[hypothesis_id] = {
            "null": None,
            "alternative": None,
            "status": "UNTESTED",
            "linked_questions": [],
            "evidence": [],
            "verdict": None,
        }
    entry = {
        "stage": stage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **evidence,
    }
    hyps[hypothesis_id].setdefault("evidence", []).append(entry)
    if status:
        hyps[hypothesis_id]["status"] = status
    if verdict is not None:
        hyps[hypothesis_id]["verdict"] = verdict
    return register
