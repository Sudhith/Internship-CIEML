# CIEML Uncertainty Model v2 — Redesign: Confidence / Measurement-Model Uncertainty / Evidence Reliability

**Status:** Design only. Nothing in `cieml/uncertainty/` has been changed. This document is the
artifact requested before any code migration — see [§11 Migration strategy](#11-migration-strategy)
for how v1 (`PROPAGATION_RULES.md`, implemented, `cieml/uncertainty/`) maps onto v2 below.

**Supersedes (on adoption):** `docs/uncertainty/PROPAGATION_RULES.md` (rules R1–R7) and the
two-axis framing in `docs/uncertainty/README.md`. Both are left untouched for now because
`cieml/uncertainty/assemble.py` still implements exactly what they describe; rewriting the
docs to describe unimplemented code would make the docs lie about the running system.

---

## 0. Executive summary

The v1 audit found six symptoms: near-universal saturation at 100, all claims reading
uncertainty≈100, confidence and uncertainty statistically independent but practically
indistinguishable, unavoidable accumulation under serial propagation, correlated sources
counted twice, and dashboards that stopped being informative. All six trace to **two design
errors**, not implementation bugs:

1. **A single scalar was asked to carry two different kinds of doubt.** "How noisy is this
   number" (measurement/model uncertainty) and "how complete is the evidence base behind it"
   (coverage/representativeness) were summed into one "uncertainty" total. These have different
   units of concern, different remedies (more precision vs. more coverage), and — critically —
   summing them means a campaign with excellent measurement precision but thin spatial coverage
   (exactly the Visakhapatnam case: n=6 stations, one season) reads as "high uncertainty"
   everywhere, when the real story is "trustworthy readings, narrow evidence base."
2. **The combination arithmetic did not distinguish independent from correlated sources**, and
   bounded the result by hard-clipping a sum that has no natural ceiling, rather than by using a
   combination rule that is bounded by construction.

This redesign fixes both by (a) **adopting your proposed three-way split** — Confidence,
Measurement & Model Uncertainty, Evidence Reliability — as three separately reported,
separately visualized axes, and (b) replacing the ad hoc R1–R7 arithmetic with a single,
internally consistent combination rule adapted from measurement-uncertainty metrology (GUM) and
sequential Bayesian/Kalman updating, so that (i) independent sources still combine by
root-sum-square exactly as before, (ii) correlated sources are combined by an explicit,
declared correlation coefficient instead of being silently double-counted, (iii) corroborating
downstream evidence can *reduce* propagated doubt, never only add to it, and (iv) the reported
score is bounded in [0, 100) by a smooth saturating map applied once at report time, not by
clipping a sum that could be arbitrarily large.

---

## 1. Diagnosis (grounding)

Traced precisely against the live ledger output (Visakhapatnam campaign):

- **Unbounded mixed accumulation.** `combine_hybrid`'s total is
  `sqrt(u_r² + u_m²) + u_s + α·u_e` — a sum of several ~O(50–100) terms with no ceiling of its
  own; `_clip(0,100)` does all the bounding, destroying the one place variation actually exists
  once several stages deep. Concretely, the environmental packet computed
  `sqrt(35²+0²) + 20 + 1.0×54.55 = 109.6 → clipped to 100.0`; nothing downstream of that point
  can be distinguished from a packet that computed 300.
- **Serial inheritance is a one-directional random walk.** Every stage inherits
  `0.35 × parent.total` as a new component and only ever adds local doubt on top. A process
  that only ever adds non-negative increments is a submartingale with strictly non-negative
  drift — it cannot do anything but trend toward the ceiling over a 9-stage chain
  (QA→Measurement→Statistical→Model→Explainability→Anomaly→Environmental→Policy→Decision→Claim).
- **No resolution mechanism.** Nothing in v1 allows converging, corroborating evidence (e.g.
  Stage 7's bootstrap/consensus/LOSO/permutation battery independently re-testing "do regimes
  exist," a question Stage 6 already carried doubt about) to *reduce* inherited doubt. Every
  coherent belief-updating framework (Bayesian updating, Kalman filtering, GUM Type A
  re-evaluation) requires that agreeing independent evidence sharpen, not just add to, the
  estimate. v1 structurally cannot do this.
- **Correlated sources double-counted.** "Single regional meteo point" is encoded twice: once
  as a fixed `SYSTEMATIC(20.0)` constant, and again — independently — as the data-driven
  `EXTERNAL(54.55)` support-gap component, which is *itself* computed from that same single
  meteo source. Both get summed as if independent. This is exactly the case GUM's covariance
  cross-term exists to prevent.
- **Two different questions collapsed into one number.** "Is the sonde reading precise" and "is
  six stations for one month enough to trust this generalizes" are different questions with
  different remedies, but both fed the same additive total.

---

## 2. Literature basis

- **GUM — *Guide to the Expression of Uncertainty in Measurement* (JCGM 100:2008).** The
  standard reference for combining measurement uncertainties. Two provisions matter here: (a)
  Type A (statistical) vs. Type B (other, e.g. literature bands, expert judgement) uncertainty
  evaluation — CIEML already has both kinds (bootstrap σ is Type A; a domain plausibility band
  is Type B) but doesn't distinguish them; (b) the **combined standard uncertainty** formula
  includes an explicit covariance term for correlated inputs, degenerating to root-sum-square
  when inputs are independent and to arithmetic sum when inputs are perfectly correlated. §5
  adapts this directly.
- **IPCC uncertainty guidance (Mastrandrea et al. 2010, *Guidance Note for Lead Authors of the
  IPCC Fifth Assessment Report on Consistent Treatment of Uncertainties*).** The direct
  precedent for keeping **confidence** (based on the type, amount, quality, and consistency of
  evidence, plus the degree of agreement) as an axis *distinct from* a quantified probability
  axis. This is the same shape of problem CIEML has, and the same shape of fix you proposed:
  don't force "how much evidence do we have" and "how numerically precise is it" through one
  number.
- **Sequential Bayesian updating / Kalman filtering.** The textbook recipe for combining a prior
  estimate's uncertainty with a new, independent measurement's uncertainty about the *same*
  quantity: precision (inverse variance) adds,
  `1/σ_post² = 1/σ_prior² + 1/σ_local²`, which guarantees `σ_post ≤ min(σ_prior, σ_local)`.
  This is the formal mechanism that makes "uncertainty can decrease when evidence agrees"
  possible, and is what §6 uses for the "resolving" half of each engine's local budget.
- **Global sensitivity analysis / variance decomposition (Saltelli-style).** Apportioning a
  total variance into fractional per-source contributions is the standard basis for a "source
  contribution chart" — used directly in §9.

---

## 3. The three-axis model

| Axis | Question it answers | Polarity | Owner (unchanged / new) |
|---|---|---|---|
| **Confidence (C)** | How strongly does the evidence support the claim being *true*? | higher = better | EBSVE four-pillar score — **unchanged by this redesign** |
| **Measurement & Model Uncertainty (M)** | How much numerical doubt is there in the observations, statistics, and models themselves? | higher = worse (more doubt) | `cieml.uncertainty` — redesigned below |
| **Evidence Reliability (R)** | How complete and representative is the evidence base the claim rests on? | higher = better (more complete) | new axis, §7 |

Every engine packet and every EBSVE claim reports all three independently. **None of the three
is derived from another** (in particular, `M ≠ 100 − C` and `R ≠ 100 − C`, preserved from the v1
guarantee, extended to the new axis).

Note the polarity asymmetry: C and R are "higher = better" (they answer "how strong/complete"),
M is "higher = worse" (it answers "how much doubt"). This mirrors how each concept is
naturally described in English and matches IPCC's own convention (their "confidence" and
"evidence" axes are both positively framed; their "likelihood/uncertainty" axis is not). Where a
single "higher = worse" dashboard convention is wanted, show `Evidence Gap = 100 − R` alongside R
rather than renaming R itself.

### 3.1 Naming and engine identity

Adopting your recommendation: the package's public identity becomes the **Evidence Reliability
Engine**, with Measurement & Model Uncertainty as a sibling product it also emits — not a
subordinate of it. Contract implications are in §12.

---

## 4. Correlation and provenance rules

**Rule.** A single root cause of doubt is represented by **exactly one component**, tagged with
a stable `provenance_id` (e.g. `"single_regional_meteo"`, `"n_stations=6"`,
`"bootstrap_resampling_stage06"`). If a second engine wants to acknowledge the *same*
limitation, it references the existing component by `provenance_id` — it does not instantiate a
fresh magnitude for it. This is a data-modeling discipline, not a formula, and it is the direct,
structural fix for the "single regional meteo point counted as both systematic and external"
bug: under this rule that limitation is authored once (by the External/Environmental engine,
which is closest to the source) and inherited by reference everywhere else, never re-estimated.

**Combination across genuinely distinct components** (different `provenance_id`) uses a declared
correlation coefficient ρ ∈ [0, 1] per pair, defaulting to **ρ = 0 (independent)** unless a
specific, documented reason to believe partial correlation exists (e.g. "both trace to the same
sensor batch," ρ = 0.3, cited). Components sharing a provenance pool that legitimately *are*
distinct-but-related observations of the same underlying issue (not accidental duplicates — see
Rule above) may declare ρ close to 1; this is what replaces the old, categorical
"systematic → always sum" rule with one continuous, justified dial (§5 shows sum falls out of
this at ρ = 1 as a special case, not a separate rule).

**Correlation graph.** The dashboard (§10) renders provenance pools and declared ρ values as a
graph: nodes are components, edges are declared correlations, edge weight = ρ. This is a direct
visualization of the table above — no additional math.

---

## 5. Propagation equations

All combination happens in **raw intensity space** (the 0–100 input values, treated as
pseudo-standard-deviations, exactly as v1's inputs already are — no transform needed at input
time). Bounding to a reportable 0–100 score happens **once**, at the point of reporting, via a
smooth saturating map — not at every intermediate combination step. This separation is the
single most important structural change from v1, where saturation-by-clipping was applied
(implicitly, via `_clip`) after every step, compounding information loss at every stage.

### 5.1 Sibling combination (within one engine's local budget)

For components `{σ_1, …, σ_n}` with pairwise correlations `ρ_ij` (default 0 across distinct
`provenance_id`s, per §4):

```
σ_local² = Σ_i σ_i²  +  2 · Σ_{i<j} ρ_ij · σ_i · σ_j
```

This is the GUM combined-uncertainty formula, unmodified. Two special cases recover exactly the
useful pieces of v1:

- **All ρ_ij = 0 (independent):** `σ_local = sqrt(Σ σ_i²)` — literal root-sum-square, exactly
  v1's R1, and exactly what GUM prescribes for independent random-like sources. No regression.
- **All ρ_ij = 1 within one pool:** `σ_local = Σ σ_i` — arithmetic sum, exactly v1's R2, now
  understood as the ρ = 1 endpoint of one continuous rule instead of a separately-justified
  special case for "systematic-looking" kinds.

### 5.2 Serial "update" propagation (engine A → engine B)

Engine B's local evidence is split into two conceptually different contributions before
combining with what it inherited from A:

- **Corroborating evidence** — new, independent information *about the same question* A already
  had doubt about (e.g. Stage 7's bootstrap/consensus/LOSO/permutation battery re-testing
  Stage 6's "do regimes exist" question). Combine sibling corroborating components via §5.1 to
  get `σ_corrob`, then **precision-fuse** with the inherited value:

  ```
  σ_post = sqrt( 1 / (1/σ_in² + 1/σ_corrob²) )        (σ_in, σ_corrob > 0)
  ```

  This is the standard Kalman/Bayesian inverse-variance update. It is **guaranteed**
  `σ_post ≤ min(σ_in, σ_corrob)` — agreeing independent evidence can only sharpen the estimate.
  If B has no corroborating evidence, `σ_post = σ_in` unchanged (no spurious resolution
  invented). If either input is exactly 0 ("perfectly certain"), that input dominates:
  `σ_post = 0`.

- **New, independent evidence** — doubt about a *different* question that B introduces (e.g.
  Explainability's cross-method disagreement is a claim about interpretability, not about
  whether regimes exist — it must not be allowed to "resolve" Stage 6/7's discovery doubt, nor
  should it be blocked from adding its own). Combine sibling new-source components via §5.1 to
  get `σ_new`, then combine with `σ_post` via the same general formula (§5.1), with declared
  correlation (default 0):

  ```
  σ_out = sqrt( σ_post² + σ_new² + 2ρ·σ_post·σ_new )
  ```

**Classifying "corroborating" vs. "new" is a per-engine judgement call, made explicit in code as
a boolean tag on each local `UncertaintyComponent` (`resolves_upstream: bool`), not inferred
automatically.** Migration guidance for the current 9 engines is in §11.

### 5.3 Report-time saturation (bounding without clipping)

Applied exactly once, wherever a `σ` (in the unbounded intensity space above) needs to become a
reportable 0–100 score:

```
U_report = 100 · σ / (σ + k)          (k = calibration constant, default k = 100)
```

A hyperbolic ("Michaelis–Menten") saturating map: `U_report → 0` as `σ → 0`,
`U_report → 100` asymptotically as `σ → ∞` but **never reaches or exceeds 100 for finite σ**,
monotonically increasing (never inverts ordering), smooth everywhere (no clipping discontinuity).
Two packets that would both have hit the old hard ceiling — say raw combined intensities of 110
and 300 — now report as 52.4 and 75.0 respectively: still distinguishable, still ordered
correctly, still bounded. `k` is a genuine calibration parameter, not asserted — see §8.

---

## 6. Uncertainty budgets (replacing cumulative sums)

Every engine reports, per the requested fields, computed from §5.2's three intermediate values
`σ_in → σ_post → σ_out`:

| Field | Definition | Sign |
|---|---|---|
| **Inherited uncertainty** | `saturate(σ_in)` | — |
| **Resolved uncertainty** | `saturate(σ_in) − saturate(σ_post)` | ≥ 0 always (precision-fusion cannot increase σ) |
| **New uncertainty** | `saturate(σ_out) − saturate(σ_post)` | ≥ 0 always |
| **Remaining uncertainty** | `saturate(σ_out)` | — |
| **Net uncertainty** | ≡ Remaining uncertainty (identical by definition; both fields kept because the requested vocabulary names them separately — do not let a future revision silently redefine one without the other) | — |
| **Confidence gained** | Only meaningful where an engine also revises a Confidence-axis score (chiefly EBSVE claim closure); `ΔC` this stage contributed, else `null` | can be ± |

**The bookkeeping telescopes exactly, by construction:**

```
Inherited − Resolved + New
  = saturate(σ_in) − [saturate(σ_in) − saturate(σ_post)] + [saturate(σ_out) − saturate(σ_post)]
  = saturate(σ_post) + saturate(σ_out) − saturate(σ_post)
  = saturate(σ_out)
  = Remaining
```

So the ledger's own arithmetic is auditable without re-deriving σ values — a reviewer can check
`Inherited − Resolved + New == Remaining` on the reported numbers alone and it will hold exactly.

---

## 7. Evidence Reliability (R) — separate scoring model

R is a property of the **evidence base's coverage**, not of measurement noise, so it does not
use the σ/precision machinery above — that machinery exists to combine *doubt sources*; coverage
is better modeled as a **weighted completeness score**, directly bounded by construction (a
weighted mean of already-bounded fractions needs no saturating map):

```
R = 100 · Σ_d (w_d · coverage_d) / Σ_d w_d,     coverage_d ∈ [0, 1]
```

Recommended default dimensions (declared in the Domain Configuration Layer, not hardcoded —
see §8):

| Dimension `d` | Example `coverage_d` for Visakhapatnam | Suggested saturating target |
|---|---|---|
| Spatial coverage | stations observed / recommended minimum | `min(1, n_stations / target_n)` |
| Temporal coverage | seasons/months observed / annual cycle | `min(1, n_distinct_seasons / 4)` |
| Methodological diversity | independent methods used / target count | `min(1, n_methods / 3)` (reuses Stage 8 consensus method count) |
| External corroboration diversity | independent external data sources / target | `min(1, n_external_sources / 2)` (currently 1: Open-Meteo only) |

R is computed **once per relevant object** (chiefly per EBSVE claim, and for the External/
Environmental engine) directly from campaign/domain design metadata — it is *not* propagated
stage-to-stage like M, because it is a property of the campaign's design, which does not change
as data flows through engines. This mirrors IPCC's own practice of assessing "evidence" once per
finding rather than mechanically accumulating it across intermediate processing steps. State
this as an explicit rule (**R8**, alongside R1–R7's renumbering in §11) so implementers don't
default to serial-propagating R out of habit.

For Visakhapatnam specifically, this model would compute something like: spatial 6/? (needs a
domain-declared target — recommend 8–10 for "regionally representative" coastal monitoring, so
6/8 ≈ 0.75), temporal 1/4 seasons (0.25), methodological 3/3 (1.0, already meets target),
external 1/2 (0.5) → equal-weighted R ≈ 62.5. A moderate, **non-saturated**, clearly
discriminative number — contrast with v1's environmental packet reading a flat 100.

---

## 8. Calibration recommendations

1. **`k` (saturation constant, §5.3):** do not assert a value. Calibrate against 2–3 reference
   scenarios with an intuitively known-correct answer: a "textbook strong" synthetic case
   (single independent 20-intensity component only) should land in a "low doubt" reporting band
   (< 25); a "textbook weak" case (multiple ~80-intensity independent components) should land
   clearly in a "high doubt" band (> 75) without saturating flat at 100. Solve for `k` that
   satisfies both anchors, then freeze it as a framework constant in `configs/framework.yaml`
   (not per-domain — the *reporting scale* should be consistent across domains even though the
   *evidence-reliability targets* in §7 are domain-specific).
2. **Evidence Reliability targets (`target_n`, season count, method count, source count):**
   domain-declared in `configs/domains/<domain>.yaml` under a new `evidence_reliability` block,
   consistent with Phase B's existing philosophy that nothing scientifically load-bearing is a
   Python constant. Coastal defaults should be set by literature-informed monitoring-design
   guidance (e.g. regional water-quality network minimums), not fit to make Visakhapatnam look
   good.
3. **Correlation defaults:** ρ = 0 (independent) unless declared — never assume correlation by
   default; under-counting a real correlation is a smaller error than inventing a false
   independence assumption is currently causing, but a wrongly-assumed ρ = 1 forces manual
   justification, which is the safer default direction.
4. **`inherit_weight`/precision-fusion has no free "damping" parameter to tune** (a deliberate
   improvement over v1's `inherit_weight=0.35` magic number) — the Kalman-style fusion in §5.2
   is self-calibrating: it naturally weights inherited vs. local evidence by their *own* stated
   precision, so there is nothing arbitrary left to hand-tune there.

---

## 9. Validation methodology

1. **Exact recovery tests (regression against the one part of v1 that was already correct):**
   two independent components 30 and 40 (ρ=0) must combine to `sqrt(30²+40²) = 50`, exactly
   matching v1's R1 example and GUM's textbook case. Two components 20 and 20 declared fully
   correlated (ρ=1) must combine to 40 (sum), exactly matching v1's R2 example. These are
   **exact**, not asymptotic, under the corrected model (§5.1) — verify this explicitly, since an
   earlier draft of this redesign used a log-transform that only recovered RSS asymptotically for
   small values and silently became additive (wrong) for the actual operating range; that
   mistake is exactly why combination is now done in raw intensity space with saturation applied
   only at the boundary, and this test exists specifically to catch a regression back to that
   error.
2. **Monotonicity / no ceiling collapse:** feed a sweep of increasing raw combined intensities
   (0, 50, 100, 200, 500, 2000) through §5.3's saturating map; assert strictly increasing,
   asymptotic, never equal at two different inputs (i.e. no two distinct scenarios should ever
   report identically as "100.0" the way the current dashboard does).
3. **Resolution sanity:** construct a synthetic engine chain where a downstream stage's
   corroborating evidence is *more* precise than what it inherited (small `σ_corrob`); assert
   `Resolved > 0` and `σ_post < σ_in`. Construct a case with a *less* precise corroborating
   source; assert `Resolved ≥ 0` still (fusion never makes things worse) but small.
4. **De-duplication check:** reconstruct the "single regional meteo point" scenario from the v1
   ledger with the new provenance-pool rule; assert the External and Systematic components
   collapse to one contribution, and assert removing the (now-single) meteo component from the
   ledger changes the downstream claim's M by a materially different, and directionally correct,
   amount compared to today's double-counted version.
5. **Telescoping identity:** for every packet in a full campaign run, assert
   `Inherited − Resolved + New == Remaining` to floating-point tolerance (§6) — this should be
   checked as an automated invariant, not just a design claim, once implemented.
6. **Reviewer legibility check (qualitative but required):** regenerate the confidence-vs-M
   scatter (§10) for the full campaign; assert claims are visually separated (not all pinned to
   one corner) — this is the actual failure mode a reviewer flagged, so the fix must be verified
   against the same plot that exposed the bug, not only against unit-test numbers.

---

## 10. Dashboard redesign

Replace the current 4-panel dashboard (which has two panels rendered uninformative by
saturation) with:

1. **Uncertainty budget waterfall** (per engine, or per claim) — bars for Inherited, −Resolved,
   +New, = Remaining, in that order, so a reviewer sees *where* doubt was added or removed at a
   glance, not just a cumulative total. This directly visualizes §6's budget.
2. **Source contribution chart** — for a given packet's raw combined `σ²`, apportion
   `contribution_i = σ_i² / Σ_j σ_j²` per component (independent case) or per provenance pool
   (correlated case, with a footnote that a pooled slice reflects one shared cause). Standard
   variance-decomposition presentation (Saltelli-style), always sums to 100% by construction.
3. **Correlation graph** — nodes = components/pools, edges = declared ρ, per §4. Makes the
   "which doubts are secretly the same doubt" question inspectable rather than implicit.
4. **Engine contribution chart** — mean Remaining M by engine/object type, analogous to v1's
   panel A but now genuinely discriminative since totals no longer cluster at the ceiling.
5. **Confidence × Evidence Reliability × Measurement-Model Uncertainty scatter** — three axes,
   not two. Practical rendering: a 2D scatter of Confidence (x) vs. M (y), with **point size or
   color encoding R** (rather than forcing a true 3D plot). This directly replaces the collapsed
   "everything at uncertainty≈100" scatter with a plot where the three axes can visually
   disagree — e.g. Visakhapatnam's claims should now show high-ish Confidence, moderate M, and a
   clearly *sub-saturated*, mid-range R (§7's ≈62.5 example) — separated enough to be legible in
   the actual output, which is the concrete acceptance test for this whole redesign.

An optional, clearly-labeled **triage-only** scalar (e.g. "Review Priority") may still be
offered for manager convenience, defined transparently as a documented combination of the three
axes — but it must never be presented as a fourth "real" scientific product, precisely to avoid
recreating problem #3 (confidence and uncertainty becoming practically indistinguishable) one
level up.

---

## 11. Migration strategy

**No code changes are made by this document.** When implementation begins, in this order:

1. **Add `provenance_id` and `resolves_upstream` fields to `UncertaintyComponent`** (additive,
   non-breaking dataclass change). Backfill existing call sites in `assemble.py` with explicit
   provenance tags — this alone, even before touching the combination math, fixes the
   "single regional meteo point counted twice" bug at the source, per §4's structural rule.
2. **Replace `propagate.py`'s `combine_rss` / `combine_systematic_sum` / `combine_hybrid` /
   `propagate_serial`** with §5.1's general correlation-aware combiner and §5.2's precision-fusion
   serial update. Old rule IDs map onto the new model as: R1 (independent RSS) → §5.1 at ρ=0,
   exact; R2 (systematic sum) → §5.1 at ρ=1, exact; R3 (`combine_model_max`, currently dead code
   per the last audit) → superseded, drop rather than port, since max-of-two-doubts is a weaker
   special case of the general correlated-combination rule and was never wired in anyway; R4
   (hybrid total) → replaced by §5.1 + §5.3 (combine in raw space, saturate once at the end); R5
   (serial, `inherit_weight=0.35`) → replaced by §5.2's parameter-free precision fusion; R6
   (caution index) → replaced by the 3-axis scatter (§10.5), the scalar-caution product is
   deprecated but the "confidence never redefines uncertainty" guarantee it protected is
   preserved and *strengthened* (now applies to three axes, not two); R7 (claim packet) →
   composition of §5.2 (serial fusion into the claim) + §7 (R scored once at claim level) +
   §6 (full budget reported).
3. **Add the Evidence Reliability scorer** (§7) as a new module, `cieml/uncertainty/reliability.py`
   or similar, consuming Domain Configuration targets (§8) — independent of the M-axis rewrite,
   can land in parallel.
4. **Rewrite `visualize.py`** per §10 once the ledger schema carries budgets + provenance +
   the R axis.
5. **Regenerate the Visakhapatnam ledger and confirm the acceptance test in §9.6** — the
   confidence/M scatter must show visible spread, not a saturated cluster — before considering
   the migration complete.
6. **Version bump SC-UNC (or split into SC-MMU + SC-REL, per §12) only after step 5 passes.**
   Per this project's own contract rules, changing guarantees or outputs requires a version bump
   and a fresh reviewer checklist pass, not a silent rewrite.

Each step is independently testable and independently revertible; none requires the others to
land first except step 2 depending conceptually on step 1's provenance tagging being in place
(so the correlation rule in §5.1 has something to key off of).

---

## 12. Naming and contract recommendation

Agree with the proposed rename, with one refinement: rather than renaming the whole package
"Evidence Reliability Engine" (which would then have to also own Measurement & Model
Uncertainty, re-creating a two-things-one-name problem one level up), **split the public
identity into two sibling engines that share the `cieml.uncertainty` implementation surface**:

- **Measurement & Model Uncertainty (contract `SC-MMU`)** — owns §5's combination/propagation
  machinery, the budget fields in §6, provenance/correlation rules in §4.
- **Evidence Reliability Engine (contract `SC-REL`)** — owns §7's coverage scoring, sourced from
  Domain Configuration targets.

Both remain distinct from **EBSVE (`SC-EBSVE`)**'s Confidence axis, which is unchanged. This
gives the three-way split you described a **1:1 contract mapping** (Confidence → SC-EBSVE,
Measurement Uncertainty → SC-MMU, Evidence Reliability → SC-REL), which is the cleanest possible
story for a methods section: three named, independently-testable engines, three named axes, no
engine silently doing two jobs. `configs/framework.yaml`'s `scientific_contracts.engines` map
and `docs/contracts/README.md`'s index would each need one new row (`SC-MMU`) and `SC-UNC` would
be marked deprecated/split, pointing to both successors — a doc-only, mechanical change once
this design is adopted, not attempted here per your instruction not to touch anything until the
math is finalized.

---

## 13. Summary of what changes vs. what doesn't

| Element | v1 | v2 |
|---|---|---|
| Axes reported | Confidence, Uncertainty (1 blended axis) | Confidence, Measurement & Model Uncertainty, Evidence Reliability (3 independent axes) |
| Independent combination | RSS (R1) | RSS — **unchanged, now exact special case of one general rule** |
| Correlated combination | Ad hoc sum for "systematic-like" kinds (R2) | Declared-ρ GUM combination — **sum is the ρ=1 special case**, no more silent double-counting |
| Serial propagation | Fixed 35% inheritance + additive local (R5) | Precision-style (Kalman) fusion for corroborating evidence; additive-with-declared-ρ for new evidence — **can resolve, not just accumulate** |
| Bounding | Hard clip to [0,100] after every combination | Single smooth saturating map applied once, at report time only |
| Budget reporting | Single `total` per packet | Inherited / Resolved / New / Remaining / Net / Confidence-gained, telescoping exactly |
| Evidence completeness | Folded into "sampling"/"external" components inside the uncertainty sum | Separate, weighted-coverage axis (R), bounded by construction, scored once per claim from campaign design |
| Dashboard | 4 panels, 2 rendered uninformative by saturation | 5 panels: budget waterfall, source contribution, correlation graph, engine contribution, 3-axis scatter |
