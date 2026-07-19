# Regression Test Report (RC-1 Task 3)

## Method

The complete framework was re-executed **from raw data**, all 8 phases
(`run_phase1` → `run_phase8`), entirely in an isolated scratch directory (no
writes to the real `outputs/` or `knowledge_base/` — verified via
`knowledge_store_root`/`update_phase7_applicability` overrides added for this
purpose). This exercises domain loading, universal ingestion, QA, physical
validation, statistics, discovery, explainability, anomaly detection, external
validation, decision support, applicability, the evidence engine, and the
failure mode framework — every item in scope. Compared against the frozen
baseline at `outputs/phase8/stage14_four_pillar_closure.json` and its sibling
artifacts (the `visakhapatnam_may2026` regression baseline named in
`configs/framework.yaml` → `release.versions.regression_baseline`).

## Comparison table

| Engine | Field | Baseline | Current | Diff class |
|---|---|---|---|---|
| Discovery | `best.algorithm` | `ward` | `ward` | Expected (same) |
| Discovery | `best.k` | `3` | `3` | Expected (same) |
| Discovery | `best.silhouette` | `0.3246410174212857` | `0.3246410174212857` | Expected (same) |
| Explainability | `driver_tiers.Dominant` | `[do_mg_l__mean, ph__mean, idx_do_...]` | identical | Expected (same) |
| Explainability | `driver_tiers.Secondary` | `[turbidity_fnu__mean, idx_do_solubi...]` | identical | Expected (same) |
| Anomalies | `n_consensus_anomalies` | `11` | `11` | Expected (same) |
| Anomalies | `category_counts` | `{oxygen_regime_excursion: 5, ...}` | identical | Expected (same) |
| Anomalies | `anomaly_external_support_frac` | `0.45454545454545453` | identical | Expected (same) |
| Scientific Claims | `campaign_closure` | `MIXED_PROVISIONAL` | identical | Expected (same) |
| Scientific Claims | `campaign_mean_confidence` | `88.0` | `88.0` | Expected (same) |
| Scientific Claims | `H1`–`H6` classification (×6) | see below | identical (×6) | Expected (same) |
| Scientific Claims | `H1`–`H6` overall_confidence (×6) | see below | identical (×6) | Expected (same) |
| Decision Support | `n_recommendations` | `3` | `3` | Expected (same) |

Per-claim detail (all six, baseline == current in every cell):

| Claim | Classification | Confidence |
|---|---|---|
| H1_data_trustworthiness | EXPLORATORY | 89.0 |
| H2_physical_coherence | EXPLORATORY | 88.9 |
| H3_information_redundancy | PROVISIONAL | 88.8 |
| H4_environmental_regimes | EXPLORATORY | 79.3 |
| H5_anomaly_reality | EXPLORATORY | 86.1 |
| H6_policy_transfer | PROVISIONAL | 96.3 |

**Total comparisons: 23. Mismatches: 0.**

## Diff classification

Every comparison above classifies as **Expected** (value must be identical, and
is). No **Bug Fix**, **Regression**, **Numerical Noise**, **Scientific Change**,
or **Configuration Difference** entries were needed — the pipeline, run fresh
from raw data with the fully-wired SC-FMF integration in place, reproduces the
frozen scientific conclusions exactly.

## SC-FMF dossier from this run (new signal, not a regression-tracked value)

The failure dossier is new in this release (it didn't exist at the baseline) so
it has no prior value to diff against — reported here for completeness, not as
a pass/fail regression item:

| Engine | Severity | Modes triggered |
|---|---|---|
| discovery | NONE | — |
| explainability | WARNING | `xai_high_feature_correlation` |
| anomaly_intelligence | NONE | — |
| ebsve | NONE | — |
| decision_support | NONE | — |
| framework_validation | NONE | — |

The explainability WARNING is the same genuine finding reported in the SC-FMF
Integration Report (§4C) — two dominant drivers correlated at 0.9135 against
the 0.90 threshold — reproduced identically on this from-scratch run,
consistent with the deterministic-detector guarantee in SC-FMF's contract.

## Framework Validation Engine (SC-FVE) result on this run

`CERTIFIED`, 11/11 tests passing (10 pre-existing + `acc_phase_k_engines_import`
added during the Phase K review).

## Verdict

**PASS.** No scientific conclusion differs from the frozen baseline. All
regression-critical fields across Discovery, Explainability, Anomaly
Intelligence, Scientific Claims (EBSVE), and Decision Support are unchanged.
