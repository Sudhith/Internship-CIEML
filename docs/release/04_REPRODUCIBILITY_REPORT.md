# Reproducibility Report (RC-1 Task 4)

## Method

The complete 8-phase pipeline was executed twice, independently, from raw
data, in two separate scratch directories, with no shared state between runs
(separate `output_dir` trees, separate `knowledge_store_root`). Same code,
same config, same `RANDOM_STATE` defaults (`configs/framework.yaml` →
`reproducibility.default_random_state: 42`, and each stage's own local seeds
where declared). This directly tests **deterministic outputs / seed
stability** end-to-end, not just within one stage.

## Twin-run diff

| Check | Result |
|---|---|
| Discovery: best algorithm/k/silhouette/stability | MATCH |
| Explainability: driver tiers (Dominant/Secondary/Negligible) | MATCH |
| Explainability: SC-FMF failure report severity | MATCH |
| Anomaly: consensus count | MATCH |
| Anomaly: category counts | MATCH |
| EBSVE: campaign closure | MATCH |
| EBSVE: campaign mean confidence | MATCH |
| EBSVE: all 6 claims' classification | MATCH (×6) |
| EBSVE: all 6 claims' overall confidence | MATCH (×6) |
| Uncertainty ledger summary (mean uncertainty, max, claim caution, claim reliability) | MATCH |
| SC-FMF dossier severities (all 6 engines) | MATCH |

**21/21 identical.**

## Stability dimensions

- **Deterministic outputs:** confirmed above — twin runs from raw data produce
  bit-identical scientific results across every checked field.
- **Seed stability:** the only stochastic components (KMeans/GMM/spectral
  clustering candidate search, RandomForest/XGBoost/LightGBM training,
  bootstrap/permutation batteries) all resolve to the same selected model,
  same driver tiers, and same downstream classifications across runs — the
  fixed `RANDOM_STATE=42` default holds through the full 8-phase chain.
- **Configuration stability:** both runs read the same frozen
  `configs/*.yaml` files; no config was mutated mid-run (verified — the RC-1
  freeze declares these locked, and both runs used identical config content).
- **Artifact stability:** identical artifact filenames, identical JSON key
  sets, confirmed by the regression run's `arch_artifact_contract_covers_loaders`
  validation-suite test (still passing, 11/11).
- **Schema stability:** `cieml.evidence.artifacts.ARTIFACT_SPECS` and the
  claim pack schema (`cieml.claims.schema.ScientificClaim`) were not touched
  during SC-FMF integration; both runs load them identically.
- **API stability:** `run_phase1`...`run_phase8`, `run_stage14`, and
  `build_campaign_uncertainty_ledger` all gained new *optional*
  keyword-only parameters this release (`knowledge_store_root`,
  `update_phase7_applicability`, `failure_reports`) — every existing
  positional/keyword call site continues to work unchanged, confirmed by
  both twin runs using the pre-existing call pattern successfully.
- **Scientific stability:** see the Regression Test Report (Task 3) — zero
  scientific conclusion changed from the frozen baseline, and this twin run
  additionally confirms zero drift between two *fresh* executions of the
  current codebase, independent of the baseline entirely.

## Verdict

**Reproducible.** Two independent full-pipeline executions from raw data
produced identical scientific conclusions, identical SC-FMF failure
assessments, and identical uncertainty ledger summaries.
