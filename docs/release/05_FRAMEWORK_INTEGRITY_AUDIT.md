# Framework Integrity Audit (RC-1 Task 5)

## Every Scientific Contract satisfied

17 contracts registered in `configs/framework.yaml` → `scientific_contracts.engines`,
each with a corresponding `docs/contracts/*.md` file. Cross-checked: every
contract's own `status:` frontmatter field matches `framework.yaml`'s
`engines:` implementation-status block exactly — no drift.

| Status | Count | Contracts |
|---|---|---|
| implemented | 13 | SC-DCL, SC-PHYS, SC-STAT, SC-DISC, SC-XAI, SC-ANOM, SC-EBSVE, SC-DSS, SC-APP, SC-KB, SC-MMU, SC-REL, SC-FMF (bumped this release — wired into all 6 engines the catalog declares: discovery, explainability, anomaly_intelligence, ebsve, decision_support, framework_validation) |
| partial (documented, not a defect) | 3 | SC-ING (Kor adapter still primary over the generic path), SC-QA (Stage 2 still native), SC-FVE (compliance matrix is a category-level roll-up, not yet per-contract) |
| deprecated (superseded, retained for audit) | 1 | SC-UNC (split into SC-MMU + SC-REL) |

No contract is silently unimplemented — every `partial` status is explicit,
documented, and matches the code's actual behavior.

## Every engine callable

66 core modules across `cieml.*` import cleanly with zero exceptions
(`domain`, `claims`, `evidence` incl. all 6 H-validators, `uncertainty`,
`failure`, `validation`, `applicability`, `decision`, `knowledge`, `explain`,
`anomalies`, `stats`, `ingestion`, `qa`, `physics`, `discovery`, and all
production `stages.*` modules). Verified via direct `importlib.import_module`
over the full list, not a partial sample.

## Every engine validated

All 8 pipeline phases were re-executed end-to-end from raw data in RC-1 Task 3
(Regression Test Report) with zero exceptions and zero regression mismatches
(23/23 fields matched the frozen baseline).

## Every failure mode reachable

All 12 modes in `configs/failure/catalog.yaml` were individually exercised and
confirmed to fire with the correct severity, confidence multiplier, and
uncertainty contribution (SC-FMF Integration Report §4A + a direct
`disc_high_noise` check performed separately, since that mode did not fire in
either full-pipeline run — the campaign's actual noise/stability numbers are
healthy, which is the correct behavior, not a gap):

```
build_failure_report('discovery', {..., 'stage14_noise_or_stability': True})
-> DEGRADED, ['disc_high_noise'], multiplier=0.75, uncertainty=+25.0
```

12/12 catalog modes confirmed reachable.

## Every uncertainty / confidence object propagated

The uncertainty ledger from the full regression run contains all 16 expected
packets: one for each of the 10 `UncertaintyObject` enum members (qa,
measurement, sensor, statistical, model, explainability, anomaly,
environmental, policy, decision) plus one per scientific claim (6, matching
H1–H6). Confidence is populated everywhere the three-axis model defines it
(model, environmental, and all 6 claims) and correctly absent elsewhere (QA,
measurement, sensor, statistical, explainability, anomaly, policy, decision
have no natural single confidence score under the documented design — only an
uncertainty budget). No object type is missing; no confidence field is
silently zero where it should be populated.

## Every artifact generated

Every `ArtifactSpec` in `cieml.evidence.artifacts.ARTIFACT_SPECS` resolved to a
real file across the full regression run (Task 3's `arch_artifact_contract_covers_loaders`
validation-suite test passed, confirming the loader/spec key sets match
exactly with zero missing or extra keys).

## Every dependency resolved

All dependencies imported by the codebase (numpy, pandas, scipy, scikit-learn,
matplotlib, seaborn, PyYAML, openpyxl, statsmodels, tqdm, shap, xgboost,
lightgbm, requests) resolve to installed versions (see Release Manifest).
`hdbscan` is an optional dependency, correctly absent, and already handled by
Stage 6's own `HAS_HDBSCAN` degrade-gracefully flag — not a missing dependency
in the sense this check cares about.

## No orphan modules / no dead plugins

Checked every module under `cieml/ingestion`, `cieml/qa`, `cieml/physics`,
`cieml/discovery`, `cieml/stats`, `cieml/explain`, `cieml/anomalies` — all are
imported by at least one production `cieml.stages.*` module. None are orphaned.

## No duplicate implementations

Checked artifact keys and primary filenames in `ARTIFACT_SPECS` (0 duplicates),
and all 6 claim validators' `hypothesis_id` values (all distinct: H1–H6, no
collisions). One near-duplicate was investigated and found **not** to be a
true duplicate: `cieml/decision/gate.py`'s `gate_recommendations` (the
operational suppress/allow gate) and `stage14_robustness.py`'s
`build_failure_report("decision_support", ...)` call (the standardized dossier
entry) both evaluate the same detectors against the same bundle, but produce
two different, purpose-built shapes for two different consumers — an
intentional design, not redundant logic.

## No unused interfaces

One finding: `cieml.failure.assess_campaign` (the campaign-wide,
run-detectors-once convenience function) is exported and tested but not
currently called by the production pipeline, which instead calls
`build_failure_report` per engine directly at each stage's own completion
point (giving Stage 14 finer control over *when* each engine's consolidated
check runs, since Discovery and Anomaly Intelligence need evidence that only
exists after later stages). `assess_campaign` is fully functional and
regression-tested (see SC-FMF review history) — it is a legitimate, documented
convenience API for callers who want a single-shot campaign view, not dead or
broken code. Retained rather than removed, since deleting a working, tested
public API to satisfy an audit checkbox would itself be an undocumented
capability removal, which the freeze rules do not call for.

**Minor, non-blocking:** two pre-existing unused imports were found during
static analysis (`fcluster` in `stage06_regime_discovery.py`, `sns` in
`stage14_robustness.py`), both present before RC-1 work began and unrelated to
SC-FMF wiring. Left untouched — removing them is a legitimate future cleanup,
not a freeze-blocking integrity issue, and touching unrelated lines during a
freeze review risks scope creep beyond "bug fixes only."

## Verdict

No integrity violations found. All checked guarantees hold.
