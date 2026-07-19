"""Versioned artifact contract for the evidence bundle (Phase J).

Logical evidence keys stay stable; filenames may gain aliases without rewriting
validators. Visakhapatnam continues to use the current `stageNN_*` names as
`primary` paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ARTIFACT_CONTRACT_VERSION = "1"

PhaseSlot = Literal[1, 2, 3, 4, 5, 6, 7]


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    phase: PhaseSlot
    primary: str
    kind: Literal["json", "csv", "json_list"] = "json"
    aliases: tuple[str, ...] = ()


# Logical key -> on-disk filename(s). Aliases are tried after primary if missing.
ARTIFACT_SPECS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("stage00_inventory_report", 1, "stage00_data_inventory_report.json"),
    ArtifactSpec("stage01_qa_report", 1, "stage01_qa_report.json"),
    ArtifactSpec("stage01_qa_issues", 1, "stage01_qa_issues.csv", "csv"),
    ArtifactSpec("stage01_variable_summary", 1, "stage01_variable_summary.csv", "csv"),
    ArtifactSpec("stage01_completeness_matrix", 1, "stage01_completeness_matrix.csv", "csv"),
    ArtifactSpec("stage02_qa_report", 2, "stage02_qa_report.json"),
    ArtifactSpec("stage02_sensitivity", 2, "stage02_sensitivity.csv", "csv"),
    ArtifactSpec("stage03_physical_report", 2, "stage03_physical_report.json"),
    ArtifactSpec("stage03_physical_pairs", 2, "stage03_physical_pairs.csv", "csv"),
    ArtifactSpec("stage03_station_pair_stability", 2, "stage03_station_pair_stability.csv", "csv"),
    ArtifactSpec("stage04_feature_report", 3, "stage04_feature_report.json"),
    ArtifactSpec("stage04_station_day_features", 3, "stage04_station_day_features.csv", "csv"),
    ArtifactSpec("stage05_statistical_report", 3, "stage05_statistical_report.json"),
    ArtifactSpec("stage05_feature_decisions", 3, "stage05_feature_decisions.csv", "csv"),
    ArtifactSpec("stage05_vif", 3, "stage05_vif.csv", "csv"),
    ArtifactSpec("stage05_retained_feature_matrix", 3, "stage05_retained_feature_matrix.csv", "csv"),
    ArtifactSpec("stage06_regime_discovery_report", 4, "stage06_regime_discovery_report.json"),
    ArtifactSpec("stage06_regime_labels", 4, "stage06_regime_labels.csv", "csv"),
    ArtifactSpec("stage07_validation_report", 4, "stage07_validation_report.json"),
    ArtifactSpec("stage08_explainable_report", 5, "stage08_explainable_report.json"),
    ArtifactSpec("stage08_shap_driver_ranks", 5, "stage08_shap_driver_ranks.csv", "csv"),
    ArtifactSpec("stage09_anomaly_report", 5, "stage09_anomaly_report.json"),
    ArtifactSpec("stage09_anomaly_catalog", 5, "stage09_anomaly_catalog.csv", "csv"),
    ArtifactSpec("stage10_external_report", 6, "stage10_external_report.json"),
    ArtifactSpec("stage10_crosscorr_lags", 6, "stage10_crosscorr_lags.csv", "csv"),
    ArtifactSpec("stage11_spatial_temporal_report", 6, "stage11_spatial_temporal_report.json"),
    ArtifactSpec("stage11_spatial_gradients", 6, "stage11_spatial_gradients.csv", "csv"),
    ArtifactSpec("stage11_station_fingerprints", 6, "stage11_station_fingerprints.csv", "csv"),
    ArtifactSpec("stage12_ecological_report", 7, "stage12_ecological_report.json"),
    ArtifactSpec("stage12_interpretations", 7, "stage12_interpretation_detail.json", "json_list"),
    ArtifactSpec("stage13_decision_support_report", 7, "stage13_decision_support_report.json"),
    ArtifactSpec("stage13_applicability_domain", 7, "stage13_applicability_domain.json"),
    ArtifactSpec("stage13_decision_rules", 7, "stage13_decision_rules.csv", "csv"),
)


def specs_by_key() -> dict[str, ArtifactSpec]:
    return {s.key: s for s in ARTIFACT_SPECS}


def resolve_artifact_path(base: Path | None, spec: ArtifactSpec) -> Path | None:
    if base is None:
        return None
    base = Path(base)
    for name in (spec.primary, *spec.aliases):
        path = base / name
        if path.exists():
            return path
    return base / spec.primary  # may not exist; loaders return empty defaults
