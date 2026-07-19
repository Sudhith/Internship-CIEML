# Uncertainty propagation rules (v2)

> Implemented in `cieml/uncertainty/propagate.py`. Replaces v1's R1–R7 (mixed RSS/sum/clip,
> documented for historical reference at the bottom of this page) with one internally
> consistent model. Full mathematical justification and worked examples:
> [EVIDENCE_RELIABILITY_REDESIGN.md](EVIDENCE_RELIABILITY_REDESIGN.md) §4–§7.

All component values use **0–100** intensity of unresolved doubt, but combination happens in
**raw (unbounded) intensity space** — the 0–100 scale only applies to individually-authored
components and to the final reported value; intermediate sums are allowed to exceed 100.
Inputs from fractions/stds must be mapped explicitly before combination (see mapping table below).

## Principle

**Do not average unlike uncertainties. Do not double-count a shared root cause. Bound only once,
at the end.**
Combine only under a named rule; always retain the component vector, its `provenance_id`, and
`resolves_upstream` flag for audit.

## Notation

- \(\sigma_k\) — component of kind \(k\), raw intensity (individually clipped to [0, 100] at
  authoring time, but combined unbounded)
- \(\sigma_c\) — combined raw intensity under the GUM formula
- \(\rho_{ij}\) — declared correlation coefficient for a pair, default 0 (independent)
- \(\mathrm{sat}(\cdot)\) — the one-time saturating map to [0, 100)

## Rule V2.1 — Provenance deduplication (`_dedup_by_provenance`)

Before any combination, components sharing a `provenance_id` (the same root cause) are reduced
to their single worst estimate:

\[
\sigma_{\mathrm{pool}} = \max_{k \in \mathrm{pool}} \sigma_k
\]

This is the structural fix for the class of bug where one fact (e.g. "single regional meteo
station") was authored once but counted twice because two different engines each mentioned it.
`provenance_id="unspecified"` is never deduplicated against other unspecified components, since
it carries no identity information.

## Rule V2.2 — Correlation-aware combination (`combine_correlated`, replaces R1 + R2)

For a deduplicated set of sibling components:

\[
\sigma_c = \sqrt{\sum_k \sigma_k^2 + 2\sum_{i<j} \rho_{ij}\, \sigma_i \sigma_j}
\]

At \(\rho=0\) for every pair this is exact RSS (old R1, "independent random"). At \(\rho=1\) for
every pair this is exact sum (old R2, "systematic upper bound"). Both are now special cases of
one formula instead of two separately-justified rules — declare the \(\rho\) that matches the
actual physical relationship between two components instead of picking a rule by component kind.

## Rule V2.3 — Precision fusion for corroborating evidence (`fuse_precision`, replaces R5's
`inherit_weight`)

When new local evidence corroborates the same question a parent already had doubt about
(`resolves_upstream=True`), combine via inverse-variance (Kalman/Bayesian) fusion instead of an
arbitrary inheritance weight:

\[
\sigma_{\mathrm{post}} = \sqrt{\left(\frac{1}{\sigma_{\mathrm{in}}^2} + \frac{1}{\sigma_{\mathrm{local}}^2}\right)^{-1}}
\]

Guarantees \(\sigma_{\mathrm{post}} \le \min(\sigma_{\mathrm{in}}, \sigma_{\mathrm{local}})\):
agreeing independent evidence can only sharpen an estimate, never worsen it — the mechanism that
lets uncertainty genuinely *decrease* under corroboration, which v1's parameter-free
`inherit_weight=0.35` could never express. New evidence about a *different* question
(`resolves_upstream=False`) is instead combined additively via Rule V2.2 and can only add to or
hold doubt steady.

## Rule V2.4 — Serial engine update (`propagate_engine`, replaces R4 + R5)

For an engine consuming a parent's raw intensity:

1. Fuse any corroborating evidence into the parent (Rule V2.3) → `sigma_post`.
2. Combine any new-question evidence (Rule V2.2) → `sigma_new`; combine with `sigma_post` (Rule
   V2.2, declared `post_new_rho`, default 0) → `sigma_out`.
3. Report the full telescoping budget: `Inherited = sat(parent_raw)`,
   `Resolved = Inherited - sat(sigma_post)`, `New = sat(sigma_out) - sat(sigma_post)`,
   `Remaining = Net = sat(sigma_out)`. By construction,
   `Inherited - Resolved + New == Remaining` exactly.
