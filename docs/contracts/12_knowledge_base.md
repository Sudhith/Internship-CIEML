# Knowledge Base

```yaml
contract_id: SC-KB
engine: Knowledge Base
version: "1.0.0"
status: implemented
implements_stages: ['stage_14', 'cieml.knowledge']
```

## 1. Scientific Purpose

Maintain an **append-only scientific memory** across campaigns — validated relationships, anomaly patterns, ranges, model successes/failures, uncertainty statistics — so CIEML improves as a platform without silently rewriting past case studies.

**Problem solved:** Every campaign starting from zero institutional memory, and conversely, silent mutation of priors.

## 2. Scientific Question

**Primary:** What reusable scientific knowledge has CIEML accumulated, and at what evidence grade?

**Secondary:** Which priors have repeatedly failed and should be demoted?

## 3. Inputs

**Required**
- Versioned campaign outputs + EBSVE assessments + applicability records

**Optional**
- Curator acceptance / rejection of candidate KB entries
- Literature confirmations

**Metadata**
- Campaign ID, domain ID, timestamps, framework version

**External context**
- Optional published studies linked by curator

## 4. Outputs

**Primary**
- KB entries with grade (e.g. candidate / supported / contested / retired)

**Derived**
- Suggested domain-profile updates (never auto-applied without review)
- Failure catalogs (methods that repeatedly underperform under stated conditions)

**Confidence / uncertainty**
- Entry-level evidence grade and number of supporting campaigns
- Conflict flags when campaigns disagree

**Intermediate artifacts**
- Proposal diffs for domain YAML; audit log

## 5. Assumptions

- Append-only for published case artifacts; KB proposals are separate from frozen `outputs/`.
- Human or policy gate required before domain profile mutation.
- Cross-campaign comparability requires shared schema versions.

## 6. Scientific Guarantees

- Historical campaign outputs are not overwritten by KB learning.
- Every KB entry cites contributing campaign artifact hashes/paths.
- Contested knowledge remains contested until adjudicated.
- **Does not guarantee** that majority votes equal physical truth.

## 7. Failure Conditions

- Schema version incompatibility across entries
- Missing provenance on a proposed entry
- Attempted silent overwrite of domain profile without audit record

## 8. Applicability

**Valid for:** multi-campaign programs across all supported aquatic domains.

**Not valid for:** auto-authorizing regulatory standards.

## 9. Dependencies

**Upstream:** EBSVE; Applicability; optionally Physical Knowledge and Anomaly outputs.

**Downstream:** Domain Configuration (via reviewed updates only); future campaigns’ priors.

## 10. Verification Tests

1. Ingest two synthetic campaigns with conflicting relationship signs; assert contested entry, not silent average.
2. Confirm frozen case `outputs/` unchanged after KB propose step.
3. Independent auditor reconstructs an entry from cited artifact paths.
4. Reject a proposal; assert domain profile file unchanged.

## 11. Reviewer Checklist

- [ ] Append-only audit log
- [ ] Provenance on every entry
- [ ] No silent domain mutation
- [ ] Conflict/contested state supported
- [ ] Separated from case-study directories
