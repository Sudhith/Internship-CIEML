# User messaging

Every WARNING+ hit emits a structured message. Tone: scientific, actionable, non-alarmist.

## Message schema

```yaml
message_id: disc_poor_silhouette.v1
severity: DEGRADED
audience: [analyst, reviewer]
title: "Regime structure is weakly separated"
body: >
  Selected clustering silhouette is below the warn threshold. Treat regime labels
  as exploratory; do not base monitoring policy solely on this partition.
what_we_did: "Confidence reduced; structure_call capped at provisional/fragile."
what_you_can_do:
  - "Inspect Stage 6 selection trace and Stage 14 robustness battery."
  - "Increase spatial/temporal coverage before claiming stable regimes."
related_artifacts:
  - stage06_regime_discovery_report.json
  - stage14_sensitivity_results.csv
```

## Rules

- No station nicknames as the *cause* (“Rushikonda failed”) — use roles / metrics.
- One message per `mode_id` per run (dedupe).
- CRITICAL/FATAL messages must state **what was suppressed**.
- Messages are written to `stage*_failure_messages.json` and summarized in Phase reports.
