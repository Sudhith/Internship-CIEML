# Discovery Engine

```yaml
contract_id: SC-DISC
engine: Discovery Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_06', 'stage_07']
```

## 1. Scientific Purpose

Discover whether the analysis units **organize into environmental regimes / states** using multi-algorithm competition and explicit stability validation — without assuming the number of regimes, the algorithm, or their semantic labels.

**Problem solved:** Pre-chosen clustering solutions presented as environmental truth.

## 2. Scientific Question

**Primary:** Are environmental regimes statistically defensible in this dataset?

**Secondary:** How stable is the selected structure under resampling, algorithm disagreement, and leave-one-group-out tests?

## 3. Inputs

**Required**
- Retained feature matrix with analysis-unit IDs (e.g. station, date)

**Optional**
- Candidate algorithm list and K range (framework knobs)
- Spatial coordinates (for later context, not required to discover)

**Metadata**
- Random seeds / stability replication counts

**External context**
- None required for discovery itself

## 4. Outputs

**Primary**
- Selected labeling of analysis units (regime IDs) with winning algorithm and K
- Model comparison table (internal indices + stability)

**Derived**
- Validation report (bootstrap, consensus, LOSO/LOWO, permutation null, structure call)
- Embeddings for visualization (e.g. PCA of scaled features)

**Confidence / uncertainty**
- Stability ARI distributions
- Structure call (e.g. supported / provisional / fragile — campaign-agnostic vocabulary)
- Permutation-null gap

**Intermediate artifacts**
- Ranked candidate solutions; validation figures

## 5. Assumptions

- Features are commensurate after declared scaling.
- Analysis units are exchangeable enough for the chosen validation scheme (station dependence acknowledged in LOSO).
- Semantic meaning of regimes is **out of scope** for this engine (handled by labeling / domain vocabulary later).

## 6. Scientific Guarantees

- **No cluster solution is accepted without validation metrics and a structure call.**
- K and algorithm are selected from declared candidates by documented composite rules — not by narrative preference.
- Permutation or equivalent null comparison is reported.
- **Does not guarantee** ecological interpretation or transfer to other sites.

## 7. Failure Conditions

- Too few analysis units for any K≥2 solution
- All candidates invalid (e.g. single cluster / all noise)
- Stability suite cannot run
- Selected solution fails contracted minimum validation gates when gates are enabled

## 8. Applicability

**Valid for:** multiparameter campaigns in coastal, river, lake, estuary, harbour, reservoir, aquaculture settings with sufficient n.

**Not valid for:** forcing a predetermined regime count as a scientific finding.

## 9. Dependencies

**Upstream:** Statistical Intelligence (retained features).

**Downstream:** Explainability; Anomaly Intelligence; Process labeling; EBSVE (regime claims); Decision Support; Stage 14-style robustness (parametrized off selected algorithm/K).

## 10. Verification Tests

1. Re-run discovery with fixed seed; assert identical selection under determinism constraints.
2. Shuffle feature columns with permutation null; assert structure call weakens / ARI collapses.
3. Independent implementation of silhouette/ARI on exported labels and matrix.
4. Confirm outputs do not contain semantic regime titles invented inside this engine.

## 11. Reviewer Checklist

- [ ] Candidate set and selection rule documented
- [ ] Validation battery exported
- [ ] Structure call present with criteria
- [ ] No semantic overclaim in discovery outputs
- [ ] Algorithm/K carried forward as metadata for robustness
