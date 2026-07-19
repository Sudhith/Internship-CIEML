"""H6 — Policy Transferability validator.

Question: do monitoring recommendations transfer as stated rules with explicit
limits, rather than as site-specific numeric thresholds? This validator checks
Stage 13's actual decision-support output for concrete evidence of transferability
— sensor mappings that resolve to real hardware, decision rules that cover both
the harbour/hypoxic and open-coast/turbid failure modes (no blind spot), and an
applicability domain that says something specific rather than a generic disclaimer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cieml.evidence.base import EvidenceItem, HypothesisValidator, Pillar
from cieml.evidence.scoring import score_from_bands, score_from_fraction

# Fallback keywords only cover a genuinely absent domain profile
# (FileNotFoundError) — a ValueError from schema validation must propagate
# rather than silently reverting this claim-agnostic validator to hardcoded
# Visakhapatnam-shaped keyword literals (same reasoning as h3_feature_redundancy).
def _decision_keywords():
    try:
        from cieml.domain import get_default_domain
        d = get_default_domain()
        kw = d.decision_keywords
        return set(kw.get("harbour_hypoxia") or {"harbour", "hypox", "do", "oxygen", "ph"}), set(
            kw.get("turbid_open_coast") or {"turbid", "salinity", "freshwater", "sediment", "rainfall"}
        )
    except FileNotFoundError:
        return {"harbour", "hypox", "do", "oxygen", "ph"}, {"turbid", "salinity", "freshwater", "sediment", "rainfall"}

HARBOUR_HYPOXIA_KEYWORDS, TURBID_OPEN_COAST_KEYWORDS = _decision_keywords()


class H6Validator(HypothesisValidator):
    hypothesis_id = "H6_policy_transfer"

    def evaluate_statistical(self) -> Pillar:
        # Policy recommendations are only as trustworthy as the regime/anomaly
        # analysis they're built on — reuse the same live robustness evidence H4 uses,
        # framed here as confidence in the recommendations rather than in the regimes
        # themselves.
        sens: pd.DataFrame = self.evidence.get("stage14_sensitivity_results", pd.DataFrame())
        critical: dict = self.evidence.get("stage14_critical_checks", {})
        scored = sens[sens.get("result").isin(["pass", "fail"])] if len(sens) else pd.DataFrame()
        robustness_frac = float((scored["result"] == "pass").mean()) if len(scored) else 0.0
        n_critical_pass = sum(1 for v in critical.values() if v)
        n_critical = len(critical) or 1

        robustness_score = score_from_fraction(robustness_frac, good=0.85, bad=0.4)
        critical_score = score_from_fraction(n_critical_pass / n_critical, good=1.0, bad=0.5)
        score = float(np.mean([robustness_score, critical_score]))
        return Pillar(
            name="statistical",
            score=score,
            evidence=[
                EvidenceItem("underlying_robustness_frac_pass", robustness_frac, "stage14 sensitivity battery (live, shared with H4)", f"score={robustness_score:.0f}"),
                EvidenceItem("underlying_critical_checks_passed", f"{n_critical_pass}/{n_critical}", "stage14 critical checks (live)", f"score={critical_score:.0f}"),
            ],
            reasoning=f"Recommendations rest on regime/anomaly findings with {robustness_frac:.0%} stress-test pass rate",
            weaknesses=[] if score >= 70 else ["The regime/anomaly evidence base that recommendations rest on is not strongly robust."],
        )

    def evaluate_practical(self) -> Pillar:
        rep = self.evidence.get("stage13_decision_support_report", {})
        prio = rep.get("sensor_prioritization", []) or []
        budget = rep.get("budget_tiers", []) or []

        n_prio = len(prio)
        n_named_sensor = sum(1 for p in prio if p.get("sensor_family") and p.get("sensor_family") != "Other")
        named_frac = (n_named_sensor / n_prio) if n_prio else 0.0
        named_score = score_from_fraction(named_frac, good=1.0, bad=0.5)

        essential = next((t for t in budget if t.get("tier") == "Essential"), {})
        n_essential = len(essential.get("sensors", []) or [])
        # A deployable "essential" package should be a small, non-empty, non-full subset.
        essential_score = score_from_bands(-abs(n_essential - 2), [(0, 100.0), (-1, 75.0), (-2, 45.0), (-1e9, 10.0)]) if n_essential else 0.0

        score = float(np.mean([named_score, essential_score]))
        return Pillar(
            name="practical",
            score=score,
            evidence=[
                EvidenceItem("sensors_mapped_to_real_hardware_family", named_frac, "stage13_decision_support_report.json:sensor_prioritization", f"{n_named_sensor}/{n_prio}; score={named_score:.0f}"),
                EvidenceItem("essential_tier_size", n_essential, "stage13_decision_support_report.json:budget_tiers", f"score={essential_score:.0f}"),
            ],
            reasoning=f"{n_named_sensor}/{n_prio} prioritized measurands map to a named deployable sensor family; Essential tier has {n_essential} sensor families",
            weaknesses=[] if score >= 60 else ["Sensor prioritization does not clearly resolve to a small, deployable hardware package."],
        )

    def evaluate_physical(self) -> Pillar:
        rules: pd.DataFrame = self.evidence.get("stage13_decision_rules", pd.DataFrame())
        if len(rules):
            text = (rules.get("if", "").astype(str) + " " + rules.get("then", "").astype(str)).str.lower()
        else:
            text = pd.Series(dtype=str)

        covers_harbour = bool(text.apply(lambda t: any(k in t for k in HARBOUR_HYPOXIA_KEYWORDS)).any())
        covers_turbid = bool(text.apply(lambda t: any(k in t for k in TURBID_OPEN_COAST_KEYWORDS)).any())
        n_covered = int(covers_harbour) + int(covers_turbid)
        score = score_from_bands(n_covered, [(2, 100.0), (1, 50.0), (0, 0.0)])
        missing = [] if n_covered == 2 else (["harbour/hypoxic scenario"] if not covers_harbour else []) + (["turbid/open-coast scenario"] if not covers_turbid else [])
        return Pillar(
            name="physical",
            score=score,
            evidence=[
                EvidenceItem(
                    "decision_rules_cover_both_regime_failure_modes",
                    n_covered,
                    "stage13_decision_rules.csv",
                    f"harbour/hypoxic={covers_harbour}, turbid/open-coast={covers_turbid}; score={score:.0f}",
                )
            ],
            reasoning=(
                "Decision rules explicitly address both the harbour/hypoxic and turbid/open-coast regime types."
                if n_covered == 2
                else f"Decision rules do not address: {', '.join(missing)} — a monitoring blind spot."
            ),
            weaknesses=[f"No decision rule addresses the {m}" for m in missing],
        )

    def evaluate_environmental(self) -> Pillar:
        domain = self.evidence.get("stage13_applicability_domain", {})
        applies_to = domain.get("applies_to", []) or []
        does_not = domain.get("does_not_apply_to", []) or []
        transfer_rule = str(domain.get("transfer_rule", "") or "")

        has_applies = len(applies_to) >= 2
        has_excludes = len(does_not) >= 2
        # A concrete transfer rule instructs re-running/reusing something specific,
        # rather than a vague "use with caution" — checked via a small verb whitelist.
        concrete_rule = any(v in transfer_rule.lower() for v in ["re-run", "rerun", "reuse", "re-fit", "refit"])

        n_specific = sum([has_applies, has_excludes, concrete_rule])
        score = score_from_bands(n_specific, [(3, 100.0), (2, 70.0), (1, 40.0), (0, 0.0)])
        gaps = []
        if not has_applies:
            gaps.append("applies_to is thin (<2 stated contexts)")
        if not has_excludes:
            gaps.append("does_not_apply_to is thin (<2 stated exclusions)")
        if not concrete_rule:
            gaps.append("transfer_rule does not specify a concrete re-run/reuse action")
        return Pillar(
            name="environmental",
            score=score,
            evidence=[
                EvidenceItem("applicability_domain_specificity", n_specific, "stage13_applicability_domain.json", f"of 3 specificity checks; score={score:.0f}"),
            ],
            reasoning=f"Applicability domain states {len(applies_to)} applicable context(s), {len(does_not)} exclusion(s), concrete transfer rule={concrete_rule}",
            weaknesses=gaps,
        )

    def generate_assumptions(self) -> list[str]:
        return [
            "Harbour/hypoxic vs turbid/open-coast keyword sets used to check decision-rule coverage "
            "are a fixed, documented vocabulary, not learned from data.",
        ]
