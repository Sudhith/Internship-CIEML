"""H1 — Data Trustworthiness validator.

Question this hypothesis answers: after QA/QC, does the record support scientific
inference? Every pillar below is computed from Stage 0/1/2 artifacts — none is a
hardcoded constant.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cieml.evidence.base import EvidenceItem, HypothesisValidator, Pillar
from cieml.evidence.scoring import score_from_bands, score_from_fraction


class H1Validator(HypothesisValidator):
    hypothesis_id = "H1_data_trustworthiness"

    def evaluate_statistical(self) -> Pillar:
        var_summary: pd.DataFrame = self.evidence.get("stage01_variable_summary", pd.DataFrame())
        qa_issues: pd.DataFrame = self.evidence.get("stage01_qa_issues", pd.DataFrame())
        qa1 = self.evidence.get("stage01_qa_report", {})
        stage02_sens: pd.DataFrame = self.evidence.get("stage02_sensitivity", pd.DataFrame())

        mean_missing = float(var_summary["missing_frac"].mean()) if len(var_summary) else 1.0
        missing_score = score_from_fraction(1 - mean_missing, good=1.0, bad=0.85)

        n_obs = int(qa1.get("n_observations", 0)) or 1
        dup_row = qa_issues[qa_issues.get("category", pd.Series(dtype=str)) == "duplicates"] if len(qa_issues) else pd.DataFrame()
        n_dup = 0
        if len(dup_row):
            detail = str(dup_row.iloc[0].get("detail", ""))
            for tok in detail.split(";"):
                if "n_duplicate_keys=" in tok:
                    try:
                        n_dup = int(tok.split("=")[-1])
                    except ValueError:
                        n_dup = 0
        dup_frac = n_dup / n_obs
        dup_score = score_from_fraction(1 - dup_frac, good=1.0, bad=0.95)

        max_rel_change = float(stage02_sens["abs_rel_change"].max()) if len(stage02_sens) else 1.0
        stability_score = score_from_fraction(1 - max_rel_change, good=1.0, bad=0.90)

        score = float(np.mean([missing_score, dup_score, stability_score]))
        return Pillar(
            name="statistical",
            score=score,
            evidence=[
                EvidenceItem("mean_missing_fraction", mean_missing, "stage01_variable_summary.csv", f"score={missing_score:.0f}"),
                EvidenceItem("duplicate_key_fraction", dup_frac, "stage01_qa_issues.csv:duplicates", f"n_dup={n_dup} of {n_obs}; score={dup_score:.0f}"),
                EvidenceItem("qa_winsorization_max_rel_change", max_rel_change, "stage02_sensitivity.csv", f"raw-vs-winsorized-mean stability; score={stability_score:.0f}"),
            ],
            reasoning=f"missing={mean_missing:.4f}, duplicates={dup_frac:.4f}, QA sensitivity drift={max_rel_change:.4f}",
            weaknesses=[] if score >= 80 else ["Data completeness/stability metrics are below the strong-evidence band."],
        )

    def evaluate_practical(self) -> Pillar:
        completeness: pd.DataFrame = self.evidence.get("stage01_completeness_matrix", pd.DataFrame())
        qa1 = self.evidence.get("stage01_qa_report", {})
        core_present = qa1.get("core_variables_present", [])

        station_cols = [c for c in completeness.columns if c != "sample_date"]
        n_stations = len(station_cols)
        if len(completeness) and station_cols:
            temporal_completeness = float(completeness[station_cols].to_numpy().mean())
        else:
            temporal_completeness = 0.0
        temporal_score = score_from_fraction(temporal_completeness, good=1.0, bad=0.7)

        # 9 canonical sonde channels expected (see cieml.config.CORE_VARIABLES).
        core_score = score_from_fraction(len(core_present) / 9.0, good=1.0, bad=0.5)
        station_score = score_from_fraction(n_stations / 6.0, good=1.0, bad=0.5) if n_stations else 0.0

        score = float(np.mean([temporal_score, core_score, station_score]))
        return Pillar(
            name="practical",
            score=score,
            evidence=[
                EvidenceItem("station_day_completeness", temporal_completeness, "stage01_completeness_matrix.csv", f"score={temporal_score:.0f}"),
                EvidenceItem("core_variables_present", len(core_present), "stage01_qa_report.json", f"of 9 expected; score={core_score:.0f}"),
                EvidenceItem("stations_present", n_stations, "stage01_completeness_matrix.csv", f"of 6 expected; score={station_score:.0f}"),
            ],
            reasoning=f"station-day completeness={temporal_completeness:.3f}, core vars={len(core_present)}/9, stations={n_stations}/6",
            weaknesses=[] if score >= 80 else ["Coverage across stations/dates/variables is not campaign-complete."],
        )

    def evaluate_physical(self) -> Pillar:
        qa_issues: pd.DataFrame = self.evidence.get("stage01_qa_issues", pd.DataFrame())
        if len(qa_issues):
            impossible = qa_issues[
                qa_issues.get("category", pd.Series(dtype=str)).isin(["range_violation", "negative_values"])
                & (qa_issues.get("severity", pd.Series(dtype=str)) == "Critical")
            ]
        else:
            impossible = pd.DataFrame()
        n_critical_physical = int(len(impossible))
        # Physically impossible readings that survive QA (uncorrected, per the project's
        # flag-only-no-deletion policy) directly cost this pillar — 40 points each,
        # floored at 0, rather than being waved through as always-passing.
        score = float(max(0.0, 100.0 - 40.0 * n_critical_physical))
        details = [f"{r['variable']}: {r['detail']}" for _, r in impossible.iterrows()] if n_critical_physical else []
        return Pillar(
            name="physical",
            score=score,
            evidence=[
                EvidenceItem(
                    "n_critical_physical_impossibilities_unresolved",
                    n_critical_physical,
                    "stage01_qa_issues.csv",
                    "; ".join(details) if details else "none found",
                )
            ],
            reasoning=(
                "No unresolved physically-impossible readings at Critical severity."
                if n_critical_physical == 0
                else f"{n_critical_physical} unresolved Critical physical-implausibility issue(s): {'; '.join(details)}"
            ),
            weaknesses=details,
        )

    def evaluate_environmental(self) -> Pillar:
        fingerprints: pd.DataFrame = self.evidence.get("stage11_station_fingerprints", pd.DataFrame())
        if len(fingerprints):
            z_cols = [c for c in fingerprints.columns if c != "station"]
            mean_abs_z = float(fingerprints[z_cols].to_numpy().__abs__().mean()) if z_cols else 0.0
        else:
            mean_abs_z = 0.0
        # Mean |z| across station fingerprints: if QA/cleaning had flattened real
        # station-to-station environmental differences into noise, this would be near 0.
        score = score_from_bands(mean_abs_z, [(0.6, 100.0), (0.4, 85.0), (0.25, 65.0), (0.1, 40.0), (0.0, 15.0)])
        return Pillar(
            name="environmental",
            score=score,
            evidence=[
                EvidenceItem(
                    "mean_abs_station_fingerprint_z",
                    mean_abs_z,
                    "stage11_station_fingerprints.csv",
                    f"cross-station environmental separation retained after QA; score={score:.0f}",
                )
            ],
            reasoning=f"mean |z| across station fingerprints = {mean_abs_z:.3f} — QA did not erase station-level structure.",
            weaknesses=[] if score >= 70 else ["Station-to-station environmental structure is weak after QA — check for over-aggressive cleaning."],
        )

    def generate_assumptions(self) -> list[str]:
        return [
            "Stage 2 policy is flag-only (no deletion); the physical pillar therefore scores whatever "
            "implausible readings remain in the record, not a post-hoc-cleaned subset.",
        ]

    def generate_limitations(self, pillars):
        base = super().generate_limitations(pillars)
        return base + [
            "Environmental pillar reuses Stage 11 station fingerprints (computed downstream in Phase 6) "
            "as a proxy for 'QA preserved real structure' rather than a dedicated pre/post-QA comparison.",
        ]
