# Architecture audit template

**Framework version:**  
**Audit date:**  
**Auditor:**

## Separation of concerns

- [ ] Domain science in `configs/domains/`, not in scoring ABC
- [ ] Campaign metadata in `configs/campaigns/`
- [ ] Claims in `configs/claims/`
- [ ] Framework knobs in `configs/framework.yaml`
- [ ] Case conclusions only in `docs/CASE_STUDY_*.md` / `cases/`

## Interfaces

- [ ] Artifact contract versioned; aliases documented
- [ ] Claim pack plugins resolve without editing `scoring.py`
- [ ] QA / ingestion registries used for extension points

## Independence

- [ ] Four EBSVE pillars do not reuse each other’s scores
- [ ] Uncertainty axes distinct from confidence
- [ ] Failure modes do not invent evidence

## Findings

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| | | | |

## Verdict

`pass` / `conditional` / `fail`
