# CIEML 2.0 — Progress to date

**Document purpose:** Narrative record of what was built, why, and where it stands as of **Release Candidate 1 (`2.0.0-rc1`)**.  
**Audience:** Collaborators, co-authors, and future-you revisiting the redesign.  
**Not a substitute for:** Scientific Contracts (`docs/contracts/`), RC-1 evidence pack (`docs/release/`), or case-study artifacts (`outputs/`).

| Item | Value |
|------|--------|
| Framework version | `2.0.0-rc1` |
| Redesign phases A–K | **Done** |
| Phase L (manuscript rewrite) | Remaining |
| First demonstration | Visakhapatnam coastal sonde campaign (May 2026) |
| Campaign closure | **MIXED_PROVISIONAL** (mean confidence ~88/100) |
| Freeze status | Frozen for regression (no algorithm / threshold / confidence recalibration without a new RC) |

---

## 1. What we set out to do

CIEML began as an executable **coastal analysis pipeline** for one multiparameter sonde campaign at Visakhapatnam. That pipeline already produced serious science (QA → physics → regimes → explainable ML → anomalies → ecological interpretation → decision support → four-pillar claim closure).

The redesign goal was larger:

> Transform the pipeline into a reusable **Environmental Intelligence Framework** — a methodology for *any* aquatic monitoring dataset — **without changing the scientific meaning** of the Visakhapatnam demonstration.

In other words:

- **Keep** Visakhapatnam conclusions as regression baselines.
- **Move** hardcoded science into domain profiles, claim packs, and contracts.
- **Separate** framework methodology from case-study results.
- **Add** explicit uncertainty, failure modes, applicability limits, and framework self-validation.

---

## 2. Non-negotiable invariants

These rules governed every phase:

1. **Case-study scientific conclusions stay put.** Architecture and configuration move; results are not “optimized” to look stronger.
2. **Artifact filenames `stageNN_*` stay stable** so loaders, validators, and H4/DSS contracts keep working.
3. **Do not rebuild the EBSVE pillar ABC.** Claim packs and artifact aliases migrate onto the existing `HypothesisValidator` / scoring design.
4. **Flag, do not silently delete.** QA documents issues; exclusion policies are explicit.
5. **Transfer rules, not transplanted cutoffs.** Recommendations travel with applicability domains — never as numeric thresholds copied from Vizag to another coast.
6. **Definitive only when earned.** Continuous pillar scores and graded claim classes beat binary pass/fail theater.

---

## 3. Separation of concerns (what lives where)

| Layer | Location | Contains | Must not contain |
|-------|----------|----------|------------------|
| Framework constitution | `configs/framework.yaml`, `docs/FRAMEWORK.md` | Engines, philosophy, scoring tiers, release freeze | Site conclusions |
| Scientific contracts | `docs/contracts/` | Per-engine guarantees, inputs, failure conditions | Campaign results |
| Domain profile | `configs/domains/` (e.g. `coastal.yaml`) | Parameters, plausibility, physics pairs, CEAM vocab | Campaign verdicts |
| Campaign metadata | `configs/campaigns/` | Paths, stations, roles, adapter, claim pack id | Scientific conclusions |
| Claim packs | `configs/claims/` | Open hypotheses (H1–H6) + validator bindings | Hardcoded pillar scores |
| Case study outputs | `outputs/phase1` … `phase8` | Demonstration evidence (source of truth for Vizag) | Redefinition of methodology |
| Knowledge base | `knowledge_base/` | Append-only proposals / entries from campaigns | Auto-mutation of domain YAML |

---

## 4. Redesign phases completed (A–K)

### Phase A — Constitution

- Defined CIEML as an **Environmental Intelligence Framework**, not a single-study notebook.
- Introduced framework vs case documentation split.
- Added `configs/framework.yaml` and scientific contract scaffolding.
- Locked the philosophical rule: case studies *demonstrate* contracts; they do not redefine them.

**Commit:** `fb1b592` — *Add CIEML Phase A constitution, scientific contracts, and framework docs.*

### Phases B–E — Domain, ingestion, QA, physics

- **B — Domain Configuration Layer:** Extracted known constants (plausibility ranges, core variables, expected pairs, process vocabularies) into `configs/domains/`.
- **C — Universal ingestion:** Adapter registry (`kor_ysi`, generic path) + canonical observation schema.
- **D — Scientific QA:** Registry-oriented QA; pilot range / magnitude overshoot (e.g. turbidity extremes) without silent deletion.
- **E — Physical Knowledge Engine:** Domain-declared physical relationships drive coherence tests.

