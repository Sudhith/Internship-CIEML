# Domain Configuration Layer

```yaml
contract_id: SC-DCL
engine: Domain Configuration Layer
version: "1.0.0"
status: implemented
implements_stages: ['config constants (legacy)']
```

## 1. Scientific Purpose

Provide a machine-readable **domain knowledge profile** so analytical engines remain identical across aquatic environments while scientific priors (limits, relationships, vocabularies, QA knobs) stay explicit, versioned, and reviewable.

**Problem solved:** Preventing domain science from being silently hardcoded inside algorithms.

## 2. Scientific Question

**Primary:** What domain-specific scientific priors and operating parameters apply to this analysis, and are they complete enough to run the pipeline?

**Secondary:** Which relationships, ranges, and vocabularies are in-scope for the declared domain (coastal, river, lake, …)?

## 3. Inputs

**Required**
- Domain profile identifier (e.g. `coastal`)
- Profile document conforming to domain schema (parameters, physical limits, relationships, QA parameters, anomaly priors, sensor packs, applicability notes, regime/process vocabularies)

**Optional**
- Campaign overrides that *reference* domain keys (never silent replacement of physical laws)
- Literature citation metadata for relationships and bands

**Metadata**
- Profile version, schema version, author, last review date

**External context**
- None required (knowledge is declarative)

## 4. Outputs

**Primary**
- Validated `DomainProfile` object consumed by all engines

**Derived**
- Enabled physical relationships for available variables
- Enabled QA check parameter sets
- Process / regime family vocabulary

**Confidence / uncertainty**
- Profile completeness score (fraction of required schema keys present)
- Staleness / review-age flag

**Intermediate artifacts**
- Schema validation report
- Diff vs previous profile version (when available)

## 5. Assumptions

- The chosen domain is appropriate for the monitoring design.
- Literature bands and relationships are screening priors, not site truth.
- Profile authors did not encode campaign *results* as domain *laws*.
- Units in the profile match the ingestion canonical unit system.

## 6. Scientific Guarantees

- Engines receive priors only through the loaded profile (no hidden alternate constants once Phase B is complete).
- Invalid or incomplete profiles fail validation before analysis proceeds.
- Profile contents are inspectable and versioned.
- **Does not guarantee** that priors are correct for every site — only that they are explicit.

## 7. Failure Conditions

- Missing required schema sections
- Contradictory relationship definitions (same pair, opposite expected signs without domain qualifier)
- Empty parameter set for a domain that claims multiparameter monitoring
- Campaign override attempting to invent undocumented variables without synonym map

## 8. Applicability

**Valid for:** coastal, river, lake, estuary, harbour, reservoir, aquaculture (each via its own profile).

**Not valid as:** a substitute for campaign metadata (stations, paths) or as a place to store case-study conclusions.

## 9. Dependencies

**Upstream:** none (root configuration engine).

**Downstream:** all other engines SHOULD read domain priors from this layer once implemented.

## 10. Verification Tests

1. Load profile; assert schema validation passes.
2. Remove a required key; assert load fails.
3. Confirm Stage QA / physics engines resolve bands and pairs from the profile, not from leftover hardcoded duplicates (post–Phase B).
4. Independently review cited relationships against listed references.

## 11. Reviewer Checklist

- [ ] Schema documented and versioned
- [ ] Priors cited or explicitly marked “screening heuristic”
- [ ] No campaign conclusions stored in domain profile
- [ ] Completeness / validation report produced
- [ ] Engines documented as consumers of this profile
