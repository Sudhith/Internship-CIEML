# Regression protocol

## When to run

- After any contract-touching phase (B–K, FMF, uncertainty, validation)
- Before tagging a framework release
- After changing scoring thresholds, claim packs, or artifact names

## Primary demonstration

Campaign: `visakhapatnam_may2026`  
Domain: `coastal`  
Claim pack: `coastal_monitoring_v1`

## Critical frozen artifacts (diff these)

| Artifact | Tolerance |
|----------|-----------|
| Claim classifications (H1–H6) | Exact |
| Campaign closure | Exact |
| Regime labels | Exact (ARI=1) or documented seed change |
| SHAP top drivers set | Exact set (order soft) |
| Anomaly consensus count | Exact or ±0 with documented detector change |
| Failure CRITICAL+ mode_ids | Superset allowed only if newly detected; removals need waiver |

## Procedure

1. Checkout clean tree; install pinned deps.
2. Re-run affected phases (`scripts/run_phaseN.py`).
3. Run `python -m cieml.validation.run_suite`.
4. Diff critical artifacts vs `configs/validation/baselines/` (or last certified `outputs/phase8`).
5. If scientific-neutral rename only: update alias map + baselines in same PR.
6. Record result in certification report (pass/fail + waiver list).

## Waivers

Waivers require: reason, owner, expiry, linked issue. No silent baseline rewrites.
