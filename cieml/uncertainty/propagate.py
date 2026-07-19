"""Uncertainty Model v2 propagation math.

Replaces v1's mixed RSS+sum+clip rules (R1-R7) with one internally consistent
model, per docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md:

  1. Combine sibling components in RAW (unbounded) intensity space using the GUM
     combined-uncertainty formula, generalized with a declared correlation
     coefficient rho per pair (rho=0 -> exact RSS, rho=1 -> exact sum; both are
     now special cases of one formula instead of two separately-justified rules).
  2. Components sharing the same provenance_id (the same root cause, e.g. "single
     regional meteo station") are deduplicated to their single worst estimate
     BEFORE combination, so a shared limitation is never counted once per engine
     that happens to mention it.
  3. Serial propagation between engines splits local evidence into corroborating
     (same question the parent already had doubt about -> Kalman/Bayesian
     precision fusion, which can only ever REDUCE doubt) vs. new (a different
     question -> additive combination via step 1).
  4. Bounding to a reportable [0, 100) score happens exactly once, via a smooth
     saturating map, at the point of reporting -- never by clipping an
     intermediate sum, which is what caused v1's ceiling effect.

All combination happens in raw intensity space; only `saturate()` maps to [0,100).
"""
from __future__ import annotations

import math
from typing import Iterable

from cieml.uncertainty.models import (
    UncertaintyBudget,
    UncertaintyComponent,
    UncertaintyObject,
    _clip,
)

CorrelationMap = dict[frozenset, float]

DEFAULT_SATURATION_K = 100.0


def saturate(raw: float, k: float = DEFAULT_SATURATION_K) -> float:
    """Sec 5.3 - hyperbolic saturating map. Bounded in [0, 100) by construction;
    monotonic; smooth; never clips (two different large raw values remain
    distinguishable instead of both reading exactly "100.0"). Apply exactly once,
    at report time -- never chain this through intermediate combination steps.
    """
    raw = max(0.0, float(raw))
    if raw <= 0:
        return 0.0
    return 100.0 * raw / (raw + float(k))


def _rho(correlations: CorrelationMap | None, id_a: str, id_b: str, default: float) -> float:
    if not correlations or id_a == id_b:
        return default
    key = frozenset((id_a, id_b))
    rho = correlations.get(key, default)
    return float(max(0.0, min(1.0, rho)))


def _dedup_by_provenance(components: list[UncertaintyComponent]) -> tuple[list[UncertaintyComponent], list[str]]:
    """A single root cause must contribute once. If two components share a
    provenance_id (accidental re-derivation of the same limitation, or a
    deliberate second estimate of it), keep only the larger magnitude rather
    than summing/RSS-ing them as if independent -- this is the direct,
    structural fix for the "single regional meteo counted as both systematic
    and external" class of bug. `provenance_id="unspecified"` (the default for
    call sites that haven't been tagged) is treated as always-unique, never
    deduplicated against other "unspecified" components, since it carries no
    identity information.
    """
    warnings: list[str] = []
    pools: dict[str, list[UncertaintyComponent]] = {}
    unspecified: list[UncertaintyComponent] = []
    for c in components:
        if c.provenance_id == "unspecified":
            unspecified.append(c)
        else:
            pools.setdefault(c.provenance_id, []).append(c)

    deduped: list[UncertaintyComponent] = list(unspecified)
    for pid, group in pools.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue
        worst = max(group, key=lambda c: c.value)
        warnings.append(
            f"provenance '{pid}': {len(group)} components ({[round(c.value, 1) for c in group]}) "
            f"deduplicated to the worst estimate ({worst.value:.1f}, source={worst.source}) "
            "instead of being combined as independent."
        )
        deduped.append(worst)
    return deduped, warnings


def combine_correlated(
    components: list[UncertaintyComponent],
    *,
    correlations: CorrelationMap | None = None,
    default_rho: float = 0.0,
) -> tuple[float, list[str]]:
    """Sec 5.1 - GUM combined-uncertainty formula with provenance dedup.

    sigma_c^2 = sum(sigma_i^2) + 2 * sum_{i<j} rho_ij * sigma_i * sigma_j

    rho_ij defaults to 0 (independent -> exact RSS at the limit of all pairs
    independent). Declare `correlations[frozenset({id_a, id_b})] = rho` for
    pairs known to be partially correlated without being the same root cause
    (same-provenance pairs are deduplicated, not rho-combined -- see
    `_dedup_by_provenance`). Returns (raw_sigma, dedup_warnings); raw_sigma is
    UNBOUNDED (may exceed 100) -- caller applies `saturate()` once, at report time.
    """
    if not components:
        return 0.0, []
    deduped, warnings = _dedup_by_provenance(components)
    n = len(deduped)
    total_sq = sum(c.value ** 2 for c in deduped)
    cross = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            rho = _rho(correlations, deduped[i].provenance_id, deduped[j].provenance_id, default_rho)
            cross += 2.0 * rho * deduped[i].value * deduped[j].value
    raw = math.sqrt(max(0.0, total_sq + cross))
    return raw, warnings


def fuse_precision(sigma_in: float, sigma_local: float) -> float:
    """Sec 5.2 - Kalman/Bayesian inverse-variance ("precision-adds") update for
    corroborating evidence about the SAME question. Guarantees
    sigma_post <= min(sigma_in, sigma_local): agreeing independent evidence can
    only sharpen an estimate, never worsen it. If either input is exactly 0
    ("perfectly certain"), that input dominates and sigma_post = 0.
    """
    sigma_in = max(0.0, float(sigma_in))
    sigma_local = max(0.0, float(sigma_local))
    if sigma_in <= 0.0 or sigma_local <= 0.0:
        return 0.0
    return math.sqrt(1.0 / (1.0 / sigma_in ** 2 + 1.0 / sigma_local ** 2))