**Commit:** `0b46ebb` — *Add CIEML Phases B-E domain, ingestion, QA, and physics layers.*

### Phases F–I — Stats, discovery, explainability, anomalies

- **F — Statistical Intelligence:** Assumption-aware statistical method choice.
- **G — Discovery Engine:** Regime discovery surface polish (Stage 14 sensitivity battery preserved).
- **H — Explainability:** Multi-method / consensus-oriented explainable ML surface.
- **I — Anomaly Intelligence:** Typed anomaly origins rather than opaque outlier lists.

**Commit:** `628657d` — *Add CIEML Phases F-I stats, discovery, explainability, and anomaly origins.*

### Uncertainty Propagation Framework (cross-cutting; not lettered A–L)

Early uncertainty exports saturated near 100 and mixed confidence with uncertainty. A redesign split the model into:

- **SC-MMU** — Measurement & Model Uncertainty  
- **SC-REL** — Evidence Reliability  

Confidence, remaining uncertainty, and reliability became separately reportable. Stage 14 exports a typed uncertainty ledger. On Visakhapatnam, claims separate on the confidence/uncertainty plane rather than clustering at the ceiling.

**Commit:** `dfde46a` — *Add CIEML uncertainty propagation framework and Stage 14 ledger export.*

### Phase J — Claim packs on EBSVE

- Introduced versioned **claim packs** (`configs/claims/coastal_monitoring_v1.yaml`) replacing a fixed hypothesis-only worldview.
- Campaign selects `claim_pack: coastal_monitoring_v1`.
- EBSVE resolves validators from the pack (plugin registry); `HypothesisValidator` ABC and scoring unchanged.
- Evidence loaders use a versioned **artifact alias map**.
- Stage −1 loads the claim register from the pack; `configs/hypotheses.yaml` retained as a deprecated shim.
- Regression: claim classes matched the frozen Visakhapatnam baseline (`MIXED_PROVISIONAL`).

**Commit:** `c9d3dfe` — *Add CIEML Phase J claim packs and EBSVE plugin registry.*

### Scientific Failure Mode Framework (SC-FMF) + Framework Validation (SC-FVE)

Two systems that sit beside A–L:

1. **SC-FMF** (`cieml/failure/`, `configs/failure/catalog.yaml`, `docs/failure/`)  
   Declares when engine conclusions must not be trusted: taxonomy, severity, detection, recovery, DSS suppress rules. Shared `build_failure_report()` shape across engines.

2. **SC-FVE** (`cieml/validation/`, `configs/validation/suite.yaml`, `docs/validation/`)  
   Certifies **CIEML itself** (architecture, reproducibility, contracts, evidence integrity) — not the dataset.  
   Run: `python -m cieml.validation`.

FMF assessments were wired into Stages 06, 08, 09, 10 (and consolidated at Stage 14 / EBSVE / DSS gate).

**Commits:**  
`3768d36` — *Add SC-FMF failure modes and SC-FVE framework validation.*  
`3176029` — *Wire SC-FMF assessments into Stages 06 through 10.*

### Phase K — Decision support, applicability, knowledge base

- **DSS** (`cieml/decision/`): Template-driven monitoring recommendations from `configs/decision/`; role-based spatial design (no “Rushikonda-like” hardcoding); FMF gate before trusting DSS.
- **Applicability** (`cieml/applicability/`): Campaign- and claim-level enrichment — where conclusions may / may not transfer.
- **Knowledge Base** (`cieml/knowledge/`, `knowledge_base/`): Append-only store for proposals/entries; **domain YAML is never auto-mutated**.
- Stage 13 refactored toward DSS + APP; Stage 14 enriches applicability, gates DSS, proposes KB entries.

**Commit:** `5e08f8b` — *Add CIEML Phase K decision support, applicability, and knowledge base.*

### CEAM — Coastal Environmental Analysis Module (Stage 12)

Stage 12 was audited as only a **partial** process-labeling engine (hardcoded harbour assumptions, weak consumption of Stages 9–11). It was rebuilt as **SC-CEAM**:

- Package `cieml/ceam/` — context, regime, hydrodynamics, water quality, meteorology, spatial, temporal, ecological, fusion, narrative, summary, engine.
- Domain `ceam:` thresholds / titles / roles in `configs/domains/coastal.yaml`.
- Campaign stations carry explicit **roles** (`harbour_embayment`, `open_coast`, `ambient_reference`).
- Consumes upstream outputs only (does not re-run clustering / SHAP / anomalies / QA).
- Emits coastal assessment JSON, scientific narrative, and traceability artifacts while keeping legacy Stage 12 outputs for H4 / DSS compatibility.
- Four-level units: Observation → Interpretation → Evidence → Confidence & Limitations.

