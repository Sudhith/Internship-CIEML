"""Load claim packs from configs/claims/."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from cieml.claims.schema import ScientificClaim

ROOT = Path(__file__).resolve().parents[2]
CLAIMS_DIR = ROOT / "configs" / "claims"
DEFAULT_CLAIM_PACK = "coastal_monitoring_v1"


@dataclass
class ClaimPack:
    pack_id: str
    title: str
    version: str
    claims: list[ScientificClaim]
    scientific_questions: dict[str, Any] = field(default_factory=dict)
    four_pillars: list[str] = field(default_factory=list)
    classification_rule: str | None = None
    assumptions_to_test_not_assume: list[str] = field(default_factory=list)
    domain_affinity: str | None = None
    campaign_agnostic: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    def claim_ids(self) -> list[str]:
        return [c.claim_id for c in self.claims]

    def as_hypotheses_dict(self) -> dict[str, dict[str, Any]]:
        """Legacy register shape: hypotheses keyed by claim_id."""
        return {
            c.claim_id: {
                "null": c.null_hypothesis,
                "alternative": c.alternative_hypothesis,
                "linked_questions": list(c.linked_questions),
                "accept_if": list(c.accept_if),
                "reject_if": list(c.reject_if),
                "expected_mechanisms": list(c.expected_mechanisms),
                "title": c.title,
                "description": c.description,
                "validator": c.validator,
                "applicability": dict(c.applicability),
            }
            for c in self.claims
        }


def resolve_pack_path(pack_id_or_path: str | Path | None = None) -> Path:
    if pack_id_or_path is None:
        return CLAIMS_DIR / f"{DEFAULT_CLAIM_PACK}.yaml"
    p = Path(pack_id_or_path)
    if p.suffix in {".yaml", ".yml"} and p.exists():
        return p
    # Treat as pack_id
    candidate = CLAIMS_DIR / f"{pack_id_or_path}.yaml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Claim pack not found: {pack_id_or_path} (looked for {candidate})")


@lru_cache(maxsize=8)
def load_claim_pack(pack_id_or_path: str | None = None) -> ClaimPack:
    path = resolve_pack_path(pack_id_or_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    claims_raw = raw.get("claims") or []
    if isinstance(claims_raw, dict):
        # Allow legacy dict form {id: {...}}
        claims = [ScientificClaim.from_dict({"claim_id": k, **(v or {})}) for k, v in claims_raw.items()]
    else:
        claims = [ScientificClaim.from_dict(c) for c in claims_raw]
    if not claims:
        raise ValueError(f"Claim pack {path.name} has an empty claims list")
    return ClaimPack(
        pack_id=str(raw.get("pack_id") or path.stem),
        title=str(raw.get("title") or path.stem),
        version=str(raw.get("version") or "0.0.0"),
        claims=claims,
        scientific_questions=dict(raw.get("scientific_questions") or {}),
        four_pillars=list(raw.get("four_pillars") or raw.get("acceptance_criteria_four_pillars") or []),
        classification_rule=raw.get("classification_rule") or raw.get("rule"),
        assumptions_to_test_not_assume=list(raw.get("assumptions_to_test_not_assume") or []),
        domain_affinity=raw.get("domain_affinity"),
        campaign_agnostic=bool(raw.get("campaign_agnostic", True)),
        raw=raw,
    )
