# Claim packs

A **claim pack** is a configuration that lists the scientific claims EBSVE will
audit for a campaign. The four-pillar scoring ABC (`HypothesisValidator`) is
framework code; which claims run is pack content.

| File | Role |
|------|------|
| `coastal_monitoring_v1.yaml` | First pack — legacy H1–H6 coastal monitoring claims |

**Rules**
- Claim IDs must stay stable once published (artifact / ledger compatibility).
- Adding a claim = YAML entry + optional validator plugin; do not edit pillar math.
- Domain priors (equivalence groups, decision keywords) live in `configs/domains/`,
  not inside claim packs.
- `configs/hypotheses.yaml` is a deprecated compatibility shim pointing here.
