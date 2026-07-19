# Severity levels

Ordered from least to most severe. Higher severity **overrides** lower for the
engine `status` field; multiple hits accumulate as a list.

| Level | Engine status | Scientific meaning | Default pipeline effect |
|-------|---------------|--------------------|-------------------------|
| **INFO** | `ok` | Notable condition; trust unchanged | Log only |
| **WARNING** | `warning` | Elevated risk; result still usable with caveat | User message; modest confidence reduction |
| **DEGRADED** | `degraded` | Conclusion weakened; must not be treated as full strength | Apply `confidence_multiplier`; prefer fallback if defined |
| **CRITICAL** | `failed` | Engine conclusion **not trustworthy** for primary claim use | Suppress claim pillar / recommendation; keep diagnostics |
| **FATAL** | `aborted` | Cannot proceed scientifically or contractually | Stop downstream consumers that declare hard dependency |

## Mapping examples (from the design brief)

| Situation | Severity |
|-----------|----------|
| Discovery: poor silhouette but regimes still selected | DEGRADED |
| Discovery: too few stations for LOSO/spatial claims | DEGRADED → CRITICAL if n below hard floor |
| Explainability: highly correlated drivers | WARNING |
| Anomaly: no external validation available | DEGRADED (environmental pillar / F-EVID) |
| Decision Support: low EBSVE evidence | CRITICAL → suppress recommendation |
| Missing mandatory upstream artifact | FATAL for dependent engine |

## Policy constants (`configs/framework.yaml` → `failure_modes`)

```yaml
confidence_multipliers:
  INFO: 1.00
  WARNING: 0.95
  DEGRADED: 0.75
  CRITICAL: 0.40
  FATAL: 0.00
suppress_recommendations_at: CRITICAL
abort_hard_dependents_at: FATAL
```

Multipliers **compose** across hits by taking the **minimum** (most severe), not the product,
unless a mode declares `compose: multiply`. This avoids accidental double-counting when
correlated detectors fire together (aligns with uncertainty correlation policy).
