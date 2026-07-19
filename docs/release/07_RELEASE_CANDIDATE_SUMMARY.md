# CIEML 2.0 — Release Candidate 1 Summary

**Verdict: RELEASE CANDIDATE.** See `06_SCIENTIFIC_CERTIFICATION_REPORT.md`
for the full category breakdown and reasoning.

## What RC-1 covers

| # | Report | Result |
|---|---|---|
| 1 | [SC-FMF Integration Report](01_SC_FMF_INTEGRATION_REPORT.md) | Failure catalog wired into all 6 declared engines (Discovery, Explainability, Anomaly Intelligence, EBSVE, Framework Validation, Decision Support). 18-case severity matrix: 1 identical report shape across every engine/severity. 3 bugs found and fixed during integration. |
| 2 | [Scientific Code Freeze Report](02_SCIENTIFIC_CODE_FREEZE_REPORT.md) | `FRAMEWORK_VERSION=2.0.0-rc1`, freeze rules in effect, all component versions recorded. |
| 3 | [Regression Test Report](03_REGRESSION_TEST_REPORT.md) | Full 8-phase pipeline re-run from raw data: **23/23** regression-critical fields byte-identical to the frozen `visakhapatnam_may2026` baseline. Zero scientific changes. |
| 4 | [Reproducibility Report](04_REPRODUCIBILITY_REPORT.md) | Two independent from-scratch full-pipeline runs: **21/21** identical. |
| 5 | [Framework Integrity Audit](05_FRAMEWORK_INTEGRITY_AUDIT.md) | 66/66 modules import cleanly, 12/12 failure modes reachable, 0 orphans, 0 true duplicates, 1 documented (not removed) unused convenience API. |
| 6 | [Release Manifest](RELEASE_MANIFEST.md) | 96 modules checksummed, dependency versions recorded, config versions recorded. Regenerate via `python scripts/generate_release_manifest.py`. |
| 7 | [Scientific Certification Report](06_SCIENTIFIC_CERTIFICATION_REPORT.md) | 13 categories assessed; ~96% measured readiness; verdict RELEASE CANDIDATE. |
| 8 | This document | Executive summary. |

## Success criteria — checked against the original RC-1 request

- [x] All SC-FMF integrations complete across every engine the catalog declares (6/6).
- [x] No scientific conclusions differ from the frozen Visakhapatnam baseline except documented bug fixes (0 differences found — the bug fixes made during SC-FMF wiring did not alter any scientific number; see Integration Report §5).
- [x] All regression tests pass (23/23).
- [x] Framework outputs are reproducible under repeated execution (21/21 twin-run).
- [x] Scientific contracts remain satisfied (17/17 status-consistent, 13 implemented).
- [x] No architectural regressions introduced (0 integrity violations).
- [x] Framework receives a "Release Candidate" (or higher) certification with documented evidence (this document + reports 1–6).

## What changed to reach RC-1 (this session)

- New module: `cieml/failure/report.py` — the single shared `build_failure_report()` every engine calls.
- New catalog policy table: `uncertainty_contributions` (independent from `confidence_multipliers`, both in `configs/failure/catalog.yaml`).
- Wired into: `stage06_regime_discovery.py`, `stage08_explainable_ml.py`, `stage09_anomaly_discovery.py`, `stage10_external_validation.py`, `cieml/evidence/engine.py`, `cieml/validation/suite.py`, and consolidated at `stage14_robustness.py`.
- Uncertainty ledger (`cieml/uncertainty/assemble.py`) now folds failure-mode hits into the matching budget as provenance-tagged components, routed by the catalog's `pillar_impact` field.
- 3 bugs fixed: a sequencing false-positive in the external-support detector, an unhandled crash on empty/missing claim packs in EBSVE, and an unreachable failure mode (`integ_contract_failure_unmapped`).
- 2 testability additions (both backward-compatible, default-preserving): `knowledge_store_root` and `update_phase7_applicability` on `run_stage14`/`run_phase8`, so test/regression runs never mutate the real `knowledge_base/` or a real `phase7_dir`.
- Release metadata: `configs/framework.yaml` → `release:` block, version bumped to `2.0.0-rc1`.
- `docs/release/` created with all 8 RC-1 deliverables plus the manifest generator script.

## Git tag recommendation

`v2.0.0-rc1` — not applied automatically; tagging and pushing are left to the
user per standing repository conventions.

## What's explicitly NOT in RC-1

Per the freeze mandate: no algorithm changes, no threshold tuning, no
confidence/uncertainty recalibration, no new engines. Phase L (manuscript
rewrite) and a second demonstration campaign remain future work, not RC-1
blockers.
