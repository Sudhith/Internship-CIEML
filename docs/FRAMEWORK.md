# CIEML 2.0 — Environmental Intelligence Framework

**Status:** Constitution (Phase A). The executable pipeline today still runs as phased Stages −1–14; this document defines the *target* reusable identity of the framework.

**What this document is:** the scientific methodology and architectural contract.

**What this document is not:** results from any particular monitoring campaign. For the first demonstration, see [CASE_STUDY_VISAKHAPATNAM.md](CASE_STUDY_VISAKHAPATNAM.md).

---

## 1. Purpose

CIEML 2.0 (Coastal Interpretable Environmental Machine Learning → **Environmental Intelligence Framework**) is a reusable scientific methodology for transforming multiparameter environmental monitoring data into:

- statistically validated structure,
- physically interpretable relationships,
- explainable drivers,
- evidence-audited scientific claims,
- decision-ready monitoring guidance,

with explicit applicability limits and uncertainty.

The framework answers:

> How should any aquatic environmental monitoring dataset be scientifically analyzed?

It does **not** answer, as its primary product:

> What happened at one named site?

Site-specific findings are **case-study outputs**, not framework definitions.

---

## 2. Design principles

1. **Domain-configurable, engine-invariant.** Analytical engines stay identical across coastal, estuarine, riverine, lacustrine, reservoir, harbour, and aquaculture settings. Only a **domain profile** and **campaign metadata** change.
2. **Nothing scientifically essential is hardcoded as truth.** Station count, station names, campaign length, number of regimes, dominant drivers, anomaly counts, clustering algorithm, ML model, weather provider, and numeric decision thresholds are *discovered or configured*, not assumed as universal facts.
3. **Flag, do not silently delete.** QA documents issues; exclusion policies are explicit and auditable.
4. **Four-pillar evidence.** Major claims require independent evaluation of statistical evidence, practical significance, physical plausibility, and environmental validation.
5. **Traceability.** Every scored claim must point back to source artifacts, calculations, figures, and limitations.
6. **Definitive only when earned.** Continuous confidence and graded claim classes beat binary pass/fail theater.
7. **Transfer rules, not transplanted cutoffs.** Recommendations travel as framework logic with applicability domains — never as numeric thresholds copied from one campaign to another.

---

## 3. Separation of concerns

| Layer | Contains | Must not contain |
|-------|----------|------------------|
| **Framework** | Engines, contracts, evidence philosophy, decision templates | Site conclusions, fixed K, fixed drivers |
| **Domain profile** (`configs/domains/`) | Expected parameters, plausibility bands, physical relationships, QA knobs, vocabularies | Campaign results |
| **Campaign** (`configs/campaigns/`) | Paths, stations, coords, timezone, adapter choice, external-data endpoints | Scientific verdicts |
| **Case study** (`docs/` case docs + `outputs/`) | Demonstration results for one dataset | Redefinition of methodology |

---

## 4. Engine taxonomy (logical architecture)

Executable stages today map onto these engines. Engine names are the public scientific surface; `stageNN_*` artifact IDs remain the interchange contract until an explicit alias layer is introduced.

| Engine | Responsibility |
|--------|----------------|
| **Domain Configuration Layer** | Load domain science (limits, relationships, QA params, vocabularies) |
| **Universal Ingestion** | Adapter-based standardization to a canonical observation schema |
| **Scientific QA** | Configurable integrity checks (missing, flatline, range, overshoot, …) |
| **Physical Knowledge Engine** | Applicable signed relationships given observed variables |
| **Statistical Intelligence** | Assumption-aware method selection and feature sufficiency |
| **Discovery Engine** | Multi-algorithm structure discovery + stability validation |
| **Explainability Engine** | Multi-method driver consensus (not single-tool authority) |
| **Anomaly Intelligence** | Multi-detector events with typed probable origin |
| **Context plugins** | Optional external forcing and spatiotemporal organization |
| **Process labeling** | Evidence-scored semantic families from domain vocabulary |
| **EBSVE** | Evidence-Based Scientific Validation Engine — claim audit centerpiece |
| **Decision Support Engine** | Monitoring design guidance with confidence and limits |
| **Applicability Domain Engine** | Where each claim/recommendation may and may not be trusted |
| **Knowledge Base** | Append-only memory across campaigns (Phase K / SC-KB) |
| **Uncertainty Propagation** | Typed uncertainty budgets distinct from confidence; serial propagation with named rules |

