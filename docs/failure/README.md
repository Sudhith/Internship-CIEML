# Scientific Failure Mode Framework (SC-FMF)

**Role:** Every CIEML engine must state when its scientific conclusions must **not**
be trusted — and what the pipeline does instead of silently succeeding.

This framework is complementary to:

| Layer | Question |
|-------|----------|
| [Scientific Contracts](../contracts/README.md) | What does the engine promise? |
| [Uncertainty Model](../uncertainty/README.md) | How much residual doubt remains when it *does* run? |
| **Failure Mode Framework (this)** | When must outputs be marked untrusted / degraded / suppressed? |
| [Framework Validation](../validation/README.md) | Does CIEML *itself* meet its architecture promises? |

**Principle:** Success is not the default. Absence of a detected failure is not proof
of correctness — but a *detected* failure mode must reduce confidence, warn, fall back,
or abort according to severity.

---

## Documents

| Doc | Content |
|-----|---------|
| [TAXONOMY.md](TAXONOMY.md) | Failure classes (input, assumption, method, evidence, transfer, integrity) |
| [SEVERITY.md](SEVERITY.md) | INFO / WARNING / DEGRADED / CRITICAL / FATAL |
| [DETECTION.md](DETECTION.md) | Automatic detectors + engine hooks |
| [RECOVERY.md](RECOVERY.md) | Recovery strategies, fallbacks, confidence reduction rules |
| [MESSAGING.md](MESSAGING.md) | User-facing message contracts |
| [REVIEWER_REPORTING.md](REVIEWER_REPORTING.md) | Reviewer failure dossier |
| [ENGINE_CATALOG.md](ENGINE_CATALOG.md) | Per-engine failure modes (human index) |

Machine catalog: `configs/failure/catalog.yaml`  
Contract: [SC-FMF](../contracts/15_failure_modes.md)  
Runtime: `cieml/failure/`

---

## Packet emitted by every engine

```text
FailureAssessment
  engine_id
  status: ok | warning | degraded | failed | aborted
  modes[]: FailureModeHit
    mode_id, severity, evidence, message, recovery_applied, confidence_delta
  confidence_multiplier   # 0–1 applied to engine confidence
  suppress_downstream     # bool — Decision Support / claim closure gates
  user_messages[]
  reviewer_notes[]
```

Engines that omit a FailureAssessment are treated as **contract-incomplete** under
SC-FMF (framework validation flags this).
