"""ScientificClaim schema — public claim surface for EBSVE packs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScientificClaim:
    """One auditable scientific claim in a claim pack.

    Runtime pillar scores / confidence / classification are produced by the
    bound `HypothesisValidator` plugin; this object holds pack metadata only.
    """

    claim_id: str
    title: str
    description: str
    null_hypothesis: str | None = None
    alternative_hypothesis: str | None = None
    validator: str | None = None  # "module.path:ClassName"
    linked_questions: list[str] = field(default_factory=list)
    accept_if: list[str] = field(default_factory=list)
    reject_if: list[str] = field(default_factory=list)
    expected_mechanisms: list[str] = field(default_factory=list)
    applicability: dict[str, Any] = field(default_factory=dict)
    future_validation_seeds: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScientificClaim":
        claim_id = str(data.get("claim_id") or data.get("id") or "").strip()
        if not claim_id:
            raise ValueError("ScientificClaim requires claim_id")
        title = str(data.get("title") or claim_id)
        description = str(
            data.get("description")
            or data.get("alternative_hypothesis")
            or data.get("alternative")
            or title
        )
        return cls(
            claim_id=claim_id,
            title=title,
            description=description,
            null_hypothesis=data.get("null_hypothesis", data.get("null")),
            alternative_hypothesis=data.get("alternative_hypothesis", data.get("alternative")),
            validator=data.get("validator"),
            linked_questions=list(data.get("linked_questions") or []),
            accept_if=list(data.get("accept_if") or []),
            reject_if=list(data.get("reject_if") or []),
            expected_mechanisms=list(data.get("expected_mechanisms") or []),
            applicability=dict(data.get("applicability") or {}),
            future_validation_seeds=list(data.get("future_validation") or data.get("future_validation_seeds") or []),
            raw=dict(data),
        )

    def to_register_entry(self) -> dict[str, Any]:
        """Shape expected by the Stage -1 hypothesis/claim register."""
        return {
            "claim_id": self.claim_id,
            "title": self.title,
            "description": self.description,
            "null": self.null_hypothesis,
            "alternative": self.alternative_hypothesis,
            "status": "UNTESTED",
            "linked_questions": list(self.linked_questions),
            "accept_if": list(self.accept_if),
            "reject_if": list(self.reject_if),
            "expected_mechanisms": list(self.expected_mechanisms),
            "applicability": dict(self.applicability),
            "validator": self.validator,
            "evidence": [],
            "verdict": None,
        }
