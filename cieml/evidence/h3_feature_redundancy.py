"""H3 — Information Redundancy validator.

Question: is a reduced feature set informationally sufficient (no unique signal
lost) while removing redundant measurement channels? Every pillar computed from
Stage 4/5 artifacts; the statistical pillar recomputes VIF fresh on the *final*
retained matrix rather than trusting the pre-pruning stage05_vif.csv snapshot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cieml.evidence.base import EvidenceItem, HypothesisValidator, Pillar
from cieml.evidence.scoring import score_from_bands, score_from_fraction

# Domain-sourced priors (Phase B). Fallback constants only cover a genuinely
# absent profile (FileNotFoundError) — a ValueError from schema validation
# (e.g. a domain profile missing a required key) is deliberately NOT caught
# here, so a broken profile fails loudly instead of this "claim-agnostic"
# validator silently reverting to hardcoded Visakhapatnam-shaped literals.
def _domain_groups():
    try:
        from cieml.domain import get_default_domain
        d = get_default_domain()
        return list(d.physical_equivalence_groups), dict(d.process_categories)
    except FileNotFoundError:
        return [
            {"salinity_psu", "spcond_us_cm", "conductivity_us_cm", "tds_mg_l", "nlf_cond_us_cm"},
            {"do_mg_l", "do_sat_pct"},
        ], {
            "thermal": ["temperature_c"],
            "oxygen": ["do_mg_l", "do_sat_pct", "do_solubility", "do_sat_gap"],
            "salinity_ionic": ["salinity_psu", "spcond_us_cm", "conductivity_us_cm", "tds_mg_l", "mixing_contrast"],
            "turbidity": ["turbidity_fnu", "mixing_contrast"],
            "ph_carbonate": ["ph", "carbonate_thermal"],
        }

PHYSICAL_EQUIVALENCE_GROUPS, PROCESS_CATEGORIES = _domain_groups()


def _base_var(feature: str) -> str:
    return feature.split("__")[0].replace("idx_", "")


class H3Validator(HypothesisValidator):
    hypothesis_id = "H3_information_redundancy"

    def evaluate_statistical(self) -> Pillar:
        rep = self.evidence.get("stage05_statistical_report", {})
        factor = rep.get("factorability", {})
        kmo = float(factor.get("kmo_model", 0.0) or 0.0)
        bartlett_p = float(factor.get("bartlett_p", 1.0) if factor.get("bartlett_p") is not None else 1.0)
        kmo_score = score_from_bands(kmo, [(0.8, 100.0), (0.7, 90.0), (0.6, 75.0), (0.5, 55.0), (0.0, 20.0)])
        bartlett_score = 100.0 if bartlett_p < 0.05 else 0.0

        max_vif, vif_note = self._final_vif()
        vif_score = score_from_bands(-max_vif, [(-5.0, 100.0), (-10.0, 75.0), (-20.0, 40.0), (-1e9, 0.0)])

        score = float(np.mean([kmo_score, bartlett_score, vif_score]))
        return Pillar(
            name="statistical",
            score=score,
            evidence=[
                EvidenceItem("kmo_model", kmo, "stage05_statistical_report.json:factorability", f"score={kmo_score:.0f}"),
                EvidenceItem("bartlett_p", bartlett_p, "stage05_statistical_report.json:factorability", f"score={bartlett_score:.0f}"),
                EvidenceItem("max_vif_final_retained_set", max_vif, "recomputed from stage05_retained_feature_matrix.csv", f"{vif_note}; score={vif_score:.0f}"),
            ],
            reasoning=f"KMO={kmo:.3f}, Bartlett p={bartlett_p:.2e}, max VIF on final retained set={max_vif:.1f}",
            weaknesses=[] if score >= 80 else ["Factorability or final-set multicollinearity is below the strong-evidence band."],
        )

    def _final_vif(self) -> tuple[float, str]:
        matrix: pd.DataFrame = self.evidence.get("stage05_retained_feature_matrix", pd.DataFrame())
        meta = {"station", "sample_date"}
        cols = [c for c in matrix.columns if c not in meta]
        if len(matrix) < 5 or len(cols) < 2:
            return float("nan"), "insufficient data to recompute"
        try:
            from sklearn.preprocessing import StandardScaler
            from statsmodels.stats.outliers_influence import variance_inflation_factor

            X = matrix[cols].apply(pd.to_numeric, errors="coerce").dropna()
            if len(X) < 5:
                return float("nan"), "insufficient complete rows"
            Xs = StandardScaler().fit_transform(X)
            vifs = [variance_inflation_factor(Xs, i) for i in range(Xs.shape[1])]
            finite = [v for v in vifs if np.isfinite(v)]
            max_vif = float(max(vifs)) if not any(np.isinf(v) for v in vifs) else float("inf")
            return max_vif, f"n_features={len(cols)}, n_inf={sum(1 for v in vifs if np.isinf(v))}, max_finite={max(finite) if finite else float('nan'):.1f}"
        except Exception as exc:  # noqa: BLE001
            return float("nan"), f"VIF recomputation failed: {exc}"

    def evaluate_practical(self) -> Pillar:
        rep = self.evidence.get("stage05_statistical_report", {})
        retained = rep.get("retained_features", []) or []
        base_vars_retained = {_base_var(f) for f in retained if not str(f).startswith("idx_")}
        # 8 base sonde channels were candidates for engineering (see stage04.BASE_VARS);
        # a raw-channel count below that measures genuine deployable sensor reduction.
        n_base_candidates = 8
        reduction = 1.0 - (len(base_vars_retained) / n_base_candidates)
        score = score_from_fraction(reduction, good=0.3, bad=0.0)
        return Pillar(
            name="practical",
            score=score,
            evidence=[
                EvidenceItem(
                    "raw_sensor_channel_reduction",
                    reduction,
                    "stage05_statistical_report.json:retained_features",
                    f"{len(base_vars_retained)}/{n_base_candidates} raw channels retained; score={score:.0f}",
                )
            ],
            reasoning=f"Raw measurement channels reduced from {n_base_candidates} to {len(base_vars_retained)} ({reduction:.0%} reduction)",
            weaknesses=[] if score >= 60 else ["Little to no deployable sensor-channel reduction achieved."],
        )

    def evaluate_physical(self) -> Pillar:
        decisions: pd.DataFrame = self.evidence.get("stage05_feature_decisions", pd.DataFrame())
        removed = decisions[decisions.get("decision", pd.Series(dtype=str)).astype(str).str.startswith("remove")] if len(decisions) else pd.DataFrame()
        retained_bases = {
            _base_var(f) for f in decisions.loc[decisions.get("decision") == "retain", "feature"]
        } if len(decisions) else set()

        justified, unjustified = [], []
        for _, r in removed.iterrows():
            removed_base = _base_var(r["feature"])
            group = next((g for g in PHYSICAL_EQUIVALENCE_GROUPS if removed_base in g), None)
            if group and (group & retained_bases):
                justified.append(str(r["feature"]))
            else:
                unjustified.append(str(r["feature"]))
        n_removed = len(justified) + len(unjustified)
        frac_justified = (len(justified) / n_removed) if n_removed else 1.0
        score = score_from_fraction(frac_justified, good=1.0, bad=0.5)
        return Pillar(
            name="physical",
            score=score,
            evidence=[
                EvidenceItem(
                    "removed_features_physically_justified",
                    frac_justified,
                    "stage05_feature_decisions.csv + documented equivalence groups",
                    f"justified={justified}, unjustified={unjustified}; score={score:.0f}",
                )
            ],
            reasoning=(
                "Every removed feature belongs to the same physical-equivalence group as a "
                "feature that was retained (e.g. conductivity family -> salinity; DO% -> DO mg/L)."
                if not unjustified
                else f"{len(unjustified)} removed feature(s) lack a documented physical-equivalence justification: {unjustified}"
            ),
            weaknesses=[f"No documented physical equivalence for removed feature(s): {unjustified}"] if unjustified else [],
        )

    def evaluate_environmental(self) -> Pillar:
        rep = self.evidence.get("stage05_statistical_report", {})
        retained = rep.get("retained_features", []) or []
        bases = {_base_var(f) for f in retained}
        covered = [cat for cat, members in PROCESS_CATEGORIES.items() if bases & set(members)]
        score = score_from_fraction(len(covered) / len(PROCESS_CATEGORIES), good=1.0, bad=0.4)
        missing = [cat for cat in PROCESS_CATEGORIES if cat not in covered]
        return Pillar(
            name="environmental",
            score=score,
            evidence=[
                EvidenceItem(
                    "coastal_process_categories_covered",
                    len(covered),
                    "stage05_statistical_report.json:retained_features vs documented process-category map",
                    f"covered={covered}; of {len(PROCESS_CATEGORIES)} categories; score={score:.0f}",
                )
            ],
            reasoning=f"Retained set spans {len(covered)}/{len(PROCESS_CATEGORIES)} coastal-process categories",
            weaknesses=[f"No retained feature represents: {missing}"] if missing else [],
        )

    def generate_assumptions(self) -> list[str]:
        return [
            "Physical-equivalence groups (conductivity family, DO family) and coastal-process "
            "categories are a documented, fixed domain mapping in this validator, not learned from data.",
        ]
