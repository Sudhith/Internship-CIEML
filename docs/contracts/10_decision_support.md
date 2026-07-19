# Decision Support Engine

```yaml
contract_id: SC-DSS
engine: Decision Support Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_13', 'stage_14', 'cieml.decision']
```

## 1. Scientific Purpose

Translate audited scientific structure into **monitoring and management recommendations** (sensors, sampling, EWIs, budget tiers, policy rules) that always carry confidence, expected benefit, limitations, and resource needs — never as naked site folklore.

**Problem solved:** Advice detached from evidence and transfer limits.

## 2. Scientific Question

**Primary:** What monitoring decisions are justified by the evidence, and how strongly?

**Secondary:** What should be prioritized under resource constraints?

## 3. Inputs

**Required**
- Consensus drivers / sensor map (from Explainability)
- Claim confidence for relevant claims (from EBSVE) when available
- Regime/process labels or fingerprints (optional but recommended)

**Optional**
- Anomaly catalog; external support fractions; cost tables

**Metadata**
- Campaign design (number of stations — as design facts, not conclusions)

**External context**
- Policy constraints supplied by user (budget, staffing)

## 4. Outputs

**Primary**
- Recommendation set: sensor prioritization, sampling strategy, EWIs, decision rules, budget tiers

**Derived**
- Manager brief (human-readable)
- Workflow schematic artifacts

**Confidence / uncertainty**
- Per-recommendation confidence linked to driver tiers / claim classes
- Explicit “do not transfer cutoffs” statements

**Intermediate artifacts**
- Rule tables; prioritization figures

## 5. Assumptions

- Recommendations optimize monitoring design quality, not political outcomes.
- Driver importance from XAI is associative with structure, not proven causality.
- Role-based guidance (e.g. “harbour-type station”) generalizes better than named-station advice.

## 6. Scientific Guarantees

- **No recommendation is emitted without linked evidence references and limitations.**
- Numeric thresholds from one campaign are not presented as universal standards.
- Sensor priority aligns to documented driver tiers when XAI inputs exist.
- **Does not guarantee** regulatory compliance or risk elimination.

## 7. Failure Conditions

- No drivers and no claim confidences available
- Empty recommendation templates
- Contradictory inputs (e.g. all claims Exploratory, the weakest EBSVE tier) without degradation path — must emit “insufficient evidence” rather than strong advice

## 8. Applicability

**Valid for:** producing *transferable monitoring design rules* across coastal, river, lake, estuary, harbour, reservoir, aquaculture — after re-running upstream engines on local data.

**Not valid for:** copying one campaign’s numeric alert thresholds to another site without re-analysis.

## 9. Dependencies

**Upstream:** Explainability; EBSVE (recommended); Discovery/labeling; optional Anomaly/Context.

**Downstream:** Applicability Domain Engine; Knowledge Base; end users.

## 10. Verification Tests

1. Mask Dominant drivers; assert Essential sensor tier changes or confidence drops.
2. Confirm every recommendation row has limitations + evidence pointers.
3. Independent reviewer maps each EWI to a measured variable present in the campaign.
4. Search outputs for forbidden universal-threshold language; assert absent.

## 11. Reviewer Checklist

- [ ] Evidence links present
- [ ] Confidence per recommendation
- [ ] Limitations / non-transfer of cutoffs stated
- [ ] Role-based, not only site-named, guidance
- [ ] Degrades under Exploratory/insufficient claims
