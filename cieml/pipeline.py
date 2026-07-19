"""CIEML 2.0 pipeline runner (phased execution)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from cieml.config import DATA_DIR, PHASE1_DIR, PHASE2_DIR, PHASE3_DIR, PHASE4_DIR, PHASE5_DIR, PHASE6_DIR, PHASE7_DIR, PHASE8_DIR
from cieml.reporting.phase1_summary import write_phase1_summary
from cieml.reporting.phase2_summary import write_phase2_summary
from cieml.reporting.phase3_summary import write_phase3_summary
from cieml.reporting.phase4_summary import write_phase4_summary
from cieml.reporting.phase5_summary import write_phase5_summary
from cieml.reporting.phase6_summary import write_phase6_summary
from cieml.reporting.phase7_summary import write_phase7_summary
from cieml.reporting.phase8_summary import write_phase8_summary
from cieml.stages.stage_m1_hypotheses import run_stage_m1
from cieml.stages.stage00_ingestion import run_stage00
from cieml.stages.stage01_audit import run_stage01
from cieml.stages.stage02_sensor_qa import run_stage02
from cieml.stages.stage03_physical_validation import run_stage03
from cieml.stages.stage04_feature_engineering import run_stage04
from cieml.stages.stage05_statistical_validation import run_stage05
from cieml.stages.stage06_regime_discovery import run_stage06
from cieml.stages.stage07_regime_validation import run_stage07
from cieml.stages.stage08_explainable_ml import run_stage08
from cieml.stages.stage09_anomaly_discovery import run_stage09
from cieml.stages.stage10_external_validation import run_stage10
from cieml.stages.stage11_spatial_temporal import run_stage11
from cieml.stages.stage12_ecological_interpretation import run_stage12
from cieml.stages.stage13_decision_support import run_stage13
from cieml.stages.stage14_robustness import run_stage14
from cieml.utils.hypothesis_ledger import append_evidence, load_register, save_register


def _load_observations(
    phase1_dir: Path, data_dir: Path, phase2_dir: Path | None = None
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Prefer QA-annotated Phase 2 observations (carries qa_flag_any); fall back to raw
    Phase 1 observations; fall back to fresh ingestion."""
    inv_path = phase1_dir / "stage00_file_inventory.csv"
    inventory = pd.read_csv(inv_path) if inv_path.exists() else None

    if phase2_dir is not None:
        ann_parquet = phase2_dir / "stage02_observations_annotated.parquet"
        ann_csv = phase2_dir / "stage02_observations_annotated.csv"
        if ann_parquet.exists():
            return pd.read_parquet(ann_parquet), inventory
        if ann_csv.exists():
            return pd.read_csv(ann_csv), inventory

    parquet = phase1_dir / "stage00_observations.parquet"
    csv = phase1_dir / "stage00_observations.csv"
    if parquet.exists():
        return pd.read_parquet(parquet), inventory
    if csv.exists():
        return pd.read_csv(csv), inventory
    s0 = run_stage00(data_dir=data_dir, output_dir=phase1_dir)
    return s0["observations"], s0["inventory"]


def _write_manifest(output_dir: Path, filename: str, manifest: dict[str, Any]) -> None:
    (output_dir / filename).write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


