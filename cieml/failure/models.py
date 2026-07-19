"""Failure mode data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"

    @property
    def rank(self) -> int:
        return {"INFO": 0, "WARNING": 1, "DEGRADED": 2, "CRITICAL": 3, "FATAL": 4}[self.value]


STATUS_FOR_SEVERITY = {
    Severity.INFO: "ok",
    Severity.WARNING: "warning",
    Severity.DEGRADED: "degraded",
    Severity.CRITICAL: "failed",
    Severity.FATAL: "aborted",
}


@dataclass
class FailureModeHit:
    mode_id: str
    engine_id: str
    severity: Severity
    title: str
    evidence: dict[str, Any] = field(default_factory=dict)
    recovery_applied: list[str] = field(default_factory=list)
    message: str = ""
    pillar_impact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "engine_id": self.engine_id,
            "severity": self.severity.value,
            "title": self.title,
            "evidence": self.evidence,
            "recovery_applied": self.recovery_applied,
            "message": self.message,
            "pillar_impact": self.pillar_impact,
        }
