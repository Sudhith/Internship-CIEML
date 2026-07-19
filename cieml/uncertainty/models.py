"""Data models for the Uncertainty Model v2 (Measurement & Model Uncertainty +
Evidence Reliability, both distinct from EBSVE Confidence).

See docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md for the full mathematical
justification. Every component now declares a `provenance_id` (its root cause)
and `resolves_upstream` (whether it corroborates the same question the parent
engine already had doubt about, vs. introduces doubt about a new question) —
these two fields are what makes the v2 propagation model in `propagate.py`
possible: provenance dedup prevents the same root cause being counted twice,
and the corroborating/new split is what lets uncertainty decrease when evidence
agrees instead of only ever accumulating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class UncertaintyKind(str, Enum):
    RANDOM = "random"
    SYSTEMATIC = "systematic"
    SAMPLING = "sampling"
    SENSOR = "sensor"
    MODEL = "model"
    INTERPRETATION = "interpretation"
    EXTERNAL = "external"


class UncertaintyObject(str, Enum):
    MEASUREMENT = "measurement"
    SENSOR = "sensor"
    QA = "qa"
    STATISTICAL = "statistical"
    MODEL = "model"
    EXPLAINABILITY = "explainability"
    ANOMALY = "anomaly"
    POLICY = "policy"
    ENVIRONMENTAL = "environmental"
    DECISION = "decision"
    SCIENTIFIC_CLAIM = "scientific_claim"


def _clip(x: float) -> float:
    return float(max(0.0, min(100.0, x)))


@dataclass
class UncertaintyComponent:
    kind: UncertaintyKind
    value: float
    source: str
    rationale: str
    # v2 additions — see module docstring.
    provenance_id: str = "unspecified"
    resolves_upstream: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            self.kind = UncertaintyKind(self.kind)
        self.value = _clip(float(self.value))
        if not self.provenance_id:
            self.provenance_id = "unspecified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "value": round(self.value, 2),
            "source": self.source,
            "rationale": self.rationale,
            "provenance_id": self.provenance_id,
            "resolves_upstream": self.resolves_upstream,
        }


@dataclass
class UncertaintyBudget:
    """v2 budget — replaces v1's single `total` with the full Inherited / Resolved /
    New / Remaining / Net bookkeeping (docs §6). `remaining` and `net` are identical
    by definition (see design doc); both are kept because the requested vocabulary
    names them separately.
    """

    object_type: UncertaintyObject
    components: list[UncertaintyComponent] = field(default_factory=list)
    inherited: float = 0.0
    resolved: float = 0.0
    new_uncertainty: float = 0.0
    remaining: float = 0.0
    net: float = 0.0
    rule_id: str = "V2_correlated_fusion"
    rule_detail: str = ""
    dedup_warnings: list[str] = field(default_factory=list)
    # Unbounded raw intensity behind `remaining` (pre-saturation). NOT for display —
    # for chaining into the next engine's `parent_raw`. Saturating this again before
    # re-combining would silently reintroduce the repeated-saturation artifact this
    # redesign exists to remove (saturate() must be applied exactly once, at the
    # final report boundary — see propagate.saturate docstring).
    raw_total: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.object_type, str):
            self.object_type = UncertaintyObject(self.object_type)
        self.inherited = _clip(float(self.inherited))
        self.resolved = _clip(float(self.resolved))
        self.new_uncertainty = _clip(float(self.new_uncertainty))
        self.remaining = _clip(float(self.remaining))
        self.net = _clip(float(self.net))
        self.raw_total = max(0.0, float(self.raw_total))

    @property
    def total(self) -> float:
        """Legacy alias for `remaining`, kept only so any stray v1 reference fails
        loudly with a clear value rather than an AttributeError elsewhere; prefer
        `.remaining` in new code."""
        return self.remaining

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type.value,
            "components": [c.to_dict() for c in self.components],
            "inherited": round(self.inherited, 2),
            "resolved": round(self.resolved, 2),
            "new_uncertainty": round(self.new_uncertainty, 2),
            "remaining": round(self.remaining, 2),
            "net": round(self.net, 2),
            "rule_id": self.rule_id,
            "rule_detail": self.rule_detail,
            "dedup_warnings": list(self.dedup_warnings),
            "raw_total": round(self.raw_total, 3),
        }


@dataclass
class EngineUncertaintyPacket:
    """Mandatory scientific envelope for an engine output.

    Three independent axes per docs §3: `confidence` (EBSVE, unchanged),
    `uncertainty` (Measurement & Model Uncertainty budget, this module),
    `evidence_reliability` (coverage/completeness score, `reliability.py`).
    None is derived from another.
    """

    engine: str
    object_type: UncertaintyObject
    result_ref: str
    confidence: float | None
    uncertainty: UncertaintyBudget
    limitations: list[str] = field(default_factory=list)
    remaining_unknowns: list[str] = field(default_factory=list)
    evidence_reliability: float | None = None
    evidence_reliability_detail: dict[str, Any] | None = None
    confidence_gained: float | None = None
    caution: float | None = None  # optional legacy triage scalar — see propagate.caution_index

    def __post_init__(self) -> None:
        if isinstance(self.object_type, str):
            self.object_type = UncertaintyObject(self.object_type)
        if self.confidence is not None:
            self.confidence = _clip(float(self.confidence))
        if self.evidence_reliability is not None:
            self.evidence_reliability = _clip(float(self.evidence_reliability))
        if self.caution is not None:
            self.caution = _clip(float(self.caution))

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "object_type": self.object_type.value,
            "result_ref": self.result_ref,
            "confidence": None if self.confidence is None else round(self.confidence, 2),
            "uncertainty": self.uncertainty.to_dict(),
            "limitations": list(self.limitations),
            "remaining_unknowns": list(self.remaining_unknowns),
            "evidence_reliability": None if self.evidence_reliability is None else round(self.evidence_reliability, 2),
            "evidence_reliability_detail": self.evidence_reliability_detail,
            "confidence_gained": None if self.confidence_gained is None else round(self.confidence_gained, 2),
            "caution": None if self.caution is None else round(self.caution, 2),
        }