**Commit:** `41583ba` — *Implement Stage 12 as full Coastal Environmental Analysis Module.*

### Release Candidate 1 freeze

- Version bump to `2.0.0-rc1` with freeze rules in `configs/framework.yaml`.
- Full evidence pack under `docs/release/` (FMF integration, code freeze, regression, reproducibility, integrity audit, certification, RC summary, checksums manifest).
- Manifest generator: `scripts/generate_release_manifest.py`.

**Commit:** `74297de` — *Freeze CIEML 2.0.0-rc1 release package and framework docs.*

---

## 5. Executable pipeline (what still runs day-to-day)

The public scientific surface is engine contracts; the runnable unit remains **phased Stages −1–14**.

| Phase | Stages | Role |
|------|--------|------|
| 1 | −1, 0, 1 | Claim register, ingestion, scientific audit |
| 2 | 2, 3 | Sensor QA, physical validation |
| 3 | 4, 5 | Feature engineering, statistical validation |
| 4 | 6, 7 | Regime discovery & validation |
| 5 | 8, 9 | Explainable ML, anomaly discovery |
| 6 | 10, 11 | External / meteo validation, spatial–temporal analysis |
| 7 | 12, 13 | CEAM interpretation, decision support |
| 8 | 14 + EBSVE | Robustness, uncertainty ledger, four-pillar claim closure |

**How to run (sequential):**

```text
python scripts/run_phase1.py
…
python scripts/run_phase8.py
```

**Framework self-check:**

```text
python -m cieml.validation
```

**Default campaign:** `configs/campaigns/visakhapatnam_may2026.yaml`  
**Default data root:** `DATA/` (Kor / YSI-style multiparameter exports)

---

## 6. Scientific Contracts inventory

Contracts live under `docs/contracts/`. Status at RC-1 (framework freeze): feature-complete for the engines below; changing guarantees requires a contract version bump.

| ID | Engine |
|----|--------|
| SC-DCL | Domain Configuration |
| SC-ING | Universal Ingestion |
| SC-QA | Scientific QA |
| SC-PHYS | Physical Knowledge |
| SC-STAT | Statistical Intelligence |
| SC-DISC | Discovery |
| SC-XAI | Explainability |
| SC-ANOM | Anomaly Intelligence |
| SC-EBSVE | Evidence-Based Scientific Validation |
| SC-DSS | Decision Support |
| SC-APP | Applicability Domain |
| SC-KB | Knowledge Base |
| SC-MMU / SC-REL | Measurement–Model Uncertainty / Evidence Reliability |
| SC-FMF | Failure Modes |
| SC-FVE | Framework Validation |
| SC-CEAM | Coastal Environmental Analysis |

Legacy `SC-UNC` is deprecated in favor of the MMU + REL split.

---

## 7. Visakhapatnam demonstration — what the framework concluded

**Source of truth:** `outputs/phase8/` (especially `PHASE8_SUMMARY.md`, `stage14_scientific_closure.md`).

### Campaign-level verdict

- **Closure class:** `MIXED_PROVISIONAL`
- **Mean confidence:** ~88/100
- **Regime structure after Stage 14:** statistically useful but labeled **fragile** (spatial power limited by six stations)
- **Weakest campaign-wide pillar:** H4 environmental (spatial gradients not confirmatory at n=6)

### Per-claim classes (coastal monitoring pack)

| Claim | Class | One-line reading |
|-------|-------|------------------|
| H1 data trustworthiness | EXPLORATORY | Mostly clean; residual critical turbidity magnitude issues |
| H2 physical coherence | EXPLORATORY | Campaign-wide physics holds; not fully station-stable |
| H3 information redundancy | PROVISIONAL | Channels reducible with process coverage retained |
| H4 environmental regimes | EXPLORATORY | Multivariate regimes supported; spatial confirmation weak |
| H5 anomaly reality | EXPLORATORY | Consensus anomalies exist; external meteo support partial |
| H6 policy / monitoring transfer | PROVISIONAL | DSS package coherent for harbour vs open-coast regimes |

### Interpretive coastal story (CEAM / Stage 12)

Three regimes in May 2026 station-days:

