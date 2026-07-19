"""Load configs/failure/catalog.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "configs" / "failure" / "catalog.yaml"


@dataclass
class FailureMode:
    mode_id: str
    engine_id: str
    class_id: str
    severity: str
    title: str
    detection: str | None = None
    recovery: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureCatalog:
    version: str
    policy: dict[str, Any]
    thresholds: dict[str, Any]
    modes: list[FailureMode]

    def modes_for(self, engine_id: str) -> list[FailureMode]:
        return [m for m in self.modes if m.engine_id == engine_id]

    def by_id(self) -> dict[str, FailureMode]:
        return {m.mode_id: m for m in self.modes}


@lru_cache(maxsize=2)
def load_failure_catalog(path: str | None = None) -> FailureCatalog:
    p = Path(path) if path else CATALOG_PATH
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    modes = []
    for m in raw.get("modes") or []:
        modes.append(
            FailureMode(
                mode_id=str(m["mode_id"]),
                engine_id=str(m["engine_id"]),
                class_id=str(m.get("class") or ""),
                severity=str(m.get("severity") or "WARNING"),
                title=str(m.get("title") or m["mode_id"]),
                detection=m.get("detection"),
                recovery=list(m.get("recovery") or []),
                raw=dict(m),
            )
        )
    return FailureCatalog(
        version=str(raw.get("version") or "0"),
        policy=dict(raw.get("policy") or {}),
        thresholds=dict(raw.get("thresholds") or {}),
        modes=modes,
    )
