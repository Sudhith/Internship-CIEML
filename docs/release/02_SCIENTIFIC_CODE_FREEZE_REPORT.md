# Scientific Code Freeze Report (RC-1 Task 2)

## Release identity

| Field | Value |
|---|---|
| FRAMEWORK_VERSION | `2.0.0-rc1` |
| BUILD_NUMBER | 1 |
| RELEASE_DATE | 2026-07-19 |
| Artifact Contract Version | `1` |
| Scientific Contracts Version | `1.0.0` |
| Domain Profile Version (coastal) | `1.0.0` |
| Claim Pack Version (coastal_monitoring_v1) | `1.0.0` |
| Regression Baseline | `visakhapatnam_may2026` (`outputs/phase8/stage14_four_pillar_closure.json`) |
| Validation Suite Version | `1.0.0` |
| Git tag recommendation | `v2.0.0-rc1` |

Recorded machine-readably in `configs/framework.yaml` → `release:` block, and
regenerable via `python scripts/generate_release_manifest.py` →
`docs/release/RELEASE_MANIFEST.{json,md}`.

## Freeze rules in effect from this point

No algorithmic changes · no statistical changes · no parameter tuning · no
threshold modifications · no confidence calibration · no uncertainty redesign ·
no architectural expansion · no new engines. **Only bug fixes are permitted.**

This report itself documents the last set of changes made *before* the freeze
took effect (SC-FMF stage wiring, Task 1) — those are integration and two
narrowly-scoped bug fixes (§5 of the SC-FMF Integration Report), not new
science, and are the reason the freeze is being declared now rather than
earlier.

## What "frozen" means operationally

- `configs/framework.yaml`, `configs/domains/*.yaml`, `configs/claims/*.yaml`,
  `configs/failure/catalog.yaml`, `configs/validation/suite.yaml`, and
  `docs/contracts/*.md` are locked at the versions listed above. Any future
  edit to a scientific guarantee, threshold, or contract requires a version
  bump per each file's own stated rule (already enforced by convention
  throughout this codebase — e.g. `docs/contracts/README.md` rule 1: "No
  silent promise changes").
- Output artifact filenames (`stageNN_*.{csv,json,parquet,png}`) are frozen
  per the artifact contract (`cieml.evidence.artifacts.ARTIFACT_SPECS`);
  renaming a primary filename requires updating that map and is itself
  classified as a breaking change, not a bug fix.
- The claim pack (`coastal_monitoring_v1`, H1–H6) and their bound validator
  classes (`cieml.evidence.h1_data_trust.H1Validator` etc.) are frozen; pillar
  scoring algebra in `cieml.evidence.base.HypothesisValidator` is frozen.
- The uncertainty propagation model (`cieml.uncertainty.propagate`) — the GUM
  combination formula, precision fusion, and the saturation map — is frozen.

## Release manifest summary

From the generated manifest (see `docs/release/RELEASE_MANIFEST.md` for the
full table): **96 Python modules** under `cieml/`, each with a recorded SHA-256
checksum and line count, forming the complete, auditable module inventory for
this release. Key dependency versions (installed, verified via
`importlib.metadata`): numpy 2.2.3, pandas 2.2.3, scipy 1.17.0,
scikit-learn 1.8.0, statsmodels 0.14.6, shap 0.49.1, xgboost 3.1.3,
lightgbm 4.6.0. `hdbscan` is an optional dependency and is correctly reported
as not installed — Stage 6 already degrades gracefully via its own
`HAS_HDBSCAN` flag when this is the case, so its absence does not block RC-1.

## Waivers

None issued. No test was skipped or excluded to reach this freeze point.
