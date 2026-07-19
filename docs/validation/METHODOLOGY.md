# Framework validation methodology

## Core questions

1. **Reproducibility** — Can another researcher re-run CIEML and obtain bit-stable
   scientific *classifications* (and documented numeric tolerances for floats)?
2. **Determinism** — Fixed seeds + fixed inputs → identical artifacts (or declared NDE)?
3. **Engine independence** — No hidden score reuse across pillars/engines?
4. **Interface stability** — Artifact contract + claim pack + domain profile APIs stable?
5. **Contract satisfaction** — Every SC-* guarantee has a verification test that passes?
6. **Uncertainty correctness** — Propagation obeys SC-MMU/SC-REL (no `U=100-C`, no unlike averaging)?
7. **Provenance completeness** — Every scored claim cites openable EvidenceItem sources?
8. **Domain swap** — New domain YAML (+ adapter) runs without editing engine code?
9. **Evidence-based claims** — No hardcoded Visakhapatnam verdicts in shared ABC/scoring?

## What “pass” means

| Level | Meaning |
|-------|---------|
| **CERTIFIED** | All critical suite tests green; readiness checklist complete |
| **CONDITIONAL** | Non-critical gaps documented with owners/dates |
| **NOT READY** | Any critical reproducibility, contract, or evidence-integrity failure |

Certification is about the **framework**, not endorsement of a case study’s scientific story.
