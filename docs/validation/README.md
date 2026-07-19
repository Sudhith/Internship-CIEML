# Framework Validation Engine (SC-FVE)

**Role:** Validate **CIEML itself** — architecture, contracts, reproducibility, and
scientific process integrity.

| This engine validates | This engine does **not** validate |
|----------------------|-----------------------------------|
| Framework structure & contracts | Whether Visakhapatnam regimes are “true” |
| Determinism & provenance | Whether a ML model is accurate enough for ops |
| Engine independence & interfaces | Regulatory compliance of a site |
| Uncertainty propagation rules | Field sampling design adequacy (except as contract checks) |
| Domain-swap without code edits | Policy decisions |

Companion: [Failure Mode Framework](../failure/README.md) (when *campaign* science fails).  
This package answers: when must we **distrust the framework implementation**?

---

## Documents

| Doc | Content |
|-----|---------|
| [METHODOLOGY.md](METHODOLOGY.md) | Validation questions & philosophy |
| [CATEGORIES.md](CATEGORIES.md) | Architecture … Traceability categories |
| [SUITE.md](SUITE.md) | Test suite map (unit / regression / acceptance / scientific / architecture / evidence) |
| [REGRESSION_PROTOCOL.md](REGRESSION_PROTOCOL.md) | Visakhapatnam + synthetic regression protocol |
| [COMPLIANCE_MATRIX.md](COMPLIANCE_MATRIX.md) | Contract × category matrix |
| [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) | Architecture audit template |
| [SCIENTIFIC_AUDIT.md](SCIENTIFIC_AUDIT.md) | Scientific audit template |
| [READINESS_CHECKLIST.md](READINESS_CHECKLIST.md) | Release / adoption readiness |
| [CERTIFICATION_REPORT_TEMPLATE.md](CERTIFICATION_REPORT_TEMPLATE.md) | Framework certification report |

Machine suite: `configs/validation/suite.yaml`  
Contract: [SC-FVE](../contracts/16_framework_validation.md)  
Runtime: `cieml/validation/`
