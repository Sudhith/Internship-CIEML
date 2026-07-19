# Uncertainty Propagation Engine (v1, superseded)

```yaml
contract_id: SC-UNC
engine: Uncertainty Propagation Framework
version: "1.0.0"
status: deprecated
implements_stages: [stage_14 ledger assembly; optional per-engine packets]
superseded_by: [SC-MMU, SC-REL]
```

> **Deprecated.** SC-UNC v1's mixed RSS/sum/clip propagation and single
> "uncertainty" number conflated Measurement & Model Uncertainty with Evidence
> Reliability, and its `combine_hybrid`/clip-at-every-step rule produced a
> ceiling-saturation artifact where nearly every claim reported uncertainty≈100.
> Uncertainty Model v2 replaces this contract with two sibling contracts sharing
> the `cieml.uncertainty` implementation surface:
>
> - **[SC-MMU — Measurement & Model Uncertainty](13_measurement_model_uncertainty.md)**
>   owns the combination/propagation machinery (this document's §5–§7), now
>   correlation-aware and provenance-deduplicated, saturating exactly once at
>   report time.
> - **[SC-REL — Evidence Reliability](14_evidence_reliability.md)** owns
>   coverage/completeness scoring, previously folded into (and hidden inside)
>   this contract's uncertainty totals.
>
> See `docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md` for the full
> mathematical justification and migration record. This document is retained
> for historical/audit reference only; do not implement against it.

---

## Original v1 contract (historical)

## 1. Scientific Purpose

Represent and propagate **uncertainty** as a typed budget distinct from evidence **confidence**, so CIEML outputs remain scientifically honest under measurement, model, and transfer doubt.

## 2. Scientific Question

How much unresolved doubt remains in each result, of what kinds, and how does that doubt accumulate across engines without false cancellation?

## 3. Inputs

**Required:** Engine results and/or upstream artifacts; optional confidence scores; diagnostics (n, QA rates, stability σ, method disagreement, external support).

**Optional:** Vendor sensor precision; calibration certificates.

**Metadata:** Domain/campaign IDs; framework version.

## 4. Outputs

**Primary:** `UncertaintyLedger`, per-engine `EngineUncertaintyPacket`, claim-level budgets.

**Derived:** Caution index (optional); waterfall/heatmap/matrix/dashboard figures.

**Confidence:** Not produced here (consumed from EBSVE / engines).

**Uncertainty:** Typed component budgets + totals under named rules.

## 5. Assumptions

- Component intensities are comparable on a declared 0–100 scale.
- Independence assumptions for RSS are stated per combination.
- Missing sensor datasheets → explicit unknowns, not silent zero uncertainty.

## 6. Scientific Guarantees

- Confidence is never redefined as 100 − uncertainty.
- Unlike components are not averaged away.
- Every total cites the propagation rule ID (R1–R7).
- Component vectors are retained for audit.

## 7. Failure Conditions

- Empty ledger when Stage 14 runs with evidence present
- Propagation without rule ID
- Negative or >100 components after clipping policy violation

## 8. Applicability

All aquatic domains; intensity maps may be domain-tuned later via Domain Configuration.

## 9. Dependencies

**Upstream:** All scientific engines (as available). **Downstream:** Decision Support, Applicability, manuscript limitations, Knowledge Base.

## 10. Verification Tests

1. Two independent random components 30 and 40 → RSS total 50 under R1.
2. Systematic 20 + 20 → total 40 under R2 (not 20).
3. High confidence with high \(u_{\mathrm{ext}}\) remains high U at claim level.
4. Figures regenerate from ledger JSON alone.

## 11. Reviewer Checklist

- [ ] Confidence and uncertainty both present where claims are closed
- [ ] Propagation rules cited
- [ ] No mean-pooling of unlike kinds
- [ ] Remaining unknowns listed
- [ ] Visual audit (waterfall / matrix) available
