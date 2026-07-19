# Measurement & Model Uncertainty Engine

```yaml
contract_id: SC-MMU
engine: Measurement & Model Uncertainty (Uncertainty Model v2)
version: "2.0.0"
status: implemented
implements_stages: [stage_14 ledger assembly; optional per-engine packets]
supersedes: SC-UNC v1.0.0 (split; see docs/contracts/13_uncertainty.md)
sibling_contract: SC-REL (docs/contracts/14_evidence_reliability.md)
```

## 1. Scientific Purpose

Represent and propagate **Measurement & Model Uncertainty (M)** — sensor, sampling,
model, and interpretation doubt — as a typed budget distinct from evidence
**Confidence** (SC-EBSVE) and from **Evidence Reliability** (SC-REL), so CIEML
outputs remain scientifically honest under measurement, model, and transfer doubt,
without conflating "how sure are we" with "how much have we looked."

## 2. Scientific Question

How much unresolved measurement/model doubt remains in each result, of what kinds,
how does agreement between independent evidence sharpen it, and how does it
accumulate across engines without false cancellation or double-counting a shared
root cause?

## 3. Inputs

**Required:** Engine results and/or upstream artifacts; diagnostics (n, QA rates,
stability σ, method disagreement, external support gaps); a `provenance_id` per
declared component (its root cause) and a `resolves_upstream` flag (whether it
corroborates the parent engine's existing doubt about the same question, vs.
introduces doubt about a new one).

**Optional:** Vendor sensor precision; calibration certificates; a declared
pairwise correlation map (`{frozenset({id_a, id_b}): rho}`) for components that
are partially, not fully, correlated without sharing a root cause.

**Metadata:** Domain/campaign IDs; framework version.

## 4. Outputs

**Primary:** `UncertaintyLedger` (`cieml.uncertainty.assemble.build_campaign_uncertainty_ledger`),
per-engine `EngineUncertaintyPacket`, per-claim `UncertaintyBudget`.

**Derived:** Optional triage-only "Caution" scalar (`propagate.caution_index`,
never a fourth scientific axis); budget waterfall / source contribution /
correlation graph / engine contribution / confidence-uncertainty-reliability
scatter figures (`cieml.uncertainty.visualize`).

**Confidence:** Not produced here (consumed from EBSVE / engines).

**Evidence Reliability:** Not produced here (consumed from SC-REL).

**Uncertainty:** Typed, provenance-tagged component budgets with a full
Inherited / Resolved / New / Remaining / Net breakdown per engine, under one
named propagation model.

## 5. Assumptions

- Component intensities are comparable on a declared, unbounded raw scale before
  the single final saturating map to [0, 100).
- Independence (ρ=0) is the default for any pair without a declared correlation;
  declaring ρ=1 recovers exact systematic-sum behavior as a special case of the
  same formula, not a separately-justified rule.
- Two components sharing a `provenance_id` are the same root cause and are
  deduplicated to their worst estimate before combination — never independently
  summed or RSS'd.
- Missing sensor datasheets → explicit unknowns (component absent, limitation
  logged), not silent zero uncertainty.

## 6. Scientific Guarantees

- Confidence is never redefined as 100 − uncertainty, and uncertainty is never
  derived from Evidence Reliability or vice versa — three independent axes.
- Combination happens once, in raw (unbounded) intensity space, using one
  correlation-aware GUM-style formula (`propagate.combine_correlated`); bounding
  to [0, 100) happens exactly once, at the point of reporting
  (`propagate.saturate`) — never by clipping an intermediate sum.
- Corroborating evidence about the same question is combined via
  precision/inverse-variance fusion (`propagate.fuse_precision`), which can only
  ever reduce doubt, never increase it; new evidence about a different question
  is combined additively and can only increase or hold doubt steady.
- A shared root cause (same `provenance_id`) is counted exactly once, regardless
  of how many engines mention it.
- Every budget reports the full telescoping identity: `Inherited − Resolved + New
  = Remaining`, and this identity holds exactly (not approximately) by
  construction.
- Component vectors, provenance IDs, and dedup warnings are retained for audit.

## 7. Failure Conditions

- Empty ledger when Stage 14 runs with evidence present.
- A `UncertaintyBudget` without a `rule_id` or `raw_total`.
- A reported `remaining` outside [0, 100), or `raw_total` used directly for
  display instead of only for chaining into the next engine's `parent_raw`.
- Two components sharing a provenance_id combined as if independent (missing
  dedup) — the direct regression class this contract exists to prevent.
- Saturation applied more than once along a single propagation chain.

## 8. Applicability

All aquatic domains; intensity maps may be domain-tuned later via Domain
Configuration. The engine-chain wiring (which engine's raw output feeds which
engine's `parent_raw`) is campaign/domain-specific and lives in `assemble.py`,
not in this contract.

## 9. Dependencies

**Upstream:** All scientific engines (as available), SC-EBSVE (for claim-level
Confidence, reported alongside but never derived from M). **Downstream:**
Decision Support, Applicability, manuscript limitations, Knowledge Base.

## 10. Verification Tests

1. Two independent random components 30 and 40 → raw combined σ = 50.0 exactly
   (`sqrt(30^2+40^2)`), matching RSS as the ρ=0 special case.
2. Two fully correlated (ρ=1) components 20 and 20 → raw combined σ = 40.0
   exactly (`20+20`), matching the systematic-sum special case.
3. Two components sharing a `provenance_id` (e.g. 54.5 and 20.0) deduplicate to
   the worse estimate (54.5) before combination, not `sqrt(54.5^2+20^2)`.
4. Corroborating evidence fusion is bounded: `fuse_precision(60, 15) <= 15`
   (agreement can only sharpen, never worsen, an estimate).
5. Telescoping identity holds exactly for every packet in a real campaign
   ledger: `inherited - resolved + new == remaining` to floating-point precision.
6. `saturate(raw)` is monotonic, bounded in [0, 100), and never clips two
   distinguishable large raw values to the same reported value.
7. Figures regenerate from ledger JSON alone.

## 11. Reviewer Checklist

- [ ] Confidence, Uncertainty, and Evidence Reliability all present where claims
      are closed, and visibly independent (not collinear by construction)
- [ ] Every component carries a `provenance_id`
- [ ] Propagation rule cited per budget (`rule_id`, `rule_detail`)
- [ ] No mean-pooling of unlike kinds; no double-counted shared root causes
- [ ] Remaining unknowns listed
- [ ] Visual audit (budget waterfall / source contribution / confidence-M-R
      scatter) available and shows genuine spread, not a saturated cluster
