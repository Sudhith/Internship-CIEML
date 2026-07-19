# Evidence-Based Scientific Validation Engine (EBSVE)

```yaml
contract_id: SC-EBSVE
engine: Evidence-Based Scientific Validation Engine (EBSVE)
version: "1.0.0"
status: implemented
implements_stages: ['stage_14', 'cieml.evidence']
```

## 1. Scientific Purpose

Serve as the **scientific court of audit** for CIEML: every major claim must be evaluated under four independent evidence pillars with continuous confidence, graded classification, traceable evidence items, and explicit limitations — without hardcoded case verdicts.

**Problem solved:** Narrative conclusions that cannot be traced to computed evidence.

## 2. Scientific Question

**Primary:** Which scientific claims are defensible for this campaign, at what confidence, and under what limitations?

**Secondary:** Where is evidence incomplete, conflicting, or only exploratory?

## 3. Inputs

**Required**
- Claim pack (`configs/claims/*.yaml`; Visakhapatnam default: `coastal_monitoring_v1`)
- Evidence bundle of upstream artifacts (via loaders / artifact contract)
- Optional robustness / sensitivity battery results

**Optional**
- External validation summaries; interpretation tables; decision briefs

**Metadata**
- Pillar weights; classification thresholds (framework config)

**External context**
- As referenced by claim-specific validators (e.g. meteo support fractions)

## 4. Outputs

**Primary**
- Per-claim assessment: four pillars, overall confidence, classification, reasoning, limitations, future tests

**Derived**
- Campaign-level closure summary
- Reviewer tables / figures

**Confidence / uncertainty**
- Continuous pillar scores (0–100 scale as implemented)
- Evidence strength / maturity labels
- Explicit weaknesses per pillar

**Intermediate artifacts**
- Evidence item traces (name, value, source path, interpretation)
- Robustness sensitivity tables when Stage-14-style battery is run

## 5. Assumptions

- Upstream artifacts named in evidence items exist and match the artifact contract.
- Pillars are scored independently (no score reuse across pillars).
- Classification thresholds are framework-level, not silently case-edited.
- Domain-specific validator logic is configuration/plugin content, not a change to pillar algebra.

## 6. Scientific Guarantees

- **No major claim classification without four pillar evaluations.**
- Every pillar score cites `EvidenceItem` sources a reviewer can open.
- **No hardcoded Visakhapatnam (or any site) verdict inside the shared scoring ABC.**
- Robustness battery, when run, parametrizes off discovered algorithm/K rather than assuming a fixed solution.
- **Does not guarantee** that “Definitive” claims are universally true outside the applicability domain.

## 7. Failure Conditions

- Claim pack empty
- Evidence bundle missing mandatory artifacts for a claim
- Pillar evaluator raises / returns non-finite scores
- Classification thresholds misconfigured

## 8. Applicability

**Valid for:** any domain/campaign that produces the required upstream artifacts and a claim pack.

**Phase J:** Claim list is pack configuration; pillar ABC (`HypothesisValidator`) is not rewritten per campaign.

**Not valid for:** replacing physical fieldwork or regulatory compliance certification.

## 9. Dependencies

**Upstream:** Essentially all scientific engines (trust, physics, stats, discovery, XAI, anomalies, context, labeling, DSS inputs as relevant per claim).

**Downstream:** Applicability Domain Engine; Knowledge Base; manuscript/reviewer communication; Decision Support may consume claim confidence.

## 10. Verification Tests

1. Remove one upstream artifact; assert affected claim’s pillar weakens or fails with explicit missing-source weakness.
2. Re-run scoring twice; assert deterministic scores given fixed inputs.
3. Independent reviewer follows each EvidenceItem.source to the file and recomputes the cited value.
4. Confirm pillar scores are not copied across pillars in serialized JSON.

## 11. Reviewer Checklist

- [ ] Four pillars present for every claim
- [ ] Evidence items have source paths
- [ ] Classification uses framework tiers
- [ ] Limitations and future validation listed
- [ ] Shared scorer (not per-claim ad hoc pass/fail) used
- [ ] Domain plugins do not bypass ABC
