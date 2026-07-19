# CIEML Knowledge Base (SC-KB)

Append-only scientific memory across campaigns. **Never** silently mutates
`configs/domains/` or frozen `outputs/`.

| Path | Role |
|------|------|
| `audit_log.jsonl` | Every propose / accept / reject event |
| `entries/*.json` | Versioned KB entries (candidate → supported / contested / retired) |
| `proposals/` | Suggested domain-profile diffs awaiting human review |

```text
python -c "from cieml.knowledge import propose_from_campaign; propose_from_campaign(...)"
```

Grade vocabulary: `candidate` | `supported` | `contested` | `retired`.
