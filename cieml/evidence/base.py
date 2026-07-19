"""Core types and the shared validator contract for the evidence engine.

Every `HypothesisValidator` subclass implements exactly four evaluation methods —
one per pillar — and each must return a `Pillar` whose score is computed from
`EvidenceItem`s that name their upstream source. The base class owns confidence
aggregation, classification, and reasoning generation so every hypothesis is
scored by the same shared, documented logic; subclasses cannot silently skip a
pillar or hardcode a status because `evaluate_*` is abstract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from cieml.evidence.scoring import classify, evidence_strength_label, maturity_label, weighted_mean

PILLAR_NAMES = ("statistical", "practical", "physical", "environmental")


@dataclass
class EvidenceItem:
    """One measurable fact feeding a pillar score, with its source traced so a
    reviewer can find exactly where a number came from."""

    name: str
    value: Any
    source: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "source": self.source, "interpretation": self.interpretation}


@dataclass
class Pillar:
    """One of the four evidence pillars for a hypothesis."""

    name: str
    score: float
    evidence: list[EvidenceItem] = field(default_factory=list)
    reasoning: str = ""
    weaknesses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(float(self.score), 1),
            "evidence": [e.to_dict() for e in self.evidence],
            "reasoning": self.reasoning,
            "weaknesses": self.weaknesses,
        }


@dataclass
class HypothesisAssessment:
    """Per-claim four-pillar assessment (legacy name kept for artifact stability).

    Phase J public alias: `ClaimAssessment`. Serialized dicts include both
    `hypothesis_id` and `claim_id` with the same value.
    """

    hypothesis_id: str
    null_hypothesis: str | None
    alternative_hypothesis: str | None
    pillars: dict[str, Pillar]
    pillar_weights: dict[str, float]
    overall_confidence: float
    evidence_strength: str
    scientific_maturity: str
    classification: str
    reasoning_summary: str
    limitations: list[str]
    future_validation: list[str]
    assumptions: list[str]

    @property
    def claim_id(self) -> str:
        return self.hypothesis_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "claim_id": self.hypothesis_id,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "pillars": {k: v.to_dict() for k, v in self.pillars.items()},
            "pillar_weights": self.pillar_weights,
            "overall_confidence": round(float(self.overall_confidence), 1),
            "evidence_strength": self.evidence_strength,
            "scientific_maturity": self.scientific_maturity,
            "classification": self.classification,
            "reasoning_summary": self.reasoning_summary,
            "limitations": self.limitations,
            "future_validation": self.future_validation,
            "assumptions": self.assumptions,
        }


# Phase J product rename (public API); internal ABC remains HypothesisValidator.
ClaimAssessment = HypothesisAssessment


class HypothesisValidator(ABC):
    """Base class for all per-hypothesis evidence validators.

    Construct with a pre-loaded `evidence` bundle (see `cieml.evidence.loaders`)
    and the Stage -1 hypothesis register. Call `run()` to get a full
    `HypothesisAssessment`. Pillar weights default to equal (25% each); override
    `pillar_weights` in a subclass only when a hypothesis has a documented reason
    for weighting pillars unevenly (state the reason in a comment if you do).
    """

    hypothesis_id: str
    pillar_weights: dict[str, float] = {"statistical": 1.0, "practical": 1.0, "physical": 1.0, "environmental": 1.0}

    def __init__(self, evidence: dict[str, Any], register: dict[str, Any] | None = None):
        self.evidence = evidence
        self.register = register or {}

    @abstractmethod
    def evaluate_statistical(self) -> Pillar: ...

    @abstractmethod
    def evaluate_practical(self) -> Pillar: ...

    @abstractmethod
    def evaluate_physical(self) -> Pillar: ...

    @abstractmethod
    def evaluate_environmental(self) -> Pillar: ...

    def generate_limitations(self, pillars: dict[str, Pillar]) -> list[str]:
        return [w for p in pillars.values() for w in p.weaknesses]

    def generate_future_validation(self, pillars: dict[str, Pillar], classification: str) -> list[str]:
        if classification == "DEFINITIVE":
            return []
        weakest = min(pillars.values(), key=lambda p: p.score)
        return [f"Strengthen the {weakest.name} pillar (currently weakest at {weakest.score:.0f}/100) before treating this hypothesis as settled."]

    def generate_assumptions(self) -> list[str]:
        return []

    def compute_confidence(self, pillars: dict[str, Pillar]) -> float:
        return weighted_mean({k: p.score for k, p in pillars.items()}, self.pillar_weights)

    def classify_claim(self, pillars: dict[str, Pillar]) -> str:
        return classify({k: p.score for k, p in pillars.items()})

    def generate_reasoning(self, pillars: dict[str, Pillar], confidence: float, classification: str) -> str:
        parts = [f"{p.name}={p.score:.0f}/100 ({p.reasoning})" for p in pillars.values()]
        return f"{classification} at confidence {confidence:.0f}/100 — " + "; ".join(parts)

    def run(self) -> HypothesisAssessment:
        pillars = {
            "statistical": self.evaluate_statistical(),
            "practical": self.evaluate_practical(),
            "physical": self.evaluate_physical(),
            "environmental": self.evaluate_environmental(),
        }
        confidence = self.compute_confidence(pillars)
        classification = self.classify_claim(pillars)
        min_score = min(p.score for p in pillars.values())
        reg_claims = self.register.get("claims") or self.register.get("hypotheses") or {}
        reg_hyp = reg_claims.get(self.hypothesis_id, {})
        return HypothesisAssessment(
            hypothesis_id=self.hypothesis_id,
            null_hypothesis=reg_hyp.get("null") or reg_hyp.get("null_hypothesis"),
            alternative_hypothesis=reg_hyp.get("alternative") or reg_hyp.get("alternative_hypothesis"),
            pillars=pillars,
            pillar_weights=dict(self.pillar_weights),
            overall_confidence=confidence,
            evidence_strength=evidence_strength_label(confidence),
            scientific_maturity=maturity_label(confidence, min_score),
            classification=classification,
            reasoning_summary=self.generate_reasoning(pillars, confidence, classification),
            limitations=self.generate_limitations(pillars),
            future_validation=self.generate_future_validation(pillars, classification),
            assumptions=self.generate_assumptions(),
        )
