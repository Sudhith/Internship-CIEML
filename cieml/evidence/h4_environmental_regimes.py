"""H4 — Environmental Regimes validator.

Question: does the coastline naturally organize into stable, interpretable
environmental regimes? Draws on Stage 6/7 regime discovery+validation, Stage 14's
own robustness battery (seed/scaling/clustering/feature/noise/permutation/LOSO
stress tests, computed live in the same run and passed in via `evidence`), Stage
12's ecological interpretation confidence, and Stage 11's spatial structure —
including the p-value-backed spatial-gradient significance test added specifically
so this pillar cannot be fooled by an n=6-station rho that looks strong but isn't
statistically distinguishable from noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cieml.evidence.base import EvidenceItem, HypothesisValidator, Pillar
from cieml.evidence.scoring import score_from_bands, score_from_fraction


class H4Validator(HypothesisValidator):
    hypothesis_id = "H4_environmental_regimes"

    def evaluate_statistical(self) -> Pillar:
        val = self.evidence.get("stage07_validation_report", {})
        boot = float(val.get("bootstrap_ari_mean", 0.0) or 0.0)
        loso = float(val.get("loso_ari_mean", 0.0) or 0.0)
        lowo = float(val.get("lowo_ari_mean", 0.0) or 0.0)
        perm_null = float(val.get("permutation_null_ari_mean", 1.0) or 1.0)

        sens: pd.DataFrame = self.evidence.get("stage14_sensitivity_results", pd.DataFrame())
        seed_rows = sens[sens.get("test_family") == "seed_stability"] if len(sens) else pd.DataFrame()
        seed_mean = float(seed_rows["value_mean"].mean()) if len(seed_rows) else np.nan

        boot_score = score_from_fraction(boot, good=0.8, bad=0.2)
        loso_score = score_from_fraction(loso, good=0.7, bad=0.2)
        lowo_score = score_from_fraction(lowo, good=0.7, bad=0.2)
        null_score = score_from_fraction(1 - perm_null, good=0.95, bad=0.5)
        seed_score = score_from_fraction(seed_mean, good=0.8, bad=0.3) if np.isfinite(seed_mean) else 50.0

        score = float(np.mean([boot_score, loso_score, lowo_score, null_score, seed_score]))
        return Pillar(
            name="statistical",
            score=score,
            evidence=[
                EvidenceItem("stage07_bootstrap_ari", boot, "stage07_validation_report.json", f"score={boot_score:.0f}"),
                EvidenceItem("stage07_loso_ari", loso, "stage07_validation_report.json", f"score={loso_score:.0f}"),
                EvidenceItem("stage07_lowo_ari", lowo, "stage07_validation_report.json", f"score={lowo_score:.0f}"),
                EvidenceItem("permutation_null_ari", perm_null, "stage07_validation_report.json", f"beats_null score={null_score:.0f}"),
                EvidenceItem("stage14_seed_stability_ari", seed_mean, "stage14 sensitivity battery (live)", f"score={seed_score:.0f}"),
            ],
            reasoning=f"bootstrap ARI={boot:.2f}, LOSO={loso:.2f}, LOWO={lowo:.2f}, permutation null={perm_null:.3f}",
            weaknesses=[] if score >= 75 else ["Regime-recovery ARI under resampling/leave-out tests is not strongly stable."],
        )

    def evaluate_practical(self) -> Pillar:
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
            name="practical",
            score=score,
            evidence=[
                EvidenceItem("robustness_frac_pass", robustness_frac, "stage14 sensitivity battery (live)", f"{len(scored)} tests; score={robustness_score:.0f}"),
                EvidenceItem("critical_checks_passed", f"{n_critical_pass}/{n_critical}", "stage14 critical checks (live)", f"score={critical_score:.0f}"),
            ],
            reasoning=f"{robustness_frac:.0%} of stress tests pass; {n_critical_pass}/{n_critical} critical checks pass",
            weaknesses=[] if score >= 70 else ["Regime structure is sensitive to a meaningful share of the stress-test perturbations."],
        )

    def evaluate_physical(self) -> Pillar:
        interps: list = self.evidence.get("stage12_interpretations", [])
        if not interps:
            return Pillar(
                name="physical", score=0.0,
                evidence=[EvidenceItem("regime_interpretations", 0, "stage12_interpretation_detail.json", "no data")],
                reasoning="No regime interpretations available from Stage 12.",
                weaknesses=["Stage 12 ecological interpretation has not run or produced no output."],
            )
        confidences = [i.get("confidence") for i in interps]
        n_named = sum(1 for c in confidences if c in {"supported", "provisional"})
        named_frac = n_named / len(confidences)
        mean_evidence_score = float(np.mean([i.get("evidence_score", 0.0) for i in interps]))
        # evidence_score is uncapped in stage12 (roughly 0-5 in practice); normalize
        # against the "supported" cutoff (3.5) used there so 3.5 maps near 80/100.
        evidence_score_norm = score_from_bands(mean_evidence_score, [(3.5, 90.0), (2.5, 70.0), (2.0, 50.0), (0.0, 20.0)])
        named_score = score_from_fraction(named_frac, good=1.0, bad=0.3)
        score = float(np.mean([named_score, evidence_score_norm]))
        unnamed = [i.get("regime") for i in interps if i.get("confidence") not in {"supported", "provisional"}]
        return Pillar(
            name="physical",
            score=score,
            evidence=[
                EvidenceItem("regimes_with_named_interpretation", f"{n_named}/{len(confidences)}", "stage12_interpretation_detail.json", f"score={named_score:.0f}"),
                EvidenceItem("mean_evidence_score", mean_evidence_score, "stage12_interpretation_detail.json", f"score={evidence_score_norm:.0f}"),
            ],
            reasoning=f"{n_named}/{len(confidences)} regimes have a named, evidence-backed interpretive family (mean evidence score {mean_evidence_score:.1f})",
            weaknesses=[f"Regime(s) without a defensible physical interpretation: {unnamed}"] if unnamed else [],
        )

    def evaluate_environmental(self) -> Pillar:
        gradients: pd.DataFrame = self.evidence.get("stage11_spatial_gradients", pd.DataFrame())
        st_report = self.evidence.get("stage11_spatial_temporal_report", {})

        if len(gradients) and "significant_05" in gradients.columns:
            sig_frac = float(gradients["significant_05"].mean())
        else:
            sig_frac = 0.0
        sig_score = score_from_fraction(sig_frac, good=0.3, bad=0.0)

        n_edges = int(st_report.get("n_network_edges", 0) or 0)
        n_stations = int(st_report.get("n_stations", 6) or 6)
        max_edges = n_stations * (n_stations - 1) / 2
        edge_frac = n_edges / max_edges if max_edges else 0.0
        # A similarity network that is neither empty (no structure at all) nor
        # fully connected (every station indistinguishable) indicates genuine
        # spatial organization; score peaks at a moderate, non-trivial edge density.
        structure_score = score_from_bands(1 - abs(edge_frac - 0.4), [(0.85, 100.0), (0.7, 70.0), (0.5, 40.0), (0.0, 15.0)])

        score = float(np.mean([sig_score, structure_score]))
        return Pillar(
            name="environmental",
            score=score,
            evidence=[
                EvidenceItem(
                    "significant_spatial_gradients_frac",
                    sig_frac,
                    "stage11_spatial_gradients.csv (p-value-tested, n=6 stations)",
                    f"fraction of feature-axis gradients significant at p<0.05; score={sig_score:.0f}",
                ),
                EvidenceItem("station_similarity_network_edge_density", edge_frac, "stage11_spatial_temporal_report.json", f"{n_edges}/{int(max_edges)} possible edges; score={structure_score:.0f}"),
            ],
            reasoning=f"{sig_frac:.0%} of tested spatial gradients are statistically significant (n=6 stations); network edge density={edge_frac:.2f}",
            weaknesses=["Most 'spatial gradient' correlations at n=6 stations are not statistically significant — treat as suggestive, not confirmatory."] if sig_frac < 0.2 else [],
        )

    def generate_limitations(self, pillars):
        base = super().generate_limitations(pillars)
        return base + [
            "Spatial-gradient significance is tested with only 6 stations; even a real coastline "
            "gradient may fail to clear p<0.05 at this sample size (low power, not necessarily absence of effect).",
        ]
