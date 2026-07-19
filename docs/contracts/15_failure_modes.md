# Scientific Failure Mode Framework

```yaml
contract_id: SC-FMF
engine: Scientific Failure Mode Framework
version: "1.0.0"
status: implemented
implements_stages: ['cross_cutting', 'cieml.failure', 'stage06', 'stage08', 'stage09', 'stage10', 'stage14', 'cieml.evidence.engine', 'cieml.validation.suite']
```

## 1. Scientific Purpose

Ensure CIEML never treats engine success as the default: every engine must declare,
detect, and respond to conditions under which its conclusions must not be trusted.

## 2. Scientific Question

**Primary:** When must this engine’s outputs be warned, degraded, suppressed, or aborted?

**Secondary:** What recovery/fallback preserves scientific honesty without inventing support?

## 3. Inputs

**Required**
- Failure mode catalog (`configs/failure/catalog.yaml`)
- Engine artifacts / live metrics for detectors
- Severity policy from `configs/framework.yaml`

**Optional**
- Domain/campaign threshold overrides

## 4. Outputs

**Primary**
- Per-engine `FailureAssessment`
- Campaign failure dossier

**Derived**
- User messages; confidence multipliers; recommendation suppressions

## 5. Assumptions

- Detectors are deterministic given fixed inputs.
- Severity compose uses documented policy (`min` by default).
- Fallbacks are declared; silent method switching is forbidden.

## 6. Scientific Guarantees

- CRITICAL+ hits produce user-visible messages and reviewer dossier entries.
- Decision Support does not emit actionable recommendations under `dss_low_evidence`.
- Failure reduces confidence explicitly; it does not set `U = 100 - C`.

## 7. Failure Conditions

- Catalog missing or empty
- Detector raises unexpectedly
- Contract §7 condition unmapped to any mode (framework validation fail)

## 8. Applicability

Valid for all CIEML engines and claim packs. Not a substitute for field QA.

## 9. Dependencies

Upstream: all scientific engines. Downstream: EBSVE, DSS, Uncertainty ledger, Framework Validation.

## 10. Verification Tests

1. Inject `n_stations` below hard floor → `disc_too_few_stations` CRITICAL.
2. Remove Stage 10 support → `anom_no_external_validation` fires; environmental confidence reduced.
3. Force low EBSVE confidence → DSS recommendations suppressed.
4. Re-run detectors twice on fixed artifacts → identical hits.

## 11. Reviewer Checklist

- [ ] Catalog covers contract failure conditions
- [ ] Severity policy documented
- [ ] Suppressions visible in dossier
- [ ] No silent fallbacks
