# Physical Knowledge Engine

```yaml
contract_id: SC-PHYS
engine: Physical Knowledge Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_03']
```

## 1. Scientific Purpose

Test whether observed variables obey **declared physical / biogeochemical relationships** applicable to the domain, and report only relationships that were both applicable and empirically evaluated.

**Problem solved:** Statistical structure floating free of physical plausibility.

## 2. Scientific Question

**Primary:** Do the measured variables obey the known physical relationships that apply in this domain?

**Secondary:** Which expected relationships are unsupported, untestable, or violated?

## 3. Inputs

**Required**
- Observations or station-day aggregates
- Domain relationship catalog (pair, expected direction, applicable domains, tolerance, references)

**Optional**
- QA flags (to run sensitivity with/without Critical points)
- Station stratification

**Metadata**
- Units confirmed canonical

**External context**
- None required

## 4. Outputs

**Primary**
- Per-relationship evaluation table (sign, association strength, n, verdict: supported / violated / untestable)

**Derived**
- Station-wise stability of relationships
- Correlation / association matrices among evaluated variables

**Confidence / uncertainty**
- Per-pair confidence from sample size and effect stability
- Fraction of applicable pairs supported

**Intermediate artifacts**
- Pair plots / stability figures

## 5. Assumptions

- Relationships in the catalog are appropriate for the domain and variable definitions.
- Association method (e.g. Spearman) matches non-normal environmental data unless otherwise justified.
- “Untestable” (e.g. zero-inflated partner variable) is reported, not forced.

## 6. Scientific Guarantees

- **No unsupported physical relationship is reported as confirmed.**
- Only catalog relationships marked applicable to the domain and present variables are evaluated.
- Untestable pairs are explicit outcomes, not silent skips without record.
- **Does not guarantee** causal mechanism identification.

## 7. Failure Conditions

- Fewer than configured minimum applicable pairs available
- Insufficient n for any pair test
- Relationship catalog empty for domain
- Unit mismatch discovered post-ingest

## 8. Applicability

**Valid for:** all domains with a non-empty relationship catalog.

**Not valid for:** claiming pollutant source attribution from pairwise signs alone.

## 9. Dependencies

**Upstream:** Ingestion; QA (recommended); Domain Configuration.

**Downstream:** Feature engineering / Statistical Intelligence; EBSVE physical pillars; Decision Support caveats.

## 10. Verification Tests

1. On synthetic data with known positive/negative associations, assert correct support/violation calls.
2. Remove one variable; assert dependent pairs become untestable, not “supported.”
3. Independent recount of Spearman (or declared) statistics on the same table.
4. Check that each “supported” row cites catalog reference metadata.

## 11. Reviewer Checklist

- [ ] Catalog relationships cited
- [ ] Applicable-domain filters applied
- [ ] Untestable distinct from violated
- [ ] No causal overclaim in outputs
- [ ] Sensitivity to QA flags documented if offered