```text
Domain profile ──► Ingest ──► QA ──► Physics ──► Stats ──► Discovery
                                                              │
                         Decision ◄── EBSVE ◄── XAI / Anomalies / Context
                              │
                      Applicability ──► Knowledge Base
```

---

## 5. Scientific claims (not fixed H1–H6)

The framework supports an open **claim pack**: any number of scientific claims, each with description, evidence, limitations, confidence, applicability, and future validation needs.

A coastal-monitoring claim pack may instantiate claims analogous to today’s H1–H6 (data trust, physical coherence, redundancy, regimes, anomalies, policy transfer). That pack is a **configuration**, not the engine.

Every major claim must be evaluated under four **independent** pillars:

1. Statistical evidence  
2. Practical significance  
3. Physical plausibility  
4. Environmental validation  

Pillars must not reuse each other’s scores. Classification tiers (Definitive / Provisional / Exploratory, gated on the weakest pillar) and numeric thresholds are configured in `configs/framework.yaml` and implemented in `cieml.evidence.scoring`, not buried in case narrative.

---

## 6. Artifact contract

- Phase runners write versioned artifacts under `outputs/phaseN/`.
- Interchange filenames currently follow `stageNN_<name>.{csv,json,parquet,png}`.
- Claim registers travel as `stage_m1_hypothesis_register.json` (legacy filename; body includes `claims` + `claim_pack_id`).
- **Breaking rename of artifact IDs requires an explicit alias map** (loaders, pipeline, evidence bundle).

Framework version and contract version live in `configs/framework.yaml`.

---

## 7. How to apply CIEML to a new dataset

1. Choose or author a **domain profile** (`configs/domains/<domain>.yaml`).
2. Author a **campaign file** (paths, stations, adapter, optional external endpoints).
3. Place raw data where the campaign file points.
4. Run the phased pipeline (`scripts/run_phase1.py` … `run_phase8.py`) without changing engine code.
5. Treat outputs as a **new case study**; do not edit framework docs to insert those conclusions.

Until Phase B–C land, domain/campaign files may still be partially represented by legacy constants and `configs/stations.yaml` — see [REDESIGN_ROADMAP.md](REDESIGN_ROADMAP.md).

---

## 8. What “success” means for the framework

The redesign succeeds when:

- a new aquatic monitoring dataset can be analyzed without changing engine architecture;
- no analytical step depends on one campaign’s assumptions;
- claims are supported by computed evidence with reviewer-traceable sources;
- methodology documentation stays free of case conclusions;
- another group can adopt CIEML with **new domain profile + data adapter (+ campaign metadata)** only.

---


## 8a. Failure modes & framework validation

- When an engine’s conclusions must not be trusted: [failure/README.md](failure/README.md) (SC-FMF).
- When the **framework** itself is certified ready: [validation/README.md](validation/README.md) (SC-FVE).

## 8b. Scientific Contracts Framework

Every engine has a formal **Scientific Contract** (API-like specification for science): purpose, question, inputs/outputs, assumptions, guarantees, failure conditions, applicability, dependencies, verification tests, and a reviewer checklist.

Contracts live in [`docs/contracts/`](contracts/README.md). They define what each engine may claim — and when its outputs must not be trusted — independently of any case study.

Implementations must not silently weaken guarantees. Contract version bumps are required when inputs, guarantees, or failure conditions change.

## 9. Related documents

- Case demonstration: [CASE_STUDY_VISAKHAPATNAM.md](CASE_STUDY_VISAKHAPATNAM.md)
- Generalization roadmap: [REDESIGN_ROADMAP.md](REDESIGN_ROADMAP.md)
- Claim packs: `configs/claims/` (default `coastal_monitoring_v1.yaml`); `configs/hypotheses.yaml` is a deprecated shim
- Decision templates: `configs/decision/`
- Knowledge Base (append-only): `knowledge_base/`
- Scientific contracts: [contracts/README.md](contracts/README.md)
- Framework knobs: `configs/framework.yaml`
