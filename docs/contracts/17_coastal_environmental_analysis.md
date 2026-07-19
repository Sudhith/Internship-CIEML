# Coastal Environmental Analysis Module (CEAM)

```yaml
contract_id: SC-CEAM
engine: Coastal Environmental Analysis Module
version: "1.0.0"
status: implemented
implements_stages: ['stage12', 'cieml.ceam']
supersedes: Stage 12's original "Ecological Interpretation" (same contract slot; renamed and restructured, not a new pipeline position)
```

## 1. Scientific Purpose

Interpret upstream CIEML artifacts (Discovery regimes, Explainability drivers,
Anomaly catalog, External meteorology, Spatiotemporal products, optional
EBSVE closure) into a structured, four-level (Observation / Interpretation /
Hypothesis / rejected-Speculation) coastal environmental narrative — without
re-running or re-scoring any upstream engine.

## 2. Scientific Question

**Primary:** Given the campaign's discovered regimes and their fingerprints,
what physically and ecologically plausible interpretation does the evidence
support, at what confidence, and what must be explicitly rejected as
unsupported?

**Secondary:** Where does the evidence run out — what would CEAM need
(vertical profiles, tide series, tracers, biological surveys) that it does not
have, and does it say so rather than inventing a mechanism?

## 3. Inputs

**Required:** Stage 6 regime labels, Stage 8 regime z-fingerprints and SHAP
driver ranks, the active Domain Configuration's `ceam` block (thresholds,
titles, variable-key vocabulary, harbour/open-coast station-role vocabulary).

**Optional (degrade gracefully to a `rejected=True` unit citing the missing
artifact, never a fabricated mechanism):** Stage 1/2 QA context, Stage 3
physical-pair context, Stage 9 anomaly catalog, Stage 10 external/meteo
report and anomaly enrichment, Stage 11 spatial gradients and transitions,
Stage 14 EBSVE closure and uncertainty ledger.

## 4. Outputs

**Primary:** Per-regime four-level interpretation packets
(`stage12_interpretation_detail.json` — a JSON list, one entry per regime,
each carrying `confidence` ∈ {`exploratory`, `provisional`, `supported`} and
a numeric `evidence_score`); module-level interpretation lists for
hydrodynamics, water quality, meteorology, spatial, temporal, and ecological
topics (`stage12_coastal_environmental_assessment.json`); a campaign summary;
a publication-oriented Markdown narrative (`stage12_scientific_narrative.md`);
a full evidence-to-stage traceability table
(`stage12_traceability.{json,csv}`).

**Legacy-compatible:** `stage12_regime_interpretations.csv` and
`stage12_ecological_report.json` retain the pre-CEAM schema fields
(`regime`, `n`, `title`, `interpretive_family`, `confidence`,
`evidence_score`) so downstream consumers (H4/H6 EBSVE validators, Stage 13)
require no changes.

**Confidence:** Per-unit `confidence` string, not a single module-level score;
EBSVE (SC-EBSVE) is the sole owner of claim-level numeric confidence.

**Uncertainty:** Per-unit free-text `uncertainty` and `limitations` fields;
numeric uncertainty budgets remain owned by SC-MMU, not duplicated here.

## 5. Assumptions

- Regime family thresholds, titles, and variable-key mappings are declared in
  the Domain Configuration Layer's `ceam` block, never hardcoded per campaign.
- Harbour/open-coast classification uses campaign station **roles**
  (`configs/campaigns/*.yaml`), never place-name string matching.
- A named regime family requires the composite evidence score to clear the
  domain's `min_family_score` gate; below it, the regime is left
  `insufficient_evidence_for_named_regime` rather than force-labeled.
- CEAM does not recompute anything upstream engines already computed
  (clustering, SHAP, anomaly detection, cross-correlation, EBSVE scoring).

## 6. Scientific Guarantees

- Every interpretation unit carries all four levels: Observation,
  Interpretation, supporting Evidence (with stage/artifact/variable
  provenance), and a Confidence tier — never a bare claim.
- Unsupported topics are explicitly `rejected=True` with a `reject_reason`
  (e.g. stratification/tides — "no vertical or tidal evidence in upstream
  artifacts") rather than silently omitted or asserted anyway.
- Anthropogenic/pollution-source attribution is always rejected absent
  independent tracers or discharge inventories — CEAM cannot manufacture
  causal evidence current CIEML artifacts do not carry.
- Regime naming is evidence-gated (§5) and produces the same label for the
  same inputs and domain config — deterministic, not narratively embellished.

## 7. Failure Conditions

- Stage 6/8 regime products missing or empty → regime interpretation list is
  empty; downstream modules degrade to rejected units citing the gap.
- Domain `ceam` block missing → falls back to built-in threshold/title
  defaults (documented in each interpretation module), not a crash.
- Stage 10/11 artifacts absent → meteorology/spatial modules emit a single
  `rejected=True` unit citing the missing stage, not an invented gradient or
  event association.

## 8. Applicability

Any domain profile that declares a `ceam` block with `harbour_station_roles`
/ `open_coast_roles`, `titles`, `thresholds`, and `variable_keys` matching its
own core variables. **Not valid for:** domains without a station-role
vocabulary (role-based harbour/open-coast separation is a hard requirement,
not a heuristic fallback to place names).

## 9. Dependencies

**Upstream:** Discovery (SC-DISC), Explainability (SC-XAI), Anomaly
Intelligence (SC-ANOM), Context External (Stage 10), Context Spatiotemporal
(Stage 11), Domain Configuration (SC-DCL) for the `ceam` block, optionally
EBSVE (SC-EBSVE) and SC-MMU's uncertainty ledger. **Downstream:** EBSVE's
H4/H6 pillar evaluators read `stage12_interpretation_detail.json` directly
(confidence + evidence_score fields, unchanged schema); Decision Support
(SC-DSS) and Applicability (SC-APP) consume CEAM's interpretations indirectly
via Stage 13.

## 10. Verification Tests

1. A regime whose composite family score is below `min_family_score` is
   labeled `insufficient_evidence_for_named_regime`, not force-assigned the
   highest-scoring family regardless of magnitude.
2. Stage 10 absent → the meteorology module returns exactly one `rejected=True`
   unit citing "Missing Stage 10 artifacts", and no rainfall/wind claim
   appears anywhere else in the output.
3. `stage12_interpretation_detail.json`'s `confidence`/`evidence_score`
   fields, read by `H4Validator.evaluate_physical()` unchanged, reproduce the
   frozen `visakhapatnam_may2026` H4/H6 classification and confidence exactly
   when run through the full Stage 14 pipeline (verified: 6/6 claims
   byte-identical to the RC-1 baseline in this review).
4. Anthropogenic-influence unit is always present and always `rejected=True`
   unless independent tracer/discharge evidence is added to upstream
   artifacts (currently never the case — CEAM has no tracer input).

## 11. Reviewer Checklist

- [ ] Every interpretation unit has Observation + Interpretation + Evidence + Confidence
- [ ] Rejected units cite a specific missing artifact, not a vague disclaimer
- [ ] No place-name harbour/open-coast heuristics — station roles only
- [ ] Regime naming reproducible from domain config + fingerprints alone
- [ ] Legacy artifact schema (`stage12_regime_interpretations.csv`,
      `stage12_ecological_report.json`) unchanged for downstream consumers
