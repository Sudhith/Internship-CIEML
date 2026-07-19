# Statistical Intelligence Engine

```yaml
contract_id: SC-STAT
engine: Statistical Intelligence Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_04', 'stage_05']
```

## 1. Scientific Purpose

Construct scientifically interpretable features and **select statistical methods appropriate to the data’s assumptions**, producing a retained information set suitable for discovery without pretending all variables are unique or all methods are interchangeable.

**Problem solved:** Predetermined PCA/clustering stacks applied regardless of factorability, collinearity, or sample size.

## 2. Scientific Question

**Primary:** Which features carry non-redundant environmental information, and which analyses are statistically justified for this matrix?

**Secondary:** Where do classical assumptions fail, and what alternative methods are recommended?

## 3. Inputs

**Required**
- QA-aware observations (preferred annotated)
- Domain guidance for feature families / indices (optional formulas)

**Optional**
- Manual retain/drop overrides (must be logged)
- Target labels (only if a supervised path is explicitly enabled)

**Metadata**
- Station, date keys for aggregation

**External context**
- None required

## 4. Outputs

**Primary**
- Station-day (or declared analysis unit) feature matrix
- Feature decisions (retain/remove/reason)
- Method-selection log (why PCA / alternatives / non-parametric choices)

**Derived**
- VIF / MI / correlation / factorability diagnostics
- PCA or alternative embedding when selected

**Confidence / uncertainty**
- Diagnostics completeness
- Stability of retention under documented sensitivity options

**Intermediate artifacts**
- Descriptive stats; diagnostic figures

## 5. Assumptions

- Aggregation unit (e.g. station-day) matches the scientific question.
- Sufficient observations relative to feature dimension for the chosen methods.
- Redundancy rules are informational, not claims of process irrelevance.

## 6. Scientific Guarantees

- Method choices are logged with the diagnostics that justified them.
- Removed features carry an explicit reason code.
- **Does not guarantee** a unique “true” feature set — only a documented, reproducible retention policy.
- Will not silently run assumption-violating procedures without a warning in the method log (target state for Phase F).

## 7. Failure Conditions

- Analysis unit count below configured minimum
- All candidate features fail variance/missing filters
- Factorability / collinearity diagnostics cannot be computed
- User override removes all physically required domain core groups

## 8. Applicability

**Valid for:** multiparameter aquatic campaigns across listed domains.

**Limited for:** extremely short campaigns or single-variable series (discovery may be out of scope).

## 9. Dependencies

**Upstream:** Ingestion; QA; Physical Knowledge (recommended before interpreting indices).

**Downstream:** Discovery; Explainability; Anomaly Intelligence; EBSVE (redundancy / information claims).

## 10. Verification Tests

1. Reproduce VIF/MI/retention table from the feature matrix alone.
2. On a highly collinear synthetic set, assert redundancy removal triggers.
3. Force a failed normality/KMO condition and confirm method log recommends the contracted alternative path (Phase F).
4. Independent researcher regenerates station-day means from annotated observations.

## 11. Reviewer Checklist

- [ ] Aggregation unit defined
- [ ] Method-selection log present
- [ ] Every removal has a reason code
- [ ] Diagnostics exported
- [ ] Assumptions flagged when violated
