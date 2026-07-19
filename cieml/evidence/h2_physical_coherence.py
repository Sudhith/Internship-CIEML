"""H2 — Physical Coherence validator.

Question: do expected coastal oceanographic relationships hold within the data?
Every pillar is computed from Stage 3 artifacts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cieml.evidence.base import EvidenceItem, HypothesisValidator, Pillar
from cieml.evidence.scoring import score_from_bands, score_from_fraction


class H2Validator(HypothesisValidator):
    hypothesis_id = "H2_physical_coherence"

    def evaluate_statistical(self) -> Pillar:
        rep = self.evidence.get("stage03_physical_report", {})
        support_rate = float(rep.get("support_rate_required", 0.0) or 0.0)
        n_broken = int(rep.get("n_required_broken", 0) or 0)
        n_required = int(rep.get("n_required_pairs", 0) or 0)

        support_score = score_from_fraction(support_rate, good=1.0, bad=0.4)
        broken_score = score_from_bands(-n_broken, [(0, 100.0), (-1, 60.0), (-2, 20.0)])
        score = float(np.mean([support_score, broken_score]))
        return Pillar(
            name="statistical",
            score=score,
            evidence=[
                EvidenceItem("support_rate_required_pairs", support_rate, "stage03_physical_report.json", f"score={support_score:.0f}"),
                EvidenceItem("n_required_pairs_broken", n_broken, "stage03_physical_report.json", f"of {n_required} required pairs; score={broken_score:.0f}"),
            ],
            reasoning=f"{support_rate:.0%} of {n_required} required physical pairs supported; {n_broken} broken",
            weaknesses=[] if score >= 80 else ["Required physical-relationship support rate is below the strong-evidence band."],
        )

    def evaluate_practical(self) -> Pillar:
        pairs: pd.DataFrame = self.evidence.get("stage03_physical_pairs", pd.DataFrame())
        if len(pairs):
            required = pairs[~pairs.get("optional", pd.Series(dtype=bool)).fillna(False)]
            rhos = pd.to_numeric(required.get("rho", pd.Series(dtype=float)), errors="coerce").dropna()
        else:
            rhos = pd.Series(dtype=float)
        mean_abs_rho = float(rhos.abs().mean()) if len(rhos) else 0.0
        # Effect-size bands (Cohen-style), not p-values: with n~50k, p<0.05 is nearly
        # guaranteed for any real relationship, so statistical significance alone would
        # tell us nothing about whether a relationship is practically meaningful.
        score = score_from_bands(mean_abs_rho, [(0.5, 100.0), (0.3, 75.0), (0.1, 45.0), (0.0, 15.0)])
        return Pillar(
            name="practical",
            score=score,
            evidence=[
                EvidenceItem(
                    "mean_abs_rho_required_pairs",
                    mean_abs_rho,
                    "stage03_physical_pairs.csv",
                    f"effect-size band (not p-value); score={score:.0f}",
                )
            ],
            reasoning=f"mean |rho| across required pairs = {mean_abs_rho:.3f} (n~{int(rhos.notna().sum()) if len(rhos) else 0})",
            weaknesses=[] if score >= 70 else ["Correlations are statistically detectable but practically small (low effect size)."],
        )

    def evaluate_physical(self) -> Pillar:
        pairs: pd.DataFrame = self.evidence.get("stage03_physical_pairs", pd.DataFrame())
        broken = pairs[pairs.get("status", pd.Series(dtype=str)) == "Broken"] if len(pairs) else pd.DataFrame()
        n_broken = int(len(broken))
        score = float(max(0.0, 100.0 - 35.0 * n_broken))
        details = [f"{r['x']}~{r['y']}: {r.get('detail')}" for _, r in broken.iterrows()]
        return Pillar(
            name="physical",
            score=score,
            evidence=[
                EvidenceItem("n_pairs_with_wrong_sign", n_broken, "stage03_physical_pairs.csv:status=Broken", "; ".join(details) if details else "none"),
            ],
            reasoning="No expected relationship shows the wrong sign." if n_broken == 0 else f"{n_broken} relationship(s) contradict the expected mechanism: {'; '.join(details)}",
            weaknesses=details,
        )

    def evaluate_environmental(self) -> Pillar:
        stability: pd.DataFrame = self.evidence.get("stage03_station_pair_stability", pd.DataFrame())
        pairs: pd.DataFrame = self.evidence.get("stage03_physical_pairs", pd.DataFrame())
        if not len(stability) or not len(pairs):
            return Pillar(
                name="environmental",
                score=0.0,
                evidence=[EvidenceItem("station_pair_stability", None, "stage03_station_pair_stability.csv", "no data")],
                reasoning="No station-level stability data available.",
                weaknesses=["stage03_station_pair_stability.csv is missing or empty."],
            )
        campaign_sign = {}
        for _, r in pairs.iterrows():
            key = f"{r['x']}~{r['y']}"
            rho = r.get("rho")
            if pd.notna(rho):
                campaign_sign[key] = np.sign(rho)
        matches = []
        for _, r in stability.iterrows():
            pair, rho = r.get("pair"), r.get("rho")
            if pair in campaign_sign and pd.notna(rho):
                matches.append(np.sign(rho) == campaign_sign[pair])
        consistency = float(np.mean(matches)) if matches else 0.0
        score = score_from_fraction(consistency, good=1.0, bad=0.5)
        by_pair = (
            stability.assign(campaign_sign_match=[
                (np.sign(r.get("rho")) == campaign_sign.get(r.get("pair"))) if pd.notna(r.get("rho")) and r.get("pair") in campaign_sign else None
                for _, r in stability.iterrows()
            ])
        )
        inconsistent_pairs = sorted(set(by_pair.loc[by_pair["campaign_sign_match"] == False, "pair"]))  # noqa: E712
        return Pillar(
            name="environmental",
            score=score,
            evidence=[
                EvidenceItem(
                    "station_sign_consistency",
                    consistency,
                    "stage03_station_pair_stability.csv",
                    f"fraction of (station, pair) combos matching the campaign-level sign; score={score:.0f}",
                )
            ],
            reasoning=f"{consistency:.0%} of station-level relationships match the campaign-wide sign across 6 stations",
            weaknesses=[f"Sign is not stable across stations for: {', '.join(inconsistent_pairs)}"] if inconsistent_pairs else [],
        )

    def generate_limitations(self, pillars):
        base = super().generate_limitations(pillars)
        return base + [
            "Physical relationships are tested on raw high-frequency readings (n~51k), not station-day "
            "aggregates — statistical significance at this sample size is near-automatic, which is why "
            "the practical pillar uses effect-size bands rather than p-values.",
        ]
