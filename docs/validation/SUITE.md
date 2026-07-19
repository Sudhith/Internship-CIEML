# Framework validation suite

Configured in `configs/validation/suite.yaml`. Groups:

## 1. Architecture compliance tests (`arch_*`)

| Test ID | Assert |
|---------|--------|
| `arch_domain_priors_not_in_scoring` | `cieml.evidence.scoring` has no site literals |
| `arch_claim_pack_drives_ebsve` | Engine validators resolved from pack, not hardcoded-only list |
| `arch_artifact_contract_covers_loaders` | Every loader key ∈ artifact specs |
| `arch_framework_case_doc_split` | FRAMEWORK.md has no Visakhapatnam conclusions |

## 2. Regression tests (`reg_*`)

| Test ID | Assert |
|---------|--------|
| `reg_visakhapatnam_claim_classes` | H1–H6 classifications match frozen baseline |
| `reg_regime_labels_stable` | Stage 6 labels ARI=1 vs baseline (fixed seed) |
| `reg_shap_top3_stable` | Top-3 drivers match baseline set |
| `reg_anomaly_consensus_count` | Consensus n within tolerance |

## 3. Acceptance tests (`acc_*`)

| Test ID | Assert |
|---------|--------|
| `acc_phase_runners_exist` | `scripts/run_phase1.py` … `run_phase8.py` |
| `acc_default_campaign_loads` | domain + campaign + claim pack load |
| `acc_outputs_gitignored` | `outputs/` ignored |

## 4. Scientific verification tests (`sci_*`)

| Test ID | Assert |
|---------|--------|
| `sci_pillar_independence` | Serialized pillar scores not copies of each other |
| `sci_uncertainty_axes_distinct` | Ledger never sets U from 100−C |
| `sci_failure_catalog_maps_contracts` | Each contract §7 maps to ≥1 mode (or explicit waive) |
| `sci_dss_suppress_on_low_evidence` | Fixture with low evidence → no recommendations |

## 5. Evidence integrity tests (`evid_*`)

| Test ID | Assert |
|---------|--------|
| `evid_items_have_sources` | Every EvidenceItem.source non-empty |
| `evid_sources_resolve` | Cited paths exist under outputs/ or are declared live keys |
| `evid_claim_pack_id_on_register` | Register carries `claim_pack_id` |

## 6. Extensibility smoke (`ext_*`)

| Test ID | Assert |
|---------|--------|
| `ext_domain_stub_loads` | `harbour.yaml` extends coastal |
| `ext_claim_pack_schema` | Pack has pack_id + non-empty claims + validators |

## Execution

```text
python -m cieml.validation.run_suite
→ outputs/framework_validation/certification_report.json
→ outputs/framework_validation/compliance_matrix.json
→ outputs/framework_validation/certification_report.md
```

Critical failures ⇒ certification **NOT READY**.
