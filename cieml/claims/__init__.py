"""Scientific claim packs (Phase J) — configuration surface for EBSVE.

The four-pillar ABC remains in `cieml.evidence`. This package owns pack loading,
claim schema, and validator plugin resolution so a campaign chooses claims via
YAML instead of a hardcoded H1–H6 list inside the engine.
"""
from __future__ import annotations

from cieml.claims.loader import ClaimPack, load_claim_pack, resolve_pack_path
from cieml.claims.registry import resolve_validator_class, validators_for_pack
from cieml.claims.schema import ScientificClaim

__all__ = [
    "ClaimPack",
    "ScientificClaim",
    "load_claim_pack",
    "resolve_pack_path",
    "resolve_validator_class",
    "validators_for_pack",
]
