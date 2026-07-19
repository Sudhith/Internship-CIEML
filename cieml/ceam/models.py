"""Four-level interpretation packets (Observation / Interpretation / Evidence / Confidence)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InterpretationUnit:
    """Atomic CEAM conclusion with mandatory four-level structure."""

    topic: str
    observation: str
    interpretation: str
    supporting_evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: str = "exploratory"  # exploratory | provisional | supported
    uncertainty: str = ""
    limitations: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    level: str = "interpretation"  # observation | interpretation | hypothesis
    rejected: bool = False
    reject_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "observation": self.observation,
            "interpretation": self.interpretation,
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "limitations": self.limitations,
            "alternatives": self.alternatives,
            "level": self.level,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
        }


def evidence_item(
    stage: str,
    artifact: str,
    variable: str | None,
    value: Any,
    note: str,
    strength: str = "moderate",
) -> dict[str, Any]:
    return {
        "stage": stage,
        "artifact": artifact,
        "variable": variable,
        "value": value,
        "note": note,
        "strength": strength,
    }
