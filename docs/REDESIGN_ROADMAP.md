# CIEML generalization roadmap (Phases A–L)

Plan for transforming the executable coastal pipeline into a reusable Environmental Intelligence Framework without changing the scientific meaning of the Visakhapatnam demonstration.

**Invariant:** Case-study outputs stay regression baselines. Architecture and configuration move; conclusions are not “optimized.”

**Scientific Contracts:** Formal per-engine specs in [`docs/contracts/`](contracts/README.md). Later phases must close `partial`/`planned` contract gaps without silently changing guarantees.

| Phase | Focus | Depth |
|-------|--------|-------|
| **A** | Constitution: framework vs case docs, `framework.yaml`, layout stubs | **Done** |
| **B** | Domain Configuration Layer — extract known constants to YAML | **Done** |
| **C** | Universal ingestion adapters + canonical schema | **Done** (Kor + generic path; schema documented) |
| **D** | QA registry; pilot = range + magnitude overshoot | **Done** (pilot live; Stage 2 still native) |
| **E** | Physical Knowledge Engine from domain relationships | **Done** |
| **F** | Statistical Intelligence — assumption-aware method choice | **Done** |
| **G** | Discovery Engine surface polish (Stage 14 battery stays) | **Done** |
| **H** | Multi-method explainability consensus | **Done** |
| **I** | Typed anomaly origins | **Done** |
| **J** | Claim-pack migration on existing EBSVE (`HypothesisValidator` kept) | **Done** |
| **K** | Decision support + Applicability engine + Knowledge Base | **Done** |
| **L** | Manuscript contribution rewrite (novelty = framework) | Docs |

### Beyond A–L: Failure Mode Framework + Framework Validation (designed; partial runtime)

Two cross-cutting systems sit beside A–L:

1. **Scientific Failure Mode Framework (SC-FMF)** — `docs/failure/`, `configs/failure/catalog.yaml`, `cieml/failure/`.
   Declares when engine conclusions must not be trusted (severity, detection, recovery, DSS suppress).
2. **Framework Validation Engine (SC-FVE)** — `docs/validation/`, `configs/validation/suite.yaml`, `cieml/validation/`.
   Certifies CIEML itself (architecture, reproducibility, contracts, evidence integrity) — not the dataset.

Run certification: `python -m cieml.validation` → `outputs/framework_validation/`.

### Beyond A–L: Uncertainty model v2 (implemented; not lettered above)

An Uncertainty Propagation Framework (`cieml/uncertainty/`, contract `SC-UNC` v1) was added
alongside Phases F–I to give EBSVE claims a typed uncertainty budget distinct from confidence.
An audit found it saturated (near-universal uncertainty≈100), double-counted correlated sources,
and could not let corroborating evidence reduce propagated doubt — methodological problems, not
implementation bugs. A full redesign (three-axis Confidence / Measurement & Model Uncertainty /
Evidence Reliability model, GUM-consistent correlation-aware combination, Kalman-style serial
resolution, bounded-by-construction reporting) is documented in
[`docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md`](uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md).
**Implemented and verified** — all six migration steps in that document's §11 have landed
(`models.py`, `propagate.py`, `reliability.py`, `assemble.py`, `visualize.py` rewritten; contract
split into [SC-MMU](contracts/13_measurement_model_uncertainty.md) +
[SC-REL](contracts/14_evidence_reliability.md), old `SC-UNC` marked deprecated), and the
acceptance test in §9.6 (claims visibly separated on a confidence/uncertainty scatter, not
clustered at the ceiling) passes against the real Visakhapatnam campaign ledger — confidence
spans ~45–96, remaining uncertainty spans ~43–66, Evidence Reliability sits at a legible
sub-saturated ~62.5, none clustered at 100.

### Notes locked from design review

- `cieml/evidence/` ABC + scoring is already Phase-J-shaped; migrate domain dicts and loaders, do not rebuild pillars.
- Stage 14 sensitivity reads `regime_algorithm` / `regime_k` from data — preserve it.
- Phase B swallows `PLAUSIBILITY_RANGES`, `CORE_VARIABLES`, `EXPECTED_PAIRS`, and evidence-side group/keyword maps.
- Phase D pilot check: `stage01_audit._classify_range` overshoot logic (turbidity spike class of failures).

Implement **one phase at a time**, with Visakhapatnam re-run regression after contract-touching phases.
