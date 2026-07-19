# Universal Ingestion

```yaml
contract_id: SC-ING
engine: Universal Ingestion
version: "1.0.0"
status: partial
implements_stages: ['stage_00']
```

## 1. Scientific Purpose

Convert heterogeneous environmental monitoring files into a **canonical observation schema** without assuming vendor-specific column names, so any compliant dataset can enter the analytical path.

**Problem solved:** Brittle, one-format pipelines that cannot be reused across instruments and programs.

## 2. Scientific Question

**Primary:** Can the raw monitoring materials be standardized into a scientifically usable observation table with traceable provenance?

**Secondary:** What variables, units, stations, timestamps, and sampling frequencies were actually present?

## 3. Inputs

**Required**
- Raw data location (from campaign profile)
- Selected adapter (e.g. vendor export, generic CSV/Parquet)
- Domain synonym / variable dictionary (from Domain Configuration)

**Optional**
- Station coordinate table
- Manual column map overrides
- Timezone

**Metadata**
- File inventory, encoding, vendor tags

**External context**
- None required at ingest

## 4. Outputs

**Primary**
- Canonical observations (station, timestamp, variable, value, unit, source_file, …)
- File / record inventory

**Derived**
- Detected sampling frequency
- Parameter groups present vs domain-expected
- Station-day coverage skeleton

**Confidence / uncertainty**
- Parse success rate per file
- Unmapped column rate
- Unit-inference confidence

**Intermediate artifacts**
- Per-file summaries; rejection/skip logs

## 5. Assumptions

- Files are readable with the declared adapter.
- Station identifiers are stable within the campaign (or aliasable).
- Timestamps are interpretable after timezone policy.
- Numeric fields are not irreparably corrupted beyond parse.

## 6. Scientific Guarantees

- Every retained row traces to a source file (and row identity where available).
- Unmapped or unit-ambiguous fields are flagged, not silently coerced into wrong science variables.
- No scientific QA verdict is implied by successful ingest alone.
- **Does not guarantee** physical plausibility or sensor integrity.

## 7. Failure Conditions

- Zero successfully parsed observations
- No station or time key recoverable
- Required core variable group entirely absent when domain marks it mandatory
- Adapter mismatch (wrong parser for format)

## 8. Applicability

**Valid for:** all aquatic domains once an adapter + synonym map exist.

**Limited when:** proprietary binary formats lack an adapter; sparse metadata prevents station/time binding.

## 9. Dependencies

**Upstream:** Domain Configuration (synonyms, expected parameters); Campaign metadata (paths).

**Downstream:** Scientific QA; all later engines consume canonical observations or aggregates derived from them.

## 10. Verification Tests

1. Round-trip a known fixture file through the adapter; compare row counts and key columns.
2. Rename columns via synonyms; assert identical canonical variables.
3. Inject a corrupt file; assert inventory records failure without poisoning the full table.
4. Independent researcher reproduces inventory statistics from raw files alone.

## 11. Reviewer Checklist

- [ ] Canonical schema documented
- [ ] Provenance fields present
- [ ] Unmapped columns reported
- [ ] Adapter choice explicit in campaign config
- [ ] Empty/failed ingest triggers failure condition
