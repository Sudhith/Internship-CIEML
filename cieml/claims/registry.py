"""Resolve claim validator plugins without hardcoding the engine's claim list."""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cieml.claims.loader import ClaimPack
    from cieml.evidence.base import HypothesisValidator

# Built-in plugins for the coastal_monitoring_v1 pack. Pack YAML may override
# via `validator: module.path:ClassName`. New packs can point at these or at
# custom plugins without editing engine.py.
BUILTIN_VALIDATORS: dict[str, str] = {
    "H1_data_trustworthiness": "cieml.evidence.h1_data_trust:H1Validator",
    "H2_physical_coherence": "cieml.evidence.h2_physical_coherence:H2Validator",
    "H3_information_redundancy": "cieml.evidence.h3_feature_redundancy:H3Validator",
    "H4_environmental_regimes": "cieml.evidence.h4_environmental_regimes:H4Validator",
    "H5_anomaly_reality": "cieml.evidence.h5_anomalies:H5Validator",
    "H6_policy_transfer": "cieml.evidence.h6_policy_transfer:H6Validator",
}


def resolve_validator_class(ref: str) -> type:
    """Import `module.path:ClassName` (or `module.path.ClassName`)."""
    if not ref or not str(ref).strip():
        raise ValueError("Empty validator reference")
    ref = str(ref).strip()
    if ":" in ref:
        module_name, class_name = ref.split(":", 1)
    else:
        module_name, class_name = ref.rsplit(".", 1)
    mod = importlib.import_module(module_name)
    cls = getattr(mod, class_name)
    return cls


def validators_for_pack(pack: "ClaimPack") -> list[tuple[str, type]]:
    """Return ordered (claim_id, ValidatorClass) pairs for a pack."""
    out: list[tuple[str, type]] = []
    for claim in pack.claims:
        ref = claim.validator or BUILTIN_VALIDATORS.get(claim.claim_id)
        if not ref:
            raise KeyError(
                f"No validator plugin for claim '{claim.claim_id}'. "
                f"Set claims[].validator in the pack or register a builtin."
            )
        cls = resolve_validator_class(ref)
        # Soft check: plugin should declare matching hypothesis_id / claim_id
        declared = getattr(cls, "hypothesis_id", None) or getattr(cls, "claim_id", None)
        if declared and declared != claim.claim_id:
            raise ValueError(
                f"Validator {ref} declares id={declared!r} but pack claims {claim.claim_id!r}"
            )
        out.append((claim.claim_id, cls))
    return out