def run_phase1(data_dir: Path | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_dir or DATA_DIR)
    output_dir = Path(output_dir or PHASE1_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    claim_pack = None
    try:
        from cieml.domain import load_campaign

        claim_pack = load_campaign().claim_pack
    except FileNotFoundError:
        # No campaign profile yet at bootstrap; run_stage_m1 falls back to
        # DEFAULT_CLAIM_PACK. A bare `except Exception` here would also swallow a
        # malformed campaign YAML (yaml.YAMLError) or a genuine schema bug, which
        # should surface instead of silently degrading to the default pack.
        claim_pack = None

    print("[CIEML] Stage -1: Claim register (hypothesis layer)")
    m1 = run_stage_m1(output_dir=output_dir, claim_pack=claim_pack)

    print("[CIEML] Stage 0: Ingestion & standardization")
    s0 = run_stage00(data_dir=data_dir, output_dir=output_dir)

    print("[CIEML] Stage 1: Scientific data audit")
    s1 = run_stage01(observations=s0["observations"], inventory=s0["inventory"], output_dir=output_dir)

    payload = {"stage_m1": m1, "stage_00": {"report": s0["report"]}, "stage_01": {"report": s1["report"]}}
    summary_path = write_phase1_summary(output_dir, payload)
    manifest = {
        "phase": 1,
        "stages": ["stage_m1", "stage_00", "stage_01"],
        "data_dir": str(data_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage00_report": s0["report"],
        "stage01_report": s1["report"],
    }
    _write_manifest(output_dir, "phase1_manifest.json", manifest)
    print(f"[CIEML] Phase 1 complete -> {summary_path}")
    return {"m1": m1, "s0": s0, "s1": s1, "manifest": manifest}


def run_phase2(
    data_dir: Path | None = None,
    phase1_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    data_dir = Path(data_dir or DATA_DIR)
    phase1_dir = Path(phase1_dir or PHASE1_DIR)
    output_dir = Path(output_dir or PHASE2_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[CIEML] Loading Phase 1 observations")
    observations, _inventory = _load_observations(phase1_dir, data_dir)

    src_reg = phase1_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists() and not dst_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    elif not dst_reg.exists():
        run_stage_m1(output_dir=output_dir)

    print("[CIEML] Stage 2: Sensor QA/QC")
    s2 = run_stage02(observations=observations, output_dir=output_dir)

    print("[CIEML] Stage 3: Physical oceanographic validation")
    s3 = run_stage03(observations=observations, output_dir=output_dir)

    register = load_register(dst_reg)
    append_evidence(
        register,
        "H1_data_trustworthiness",
        stage="stage_02",
        evidence={
            "summary": s2["report"].get("h1_update"),
            "n_flag_events": s2["report"].get("n_flag_events"),
            "file_flag_rate": s2["report"].get("file_flag_rate"),
            "deletion_policy": s2["report"].get("policy", {}).get("deletion"),
        },
        status=s2["report"].get("h1_update", {}).get("status"),
        verdict="exploratory_support",
    )
    append_evidence(
        register,
        "H2_physical_coherence",
        stage="stage_03",
        evidence={
            "summary": s3["report"].get("h2_update"),
            "support_rate_required": s3["report"].get("support_rate_required"),
            "n_required_broken": s3["report"].get("n_required_broken"),
            "effect_threshold_abs_rho": s3["report"].get("effect_threshold_abs_rho"),
            "status_counts": s3["report"].get("status_counts"),
        },
        status=s3["report"].get("h2_update", {}).get("status"),
        verdict=s3["report"].get("h2_update", {}).get("verdict_lean"),
    )
    save_register(dst_reg, register)

    payload = {"stage_02": {"report": s2["report"]}, "stage_03": {"report": s3["report"]}}
    summary_path = write_phase2_summary(output_dir, payload)
    manifest = {
        "phase": 2,
        "stages": ["stage_02", "stage_03"],
        "phase1_dir": str(phase1_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage02_report": s2["report"],
        "stage03_report": s3["report"],
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase2_manifest.json", manifest)
    print(f"[CIEML] Phase 2 complete -> {summary_path}")
    return {"s2": s2, "s3": s3, "manifest": manifest, "register": register}


def run_phase3(
    data_dir: Path | None = None,
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    data_dir = Path(data_dir or DATA_DIR)
    phase1_dir = Path(phase1_dir or PHASE1_DIR)
    phase2_dir = Path(phase2_dir or PHASE2_DIR)
    output_dir = Path(output_dir or PHASE3_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[CIEML] Loading observations for feature engineering")
    observations, _ = _load_observations(phase1_dir, data_dir, phase2_dir=phase2_dir)

    # Carry hypothesis register forward
    src_reg = phase2_dir / "stage_m1_hypothesis_register.json"
    if not src_reg.exists():
        src_reg = phase1_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        run_stage_m1(output_dir=output_dir)

    print("[CIEML] Stage 4: Feature engineering")
    s4 = run_stage04(observations=observations, output_dir=output_dir)

    print("[CIEML] Stage 5: Statistical validation")
    s5 = run_stage05(
        feature_matrix=s4["feature_matrix"],
        analysis_features=s4["analysis_features"],
        output_dir=output_dir,
    )

    register = load_register(dst_reg)
    append_evidence(
        register,
        "H3_information_redundancy",
        stage="stage_05",
        evidence={
            "summary": s5["report"].get("h3_update"),
            "retained_features": s5["report"].get("retained_features"),
            "n_removed": s5["report"].get("n_removed"),
            "factorability": s5["report"].get("factorability"),
            "redundant_pairs": s5["report"].get("redundant_pairs_abs_rho_ge_0_95"),
            "pillars": {
                "statistical_significance": "VIF_MI_KMO_Bartlett_PCA",
                "practical_significance": "features_removed_only_if_rho_ge_0.95_or_zero_var",
                "physical_plausibility": "salinity_family_priority_rules",
                "environmental_interpretability": "retained_set_maps_to_coastal_processes",
            },
        },
        status=s5["report"].get("h3_update", {}).get("status"),
        verdict=s5["report"].get("h3_update", {}).get("verdict_lean"),
    )
    save_register(dst_reg, register)

    payload = {"stage_04": {"report": s4["report"]}, "stage_05": {"report": s5["report"]}}
    summary_path = write_phase3_summary(output_dir, payload)
    manifest = {
        "phase": 3,
        "stages": ["stage_04", "stage_05"],
        "phase1_dir": str(phase1_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage04_report": s4["report"],
        "stage05_report": s5["report"],
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase3_manifest.json", manifest)
    print(f"[CIEML] Phase 3 complete -> {summary_path}")
    return {"s4": s4, "s5": s5, "manifest": manifest, "register": register}


def run_phase4(
    phase3_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    phase3_dir = Path(phase3_dir or PHASE3_DIR)
    output_dir = Path(output_dir or PHASE4_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix_path = phase3_dir / "stage05_retained_feature_matrix.csv"
    if not matrix_path.exists():
        raise FileNotFoundError(f"Missing retained feature matrix: {matrix_path}. Run Phase 3 first.")
    feature_matrix = pd.read_csv(matrix_path)

    src_reg = phase3_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        run_stage_m1(output_dir=output_dir)

    print("[CIEML] Stage 6: Environmental regime discovery")
    s6 = run_stage06(feature_matrix=feature_matrix, output_dir=output_dir)

    print("[CIEML] Stage 7: Regime validation")
    s7 = run_stage07(
        labeled=s6["labeled"],
        feature_cols=s6["feature_cols"],
        best=s6["best"],
        output_dir=output_dir,
    )

    register = load_register(dst_reg)
    append_evidence(
        register,
        "H4_environmental_regimes",
        stage="stage_06_07",
        evidence={
            "best": s6["report"].get("best"),
            "validation": {
                "bootstrap_ari_mean": s7["report"].get("bootstrap_ari_mean"),
                "consensus_ari_mean": s7["report"].get("consensus_ari_mean"),
                "loso_ari_mean": s7["report"].get("loso_ari_mean"),
                "lowo_ari_mean": s7["report"].get("lowo_ari_mean"),
                "structure_checks": s7["report"].get("structure_checks"),
                "structure_call": s7["report"].get("structure_call"),
            },
            "h4_update": s7["report"].get("h4_update"),
        },
        status=s7["report"].get("h4_update", {}).get("status"),
        verdict=s7["report"].get("h4_update", {}).get("verdict_lean"),
    )
    save_register(dst_reg, register)

    payload = {"stage_06": {"report": s6["report"]}, "stage_07": {"report": s7["report"]}}
    summary_path = write_phase4_summary(output_dir, payload)
    manifest = {
        "phase": 4,
        "stages": ["stage_06", "stage_07"],
        "phase3_dir": str(phase3_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage06_report": s6["report"],
        "stage07_report": s7["report"],
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase4_manifest.json", manifest)
    print(f"[CIEML] Phase 4 complete -> {summary_path}")
    return {"s6": s6, "s7": s7, "manifest": manifest, "register": register}


def run_phase5(
    phase4_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    phase4_dir = Path(phase4_dir or PHASE4_DIR)
    output_dir = Path(output_dir or PHASE5_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_path = phase4_dir / "stage06_regime_labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing regime labels: {labels_path}. Run Phase 4 first.")
    labeled = pd.read_csv(labels_path)

    src_reg = phase4_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        run_stage_m1(output_dir=output_dir)

    print("[CIEML] Stage 8: Explainable ML")
    s8 = run_stage08(labeled=labeled, output_dir=output_dir)

    print("[CIEML] Stage 9: Anomaly discovery")
    s9 = run_stage09(labeled=labeled, output_dir=output_dir)

    register = load_register(dst_reg)
    append_evidence(
        register,
        "H4_environmental_regimes",
        stage="stage_08",
        evidence={
            "driver_tiers": s8["report"].get("driver_tiers"),
            "primary_explainer_model": s8["report"].get("primary_explainer_model"),
            "note": "SHAP/permutation drivers interpret regime membership.",
        },
        status=None,
    )
    append_evidence(
        register,
        "H5_anomaly_reality",
        stage="stage_09",
        evidence={
            "summary": s9["report"].get("h5_update"),
            "n_consensus_anomalies": s9["report"].get("n_consensus_anomalies"),
            "method_rates": s9["report"].get("method_rates"),
            "category_counts": s9["report"].get("category_counts"),
        },
        status=s9["report"].get("h5_update", {}).get("status"),
        verdict=s9["report"].get("h5_update", {}).get("verdict_lean"),
    )
    save_register(dst_reg, register)

    payload = {"stage_08": {"report": s8["report"]}, "stage_09": {"report": s9["report"]}}
    summary_path = write_phase5_summary(output_dir, payload)
    manifest = {
        "phase": 5,
        "stages": ["stage_08", "stage_09"],
        "phase4_dir": str(phase4_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage08_report": s8["report"],
        "stage09_report": s9["report"],
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase5_manifest.json", manifest)
    print(f"[CIEML] Phase 5 complete -> {summary_path}")
    return {"s8": s8, "s9": s9, "manifest": manifest, "register": register}


def run_phase6(
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    phase4_dir = Path(phase4_dir or PHASE4_DIR)
    phase5_dir = Path(phase5_dir or PHASE5_DIR)
    output_dir = Path(output_dir or PHASE6_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_path = phase4_dir / "stage06_regime_labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing regime labels: {labels_path}. Run Phase 4 first.")
    labeled = pd.read_csv(labels_path)

    anom_flags = None
    anom_catalog = None
    flags_path = phase5_dir / "stage09_anomaly_flags.csv"
    cat_path = phase5_dir / "stage09_anomaly_catalog.csv"
    if flags_path.exists():
        anom_flags = pd.read_csv(flags_path)
    if cat_path.exists():
        anom_catalog = pd.read_csv(cat_path)

    src_reg = phase5_dir / "stage_m1_hypothesis_register.json"
    if not src_reg.exists():
        src_reg = phase4_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        run_stage_m1(output_dir=output_dir)

    print("[CIEML] Stage 10: External environmental validation")
    s10 = run_stage10(
        regime_labels=labeled,
        anomaly_flags=anom_flags,
        anomaly_catalog=anom_catalog,
        output_dir=output_dir,
    )

    print("[CIEML] Stage 11: Spatial and temporal analysis")
    s11 = run_stage11(regime_labels=labeled, output_dir=output_dir)

    register = load_register(dst_reg)
    append_evidence(
        register,
        "H5_anomaly_reality",
        stage="stage_10",
        evidence={
            "summary": s10["report"].get("h5_update"),
            "anomaly_external_support_frac": s10["report"].get("anomaly_external_support_frac"),
            "n_significant_crosscorr_05": s10["report"].get("n_significant_crosscorr_05"),
            "fetch_notes": s10["report"].get("fetch_notes"),
            "limitations": s10["report"].get("limitations"),
        },
        status=s10["report"].get("h5_update", {}).get("status"),
        verdict=s10["report"].get("h5_update", {}).get("verdict_lean"),
    )
    save_register(dst_reg, register)

    payload = {"stage_10": {"report": s10["report"]}, "stage_11": {"report": s11["report"]}}
    summary_path = write_phase6_summary(output_dir, payload)
    manifest = {
        "phase": 6,
        "stages": ["stage_10", "stage_11"],
        "phase4_dir": str(phase4_dir),
        "phase5_dir": str(phase5_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage10_report": s10["report"],
        "stage11_report": s11["report"],
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase6_manifest.json", manifest)
    print(f"[CIEML] Phase 6 complete -> {summary_path}")
    return {"s10": s10, "s11": s11, "manifest": manifest, "register": register}


def run_phase7(
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """`phase1_dir`/`phase2_dir` added for CEAM (Stage 12), which reads Stage 1/2/3
    QA and physical-validation context directly — previously Stage 12 needed none
    of that, so this phase runner never had to expose them. Both default to the
    module-level PHASE1_DIR/PHASE2_DIR, preserving prior behavior for callers that
    don't pass them; a caller redirecting phase4-6/output_dir to scratch (e.g. a
    regression/twin-run test) must now also redirect these or CEAM silently reads
    the real repo's Stage 1/2 artifacts instead of the scratch run's own."""
    phase1_dir = Path(phase1_dir or PHASE1_DIR)
    phase2_dir = Path(phase2_dir or PHASE2_DIR)
    phase4_dir = Path(phase4_dir or PHASE4_DIR)
    phase5_dir = Path(phase5_dir or PHASE5_DIR)
    phase6_dir = Path(phase6_dir or PHASE6_DIR)
    output_dir = Path(output_dir or PHASE7_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_path = phase4_dir / "stage06_regime_labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing regime labels: {labels_path}. Run Phase 4 first.")
    labeled = pd.read_csv(labels_path)

    profiles = None
    prof_path = phase5_dir / "stage08_regime_z_profiles.csv"
    if prof_path.exists():
        profiles = pd.read_csv(prof_path)

    shap_drivers = None
    shap_path = phase5_dir / "stage08_shap_driver_ranks.csv"
    if shap_path.exists():
        shap_drivers = pd.read_csv(shap_path)

    anom_catalog = None
    cat_path = phase5_dir / "stage09_anomaly_catalog.csv"
    if cat_path.exists():
        anom_catalog = pd.read_csv(cat_path)

    external_report = {}
    ext_path = phase6_dir / "stage10_external_report.json"
    if ext_path.exists():
        external_report = json.loads(ext_path.read_text(encoding="utf-8"))

    src_reg = phase6_dir / "stage_m1_hypothesis_register.json"
    if not src_reg.exists():
        src_reg = phase5_dir / "stage_m1_hypothesis_register.json"
    if not src_reg.exists():
        src_reg = phase4_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        run_stage_m1(output_dir=output_dir)

    print("[CIEML] Stage 12: Coastal Environmental Analysis Module (CEAM)")
    s12 = run_stage12(
        regime_labels=labeled,
        regime_profiles=profiles,
        shap_drivers=shap_drivers,
        output_dir=output_dir,
        phase1_dir=phase1_dir,
        phase2_dir=phase2_dir,
        phase4_dir=phase4_dir,
        phase5_dir=phase5_dir,
        phase6_dir=phase6_dir,
        phase8_dir=PHASE8_DIR,
    )

    print("[CIEML] Stage 13: Decision support")
    s13 = run_stage13(
        shap_drivers=shap_drivers,
        interpretations=s12.get("interpretations"),
        anomaly_catalog=anom_catalog,
        external_report=external_report,
        output_dir=output_dir,
    )

    register = load_register(dst_reg)
    append_evidence(
        register,
        "H4_environmental_regimes",
        stage="stage_12",
        evidence={
            "n_regimes": s12["report"].get("n_regimes"),
            "interpretations": [
                {
                    "regime": i.get("regime"),
                    "title": i.get("title"),
                    "family": i.get("interpretive_family"),
                    "confidence": i.get("confidence"),
                    "evidence_score": i.get("evidence_score"),
                }
                for i in s12["report"].get("interpretations", [])
            ],
            "naming_policy": s12["report"].get("naming_policy"),
        },
        status="provisional_support",
        verdict="Regimes mapped to evidence-scored interpretive families with stated confidence.",
    )
    append_evidence(
        register,
        "H5_anomaly_reality",
        stage="stage_13",
        evidence={
            "note": "Decision support incorporates anomaly EWIs and Stage 10 external support fraction where available.",
            "anomaly_external_support_frac": external_report.get("anomaly_external_support_frac"),
            "n_ewi": len(s13["report"].get("early_warning_indicators", [])),
            "applicability_transfer_rule": s13["report"].get("applicability_domain", {}).get("transfer_rule"),
        },
        status=None,
    )
    append_evidence(
        register,
        "H6_policy_transfer",
        stage="stage_13",
        evidence={
            "decision_rules": s13["report"].get("decision_rules"),
            "budget_tiers": s13["report"].get("budget_tiers"),
            "applicability_domain": s13["report"].get("applicability_domain"),
            "management_recommendations": s13["report"].get("management_recommendations"),
            "note": "Recommendations are transferable as framework rules with explicit applicability limits; not as Visakhapatnam numeric thresholds.",
        },
        status="provisional_support",
        verdict="Monitoring design rules transferable with stated applicability domain; site-specific cutoffs are not.",
    )
    save_register(dst_reg, register)

    payload = {"stage_12": {"report": s12["report"]}, "stage_13": {"report": s13["report"]}}
    summary_path = write_phase7_summary(output_dir, payload)
    manifest = {
        "phase": 7,
        "stages": ["stage_12", "stage_13"],
        "phase4_dir": str(phase4_dir),
        "phase5_dir": str(phase5_dir),
        "phase6_dir": str(phase6_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage12_report": s12["report"],
        "stage13_report": s13["report"],
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase7_manifest.json", manifest)
    print(f"[CIEML] Phase 7 complete -> {summary_path}")
    return {"s12": s12, "s13": s13, "manifest": manifest, "register": register}


def run_phase8(
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase3_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    phase7_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    knowledge_store_root: Path | None = None,
    update_phase7_applicability: bool = True,
) -> dict[str, Any]:
    """`knowledge_store_root` / `update_phase7_applicability` pass straight
    through to `run_stage14` — see its docstring. Needed so a regression/test
    run of the full pipeline doesn't write into the real repo `knowledge_base/`
    or mutate a real `phase7_dir` passed in for comparison purposes."""
    phase1_dir = Path(phase1_dir or PHASE1_DIR)
    phase2_dir = Path(phase2_dir or PHASE2_DIR)
    phase3_dir = Path(phase3_dir or PHASE3_DIR)
    phase4_dir = Path(phase4_dir or PHASE4_DIR)
    phase5_dir = Path(phase5_dir or PHASE5_DIR)
    phase6_dir = Path(phase6_dir or PHASE6_DIR)
    phase7_dir = Path(phase7_dir or PHASE7_DIR)
    output_dir = Path(output_dir or PHASE8_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_path = phase4_dir / "stage06_regime_labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing regime labels: {labels_path}. Run Phase 4 first.")
    labeled = pd.read_csv(labels_path)

    src_reg = phase7_dir / "stage_m1_hypothesis_register.json"
    if not src_reg.exists():
        src_reg = phase6_dir / "stage_m1_hypothesis_register.json"
    dst_reg = output_dir / "stage_m1_hypothesis_register.json"
    if src_reg.exists():
        dst_reg.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        run_stage_m1(output_dir=output_dir)

    register = load_register(dst_reg)

    # Stage 14 loads every other upstream artifact itself (see cieml.evidence.loaders)
    # so its Evidence-Based Scientific Validation Engine can compute every H1-H6 pillar
    # from real evidence — pipeline.py only needs to hand it phase directories + the register.
    print("[CIEML] Stage 14: Robustness & evidence-based four-pillar closure")
    s14 = run_stage14(
        labeled=labeled,
        phase1_dir=phase1_dir,
        phase2_dir=phase2_dir,
        phase3_dir=phase3_dir,
        phase4_dir=phase4_dir,
        phase5_dir=phase5_dir,
        phase6_dir=phase6_dir,
        phase7_dir=phase7_dir,
        hypothesis_register=register,
        output_dir=output_dir,
        knowledge_store_root=knowledge_store_root,
        update_phase7_applicability=update_phase7_applicability,
    )

    pillars = s14["pillars"]
    hyps = pillars.get("hypotheses", {})
    regime_call = s14["report"].get("regime_structure_call")
    h4_status = (
        "supported"
        if regime_call == "robust_support"
        else "provisional_support"
        if regime_call == "provisional_support"
        else "fragile"
    )
    append_evidence(
        register,
        "H4_environmental_regimes",
        stage="stage_14",
        evidence={
            "regime_structure_call": regime_call,
            "robustness_frac_pass": s14["report"].get("robustness_frac_pass"),
            "critical_checks": s14["report"].get("critical_checks"),
            "evidence_engine_assessment": hyps.get("H4_environmental_regimes"),
        },
        status=h4_status,
        verdict=f"Stage 14 regime call: {regime_call}",
    )
    append_evidence(
        register,
        "H5_anomaly_reality",
        stage="stage_14",
        evidence={
            "evidence_engine_assessment": hyps.get("H5_anomaly_reality"),
            "anomaly_external_support_frac": s14["report"].get("anomaly_external_support_frac"),
        },
        status=(hyps.get("H5_anomaly_reality", {}).get("classification") or "").lower() or None,
    )
    append_evidence(
        register,
        "H6_policy_transfer",
        stage="stage_14",
        evidence={
            "evidence_engine_assessment": hyps.get("H6_policy_transfer"),
            "campaign_closure": pillars.get("campaign_closure"),
            "note": "Q9 evidence-based four-pillar audit completed; transfer limited to framework rules.",
        },
        status=(hyps.get("H6_policy_transfer", {}).get("classification") or "").lower() or None,
        verdict=f"Campaign closure: {pillars.get('campaign_closure')}",
    )
    # Explicit Q9 ledger entry via H6 + campaign note on register root
    register["stage14_campaign_closure"] = pillars.get("campaign_closure")
    register["stage14_regime_structure_call"] = regime_call
    save_register(dst_reg, register)

    payload = {"stage_14": {"report": s14["report"], "pillars": pillars}}
    summary_path = write_phase8_summary(output_dir, payload)
    manifest = {
        "phase": 8,
        "stages": ["stage_14"],
        "phase1_dir": str(phase1_dir),
        "phase2_dir": str(phase2_dir),
        "phase3_dir": str(phase3_dir),
        "phase4_dir": str(phase4_dir),
        "phase5_dir": str(phase5_dir),
        "phase6_dir": str(phase6_dir),
        "phase7_dir": str(phase7_dir),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
        "stage14_report": s14["report"],
        "four_pillar": pillars,
        "hypothesis_register": str(dst_reg),
    }
    _write_manifest(output_dir, "phase8_manifest.json", manifest)
    print(f"[CIEML] Phase 8 complete -> {summary_path}")
    return {"s14": s14, "manifest": manifest, "register": register}
