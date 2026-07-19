# Failure taxonomy

Failures are typed so detectors, recovery, and messaging stay comparable across engines.

## Primary classes

| Class ID | Name | Meaning | Typical action |
|----------|------|---------|----------------|
| `F-INPUT` | Input insufficiency | Too little / wrong structure of data for the method | Degrade or abort |
| `F-ASSUMP` | Assumption violation | Declared operating assumption false in this campaign | Warn + reduce confidence |
| `F-METHOD` | Method instability | Algorithm/index/model unstable under stress | Degrade; prefer fallback method |
| `F-EVID` | Evidence gap | Required corroboration missing (external, spatial, multi-method) | Lower pillar / environmental confidence |
| `F-CONFLICT` | Internal conflict | Engines or detectors disagree beyond tolerance | Warn; do not average away |
| `F-XFER` | Transfer risk | Result not safe outside applicability domain | Suppress recommendation / flag claim |
| `F-INTEG` | Integrity / provenance | Artifact missing, contract broken, non-reproducible | Critical / fatal |
| `F-UNC` | Uncertainty saturation | Remaining uncertainty or reliability below policy floor | Cap confidence; caution |

## Secondary facets (attach to any class)

| Facet | Values |
|-------|--------|
| `scope` | observation · station · campaign · claim · framework |
| `detectability` | automatic · semi-automatic · reviewer-only |
| `reversibility` | recoverable · partially_recoverable · irreversible |
| `downstream_impact` | local · cascade · campaign_blocking |

## Relationship to contract §7 Failure Conditions

Scientific Contracts already list failure conditions. SC-FMF **operationalizes** them:

1. Contract names the condition (scientific language).
2. Catalog assigns `mode_id`, class, severity, detector, recovery.
3. Runtime emits `FailureModeHit` when the detector fires.
4. Framework Validation checks that every contract failure condition maps to ≥1 catalog mode.
