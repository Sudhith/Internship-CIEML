# Case study — Visakhapatnam coastal multiparameter sonde campaign

**Role:** First demonstration of CIEML 2.0.

**Role it does not have:** Definition of the framework. Methodological claims belong in [FRAMEWORK.md](FRAMEWORK.md).

This document summarizes the demonstration setting and where to find results. It intentionally keeps scientific interpretation tied to **artifacts under `outputs/`**, which are the source of truth for this campaign.

---

## 1. Demonstration setting

| Item | Description |
|------|-------------|
| Region | Visakhapatnam coast (eastern India) |
| Design | Multiparameter sonde short casts at fixed coastal stations |
| Temporal coverage | Daily station-days across a one-month intensive window (May 2026 campaign files in `DATA/`) |
| Spatial design | Multiple open-coast stations plus harbour/embayment representation |
| Input format | Vendor Kor-style multiparameter exports (UTF-16 CSV family) |
| Campaign metadata (coords) | `configs/stations.yaml` (approximate public locations; not analysis thresholds) |

Exact station lists, file inventories, and completeness matrices are produced by Phase 1 artifacts — do not treat this markdown table as a substitute for `outputs/phase1/`.

---

## 2. Why this case exists

The case validates that the CIEML analytical philosophy can:

- audit and flag multiparameter sonde records,
- test physical coherence,
- discover and validate environmental structure without a pre-chosen K,
- explain regime membership with multi-model/XAI tooling,
- detect consensus anomalies and seek external context,
- close scientific claims under a four-pillar evidence audit,
- emit monitoring decision support with stated transfer limits.

It is **one** aquatic demonstration, not a universal coastal climatology.

---

## 3. Where results live (source of truth)

| Phase | Stages | Directory |
|-------|--------|-----------|
| 1 | −1, 0, 1 | `outputs/phase1/` |
| 2 | 2, 3 | `outputs/phase2/` |
| 3 | 4, 5 | `outputs/phase3/` |
| 4 | 6, 7 | `outputs/phase4/` |
| 5 | 8, 9 | `outputs/phase5/` |
| 6 | 10, 11 | `outputs/phase6/` |
| 7 | 12, 13 | `outputs/phase7/` |
| 8 | 14 + EBSVE | `outputs/phase8/` |

Start with the phase summaries:

- `outputs/phaseN/PHASEN_SUMMARY.md`
- Phase 8 closure: `outputs/phase8/stage14_scientific_closure.md`
- Reviewer-oriented EBSVE figures under `outputs/phase8/figures/`

**Do not copy numeric case conclusions into `docs/FRAMEWORK.md`.**

---

## 4. How to reproduce this case

From the repository root (with dependencies from `requirements.txt`):

```bash
python scripts/run_phase1.py
python scripts/run_phase2.py
python scripts/run_phase3.py
python scripts/run_phase4.py
python scripts/run_phase5.py
python scripts/run_phase6.py
python scripts/run_phase7.py
python scripts/run_phase8.py
```

Phase 6 external meteorology requires network access for the configured archive provider. All other phases are local given `DATA/` and prior phase outputs.

---

## 5. Applicability reminder (case → elsewhere)

Findings from this campaign support **framework rules** (e.g. dual harbour–open-coast design logic, DO/pH maintenance priority when those variables dominate regime structure *in the evidence*). They do **not** authorize transplanting Visakhapatnam-specific cutoffs, regime counts, or anomaly lists to another coastline without re-running CIEML on that dataset.

See Stage 13 / Phase 7 applicability artifacts and Phase 8 claim classifications for the campaign’s own wording of limits.

---

## 6. Relationship to redesign Phases A–L

Under the generalization roadmap, this case becomes:

- a **campaign profile** (paths, stations, adapter), and
- a **coastal domain profile** consumer,

while its scientific outputs remain frozen as demonstration evidence unless intentionally re-run for regression testing.
