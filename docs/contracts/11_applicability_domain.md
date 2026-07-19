# Applicability Domain Engine

```yaml
contract_id: SC-APP
engine: Applicability Domain Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_13', 'stage_14', 'cieml.applicability']
```

## 1. Scientific Purpose

Explicitly determine **where each claim and recommendation may be trusted**, and where it must not be applied — turning transfer from an afterthought into a first-class scientific product.

**Problem solved:** Implied universality of campaign findings.

## 2. Scientific Question

**Primary:** Where can this conclusion be trusted?

**Secondary:** Which habitat, design, and forcing conditions invalidate transfer?

## 3. Inputs

**Required**
- Claim assessments (EBSVE)
- Recommendation set (Decision Support)
- Domain profile applicability notes
- Campaign design descriptors (habitat types present, n, duration, sensor pack)

**Optional**
- Environmental condition tags (high turbidity, low salinity, high rainfall, …) observed in-campaign

**Metadata**
- Geographic region (descriptive only)

**External context**
- None required beyond what claims already used

## 4. Outputs

**Primary**
- Per-claim and per-recommendation applicability records: `applies_to`, `does_not_apply_to`, `transfer_rule`

**Derived**
- Campaign applicability summary matrix

**Confidence / uncertainty**
- Transfer confidence (stricter than in-campaign claim confidence)
- Coverage gaps (conditions never observed)

**Intermediate artifacts**
- Machine-readable `applicability.json`; human brief

## 5. Assumptions

- In-campaign support does not equal out-of-domain support.
- Unobserved conditions default to “unknown / do not transfer” rather than “safe.”
- Domain profile notes are starting priors, refined by campaign evidence.

## 6. Scientific Guarantees

- Every Definitive/Supported claim receives an applicability record.
- **Unknown transfer is stated explicitly** rather than implied safe.
- Transfer rules prefer re-run CIEML over copying cutoffs.
- **Does not guarantee** correctness in new domains without new evidence.

## 7. Failure Conditions

- Missing claim assessments
- Empty domain applicability notes and no campaign habitat tags
- Recommendations present without claim linkage

## 8. Applicability

This engine’s *own* applicability: any CIEML campaign. The habitats it *describes* include coastal, river, lake, estuary, harbour, reservoir, aquaculture, and conditioning tags (turbidity, salinity, rainfall, limited sampling, …).

## 9. Dependencies

**Upstream:** EBSVE; Decision Support; Domain Configuration; campaign descriptors.

**Downstream:** Knowledge Base; external users; manuscript limitations sections.

## 10. Verification Tests

1. For a claim, remove habitat tags; assert `does_not_apply_to` gains “unspecified habitat transfer.”
2. Confirm numeric thresholds never appear as transferable without a re-run rule.
3. Independent reviewer checks each `applies_to` entry against actual campaign design.
4. Serialize applicability JSON and reparse schema validation.

## 11. Reviewer Checklist

- [ ] Per-claim applicability present
- [ ] Per-recommendation applicability present
- [ ] Unknown ≠ allowed
- [ ] Transfer rule prefers re-analysis
- [ ] No case conclusions stored as universal domain law
