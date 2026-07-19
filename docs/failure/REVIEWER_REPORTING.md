# Reviewer reporting

## Failure dossier (campaign-level)

Artifact: `outputs/phaseN/stage*_failure_dossier.json` (+ optional markdown/figure)

| Section | Content |
|---------|---------|
| Summary | Counts by severity; engines with CRITICAL+ |
| Hits | Full `FailureModeHit` list with evidence |
| Confidence impact | Before/after multipliers per engine/claim |
| Suppressions | Recommendations / pillars / claims gated |
| Contract coverage | Contract §7 conditions ↔ catalog modes (gaps flagged) |
| Residual unknowns | Modes that are reviewer-only (not auto-detected) |

## Reviewer checklist (always)

- [ ] Every CRITICAL+ hit has a human-readable message and artifact pointer
- [ ] No DEFINITIVE claim classification when a hard-dependent engine is FATAL
- [ ] DSS recommendations absent when `dss_low_evidence` fired
- [ ] Failure dossier committed alongside EBSVE closure for the campaign
- [ ] No silent fallback (catalog declares every method switch)

## Figure suggestion

Heatmap: engines × severity counts; bar: confidence multipliers by claim.
