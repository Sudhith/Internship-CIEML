# Evidence Reliability Engine

```yaml
contract_id: SC-REL
engine: Evidence Reliability Engine (Uncertainty Model v2)
version: "2.0.0"
status: implemented
implements_stages: [stage_14 ledger assembly; per-claim reliability scoring]
supersedes: SC-UNC v1.0.0 (split; see docs/contracts/13_uncertainty.md)
sibling_contract: SC-MMU (docs/contracts/13_measurement_model_uncertainty.md)
```

## 1. Scientific Purpose

Score **Evidence Reliability (R)** — how broadly a claim's evidence base has
actually been sampled across space, time, method, and independent external
source — as an axis independent of both Confidence (SC-EBSVE, "how sure are we
given what we have") and Measurement & Model Uncertainty (SC-MMU, "how much
doubt remains in what we measured"). R answers "how much have we actually
looked," and answers it the same way regardless of how confident or uncertain
the resulting claim turns out to be.

## 2. Scientific Question

Given the domain's declared coverage targets, what fraction of the evidence base
a fully-supported claim would need has this campaign actually sampled — spatially,
temporally, methodologically, and via independent external sources — and is that
coverage being reported honestly instead of being folded into (and hidden behind)
a Confidence or Uncertainty number that answers a different question?

## 3. Inputs

**Required:** Observed counts (`n_stations`, `n_seasons`, `n_methods`,
`n_external_sources`); Domain Configuration coverage targets and weights
(`configs/domains/<name>.yaml` → `evidence_reliability.targets` /
`evidence_reliability.weights`, validated against `configs/domains/_schema.yaml`).

**Optional:** Per-dimension free-text detail for audit (`ReliabilityDimension.detail`).

**Metadata:** Domain/campaign IDs; framework version.

## 4. Outputs

**Primary:** A single Evidence Reliability score in [0, 100]
(`reliability.score_evidence_reliability`), plus its per-dimension coverage
breakdown (`reliability.build_reliability_dimensions`): spatial coverage,
temporal coverage, methodological diversity, external source diversity.

**Confidence:** Not produced here (consumed from EBSVE).

**Uncertainty:** Not produced here (consumed from SC-MMU).

## 5. Assumptions

- Coverage is a ratio of observed count to a domain-declared target, capped at
  1.0 per dimension (exceeding a target does not "over-credit" reliability).
- Dimension weights are domain-configured, not hardcoded; a domain that has no
  meaningful seasonal axis (e.g. a single controlled experiment) declares that
  via its own targets/weights rather than this engine silently assuming one.
- A structural evidence-base limitation (e.g. "only one external meteorology
  provider") belongs on this axis's `external_source_diversity` dimension, not
  duplicated as a second Measurement-axis component under SC-MMU — this is the
  structural fix for the v1 double-counting bug where the same fact was
  penalized twice under two different names.

## 6. Scientific Guarantees

- R is never derived from Confidence or Uncertainty (`R != 100 - U`, `R != C`),
  and neither of them is derived from R.
- Every dimension's coverage is bounded to [0, 1] by construction before
  weighting, so the final score is bounded to [0, 100] without clipping an
  unbounded intermediate value.
- The score is a transparent weighted mean of named, individually-reported
  dimensions — never a black-box composite.
- The same structural fact is scored on exactly one axis (R), never
  simultaneously on M (SC-MMU).

## 7. Failure Conditions

- A reliability score reported without its per-dimension detail.
- A domain profile missing `evidence_reliability` targets/weights silently
  defaulting to fabricated generous coverage instead of using the documented
  conservative fallback (`reliability.DEFAULT_TARGETS` / `DEFAULT_WEIGHTS`).
- A structural evidence-base gap (e.g. single external source) appearing as a
  component on an SC-MMU budget instead of (or in addition to) this axis.
- A reported score outside [0, 100].

## 8. Applicability

All aquatic domains; coverage targets are domain-specific and declared per
domain profile, not framework-wide constants.

## 9. Dependencies

**Upstream:** Domain Configuration Layer (SC-DCL) for targets/weights; campaign
metadata (station count, date range, methods used, external sources integrated).
**Downstream:** SC-MMU (packets carry `evidence_reliability` alongside, not
inside, their uncertainty budget); Decision Support; Knowledge Base; manuscript
limitations sections.

## 10. Verification Tests

1. Four dimensions at coverage {0.75, 0.25, 0.33, 0.5} with equal weight 1.0 →
   score = 100 × mean(0.75, 0.25, 0.33, 0.5) ≈ 45.75, computed exactly from the
   worked example in the design doc (§7).
2. Real Visakhapatnam campaign inputs (n_stations=6/8, n_seasons=1/4,
   n_methods=3/3, n_external_sources=1/2 against `coastal.yaml` targets) →
   score ≈ 62.5, sub-saturated and distinct from any Confidence or Uncertainty
   value reported for the same claims.
3. A dimension exceeding its target (e.g. 10 stations against a target of 8) is
   capped at coverage 1.0 for that dimension, not > 1.0.
4. Score responds monotonically to each dimension in isolation (more coverage on
   any one axis never lowers the score, holding others fixed).

## 11. Reviewer Checklist

- [ ] R reported alongside, not derived from, Confidence and Uncertainty
- [ ] Per-dimension coverage breakdown available for audit
- [ ] Domain-declared targets/weights cited, not hardcoded framework constants
- [ ] No structural evidence-base fact double-counted on both R and M
- [ ] Visual audit (confidence-uncertainty-reliability scatter, SC-MMU §10 panel
      5) shows R varying independently of the other two axes
