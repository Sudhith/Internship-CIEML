# SC-FMF Integration Report (RC-1 Task 1)

**Status:** Complete. **Scope:** Wire the existing Scientific Failure Mode Framework
(catalog, detectors, severity policy, recovery guidance — all pre-existing, none
redesigned) into every analytical engine that did not already have it.

## 1. What was built

One shared function, `cieml.failure.report.build_failure_report(engine_id, bundle)`,
is now called identically by all six engines. No engine implements its own failure
logic — each call site only assembles a `bundle` dict of its own live metrics and
calls the same function. Verified: **18 test cases across all 6 engines produced
exactly 1 distinct Failure Report Object field-set shape** (see §4).

| Engine | Call site | Status |
|---|---|---|
| Discovery | `stage06_regime_discovery.py` (local) + `stage14_robustness.py` (consolidated, adds `disc_high_noise` once the noise battery exists) | Wired |
| Explainability | `stage08_explainable_ml.py` | Wired |
| Anomaly Intelligence | `stage09_anomaly_discovery.py` (local, `anom_zero_consensus`) + `stage10_external_validation.py` (supplementary, `anom_no_external_validation`) + Stage 14 consolidation | Wired |
| EBSVE | `cieml/evidence/engine.py` (`run_evidence_engine`) | Wired |
| Framework Validation | `cieml/validation/suite.py` (`run_validation_suite`) | Wired |
| Decision Support | `cieml/decision/gate.py` (pre-existing from Phase K) | Already complete; also re-evaluated via the shared builder at Stage 14 for dossier consistency |

## 2. The Failure Report Object

Every call returns the same shape:

```
engine, failure_modes_triggered, severity, confidence_adjustment
{multiplier, rule}, uncertainty_adjustment {raw_contribution, rule},
scientific_impact, recovery_suggestions, blocking_status, status,
timestamp, hits, user_messages, catalog_version
```

**Confidence and uncertainty are independently declared**, not each other's
complement — `configs/failure/catalog.yaml`'s `policy` block now carries two
separate severity tables:

```yaml
confidence_multipliers: {INFO: 1.00, WARNING: 0.95, DEGRADED: 0.75, CRITICAL: 0.40, FATAL: 0.00}
uncertainty_contributions: {INFO: 0.0, WARNING: 10.0, DEGRADED: 25.0, CRITICAL: 50.0, FATAL: 80.0}
```

Confidence composes by **min** across triggered hits (one bad pillar isn't diluted
by good ones); uncertainty composes by **max** (an additional failure can never
*reduce* reported doubt) — a deliberate asymmetry, not an oversight, verified by
`configs/validation`'s `sci_uncertainty_no_complement_rule` test (still passing,
see Task 3).

## 3. Pipeline flow (as specified)

```
Run engine -> evaluate failure modes -> assign severity -> adjust confidence ->
adjust uncertainty -> generate warnings -> generate recovery suggestions ->
pass structured failure report downstream
```

Concretely: each engine's own `stageNN_*_report.json` now embeds a `failure_report`
key and a companion `stageNN_failure_report.json` is written. At Stage 14, all six
reports are re-collected (Discovery and Anomaly Intelligence re-evaluated with the
now-complete evidence set) into one `stage14_failure_dossier.json`, and every
triggered hit's declared `uncertainty_adjustment` is folded into the matching
`UncertaintyBudget` in the SC-MMU ledger as a provenance-tagged `SYSTEMATIC`
component (`provenance_id = f"failure_{mode_id}"`), routed by the catalog's
`pillar_impact` field when declared (e.g. `anom_no_external_validation` lands on
the *environmental* budget, not the *anomaly* one, exactly matching its catalog
declaration) and by `engine_id` otherwise. This closes the loop SC-FMF's own
contract requires: "failure reduces confidence explicitly; it does not set
U = 100 - C" — confirmed by construction, since the two tables are declared
independently and the uncertainty contribution is a real ledger component, not a
cosmetic multiplier.

## 4. Validation evidence (real, executed — not asserted)

**A. Controlled severity matrix** — 18 synthetic-bundle cases spanning all 6 wired
engines and the full severity range (NONE/INFO, WARNING, DEGRADED, CRITICAL, FATAL):

