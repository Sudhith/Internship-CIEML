# Scientific Contract — required schema

Every engine contract `SC-*` MUST contain the following sections, in order.

| # | Section | Content |
|---|---------|---------|
| 1 | **Scientific Purpose** | Why the engine exists; which scientific problem it solves |
| 2 | **Scientific Question** | The question(s) answered (one primary, optional secondary) |
| 3 | **Inputs** | Required, optional, metadata, external context |
| 4 | **Outputs** | Primary, derived, confidence, uncertainty, intermediate artifacts |
| 5 | **Assumptions** | Explicit operating assumptions |
| 6 | **Scientific Guarantees** | What the engine promises (and what it refuses to claim) |
| 7 | **Failure Conditions** | When outputs must be marked untrusted / engine must abort or degrade |
| 8 | **Applicability** | Valid environmental domains and design conditions |
| 9 | **Dependencies** | Upstream engines that must succeed; downstream consumers |
| 10 | **Verification Tests** | How an independent researcher verifies the engine |
| 11 | **Reviewer Checklist** | Pass/fail checklist for scientific validity review |

### Front matter (required)

```yaml
contract_id: SC-XXX
engine: <name>
version: "1.0.0"
status: implemented | partial | planned
implements_stages: [<legacy stage ids if any>]
```

### Writing norms

- Use measurable language (“reports ARI”, “emits severity”) over vague language (“is good”).
- Guarantees are about **process integrity**, not about guaranteeing a particular scientific discovery.
- Failure conditions should be machine-checkable where possible.
