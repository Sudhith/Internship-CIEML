# Scientific QA Engine

```yaml
contract_id: SC-QA
engine: Scientific QA Engine
version: "1.0.0"
status: partial
implements_stages: ['stage_01', 'stage_02']
```

## 1. Scientific Purpose

Evaluate whether observations are **scientifically trustworthy enough** for inference by applying a configurable battery of integrity checks, producing auditable flags rather than silent deletions.

**Problem solved:** Treating raw sensor streams as truth without transparent quality accountability.

## 2. Scientific Question

**Primary:** Can these observations be trusted for downstream environmental inference, and where are they compromised?

**Secondary:** Which failure modes dominate (missingness, range/overshoot, flatline, drift, duplicates, gaps)?

## 3. Inputs

**Required**
- Canonical observations
- Domain plausibility bands and QA check parameters

**Optional**
- Vendor fault codes / calibration notes
- Known maintenance windows (as metadata, not hidden exclusions)

**Metadata**
- Station, instrument IDs, cast IDs

**External context**
- Optional independent reference sensors (if available)

## 4. Outputs

**Primary**
- QA issue tables with severity and machine-readable reason codes
- Annotated observations (flag columns) and/or file-level QA summaries

**Derived**
- Completeness matrices; cross-station pattern summaries
- Sensitivity notes (impact of including flagged data)

**Confidence / uncertainty**
- Critical / suspicious / acceptable rates
- Per-check pass fractions

**Intermediate artifacts**
- Heatmaps and example flagged series figures

## 5. Assumptions

- Domain bands are screening envelopes, not regulatory limits.
- Flag policy is “document first”; exclusion is a separate, explicit decision.
- Sampling design is known well enough to interpret gaps.
- Magnitude-overshoot and flatline definitions match domain parameters.

## 6. Scientific Guarantees

- Every raised issue cites check ID, parameters used, and affected scope.
- Range/overshoot checks use domain-configured bands and thresholds (post–Phase D registry).
- No observation is deleted solely by this engine without an explicit exclusion policy artifact.
- **Does not guarantee** that unflagged data are error-free.

## 7. Failure Conditions

- Missing domain bands for variables marked core
- Critical issue rate exceeding configured campaign abort threshold (if set)
- Inability to evaluate any configured check due to missing columns
- Contradictory unit declarations unresolved at ingest

## 8. Applicability

**Valid for:** coastal, river, lake, estuary, harbour, reservoir, aquaculture — with domain-specific check sets.

**Weaker when:** single-parameter campaigns (limited cross-checks) or undocumented sensors.

## 9. Dependencies

**Upstream:** Universal Ingestion (success); Domain Configuration.

**Downstream:** Physical Knowledge, Statistical Intelligence, Discovery, Anomaly Intelligence, EBSVE (data-trust claims).

## 10. Verification Tests

1. Synthetic series with known flatlines, spikes, and overshoots must be flagged with expected check IDs.
2. Disable a check in domain config; assert it no longer fires.
3. Compare completeness rates to independent recount from canonical table.
4. Reviewer audits a random sample of Critical flags against raw files.

## 11. Reviewer Checklist

- [ ] Check registry IDs documented
- [ ] Parameters sourced from domain profile
- [ ] Flag-only vs exclusion policy stated
- [ ] Severity definitions published
- [ ] Figures/tables allow audit of Critical cases
