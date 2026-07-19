"""H5 — Anomaly Reality validator.

Question: are detected anomalies genuine environmental events rather than sensor
artifacts? Draws on Stage 9's multi-method consensus detection (including the
genuinely data-driven contamination grid search) and Stage 10's external
meteorological validation (including the FDR-corrected cross-correlation count,
not just the raw uncorrected significant-test count).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cieml.evidence.base import EvidenceItem, HypothesisValidator, Pillar
from cieml.evidence.scoring import score_from_bands, score_from_fraction


class H5Validator(HypothesisValidator):
    hypothesis_id = "H5_anomaly_reality"

    def evaluate_statistical(self) -> Pillar:
        rep9 = self.evidence.get("stage09_anomaly_report", {})
        grid = rep9.get("contamination_grid_scores", {}) or {}
        best_agreement = float(max(grid.values())) if grid else 0.0
        consensus_rate = float(rep9.get("consensus_rate", 0.0) or 0.0)

        agreement_score = score_from_fraction(best_agreement, good=0.9, bad=0.5)
        # A healthy consensus rate is neither ~0 (detectors never agree — no
        # structure) nor ~1 (everything flagged — the "anomaly" label is meaningless).
        rate_score = score_from_bands(1 - abs(consensus_rate - 0.10), [(0.85, 100.0), (0.6, 60.0), (0.0, 20.0)])

        score = float(np.mean([agreement_score, rate_score]))
        return Pillar(
            name="statistical",
            score=score,
            evidence=[
                EvidenceItem("best_cross_detector_agreement", best_agreement, "stage09_anomaly_report.json:contamination_grid_scores", f"score={agreement_score:.0f}"),
                EvidenceItem("consensus_anomaly_rate", consensus_rate, "stage09_anomaly_report.json", f"score={rate_score:.0f}"),
            ],
            reasoning=f"best cross-detector agreement={best_agreement:.2f}, consensus rate={consensus_rate:.2%}",
            weaknesses=[] if score >= 70 else ["Detector agreement or consensus rate is not in the well-behaved range."],
        )

    def evaluate_practical(self) -> Pillar:
        rep9 = self.evidence.get("stage09_anomaly_report", {})
        catalog: pd.DataFrame = self.evidence.get("stage09_anomaly_catalog", pd.DataFrame())
        n_consensus = int(rep9.get("n_consensus_anomalies", 0) or 0)
        n_samples = int(rep9.get("n_samples", 0) or 0)
        actionable = n_samples > 0 and 0 < n_consensus < n_samples * 0.3
        actionable_score = 100.0 if actionable else (40.0 if n_consensus > 0 else 0.0)

        cat_counts = rep9.get("category_counts", {}) or {}
        n_categories = len([c for c in cat_counts if c != "multivariate_outlier"])
        diversity_score = score_from_bands(n_categories, [(3, 100.0), (2, 75.0), (1, 45.0), (0, 15.0)])

        score = float(np.mean([actionable_score, diversity_score]))
        return Pillar(
            name="practical",
            score=score,
            evidence=[
                EvidenceItem("n_consensus_anomalies", n_consensus, "stage09_anomaly_report.json", f"of {n_samples} station-days; score={actionable_score:.0f}"),
                EvidenceItem("n_distinct_physical_categories", n_categories, "stage09_anomaly_report.json:category_counts", f"excluding generic 'multivariate_outlier'; score={diversity_score:.0f}"),
            ],
            reasoning=f"{n_consensus}/{n_samples} station-days flagged, spanning {n_categories} specific physical categories",
            weaknesses=[] if score >= 60 else ["Anomaly catalog is either empty, saturated, or dominated by an uninformative generic category."],
        )

    def evaluate_physical(self) -> Pillar:
        rep9 = self.evidence.get("stage09_anomaly_report", {})
        cat_counts = rep9.get("category_counts", {}) or {}
        total = sum(cat_counts.values())
        n_generic = cat_counts.get("multivariate_outlier", 0)
        specific_frac = 1 - (n_generic / total) if total else 0.0
        score = score_from_fraction(specific_frac, good=0.7, bad=0.2)
        return Pillar(
            name="physical",
            score=score,
            evidence=[
                EvidenceItem(
                    "specific_physical_class_fraction",
                    specific_frac,
                    "stage09_anomaly_report.json:category_counts",
                    f"{total - n_generic}/{total} anomalies map to a specific physical mechanism (not generic multivariate); score={score:.0f}",
                )
            ],
            reasoning=f"{specific_frac:.0%} of consensus anomalies have a specific physical-class label",
            weaknesses=[] if score >= 60 else ["Most anomalies fall into the generic 'multivariate_outlier' bucket with no specific physical mechanism assigned."],
        )

    def evaluate_environmental(self) -> Pillar:
        rep10 = self.evidence.get("stage10_external_report", {})
        support_frac = rep10.get("anomaly_external_support_frac")
        support_frac = float(support_frac) if support_frac is not None else None
        n_sig_fdr = int(rep10.get("n_significant_crosscorr_fdr_05", 0) or 0)
        n_tests = int(rep10.get("n_crosscorr_tests", 0) or 0)
        fdr_frac = (n_sig_fdr / n_tests) if n_tests else 0.0

        support_score = score_from_fraction(support_frac, good=0.6, bad=0.0) if support_frac is not None else 0.0
        # Baseline expectation under FDR control is ~5%; meaningfully more than that
        # is real signal beyond the false-discovery rate the correction already budgets for.
        fdr_score = score_from_bands(fdr_frac, [(0.30, 100.0), (0.15, 75.0), (0.05, 45.0), (0.0, 15.0)])

        score = float(np.mean([support_score, fdr_score]))
        return Pillar(
            name="environmental",
            score=score,
            evidence=[
                EvidenceItem("anomaly_external_support_frac", support_frac, "stage10_external_report.json", f"score={support_score:.0f}"),
                EvidenceItem("fdr_significant_crosscorr_frac", fdr_frac, "stage10_external_report.json (FDR-corrected)", f"{n_sig_fdr}/{n_tests}; score={fdr_score:.0f}"),
            ],
            reasoning=(
                f"external meteo support={support_frac:.0%}" if support_frac is not None else "no anomaly-catalog external enrichment available"
            ) + f"; FDR-significant env-meteo cross-correlations={fdr_frac:.0%}",
            weaknesses=[] if score >= 60 else ["External meteorological corroboration for anomalies is weak or unavailable."],
        )

    def generate_limitations(self, pillars):
        base = super().generate_limitations(pillars)
        return base + [
            "External validation uses a single regional Open-Meteo point, not station-resolved forcing "
            "(tide, local runoff, harbour operations are not observed).",
        ]