```
engine                 case       severity   conf_mult  unc_contrib  blocking  modes
discovery              NORMAL     NONE       1.0        0.0          False     []
discovery              (n=4)      DEGRADED   0.75       25.0         False     ['disc_too_few_stations']
discovery              (sil=0.18) DEGRADED   0.75       25.0         False     ['disc_poor_silhouette']
discovery              (n=2)      CRITICAL   0.4        50.0         True      ['disc_too_few_stations']
explainability         NORMAL     NONE       1.0        0.0          False     []
explainability         (corr=.95) WARNING    0.95       10.0         False     ['xai_high_feature_correlation']
explainability         (discord)  WARNING    0.95       10.0         False     ['xai_method_disagreement']
anomaly_intelligence   NORMAL     NONE       1.0        0.0          False     []
anomaly_intelligence   (n=0)      DEGRADED   0.75       25.0         False     ['anom_zero_consensus']
anomaly_intelligence   (supp=.05) DEGRADED   0.75       25.0         False     ['anom_no_external_validation']
ebsve                  NORMAL     NONE       1.0        0.0          False     []
ebsve                  (missing)  CRITICAL   0.4        50.0         True      ['ebsve_missing_artifact']
ebsve                  (n=0)      FATAL      0.0        80.0         True      ['ebsve_empty_claim_pack']
decision_support       NORMAL     NONE       1.0        0.0          False     []
decision_support       (thin app) DEGRADED   0.75       25.0         False     ['dss_missing_applicability']
decision_support       (weak ev.) CRITICAL   0.4        50.0         True      ['dss_low_evidence']
framework_validation   NORMAL     NONE       1.0        0.0          False     []
framework_validation   (fail)     CRITICAL   0.4        50.0         True      ['integ_contract_failure_unmapped']
```

Distinct field-set shapes across all 18 cases: **1**. Confidence multiplier and
uncertainty contribution scale monotonically and identically with severity
regardless of engine. `blocking_status` is `True` exactly at CRITICAL/FATAL,
`False` below — consistent everywhere.

**B. Real pipeline run, clean case** — Stage 6 (`n_stations=6`, `silhouette=0.32`)
and full Stage 9/10 on the real Visakhapatnam data: `discovery`, `anomaly_intelligence`,
`framework_validation` all report `NONE` (correctly — nothing is actually wrong).

**C. Real pipeline run, genuine finding** — Stage 8 on real data found
`max_abs_driver_corr = 0.9135` (two dominant drivers, real correlation, not
fabricated) against the 0.90 threshold → `xai_high_feature_correlation` fires
`WARNING`, confidence multiplier 0.95, uncertainty +10, correctly appears in the
uncertainty ledger's `explainability` budget as a `SYSTEMATIC` component.

**D. Real pipeline run, critical cascade** — with a deliberately incomplete Phase 7
evidence set (missing `stage13_*` artifacts), the cascade fired exactly as designed:
`ebsve` → `CRITICAL` (`ebsve_missing_artifact`), `decision_support` → `CRITICAL`
(`dss_low_evidence` + `dss_missing_applicability`), and the ledger's `policy` and
every `scientific_claim` budget picked up the corresponding `SYSTEMATIC`
components (mean claim caution rose from 67.0 to 79.3 in that run, correctly
reflecting the added doubt) — while `discovery`/`explainability`/`anomaly_intelligence`
remained unaffected, since the fault was isolated to Phase 7 artifacts.

## 5. Bugs found and fixed during integration

1. **`external_support_missing_or_low` false-positive on sequencing.** The
   detector fired "missing" whenever `anomaly_external_support_frac` was absent
   from the bundle — but Stage 9 runs *before* Stage 10 computes that value, so
   Stage 9's own local check would have permanently misreported a real DEGRADED
   finding every run, regardless of what Stage 10 later found. Fixed to
   distinguish "key absent" (soft-skip, consistent with every other detector)
   from "key present but null" (a genuine finding). ([`cieml/failure/detect.py`](../../cieml/failure/detect.py))
2. **EBSVE crashed instead of reporting `ebsve_empty_claim_pack`.** The catalog
   declares this as a FATAL, gracefully-reported mode, but `load_claim_pack`
   raising `ValueError`/`FileNotFoundError` was unhandled — an empty or
   unresolvable claim pack crashed `run_evidence_engine` outright. Fixed to
   catch both and return a structured `ABORTED`/FATAL result instead.
   ([`cieml/evidence/engine.py`](../../cieml/evidence/engine.py))
3. **`integ_contract_failure_unmapped` was unreachable.** `detect.py`'s own
   comment listed it alongside two other flag-based detections, but the code's
   `if d in {...}` set only included the other two — this mode could never fire.
   Fixed (one-line set addition).

## 6. What is intentionally out of scope

Per the freeze rules, no detection thresholds, severity assignments, or
confidence/uncertainty magnitude tables were tuned or added beyond what already
existed in `configs/failure/catalog.yaml` — only wiring and the two bugs above.
