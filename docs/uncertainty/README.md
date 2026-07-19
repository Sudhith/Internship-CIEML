# Uncertainty Model v2 — Measurement & Model Uncertainty + Evidence Reliability

> **v2 implemented.** `cieml/uncertainty/` now implements the three-axis model described
> below and in [EVIDENCE_RELIABILITY_REDESIGN.md](EVIDENCE_RELIABILITY_REDESIGN.md), which
> replaced v1's mixed RSS/sum/clip rules after an audit found saturation, double-counting,
> and loss of discriminative power once propagated across the full engine chain (nearly every
> claim reported uncertainty≈100). The redesign doc's §11 migration steps have all landed and
> been verified against the real Visakhapatnam campaign ledger (visible confidence/uncertainty
> spread, no ceiling clustering — see §9.6/step 5 of that doc for the acceptance test). The old
> single-contract model is retained at [13_uncertainty.md](../contracts/13_uncertainty.md) for
> historical reference only.

**Role:** Make **Measurement & Model Uncertainty** and **Evidence Reliability** first-class
scientific objects in CIEML, both distinct from **confidence**, and distinct from each other.

| Concept | Meaning | Scale | Contract |
|---------|---------|-------|----------|
| **Confidence** | Strength of supporting evidence for a result *within its stated applicability* | 0–100 (higher = stronger support) | [SC-EBSVE](../contracts/09_ebsve.md) |
| **Measurement & Model Uncertainty (M)** | Residual doubt from measurement, sampling, model, and interpretation gaps | 0–100 (higher = more unresolved doubt) | [SC-MMU](../contracts/13_measurement_model_uncertainty.md) |
| **Evidence Reliability (R)** | How broadly the evidence base has actually been sampled — spatially, temporally, methodologically, and via independent external sources | 0–100 (higher = broader, more independently corroborated coverage) | [SC-REL](../contracts/14_evidence_reliability.md) |

These are **three independent axes**. None is derived from another: `U != 100 - C`, `R != C`,
`R != 100 - U`. A claim can be high-confidence, moderate-uncertainty, and mid-range-reliability
all at once (e.g. tightly measured harbour hypoxia in one month, decent internal corroboration,
but only one campaign-season and one external meteo source behind it). Averaging any two of them
into one score is forbidden.

Propagation math: [PROPAGATION_RULES.md](PROPAGATION_RULES.md) · Full design record:
[EVIDENCE_RELIABILITY_REDESIGN.md](EVIDENCE_RELIABILITY_REDESIGN.md)

---

## 1. Scientific rationale

CIEML engines already emit confidence (especially EBSVE). Without explicit, *separated*
uncertainty and reliability axes:

- reviewers cannot separate "well evidenced here" from "safe to transfer" from "actually looked
  broadly enough to know";
- downstream Decision Support may overstate actionable certainty;
- random error is conflated with systematic bias and model choice;
- a structural evidence-base gap (e.g. one external meteorology source) gets silently
  double-counted as if it were also an independent measurement-precision problem.

This framework requires every engine packet to expose:

1. **Result** (or result reference)
2. **Confidence** (optional if not yet scored)
3. **Measurement & Model Uncertainty budget** (typed, provenance-tagged components; full
   Inherited/Resolved/New/Remaining/Net breakdown)
4. **Evidence Reliability score** (where the packet closes a scientific claim)
5. **Limitations**
6. **Remaining unknowns**

---

## 2. Uncertainty object types (SC-MMU)

| Object | Typical sources |
|--------|-----------------|
| Measurement | Instrument precision, digitization, short-cast noise |
| Sensor | Drift, fouling, calibration age, flatline risk |
| QA | Flag severity mix, incomplete checks, exclusion sensitivity |
| Statistical | n/p, non-normality, multicollinearity residual, method choice |
| Model | Algorithm/K instability, corroborated by independent validation via precision fusion |
| Explainability | Cross-method disagreement, correlated attribution |
| Anomaly | Detector disagreement, origin-class confidence |
| Policy | Recommendation without claim support; threshold non-transfer |
| Environmental | External support gap (single-source structural fact now lives on Evidence Reliability instead — see below) |
| Decision | Budget/ops unknowns; untested adaptive triggers |
| Scientific Claim | Pillar weaknesses + propagated upstream raw intensity |

## 2b. Evidence Reliability dimensions (SC-REL)

| Dimension | What it measures |
|-----------|-------------------|
| Spatial coverage | Stations sampled vs. domain-declared target |
| Temporal coverage | Seasons/months sampled vs. domain-declared target |
| Methodological diversity | Independent analysis methods used vs. target |
| External source diversity | Independent external validation sources integrated vs. target |

---

## 3. Uncertainty kinds (components)

| Kind | Nature | Propagation tendency |
|------|--------|----------------------|
| Random | Aleatory, reduces with replication | Correlation-aware combination (ρ=0 → exact RSS) |
| Systematic | Bias / calibration; does not shrink with n | Correlation-aware combination (ρ=1 → exact sum) |
| Sampling | Finite campaign coverage | Scales with design sparsity |
| Sensor | Hardware integrity | Feeds Measurement/QA objects |
| Model | Structural / algorithmic choice | Precision-fused with corroborating independent validation when `resolves_upstream=True` |
| Interpretation | Semantic / causal overclaim risk | Additive (new-question) combination |
| External | Unconfirmed forcing / transfer | Additive; source-count breadth reported separately on the R axis |

A component's `provenance_id` marks its root cause; components sharing a `provenance_id` are
deduplicated to their worst estimate before combination — the direct fix for the v1 bug where a
single structural fact (e.g. one regional meteo station) was counted once as a Measurement
component and again, independently, as an Environmental component.

---

## 4. Engine interface

Every engine SHOULD emit an `EngineUncertaintyPacket` (see `cieml.uncertainty.models`).

```text
Engine → Result + Confidence? + UncertaintyBudget + EvidenceReliability? + Limitations + RemainingUnknowns
                ↓
        UncertaintyLedger (campaign) — cieml.uncertainty.assemble.build_campaign_uncertainty_ledger
                ↓
        Propagation (correlation-aware combine + precision fusion) → Claim / Decision packets
                ↓
        Visualizations — budget waterfall, source contribution, correlation graph,
        engine contribution, confidence x M x R scatter (cieml.uncertainty.visualize)
```

Implementation: `cieml/uncertainty/`. Stage 14 assembles a campaign ledger and figures under
`outputs/phase8/figures/fig_uncertainty_*`.

---

## 5. What this is not

- Not a replacement for EBSVE pillar scores
- Not a demand to invent numeric sensor datasheets when absent (use declared defaults + mark
  unknowns)
- Not permission to hide low confidence behind "uncertainty language"
- Not a fourth combined "risk" score presented as primary output — an optional, clearly-labeled
  triage-only Caution scalar (`propagate.caution_index`) may still be offered for manager
  convenience, but Confidence, Measurement & Model Uncertainty, and Evidence Reliability are the
  three reported scientific axes
