# Automatic detection

## Detector contract

```text
Detector
  mode_id: str
  engine_id: str
  inputs: logical artifact keys | live metrics
  predicate: (bundle) -> bool | float
  threshold: optional numeric gate
  evidence_builder: (bundle) -> EvidenceItem-like dict
```

Detectors must be:

1. **Deterministic** given fixed artifacts (Framework Validation checks this).
2. **Side-effect free** (no writes).
3. **Explicit** about missing inputs → either skip with INFO `detector_skipped_missing_input`
   or fire DEGRADED `required_input_absent` (declared per mode).

## Hook points

| When | Where |
|------|-------|
| After each stage write | Stage runner calls `cieml.failure.assess_engine(engine_id, bundle)` |
| Before EBSVE claim scoring | Inject failure hits into evidence bundle |
| Before Decision Support emit | Gate recommendations on CRITICAL+ |
| Stage 14 / uncertainty ledger | Attach failure summary to campaign packet |

## Engine examples (design brief → detector sketches)

### Discovery Engine (`SC-DISC`)
| mode_id | Trigger |
|---------|---------|
| `disc_too_few_stations` | `n_stations < min_stations` (domain/campaign) |
| `disc_poor_silhouette` | selected silhouette < `silhouette_warn` |
| `disc_high_noise` | noise stress ARI collapse or stability < floor |
| `disc_unstable_k` | bootstrap / LOSO ARI < floor |

→ Default: DEGRADED + confidence reduction; CRITICAL if below hard floor.

### Explainability Engine (`SC-XAI`)
| mode_id | Trigger |
|---------|---------|
| `xai_high_feature_correlation` | max \|ρ\| among top drivers > threshold |
| `xai_method_disagreement` | SHAP vs permutation rank discord |
| `xai_low_model_performance` | CV score below floor |

→ WARNING (correlated vars); DEGRADED if model unfit.

### Anomaly Engine (`SC-ANOM`)
| mode_id | Trigger |
|---------|---------|
| `anom_no_external_validation` | Stage 10 support frac missing or N/A |
| `anom_zero_consensus` | consensus set empty |
| `anom_contamination_unstable` | grid search agreement flat |

→ Lower environmental confidence (DEGRADED / F-EVID).

### Decision Support (`SC-DSS`)
| mode_id | Trigger |
|---------|---------|
| `dss_low_evidence` | upstream claim class EXPLORATORY or confidence < floor |
| `dss_missing_applicability` | applicability domain empty |
| `dss_blind_spot_rules` | failure-mode keywords uncovered (H6 physical) |

→ CRITICAL → **suppress recommendation** (still emit diagnostic brief).
