# Scientific Contracts Framework

**Role in CIEML 2.0:** Every analytical engine has a formal **Scientific Contract** — analogous to an API contract in software engineering — that states what the engine computes, what scientific guarantees it provides, under which assumptions it operates, and when its outputs must not be trusted.

Contracts make engines **independently reviewable, testable, reusable, and scientifically defensible**.

They are part of the **framework constitution**, not of any case study. Case results must satisfy contracts; they must not redefine them.

---

## Why contracts exist

Without contracts, a pipeline stage is a black box that “ran.” With contracts, a reviewer can ask:

1. What scientific question does this engine answer?
2. What did it promise?
3. What did it assume?
4. When must I discard its outputs?
5. How do I verify it on a new dataset?

---

## Contract index

| ID | Engine | Spec |
|----|--------|------|
| SC-DCL | Domain Configuration Layer | [01_domain_configuration.md](01_domain_configuration.md) |
| SC-ING | Universal Ingestion | [02_universal_ingestion.md](02_universal_ingestion.md) |
| SC-QA | Scientific QA Engine | [03_scientific_qa.md](03_scientific_qa.md) |
| SC-PHYS | Physical Knowledge Engine | [04_physical_knowledge.md](04_physical_knowledge.md) |
| SC-STAT | Statistical Intelligence Engine | [05_statistical_intelligence.md](05_statistical_intelligence.md) |
| SC-DISC | Discovery Engine | [06_discovery.md](06_discovery.md) |
| SC-XAI | Explainability Engine | [07_explainability.md](07_explainability.md) |
| SC-ANOM | Anomaly Intelligence Engine | [08_anomaly_intelligence.md](08_anomaly_intelligence.md) |
| SC-EBSVE | Evidence-Based Scientific Validation Engine | [09_ebsve.md](09_ebsve.md) |
| SC-DSS | Decision Support Engine | [10_decision_support.md](10_decision_support.md) |
| SC-APP | Applicability Domain Engine | [11_applicability_domain.md](11_applicability_domain.md) |
| SC-KB | Knowledge Base | [12_knowledge_base.md](12_knowledge_base.md) |
| SC-UNC | ~~Uncertainty Propagation~~ (deprecated, split below) | [13_uncertainty.md](13_uncertainty.md) |
| SC-MMU | Measurement & Model Uncertainty | [13_measurement_model_uncertainty.md](13_measurement_model_uncertainty.md) |
| SC-REL | Evidence Reliability | [14_evidence_reliability.md](14_evidence_reliability.md) |
| SC-FMF | Scientific Failure Mode Framework | [15_failure_modes.md](15_failure_modes.md) |
| SC-FVE | Framework Validation Engine | [16_framework_validation.md](16_framework_validation.md) |
| SC-CEAM | Coastal Environmental Analysis Module | [17_coastal_environmental_analysis.md](17_coastal_environmental_analysis.md) |

Schema / required sections: [_SCHEMA.md](_SCHEMA.md)

Optional context plugins (external forcing, spatiotemporal organization) inherit the same schema when specified; they are not separate constitution engines until promoted.

---

## Rules for authors and implementers

1. **No silent promise changes.** Changing guarantees, failure conditions, or required inputs is a contract version bump.
2. **No case conclusions in contracts.** Do not cite site-specific regimes, drivers, or anomaly counts as framework guarantees.
3. **Outputs without confidence are incomplete** where the contract requires confidence/uncertainty metrics.
4. **Downstream engines must declare upstream dependencies** and refuse to run (or must degrade with explicit status) when upstream failure conditions fire.
5. **Verification tests in each contract are mandatory** for claiming the engine is scientifically complete.

---

## Relationship to executable stages

Today’s Stages −1–14 implement (fully or partially) these contracts. Redesign Phases B–K close gaps. See [../REDESIGN_ROADMAP.md](../REDESIGN_ROADMAP.md) and `configs/framework.yaml` → `engines` / `scientific_contracts`.
