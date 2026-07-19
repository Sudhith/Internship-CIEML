# Anomaly Intelligence Engine

```yaml
contract_id: SC-ANOM
engine: Anomaly Intelligence Engine
version: "1.0.0"
status: implemented
implements_stages: ['stage_09']
```

## 1. Scientific Purpose

Detect analysis units that are **unusual relative to the learned or empirical baseline**, classify probable origin when possible, and attach confidence so anomalies are actionable scientific objects rather than unlabeled outliers.

**Problem solved:** One-detector anomaly dumps without typology or trust metrics.

## 2. Scientific Question

**Primary:** Which observations (analysis units) represent genuine anomalies worth scientific attention?

**Secondary:** Are they more consistent with sensor fault, environmental event, temporal shock, multivariate novelty, or context mismatch?

## 3. Inputs

**Required**
- Feature matrix (and optionally regime labels for contextual anomalies)

**Optional**
- QA flags; external forcing series; contamination / sensitivity grid

**Metadata**
- Detector list and parameters

**External context**
- Meteorology or hydrology (strengthens environmental origin tests; optional)

## 4. Outputs

**Primary**
- Anomaly flags / catalog with detector votes
- Consensus anomaly set under declared rule

**Derived**
- Probable origin labels (sensor / environmental / temporal / multivariate / contextual / novel state) — Phase I target
- Rates by station/time

**Confidence / uncertainty**
- Detector-agreement confidence per anomaly
- Origin-class confidence
- Sensitivity to contamination parameter

**Intermediate artifacts**
- Detector comparison figures; PCA overlay of anomalies

## 5. Assumptions

- “Anomaly” is relative to the campaign distribution and chosen detectors.
- Consensus reduces false positives but can miss rare singles.
- Origin classification is probabilistic, not courtroom proof.

## 6. Scientific Guarantees

- **No anomaly is reported without a confidence or agreement metric.**
- Detector parameters and consensus rule are explicit.
- QA-flagged sensor issues are available to down-weight “environmental” origin claims.
- **Does not guarantee** external validation (that is context + EBSVE).

## 7. Failure Conditions

- Feature matrix too small for multivariate detectors
- All detectors fail
- Consensus rule undefined
- Contamination grid empty when required by config

## 8. Applicability

**Valid for:** multiparameter aquatic campaigns across domains.

**Caution in:** extremely non-stationary campaigns without temporal modeling; single-station designs (limited contextual baselines).

## 9. Dependencies

**Upstream:** Statistical Intelligence; optional Discovery and QA.

**Downstream:** Context plugins; EBSVE (anomaly-reality claims); Decision Support (EWIs).

## 10. Verification Tests

1. Inject synthetic spike outliers; assert consensus capture at expected rate.
2. Mark same points as QA Critical; assert origin confidence shifts toward sensor when classifier enabled.
3. Independent recomputation of one detector on exported features.
4. Confirm every catalog row has agreement/confidence fields populated.

## 11. Reviewer Checklist

- [ ] Consensus rule documented
- [ ] Confidence present on each reported anomaly
- [ ] Detector parameters exported
- [ ] Origin typology present or explicitly deferred
- [ ] No silent drop of minority-detector events without a report
