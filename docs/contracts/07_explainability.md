# Explainability Engine

```yaml
contract_id: SC-XAI
engine: Explainability Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_08']
```

## 1. Scientific Purpose

Identify **which measured/derived features drive membership in discovered structure**, using multiple explanation methods and reporting only drivers with cross-method support.

**Problem solved:** Single-method importance plots treated as causal environmental truth.

## 2. Scientific Question

**Primary:** What features consistently explain discovered regime structure?

**Secondary:** Where do explanation methods disagree, and how uncertain are driver ranks?

## 3. Inputs

**Required**
- Labeled analysis units (from Discovery)
- Same feature matrix used for discovery (or documented aligned subset)

**Optional**
- Model family list; background samples for SHAP-like methods

**Metadata**
- Seeds; CV folds

**External context**
- None required

## 4. Outputs

**Primary**
- Driver ranking table with method-specific scores
- Consensus driver set (multi-method agreement rule)

**Derived**
- Dependence / PDP / ALE plots for consensus drivers
- Model predictive performance for regime classification (diagnostic, not the scientific endpoint)

**Confidence / uncertainty**
- Cross-method agreement score
- Rank stability across CV folds / seeds
- Explicit “disputed drivers” list

**Intermediate artifacts**
- Per-method importance tables; figures

## 5. Assumptions

- Regime labels are inputs under test, not ground-truth ecology.
- Correlated features may share attribution; redundancy was addressed upstream but residual correlation can remain.
- Predictive accuracy is a diagnostic of separability, not proof of mechanism.

## 6. Scientific Guarantees

- **No driver is reported as dominant solely from one method** when consensus mode is enabled (Phase H target; partial today).
- Method disagreement is exported, not hidden.
- **Does not guarantee** causal physical mechanisms or management attribution.

## 7. Failure Conditions

- Labels not separable (models at chance; explanations untrustworthy)
- Feature matrix mismatch with discovery
- All methods fail to run
- Consensus set empty while single-method outputs exist — must mark explanations provisional

## 8. Applicability

**Valid for:** supervised explanation of discovered discrete states across aquatic domains.

**Not valid for:** claiming process causality without Physical Knowledge + environmental context support.

## 9. Dependencies

**Upstream:** Discovery (labels); Statistical Intelligence (features).

**Downstream:** Process labeling; Decision Support (sensor priority); EBSVE; Anomaly context.

## 10. Verification Tests

1. Permute labels; assert consensus drivers collapse / agreement drops.
2. Drop a true synthetic signal feature; assert it exits consensus.
3. Independent recomputation of permutation importance on exported model inputs.
4. Reviewer confirms disputed drivers are listed when methods conflict.

## 11. Reviewer Checklist

- [ ] ≥2 explanation methods attempted (or explicit single-method limitation)
- [ ] Consensus rule documented
- [ ] Disputed drivers exported
- [ ] No causal language in primary outputs
- [ ] Aligns to discovery feature set