def combine_raw(sigmas: Iterable[float], *, rho: float = 0.0) -> float:
    """Combine already-raw (unbounded) intensities via the same GUM formula as
    `combine_correlated`, for intermediate values that don't carry a
    provenance_id to dedup against (e.g. a pre-fused sub-budget from an internal
    corroboration step -- see Discovery's bootstrap/consensus-instability vs.
    independent-validation fusion in assemble.py). A single scalar `rho` applies
    across all pairs, since these are already-aggregated intermediate
    quantities, not individually-provenanced components.
    """
    vals = [max(0.0, float(s)) for s in sigmas if s is not None]
    vals = [v for v in vals if v > 0]
    if not vals:
        return 0.0
    total_sq = sum(v ** 2 for v in vals)
    cross = 0.0
    n = len(vals)
    for i in range(n):
        for j in range(i + 1, n):
            cross += 2.0 * rho * vals[i] * vals[j]
    return math.sqrt(max(0.0, total_sq + cross))


def propagate_engine(
    parent_raw: float,
    corroborating: list[UncertaintyComponent],
    new_evidence: list[UncertaintyComponent],
    *,
    object_type: UncertaintyObject,
    correlations: CorrelationMap | None = None,
    post_new_rho: float = 0.0,
    extra_new_raw: float = 0.0,
    extra_display_components: list[UncertaintyComponent] | None = None,
) -> UncertaintyBudget:
    """Sec 5.2/5.6 full serial update: fuse corroborating evidence with the
    inherited raw intensity (can reduce it), then add new-question evidence
    (cannot reduce it), then report the telescoping Inherited/Resolved/New/
    Remaining/Net budget. `parent_raw` is unbounded raw intensity (0 for a root
    engine with no parent, e.g. QA).

    `extra_new_raw`: an already-computed raw magnitude to fold into the "new"
    side without passing through `UncertaintyComponent` construction (which
    clips to [0,100] -- appropriate for freshly-authored intensity scores, but
    wrong for a value that is itself the output of an internal precision fusion
    and may legitimately be a different scale). `extra_display_components`:
    the components that magnitude was derived from, included in the returned
    budget's `.components` for audit/dashboard purposes without being
    re-combined a second time.
    """
    parent_raw = max(0.0, float(parent_raw))
    all_components = list(corroborating) + list(new_evidence) + list(extra_display_components or [])

    sigma_corrob, corrob_warnings = combine_correlated(corroborating, correlations=correlations) if corroborating else (0.0, [])
    if corroborating:
        sigma_post = fuse_precision(parent_raw, sigma_corrob) if parent_raw > 0 else sigma_corrob
    else:
        sigma_post = parent_raw

    sigma_new_components, new_warnings = combine_correlated(new_evidence, correlations=correlations) if new_evidence else (0.0, [])
    have_new = bool(new_evidence) or extra_new_raw > 0
    sigma_new = combine_raw([sigma_new_components, extra_new_raw]) if have_new else 0.0
    if have_new:
        sigma_out = math.sqrt(max(0.0, sigma_post ** 2 + sigma_new ** 2 + 2.0 * post_new_rho * sigma_post * sigma_new))
    else:
        sigma_out = sigma_post

    inherited = saturate(parent_raw)
    post = saturate(sigma_post)
    out = saturate(sigma_out)
    resolved = max(0.0, inherited - post)
    new_u = max(0.0, out - post)

    detail = (
        f"V2: inherited(raw={parent_raw:.1f})"
        + (f" fused with corroborating(raw={sigma_corrob:.1f}) -> post(raw={sigma_post:.1f})" if corroborating else " (no corroborating evidence)")
        + (f"; + new(raw={sigma_new:.1f}, rho={post_new_rho}) -> out(raw={sigma_out:.1f})" if have_new else "")
    )
    return UncertaintyBudget(
        object_type=object_type,
        components=all_components,
        inherited=inherited,
        resolved=resolved,
        new_uncertainty=new_u,
        remaining=out,
        net=out,
        rule_id="V2_correlated_fusion",
        rule_detail=detail,
        dedup_warnings=corrob_warnings + new_warnings,
        raw_total=sigma_out,
    )


def root_budget(
    components: list[UncertaintyComponent],
    *,
    object_type: UncertaintyObject,
    correlations: CorrelationMap | None = None,
) -> UncertaintyBudget:
    """Budget for an engine with no parent (QA is the only current root)."""
    return propagate_engine(0.0, [], components, object_type=object_type, correlations=correlations)


def caution_index(confidence: float | None, uncertainty_total: float) -> float | None:
    """Optional LEGACY triage-only scalar (v1 R6, unchanged math). Not a fourth
    scientific axis -- combines Confidence and Measurement/Model Uncertainty for
    manager convenience only; report Confidence, Uncertainty, and Evidence
    Reliability separately as the primary product (docs Sec 10). Returns None
    if confidence is unavailable (never pretend C=0).
    """
    if confidence is None:
        return None
    c = float(confidence)
    u = float(uncertainty_total)
    return _clip(math.sqrt((100.0 - c) ** 2 + u ** 2))
