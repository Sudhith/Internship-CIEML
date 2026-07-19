# Recovery strategies & confidence reduction

## Strategy vocabulary

| Strategy ID | Meaning |
|-------------|---------|
| `log_only` | Record hit; no score change beyond severity default |
| `reduce_confidence` | Apply severity multiplier (or mode-specific delta) |
| `prefer_fallback_method` | Re-run or select declared alternate method |
| `narrow_claim` | Keep result but restrict applicability text |
| `suppress_recommendation` | DSS: do not emit actionable recommendation |
| `suppress_claim_pillar` | EBSVE: mark pillar untrusted / score cap |
| `abort_engine` | Stop engine; dependents see FATAL upstream |
| `require_reviewer` | Force human review flag before DEFINITIVE |

## Fallback methods (examples)

| Engine | Primary | Fallback |
|--------|---------|----------|
| Discovery | Selected algo/K from Stage 6 | Report “structure unsupported”; skip semantic labels |
| Stats | Parametric test | Nonparametric / permutation (Phase F already selects) |
| Anomaly | Multi-method consensus | Single-method exploratory catalog with WARNING |
| External validation | Open-Meteo cross-corr | Mark F-EVID; do not invent support |
| Decision Support | Full recommendation pack | Diagnostic-only brief |

Fallbacks must be **declared in the catalog**. Silent method switching is forbidden.

## Confidence reduction rules

1. Start from engine/claim confidence \(C\).
2. Collect all `FailureModeHit` severities for that scope.
3. `confidence_multiplier = min(policy[severity])` (default compose).
4. `C' = clip(C * confidence_multiplier, 0, 100)`.
5. Mode may set `confidence_cap` (hard ceiling) or `confidence_floor_delta` (subtract points).
6. Never encode failure as `U = 100 - C` — failure reduces **confidence** and may add
   MMU/REL components separately under the Uncertainty Model.

## Ordering

```text
detect → classify severity → choose recovery → apply confidence rule →
emit user message → attach reviewer note → gate downstream
```