1. **Mixed / ambient coastal** — dominant state  
2. **Freshwater-influenced turbid coastal** — depressed salinity, elevated turbidity, open-coast stations  
3. **Harbour low-oxygen** — Fishing Harbour–linked hypoxic fingerprint  

### Explicitly *not* claimed

- Universal DO / pH / turbidity thresholds for other coasts  
- Causal pollutant-source attribution beyond water-quality fingerprints + partial meteo support  
- Seasonal or multi-year climatology from a one-month window  

---

## 8. What we gained by building the framework

1. **Methodology reusable beyond Vizag** — swap domain + campaign + claim pack; keep engines.
2. **Scientific honesty** — graded claims and documented weak pillars instead of false DEFINITIVE theater.
3. **Evidence discipline** — four independent pillars with artifact-backed trails.
4. **Safety rails** — failure modes (when not to trust), applicability (where not to transfer), uncertainty ≠ confidence.
5. **Decision readiness** — monitoring recommendations with sensor maps and suppress gates.
6. **Self-certification** — SC-FVE + RC-1 pack (regression, twin-run reproducibility, integrity, certification).
7. **Reviewer / manuscript posture** — novelty can be the framework, with Vizag as the first demonstration rather than the definition of the method.

---

## 9. RC-1 evidence pack (freeze deliverables)

Located in `docs/release/`:

| # | Document | Role |
|---|----------|------|
| 01 | SC-FMF Integration Report | Failure wiring across declared engines |
| 02 | Scientific Code Freeze Report | Version + freeze rules |
| 03 | Regression Test Report | Full pipeline vs frozen Vizag baseline |
| 04 | Reproducibility Report | Twin independent full runs |
| 05 | Framework Integrity Audit | Imports, orphans, failure reachability |
| 06 | Scientific Certification Report | Category readiness / RC verdict |
| 07 | Release Candidate Summary | Executive checklist |
| — | `RELEASE_MANIFEST.json` / `.md` | Checksums + dependency versions |

Recommended git tag (not applied automatically): `v2.0.0-rc1`.

---

## 10. Git history of the redesign (local master)

Phase-wise commits (newest last among redesign arc):

| Commit | Summary |
|--------|---------|
| `fb1b592` | Phase A — constitution + contracts |
| `0b46ebb` | Phases B–E — domain / ingestion / QA / physics |
| `628657d` | Phases F–I — stats / discovery / explain / anomalies |
| `dfde46a` | Uncertainty propagation + Stage 14 ledger |
| `c9d3dfe` | Phase J — claim packs + EBSVE registry |
| `3768d36` | SC-FMF + SC-FVE scaffolding |
| `3176029` | FMF wiring into Stages 06–10 |
| `5e08f8b` | Phase K — DSS / applicability / knowledge base |
| `41583ba` | CEAM — Stage 12 coastal analysis module |
| `74297de` | RC-1 release package + framework freeze |

Earlier pipeline commits (Phases 1–8 executable science) sit below this redesign arc on the same branch.

---

## 11. What remains (intentionally out of RC-1)

| Item | Status |
|------|--------|
| **Phase L** — Manuscript contribution rewrite (novelty = framework) | Planned / docs |
| Second demonstration campaign (non-Vizag) | Future |
| Algorithm / threshold / confidence recalibration | Blocked under RC-1 freeze |
| Uncertainty model further polish beyond MMU/REL acceptance tests | Optional research follow-on |
| Git tag `v2.0.0-rc1` + remote push | Manual (user action) |

---

## 12. Key pointers

| Need | Go here |
|------|---------|
| Framework philosophy | `docs/FRAMEWORK.md` |
| Redesign checklist A–L | `docs/REDESIGN_ROADMAP.md` |
| Visakhapatnam case framing | `docs/CASE_STUDY_VISAKHAPATNAM.md` |
| Contracts index | `docs/contracts/README.md` |
| Failure modes | `docs/failure/README.md` |
| Framework validation | `docs/validation/README.md` |
| RC-1 pack | `docs/release/07_RELEASE_CANDIDATE_SUMMARY.md` |
| Campaign config | `configs/campaigns/visakhapatnam_may2026.yaml` |
| Claim pack | `configs/claims/coastal_monitoring_v1.yaml` |
| Live results | `outputs/phase1` … `outputs/phase8` |

---

## 13. One-sentence status

**CIEML 2.0 is a frozen Release Candidate Environmental Intelligence Framework (Phases A–K + FMF/FVE + CEAM + uncertainty), demonstrated on Visakhapatnam as MIXED_PROVISIONAL, with manuscript rewrite (Phase L) and additional campaigns still ahead.**
