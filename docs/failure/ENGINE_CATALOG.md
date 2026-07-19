# Per-engine failure catalog (index)

Authoritative machine entries live in `configs/failure/catalog.yaml`. This page is the
reviewer-facing index aligned to the design brief examples.

## Domain / Ingestion / QA / Physics

| Engine | Example modes | Severity band |
|--------|---------------|---------------|
| Domain (SC-DCL) | incomplete profile, missing required keys | FATAL |
| Ingestion (SC-ING) | empty corpus, unreadable files, schema map fail | DEGRADED–FATAL |
| QA (SC-QA) | critical range/overshoot rate high | WARNING–CRITICAL |
| Physics (SC-PHYS) | required pairs broken | DEGRADED–CRITICAL |

## Statistical / Discovery / Explain / Anomaly

| Engine | Mode | Class | Severity | Recovery |
|--------|------|-------|----------|----------|
| Discovery | too few stations | F-INPUT | DEGRADED→CRITICAL | reduce confidence; narrow spatial claims |
| Discovery | poor silhouette | F-METHOD | DEGRADED | reduce confidence |
| Discovery | high noise / unstable | F-METHOD | DEGRADED | prefer “structure unsupported” |
| Explainability | highly correlated variables | F-ASSUMP | WARNING | warn user; note driver non-identifiability |
| Explainability | method disagreement | F-CONFLICT | WARNING–DEGRADED | consensus-only reporting |
| Anomaly | no external validation | F-EVID | DEGRADED | lower environmental confidence |
| Anomaly | empty consensus | F-METHOD | DEGRADED | exploratory single-method fallback |

## EBSVE / Decision / Applicability / Uncertainty

| Engine | Mode | Severity | Recovery |
|--------|------|----------|----------|
| EBSVE | missing evidence artifact for claim | CRITICAL | pillar weakness / fail claim |
| EBSVE | pillar evaluator non-finite | FATAL | abort claim assessment |
| Decision Support | low evidence | CRITICAL | **suppress recommendation** |
| Decision Support | thin applicability | DEGRADED | diagnostic-only brief |
| Uncertainty | saturated / non-discriminative ledger | WARNING | flag SC-MMU/REL audit |
| Framework Validation | contract gap | CRITICAL (framework) | certification fail |

## Worked cascade (brief examples)

```text
n_stations = 4  →  disc_too_few_stations (DEGRADED)
                →  Discovery confidence ×0.75
                →  H4 environmental regimes cannot be DEFINITIVE
                →  DSS suppresses regime-based policy rules
```

```text
No Stage 10 support  →  anom_no_external_validation (DEGRADED)
                     →  H5 environmental pillar capped
                     →  Anomaly “reality” claim stays EXPLORATORY
```

```text
EBSVE campaign_mean_confidence low  →  dss_low_evidence (CRITICAL)
                                    →  Recommendations suppressed
                                    →  Reviewer sees diagnostic brief only
```
