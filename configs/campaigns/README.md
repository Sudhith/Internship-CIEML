# Campaign profiles (Phase B+)

Campaign files describe **one monitoring dataset run** (paths, stations, adapter) — not scientific verdicts.

| File | Role |
|------|------|
| `visakhapatnam_may2026.yaml` | First demonstration campaign |

```python
from cieml.domain import load_campaign
c = load_campaign("visakhapatnam_may2026")
```

Legacy `configs/stations.yaml` remains as a fallback for region/coords.

Optional: `claim_pack: <pack_id>` selects `configs/claims/<pack_id>.yaml` (default `coastal_monitoring_v1`).
