# Domain profiles (Phase B)

Machine-readable scientific priors for CIEML engines (SC-DCL).

| File | Role |
|------|------|
| `_schema.yaml` | Required / optional keys |
| `coastal.yaml` | **Filled** coastal multiparameter profile (active default) |
| `estuary.yaml`, `harbour.yaml`, `river.yaml`, `lake.yaml`, `reservoir.yaml`, `aquaculture.yaml` | Stubs (`extends: coastal`) |

Load via:

```python
from cieml.domain import load_domain, get_default_domain
d = load_domain("coastal")
```

Engines that consume this layer: QA (`qa.*`), Physical Knowledge (`relationships`), evidence H3/H6 priors, Stage 0 core variables.
