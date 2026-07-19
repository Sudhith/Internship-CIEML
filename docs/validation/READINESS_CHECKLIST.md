# Framework readiness checklist

## Must be true for CERTIFIED

- [ ] All `critical: true` suite tests pass
- [ ] Visakhapatnam regression protocol green (or waived with expiry)
- [ ] SC-FMF catalog covers mapped contract failure conditions
- [ ] Claim pack loads; EBSVE returns four pillars per claim
- [ ] Uncertainty ledger exports without axis collapse
- [ ] FRAMEWORK.md free of case conclusions
- [ ] Architecture audit verdict ≠ fail
- [ ] Scientific audit verdict ≠ fail
- [ ] Reproducibility: twin-run claim classes identical
- [ ] Extensibility smoke: domain stub + claim pack schema OK

## Should be true (conditional allowed)

- [ ] DSS/Applicability/KB Phase K complete or marked partial with roadmap
- [ ] Full detector coverage for every catalog mode (some may be planned)
- [ ] CI runs `cieml.validation.run_suite` on PR

## Release blocker examples

- Hardcoded site verdict in `scoring.py` / ABC
- Claim classes flip without documented scientific change
- Recommendations emitted under CRITICAL `dss_low_evidence`
- Missing provenance on EvidenceItems
