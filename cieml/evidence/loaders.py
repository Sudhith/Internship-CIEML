"""Defensive loaders for the upstream stage artifacts the evidence engine consumes.

Every loader returns an empty/None-safe default when an artifact is absent so a
missing optional phase never crashes the audit — but the resulting pillar score
must reflect that absence via `scoring.score_from_fraction`/`score_from_bands`
(which score missing/NaN evidence as 0), never by silently substituting a made-up
value. `build_evidence_bundle` is the single place that knows every filename the
engine depends on (via the Phase J artifact contract in `artifacts.py`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from cieml.evidence.artifacts import ARTIFACT_CONTRACT_VERSION, ARTIFACT_SPECS, resolve_artifact_path


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_json_list(path: Path | None) -> list[Any]:
    if path is None or not Path(path).exists():
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def load_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not Path(path).exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.ParserError, OSError):
        return pd.DataFrame()


def build_evidence_bundle(
    phase1_dir: Path | None,
    phase2_dir: Path | None,
    phase3_dir: Path | None,
    phase4_dir: Path | None,
    phase5_dir: Path | None,
    phase6_dir: Path | None,
    phase7_dir: Path | None,
) -> dict[str, Any]:
    phase_dirs = {
        1: Path(phase1_dir) if phase1_dir else None,
        2: Path(phase2_dir) if phase2_dir else None,
        3: Path(phase3_dir) if phase3_dir else None,
        4: Path(phase4_dir) if phase4_dir else None,
        5: Path(phase5_dir) if phase5_dir else None,
        6: Path(phase6_dir) if phase6_dir else None,
        7: Path(phase7_dir) if phase7_dir else None,
    }

    bundle: dict[str, Any] = {
        "_artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
    }
    for spec in ARTIFACT_SPECS:
        path = resolve_artifact_path(phase_dirs.get(spec.phase), spec)
        if spec.kind == "csv":
            bundle[spec.key] = load_csv(path)
        elif spec.kind == "json_list":
            bundle[spec.key] = load_json_list(path)
        else:
            bundle[spec.key] = load_json(path)

    # Backward-compatible alias used by older call sites / notes
    if "stage12_interpretations" in bundle:
        pass  # already set via contract
    return bundle