4. `raw_total = sigma_out` is retained, unbounded, purely for chaining into the *next* engine's
   `parent_raw` — never for display, and never re-saturated before the next chain step (saturating
   twice was v1's ceiling-clustering bug).

**Forbidden:** clipping any intermediate sum to [0, 100] before the final report step;
\(U = \mathrm{mean}(u_k)\).

## Rule V2.5 — Saturation (`saturate`, replaces the clip-at-every-step behavior)

Applied **exactly once**, at report time:

\[
\mathrm{sat}(\sigma) = 100 \cdot \frac{\sigma}{\sigma + k}, \quad k = 100 \text{ (default)}
\]

Bounded in [0, 100) by construction, monotonic, smooth, and — unlike a hard clip — keeps two
different large raw intensities distinguishable instead of both reading exactly 100.0.

## Rule V2.6 — Confidence gate (non-substitution, unchanged from R6, now also gates Evidence
Reliability)

Confidence \(C\) never enters \(U\) by \(U = 100 - C\); Evidence Reliability \(R\) never enters
either \(C\) or \(U\) and is not derived from them (`R != C`, `R != 100 - U`). Optional **decision
caution** index for managers (`caution_index`, separate product, never a fourth scientific axis):

\[
\mathrm{Caution} = \min\left(100,\ \sqrt{(100-C)^2 + U^2}\right)
\]

Reported beside, not instead of, \(C\), \(U\), and \(R\).

## Rule V2.7 — Claim packet (replaces R7)

For Scientific Claim objects:

1. Combine relevant upstream engines' raw totals via Rule V2.2 (`combine_raw`, e.g. Environmental
   + Model), replacing v1's arbitrary partial-inherit hacks with a principled multi-parent
   combination.
2. Add pillar-weakness uncertainty as new evidence: \(\sigma_{\mathrm{pillar}} = 100 - \min_p s_p\)
   (weakest pillar), tagged with its own `provenance_id` per claim.
3. Apply Rule V2.4's serial update to produce the claim's full budget.
4. Score Evidence Reliability once per claim (`reliability.score_evidence_reliability`) — a
   property of the claim's evidence base, not something propagated stage-to-stage like \(M\).
5. Limitations = union of upstream limitations + claim-specific weaknesses. Remaining unknowns =
   explicit gaps (no external station forcing, single season, …).

## Mapping helpers (declared, not hidden)

| Raw quantity | Map to component value |
|--------------|--------------------------|
| Missingness fraction \(f\) | \(u = 100f\) (sampling/QA) |
| Critical QA rate \(c\) | \(u_{\mathrm{sensor}} = \min(100, 200c)\) |
| Bootstrap ARI σ \(\sigma\) | \(u_{\mathrm{model}} = \min(100, 100\sigma)\) |
| Consensus disagreement (1 − agreement) | \(u_{\mathrm{model}}\) or explainability |
| Origin confidence \(o\) for anomalies | \(u_{\mathrm{interpretation}} = 100(1-o)\) |
| External support fraction \(e\) | \(u_{\mathrm{ext}} = 100(1-e)\) |

All maps must be cited in the component `source` fields, and every component must declare a
`provenance_id`.

---

## v1 rules (historical, superseded)

Retained for audit/diff purposes only — do not implement against these; see Rule V2.1–V2.7 above.

- **R1** Independent random (RSS): \(U_{\mathcal{R}} = \sqrt{\sum u_k^2}\), clipped to 100 —
  superseded by V2.2 at \(\rho=0\), combined unbounded.
- **R2** Systematic upper bound: \(U_{\mathcal{S}} = \min(100, \sum u_k)\) — superseded by V2.2
  at \(\rho=1\).
- **R3** Model structural uncertainty via \(\max(u_{\mathrm{model}}, u_{\mathrm{instability}})\) —
  dropped (was dead code, never wired in); superseded conceptually by V2.3's precision fusion,
  which is strictly more informative than a max-of-two-doubts rule.
- **R4** Hybrid stage total with clip-at-every-step — superseded by V2.2 + V2.5 (combine raw,
  saturate once).
- **R5** Serial propagation with fixed `inherit_weight=0.35` — superseded by V2.3 (parameter-free
  precision fusion for corroborating evidence) + V2.4 (full serial update).
- **R6** Confidence gate + caution index — retained as V2.6, now also gates Evidence Reliability.
- **R7** Claim packet — superseded by V2.7 (multi-parent combination + per-claim Evidence
  Reliability scoring).
