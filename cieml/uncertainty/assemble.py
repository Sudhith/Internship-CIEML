"""Assemble a campaign uncertainty ledger from upstream artifacts + EBSVE, using
the v2 propagation model (docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md).

Engine chain (each -> next inherits the previous engine's RAW, unbounded total —
never its saturated/reported score, so bounding never compounds across stages):

    QA (root)
      -> Measurement (honest passthrough: no separately-measured local evidence
         exists yet beyond QA — see limitations)
      -> Sensor (passthrough of QA's sensor-specific slice only)
    Measurement -> Statistical (all new: a different question than raw noise)
      -> Model/Discovery (Stage 6's own clustering instability CORROBORATED by
         Stage 7's independent bootstrap/consensus/LOSO/permutation battery —
         precision-fused, so agreement can shrink the doubt, not just add to it)
        -> Explainability (all new: "can we explain it" != "does it exist")
        -> Anomaly (all new: a different question about specific points)
          -> Environmental (all new: external support gap, authored ONCE —
             the "single regional meteo station" fact now lives on the Evidence
             Reliability axis's external-source-diversity dimension instead of
             being duplicated here as a second Measurement-axis component)
    Explainability + Environmental -> Policy (principled two-parent combination,
      replacing v1's arbitrary "0.25 x environmental" hack)
      -> Decision (all new)
    Environmental + Model -> Scientific Claims (per EBSVE hypothesis; also
      scored on the Evidence Reliability axis here, since R is a property of
      the claim's evidence base, not something that propagates stage-to-stage)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cieml.uncertainty.models import (
    EngineUncertaintyPacket,
    UncertaintyBudget,
    UncertaintyComponent,
    UncertaintyKind,
    UncertaintyObject,
)
from cieml.uncertainty.propagate import (
    caution_index,
    combine_correlated,
    combine_raw,
    fuse_precision,
    propagate_engine,
    root_budget,
    saturate,
)
from cieml.uncertainty.reliability import build_reliability_dimensions, score_evidence_reliability


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _clip01_to_100(frac: float) -> float:
    return float(np.clip(frac, 0.0, 1.0) * 100.0)


def _failure_uncertainty_components(
    failure_reports: dict[str, Any] | None, engine_id: str, *, pillar_impact_target: str | None = None
) -> list[UncertaintyComponent]:
    """Convert a SC-FMF `build_failure_report()` result's triggered hits into
    UncertaintyComponents, using the SAME per-severity magnitude the failure
    report itself declared (catalog.policy.uncertainty_contributions) so the
    ledger and the failure dossier never disagree about how much doubt a given
    hit contributes. Hits carrying a `pillar_impact` route to that pillar's
    object only (e.g. anom_no_external_validation -> environmental, not
    anomaly); hits without one route to their own engine's object.
    """
    fr = (failure_reports or {}).get(engine_id)
    if not fr or not fr.get("hits"):
        return []
    from cieml.failure import load_failure_catalog

    table = load_failure_catalog().policy.get("uncertainty_contributions") or {}
    out: list[UncertaintyComponent] = []
    for h in fr["hits"]:
        impact = h.get("pillar_impact")
        if pillar_impact_target is not None:
            if impact != pillar_impact_target:
                continue
        elif impact:
            continue  # routed to a specific pillar elsewhere, not this engine's own object
        val = float(table.get(h.get("severity"), 0.0))
        if val <= 0.0:
            continue
        out.append(
            UncertaintyComponent(
                UncertaintyKind.SYSTEMATIC, val, f"SC-FMF:{engine_id}",
                h.get("title") or h.get("mode_id", "failure"), provenance_id=f"failure_{h.get('mode_id')}",
            )
        )
    return out


def _campaign_reliability_inputs(phase1_dir: Path | None, phase5_dir: Path | None, phase6_dir: Path | None) -> dict[str, Any]:
    """Gather the counts Evidence Reliability's coverage dimensions need. Falls
    back to conservative (low-coverage) defaults when a source is unavailable —
    never assumes generous coverage silently."""
    n_stations = 0
    n_seasons = 1
    n_methods = 0
    n_external_sources = 0

    try:
        from cieml.domain import load_campaign

        camp = load_campaign()
        n_stations = len(camp.stations) if camp.stations else 0
        if camp.raw.get("external"):
            n_external_sources = max(n_external_sources, len(camp.raw["external"]))
    except FileNotFoundError:
        pass

    if phase1_dir and (phase1_dir / "stage00_data_inventory_report.json").exists():
        inv = json.loads((phase1_dir / "stage00_data_inventory_report.json").read_text(encoding="utf-8"))
        if not n_stations:
            n_stations = len(inv.get("stations") or [])
        date_range = inv.get("date_range") or {}
        lo, hi = date_range.get("min"), date_range.get("max")
        if lo and hi:
            try:
                months = pd.period_range(start=pd.Timestamp(lo), end=pd.Timestamp(hi), freq="M")
                n_seasons = max(1, len(months))
            except Exception:
                n_seasons = 1

    if phase5_dir and (phase5_dir / "stage08_explainability_consensus.json").exists():
        cons = json.loads((phase5_dir / "stage08_explainability_consensus.json").read_text(encoding="utf-8"))
        n_methods = len(cons.get("methods_used") or [])

    if phase6_dir and (phase6_dir / "stage10_external_report.json").exists():
        ext = json.loads((phase6_dir / "stage10_external_report.json").read_text(encoding="utf-8"))
        if "open_meteo_ok" in (ext.get("fetch_notes") or []):
            n_external_sources = max(n_external_sources, 1)

    return {
        "n_stations": n_stations,
        "n_seasons": n_seasons,
        "n_methods": n_methods,
        "n_external_sources": n_external_sources,
    }


def _domain_reliability_config() -> dict[str, Any]:
    try:
        from cieml.domain import get_default_domain

        return dict(get_default_domain().evidence_reliability or {})
    except FileNotFoundError:
        return {}


def build_campaign_uncertainty_ledger(
    *,
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase3_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    phase7_dir: Path | None = None,
    pillars: dict[str, Any] | None = None,
    robustness_report: dict[str, Any] | None = None,
    failure_reports: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    `failure_reports` (SC-FMF): optional {engine_id: build_failure_report() result}
    map. Triggered hits are folded into the matching UncertaintyBudget as
    provenance-tagged SYSTEMATIC components (see `_failure_uncertainty_components`),
    using the same catalog severity->magnitude table the failure report itself
    reports under `uncertainty_adjustment` — so SC-FMF's stated impact and the
    ledger's actual number can never silently disagree.
    """
    phase1_dir = Path(phase1_dir) if phase1_dir else None
    phase2_dir = Path(phase2_dir) if phase2_dir else None
    phase3_dir = Path(phase3_dir) if phase3_dir else None
    phase4_dir = Path(phase4_dir) if phase4_dir else None
    phase5_dir = Path(phase5_dir) if phase5_dir else None
    phase6_dir = Path(phase6_dir) if phase6_dir else None
    phase7_dir = Path(phase7_dir) if phase7_dir else None
    pillars = pillars or {}
    robustness_report = robustness_report or {}
    failure_reports = failure_reports or {}

    packets: list[EngineUncertaintyPacket] = []

    # ============================================================ QA (root) ==
    qa_comps: list[UncertaintyComponent] = []
    if phase1_dir and (phase1_dir / "stage01_qa_issues.csv").exists():
        issues = pd.read_csv(phase1_dir / "stage01_qa_issues.csv")
        crit = float((issues.get("severity") == "Critical").mean()) if "severity" in issues.columns else 0.0
        sus = float((issues.get("severity") == "Suspicious").mean()) if "severity" in issues.columns else 0.0
        qa_comps.append(
            UncertaintyComponent(
                UncertaintyKind.SENSOR, min(100.0, 200.0 * crit), "stage01_qa_issues.csv",
                f"Critical issue rate={crit:.3f}", provenance_id="qa_critical_rate",
            )
        )
        qa_comps.append(
            UncertaintyComponent(
                UncertaintyKind.SAMPLING, _clip01_to_100(sus), "stage01_qa_issues.csv",
                f"Suspicious issue rate={sus:.3f}", provenance_id="qa_suspicious_rate",
            )
        )
        if "category" in issues.columns and (issues["category"] == "range_violation").any():
            qa_comps.append(
                UncertaintyComponent(
                    UncertaintyKind.SYSTEMATIC, 15.0, "stage01 range_violation",
                    "Range/overshoot violations imply possible calibration or envelope mismatch",
                    provenance_id="qa_range_violation",
                )
            )
    else:
        qa_comps.append(
            UncertaintyComponent(UncertaintyKind.SAMPLING, 40.0, "missing:stage01", "QA issues unavailable", provenance_id="qa_missing")
        )
    sensor_raw, _ = combine_correlated([c for c in qa_comps if c.kind == UncertaintyKind.SENSOR]) or (0.0, [])
    qa_budget = root_budget(qa_comps, object_type=UncertaintyObject.QA)
    packets.append(
        EngineUncertaintyPacket(
            engine="ScientificQA", object_type=UncertaintyObject.QA, result_ref="stage01_qa_issues.csv",
            confidence=None, uncertainty=qa_budget,
            limitations=["QA flags document risk; unflagged rows are not guaranteed clean."],
            remaining_unknowns=["Vendor calibration certificates not ingested."],
            caution=caution_index(None, qa_budget.remaining),
        )
    )

    # ===================================================== Measurement/Sensor ==
    # Honest passthrough: no separately-measured local evidence exists yet
    # beyond what QA already established (see remaining_unknowns). This is
    # deliberately NOT the v1 hack of "reuse QA's components as if new" —
    # inventing new-looking evidence from the same facts would misrepresent the
    # budget as having learned something it didn't.
    meas_budget = propagate_engine(qa_budget.raw_total, [], [], object_type=UncertaintyObject.MEASUREMENT)
    packets.append(
        EngineUncertaintyPacket(
            engine="UniversalIngestion+QA", object_type=UncertaintyObject.MEASUREMENT, result_ref="stage00_observations",
            confidence=None, uncertainty=meas_budget,
            limitations=["Short-cast sonde noise not separately quantified from QA's flag rates."],
            remaining_unknowns=["Per-sensor precision datasheets (would let this diverge from QA instead of mirroring it)."],
            caution=caution_index(None, meas_budget.remaining),
        )
    )
    sensor_budget = propagate_engine(sensor_raw, [], [], object_type=UncertaintyObject.SENSOR)
    packets.append(
        EngineUncertaintyPacket(
            engine="ScientificQA", object_type=UncertaintyObject.SENSOR, result_ref="stage01/stage02",
            confidence=None, uncertainty=sensor_budget,
            limitations=["Sensor drift checks are heuristic unless Stage 2 flags dominate."],
            remaining_unknowns=["Independent reference sensors."],
            caution=caution_index(None, sensor_budget.remaining),
        )
    )

    # ============================================================ Statistical ==
    stat_new: list[UncertaintyComponent] = []
    if phase3_dir and (phase3_dir / "stage05_method_selection.json").exists():
        ms = json.loads((phase3_dir / "stage05_method_selection.json").read_text(encoding="utf-8"))
        diag = ms.get("diagnostics") or {}
        nn = _f(diag.get("nonnormal_frac"))
        stat_new.append(
            UncertaintyComponent(
                UncertaintyKind.RANDOM, _clip01_to_100(nn), "stage05_method_selection.json",
                f"nonnormal_frac={nn:.2f}", provenance_id="stat_nonnormality",
            )
        )
        np_ = _f(diag.get("n_features"), 1.0)
        nr = _f(diag.get("n_rows"), 1.0)
        sparsity = min(1.0, (5.0 * np_) / max(nr, 1.0))
        stat_new.append(
            UncertaintyComponent(
                UncertaintyKind.SAMPLING, _clip01_to_100(max(0.0, sparsity - 0.5)), "stage05_method_selection.json",
                f"n={nr:.0f}, p={np_:.0f} sampling/design sparsity proxy", provenance_id="stat_design_sparsity",
            )
        )
        if (ms.get("dimensionality_reduction") or "").endswith("caution"):
            stat_new.append(
                UncertaintyComponent(
                    UncertaintyKind.MODEL, 25.0, "stage05_method_selection.json",
                    "PCA suitability caution / alternative embedding recommended", provenance_id="stat_pca_caution",
                )
            )
    else:
        stat_new.append(UncertaintyComponent(UncertaintyKind.SAMPLING, 30.0, "missing:stage05", "Method selection missing", provenance_id="stat_missing"))
    stat_budget = propagate_engine(meas_budget.raw_total, [], stat_new, object_type=UncertaintyObject.STATISTICAL)
    packets.append(
        EngineUncertaintyPacket(
            engine="StatisticalIntelligence", object_type=UncertaintyObject.STATISTICAL, result_ref="stage05_method_selection.json",
            confidence=None, uncertainty=stat_budget,
            limitations=["Feature retention is one reproducible policy, not unique truth."],
            remaining_unknowns=["Seasonal replication of redundancy structure."],
            caution=caution_index(None, stat_budget.remaining),
        )
    )

    # ======================================================= Model/Discovery ==
    # Stage 6's own clustering-instability estimate CORROBORATED by Stage 7's
    # independent validation battery -- the direct demonstration that agreeing
    # evidence can sharpen doubt instead of only adding to it (Sec 5.2).
    primary_instability: list[UncertaintyComponent] = []
    independent_validation: list[UncertaintyComponent] = []
    if phase4_dir and (phase4_dir / "stage07_validation_report.json").exists():
        v7 = json.loads((phase4_dir / "stage07_validation_report.json").read_text(encoding="utf-8"))
        boot_std = _f(v7.get("bootstrap_ari_std"))
        null_ari = abs(_f(v7.get("permutation_null_ari_mean")))
        cons = _f(v7.get("consensus_ari_mean"))
        primary_instability.append(
            UncertaintyComponent(
                UncertaintyKind.MODEL, min(100.0, 100.0 * boot_std), "stage07_validation_report.json",
                f"bootstrap_ari_std={boot_std:.3f}", provenance_id="discovery_bootstrap_instability",
            )
        )
        primary_instability.append(
            UncertaintyComponent(
                UncertaintyKind.MODEL, _clip01_to_100(max(0.0, 0.5 - cons)), "stage07_validation_report.json",
                f"cross-algorithm consensus_ari_mean={cons:.3f}", provenance_id="discovery_consensus_disagreement",
            )
        )
        independent_validation.append(
            UncertaintyComponent(
                UncertaintyKind.RANDOM, min(20.0, 100.0 * null_ari), "stage07_validation_report.json",
                f"permutation_null_ari~={null_ari:.3f} (should be ~0)", provenance_id="discovery_permutation_null",
                resolves_upstream=True,
            )
        )
    if robustness_report.get("robustness_frac_pass") is not None:
        frac = _f(robustness_report.get("robustness_frac_pass"))
        independent_validation.append(
            UncertaintyComponent(
                UncertaintyKind.MODEL, _clip01_to_100(1.0 - frac), "stage14_robustness_report",
                f"robustness_frac_pass={frac:.2f}", provenance_id="discovery_stage14_robustness",
                resolves_upstream=True,
            )
        )
    if not primary_instability and not independent_validation:
        primary_instability.append(UncertaintyComponent(UncertaintyKind.MODEL, 35.0, "missing:stage07", "Validation report missing", provenance_id="discovery_missing"))

    sigma_primary, _ = combine_correlated(primary_instability) if primary_instability else (0.0, [])
    sigma_validation, _ = combine_correlated(independent_validation) if independent_validation else (0.0, [])
    if primary_instability and independent_validation:
        sigma_structure = fuse_precision(sigma_primary, sigma_validation)
    else:
        sigma_structure = combine_raw([sigma_primary, sigma_validation])
    discovery_failure_components = _failure_uncertainty_components(failure_reports, "discovery")
    model_budget = propagate_engine(
        stat_budget.raw_total, [], discovery_failure_components, object_type=UncertaintyObject.MODEL,
        extra_new_raw=sigma_structure, extra_display_components=primary_instability + independent_validation,
    )
    model_confidence = 85.0 if (robustness_report.get("regime_structure_call") == "robust_support") else 60.0
    packets.append(
        EngineUncertaintyPacket(
            engine="DiscoveryEngine", object_type=UncertaintyObject.MODEL, result_ref="stage06/stage07",
            confidence=model_confidence, uncertainty=model_budget,
            limitations=["Semantic regime labels are out of scope for discovery uncertainty."],
            remaining_unknowns=["Multi-season stability of K/algorithm selection."],
            caution=caution_index(model_confidence, model_budget.remaining),
        )
    )

    # ========================================================= Explainability ==
    xai_new: list[UncertaintyComponent] = []
    if phase5_dir and (phase5_dir / "stage08_explainability_consensus.json").exists():
        cons = json.loads((phase5_dir / "stage08_explainability_consensus.json").read_text(encoding="utf-8"))
        disputed = cons.get("disputed_drivers") or []
        methods = cons.get("methods_used") or []
        xai_new.append(
            UncertaintyComponent(
                UncertaintyKind.INTERPRETATION, min(100.0, 20.0 * len(disputed)), "stage08_explainability_consensus.json",
                f"disputed_drivers={disputed}", provenance_id="xai_disputed_drivers",
            )
        )
        if len(methods) < 2:
            xai_new.append(UncertaintyComponent(UncertaintyKind.MODEL, 30.0, "stage08_explainability_consensus.json", "Fewer than 2 explanation methods available", provenance_id="xai_method_scarcity"))
        else:
            xai_new.append(UncertaintyComponent(UncertaintyKind.RANDOM, 10.0, "stage08_explainability_consensus.json", f"methods_used={methods}", provenance_id="xai_method_baseline"))
    else:
        xai_new.append(UncertaintyComponent(UncertaintyKind.INTERPRETATION, 25.0, "missing:stage08_consensus", "Consensus file missing; SHAP-only risk", provenance_id="xai_missing"))
    xai_new.extend(_failure_uncertainty_components(failure_reports, "explainability"))
    xai_budget = propagate_engine(model_budget.raw_total, [], xai_new, object_type=UncertaintyObject.EXPLAINABILITY)
    packets.append(
        EngineUncertaintyPacket(
            engine="ExplainabilityEngine", object_type=UncertaintyObject.EXPLAINABILITY, result_ref="stage08",
            confidence=None, uncertainty=xai_budget,
            limitations=["Driver attribution is associative with regimes, not causal proof."],
            remaining_unknowns=["Counterfactual / ALE consensus not yet required."],
            caution=caution_index(None, xai_budget.remaining),
        )
    )

    # =============================================================== Anomaly ==
    anom_new: list[UncertaintyComponent] = []
    if phase5_dir and (phase5_dir / "stage09_anomaly_catalog.csv").exists():
        cat = pd.read_csv(phase5_dir / "stage09_anomaly_catalog.csv")
        if "origin_confidence" in cat.columns and len(cat):
            mean_o = float(cat["origin_confidence"].mean())
            anom_new.append(
                UncertaintyComponent(
                    UncertaintyKind.INTERPRETATION, _clip01_to_100(1.0 - mean_o), "stage09_anomaly_catalog.csv",
                    f"mean origin_confidence={mean_o:.2f}", provenance_id="anomaly_origin_confidence",
                )
            )
        if "n_methods_flagged" in cat.columns and len(cat):
            agree = float(cat["n_methods_flagged"].mean()) / 5.0
            anom_new.append(
                UncertaintyComponent(
                    UncertaintyKind.MODEL, _clip01_to_100(1.0 - min(agree, 1.0)), "stage09_anomaly_catalog.csv",
                    f"mean detector votes={float(cat['n_methods_flagged'].mean()):.2f}", provenance_id="anomaly_detector_agreement",
                )
            )
    else:
        anom_new.append(UncertaintyComponent(UncertaintyKind.MODEL, 30.0, "missing:stage09", "Anomaly catalog missing", provenance_id="anomaly_missing"))
    anom_new.extend(_failure_uncertainty_components(failure_reports, "anomaly_intelligence"))
    anom_budget = propagate_engine(model_budget.raw_total, [], anom_new, object_type=UncertaintyObject.ANOMALY)
    packets.append(
        EngineUncertaintyPacket(
            engine="AnomalyIntelligence", object_type=UncertaintyObject.ANOMALY, result_ref="stage09",
            confidence=None, uncertainty=anom_budget,
            limitations=["Origin labels are probabilistic heuristics."],
            remaining_unknowns=["Station-resolved event logs / harbour operations."],
            caution=caution_index(None, anom_budget.remaining),
        )
    )

    # =========================================================== Environmental ==
    # The "single regional meteo station" fact now lives ONCE, on the Evidence
    # Reliability axis (external_source_diversity dimension) -- not duplicated
    # here as a second Measurement-axis component alongside the data-driven
    # support-gap value. This is the direct fix for the v1 double-count bug: the
    # two components were describing different axes (M vs R) that had been
    # incorrectly conflated into one M-only sum.
    env_new: list[UncertaintyComponent] = []
    support = None
    if phase6_dir and (phase6_dir / "stage10_external_report.json").exists():
        ext = json.loads((phase6_dir / "stage10_external_report.json").read_text(encoding="utf-8"))
        support = ext.get("anomaly_external_support_frac")
        if support is not None:
            env_new.append(
                UncertaintyComponent(
                    UncertaintyKind.EXTERNAL, _clip01_to_100(1.0 - _f(support)), "stage10_external_report.json",
                    f"anomaly_external_support_frac={support}", provenance_id="environmental_external_support_gap",
                )
            )
    else:
        env_new.append(UncertaintyComponent(UncertaintyKind.EXTERNAL, 50.0, "missing:stage10", "External validation missing", provenance_id="environmental_missing"))
    # anom_no_external_validation carries pillar_impact=environmental in the
    # catalog -- it belongs here, not on the anomaly_intelligence object itself.
    env_new.extend(_failure_uncertainty_components(failure_reports, "anomaly_intelligence", pillar_impact_target="environmental"))
    env_budget = propagate_engine(anom_budget.raw_total, [], env_new, object_type=UncertaintyObject.ENVIRONMENTAL)
    reliability_inputs = _campaign_reliability_inputs(phase1_dir, phase5_dir, phase6_dir)
    domain_rel_cfg = _domain_reliability_config()
    env_dims = build_reliability_dimensions(
        n_stations=reliability_inputs["n_stations"], n_seasons=reliability_inputs["n_seasons"],
        n_methods=reliability_inputs["n_methods"], n_external_sources=reliability_inputs["n_external_sources"],
        targets=domain_rel_cfg.get("targets"), weights=domain_rel_cfg.get("weights"),
    )
    env_reliability = score_evidence_reliability(env_dims)
    packets.append(
        EngineUncertaintyPacket(
            engine="ContextExternal", object_type=UncertaintyObject.ENVIRONMENTAL, result_ref="stage10",
            confidence=_clip01_to_100(_f(support)) if support is not None else None, uncertainty=env_budget,
            limitations=["Regional Open-Meteo is a proxy, not local harbour meteorology.", "Single external source — see evidence_reliability.external_source_diversity."],
            remaining_unknowns=["Tide, harbour operations, local rainfall gauges."],
            evidence_reliability=env_reliability.get("score"),
            evidence_reliability_detail=env_reliability,
            caution=caution_index(_clip01_to_100(_f(support)) if support is not None else None, env_budget.remaining),
        )
    )

    # =============================================================== Policy ==
    # Two genuinely relevant, independent parents (drivers feed sensor priority;
    # external support feeds recommendation caution) combined via the same
    # correlation-aware rule as any other sibling combination -- replacing v1's
    # arbitrary "0.25 x environmental.total" hack with a principled combination.
    policy_parent_raw = combine_raw([xai_budget.raw_total, env_budget.raw_total], rho=0.0)
    pol_new = [
        UncertaintyComponent(
            UncertaintyKind.INTERPRETATION, 15.0, "stage13",
            "Recommendations are design rules; numeric cutoffs must not transfer", provenance_id="policy_transfer_caveat",
        )
    ]
    pol_new.extend(_failure_uncertainty_components(failure_reports, "decision_support"))
    pol_budget = propagate_engine(policy_parent_raw, [], pol_new, object_type=UncertaintyObject.POLICY)
    packets.append(
        EngineUncertaintyPacket(
            engine="DecisionSupport", object_type=UncertaintyObject.POLICY, result_ref="stage13_decision_support_report.json",
            confidence=None, uncertainty=pol_budget,
            limitations=["Not a regulatory compliance instrument."],
            remaining_unknowns=["Site-specific staffing/cost constraints."],
            caution=caution_index(None, pol_budget.remaining),
        )
    )
    dec_new = [
        UncertaintyComponent(
            UncertaintyKind.SAMPLING, 10.0, "decision", "Adaptive sampling triggers untested operationally", provenance_id="decision_untested_triggers",
        )
    ]
    dec_budget = propagate_engine(pol_budget.raw_total, [], dec_new, object_type=UncertaintyObject.DECISION)
    packets.append(
        EngineUncertaintyPacket(
            engine="DecisionSupport", object_type=UncertaintyObject.DECISION, result_ref="stage13",
            confidence=None, uncertainty=dec_budget,
            limitations=["Operational feasibility not field-trialed."],
            remaining_unknowns=["Cost-benefit empirical validation."],
            caution=caution_index(None, dec_budget.remaining),
        )
    )

    # ===================================================== Scientific claims ==
    claim_packets = []
    hyps = pillars.get("hypotheses") or {}
    claim_parent_raw = combine_raw([env_budget.raw_total, model_budget.raw_total], rho=0.0)
    # EBSVE-level failures (e.g. a missing evidence artifact) affect every claim's
    # evidence base equally, not one claim specifically -- applied identically to
    # each claim's own new-evidence list, same as the pillar-gap component below.
    ebsve_failure_components = _failure_uncertainty_components(failure_reports, "ebsve")
    for hid, block in hyps.items():
        if not isinstance(block, dict):
            continue
        conf = _f(block.get("overall_confidence"), default=float("nan"))
        pillar_scores = block.get("pillars") or {}
        scores = []
        for pname, pdata in pillar_scores.items():
            if isinstance(pdata, dict) and "score" in pdata:
                scores.append(_f(pdata["score"]))
            elif isinstance(pdata, (int, float)):
                scores.append(_f(pdata))
        weakest = min(scores) if scores else 0.0
        claim_new = [
            UncertaintyComponent(
                UncertaintyKind.INTERPRETATION, max(0.0, 100.0 - weakest), f"EBSVE:{hid}",
                f"Weakest pillar score={weakest:.1f} -> pillar-gap uncertainty", provenance_id=f"claim_pillar_gap_{hid}",
            )
        ] + ebsve_failure_components
        claim_budget = propagate_engine(claim_parent_raw, [], claim_new, object_type=UncertaintyObject.SCIENTIFIC_CLAIM)
        claim_budget.rule_id = "V2_claim_fusion"
        claim_reliability = score_evidence_reliability(env_dims)  # same campaign-wide evidence base for every claim
        pkt = EngineUncertaintyPacket(
            engine="EBSVE", object_type=UncertaintyObject.SCIENTIFIC_CLAIM, result_ref=hid,
            confidence=conf if np.isfinite(conf) else None, uncertainty=claim_budget,
            limitations=list(block.get("limitations") or [])[:8],
            remaining_unknowns=list(block.get("future_validation") or [])[:8],
            evidence_reliability=claim_reliability.get("score"),
            evidence_reliability_detail=claim_reliability,
            caution=caution_index(conf if np.isfinite(conf) else None, claim_budget.remaining),
        )
        claim_packets.append(pkt)
        packets.append(pkt)

    ledger = {
        "framework": "CIEML Uncertainty Model v2",
        "contract_id": "SC-MMU+SC-REL",
        "version": "2.0.0",
        "principle": (
            "Confidence, Measurement & Model Uncertainty, and Evidence Reliability are three "
            "independent axes. None is derived from another (never U=100-C, never R=100-C)."
        ),
        "propagation_doc": "docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md",
        "packets": [p.to_dict() for p in packets],
        "claim_ids": [p.result_ref for p in claim_packets],
        "reliability_inputs": reliability_inputs,
        "summary": {
            "n_packets": len(packets),
            "mean_uncertainty": float(np.mean([p.uncertainty.remaining for p in packets])) if packets else None,
            "max_uncertainty_packet": max(packets, key=lambda p: p.uncertainty.remaining).engine if packets else None,
            "max_uncertainty_total": max((p.uncertainty.remaining for p in packets), default=None),
            "mean_claim_caution": float(np.mean([p.caution for p in claim_packets if p.caution is not None])) if claim_packets else None,
            "mean_claim_reliability": float(np.mean([p.evidence_reliability for p in claim_packets if p.evidence_reliability is not None])) if claim_packets else None,
        },
    }
    return ledger
