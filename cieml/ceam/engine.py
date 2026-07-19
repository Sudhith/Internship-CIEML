"""CEAM orchestrator — consume upstream artifacts; emit Stage 12 products."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from cieml.ceam.context import CEAMContext, build_context
from cieml.ceam.ecological import interpret_ecological
from cieml.ceam.fusion import fuse_evidence
from cieml.ceam.hydrodynamics import interpret_hydrodynamics
from cieml.ceam.meteorology import interpret_meteorology
from cieml.ceam.narrative import build_scientific_narrative
from cieml.ceam.regime import interpret_regimes
from cieml.ceam.spatial import interpret_spatial
from cieml.ceam.summary import build_campaign_summary
from cieml.ceam.temporal import interpret_temporal
from cieml.ceam.water_quality import interpret_water_quality


def run_ceam(
    *,
    regime_labels: pd.DataFrame | None = None,
    regime_profiles: pd.DataFrame | None = None,
    shap_drivers: pd.DataFrame | None = None,
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    phase8_dir: Path | None = None,
    ctx: CEAMContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or build_context(
        phase1_dir=phase1_dir,
        phase2_dir=phase2_dir,
        phase4_dir=phase4_dir,
        phase5_dir=phase5_dir,
        phase6_dir=phase6_dir,
        phase8_dir=phase8_dir,
        regime_labels=regime_labels,
        regime_profiles=regime_profiles,
        shap_drivers=shap_drivers,
    )

    regimes = interpret_regimes(ctx)
    hydro = interpret_hydrodynamics(ctx, regimes)
    wq = interpret_water_quality(ctx, regimes)
    meteo = interpret_meteorology(ctx)
    spatial = interpret_spatial(ctx, regimes)
    temporal = interpret_temporal(ctx, regimes)
    ecological = interpret_ecological(ctx, regimes, meteo)
    fusion = fuse_evidence(
        ctx,
        regimes=regimes,
        hydro=hydro,
        wq=wq,
        meteo=meteo,
        spatial=spatial,
        temporal=temporal,
        ecological=ecological,
    )
    summary = build_campaign_summary(
        regimes=regimes,
        hydro=hydro,
        wq=wq,
        meteo=meteo,
        spatial=spatial,
        temporal=temporal,
        ecological=ecological,
        fusion=fusion,
    )
    narrative_md = build_scientific_narrative(
        campaign_id=ctx.campaign_id,
        domain=ctx.domain_name,
        regimes=regimes,
        hydro=hydro,
        wq=wq,
        meteo=meteo,
        spatial=spatial,
        temporal=temporal,
        ecological=ecological,
        fusion=fusion,
        summary=summary,
    )

    # Traceability: map topics → stages cited
    trace_rows = []
    for block_name, block in [
        ("hydrodynamics", hydro),
        ("water_quality", wq),
        ("meteorology", meteo),
        ("spatial", spatial),
        ("temporal", temporal),
        ("ecological", ecological),
    ]:
        for u in block:
            stages = sorted({e.get("stage") for e in (u.get("supporting_evidence") or []) if e.get("stage")})
            trace_rows.append(
                {
                    "module": block_name,
                    "topic": u.get("topic"),
                    "level": u.get("level"),
                    "confidence": u.get("confidence"),
                    "rejected": u.get("rejected"),
                    "stages_cited": stages,
                    "uncertainty": u.get("uncertainty"),
                }
            )
    for r in regimes:
        for u in r.get("four_level") or []:
            stages = sorted({e.get("stage") for e in (u.get("supporting_evidence") or []) if e.get("stage")})
            trace_rows.append(
                {
                    "module": "regime",
                    "topic": f"regime_{r.get('regime')}_{u.get('topic')}",
                    "level": u.get("level"),
                    "confidence": u.get("confidence"),
                    "rejected": u.get("rejected"),
                    "stages_cited": stages,
                    "uncertainty": u.get("uncertainty"),
                }
            )

    return {
        "contract_id": "SC-CEAM",
        "module": "Coastal Environmental Analysis Module",
        "campaign_id": ctx.campaign_id,
        "domain": ctx.domain_name,
        "regimes": regimes,
        "hydrodynamics": hydro,
        "water_quality": wq,
        "meteorology": meteo,
        "spatial": spatial,
        "temporal": temporal,
        "ecological": ecological,
        "fusion": fusion,
        "campaign_summary": summary,
        "narrative_markdown": narrative_md,
        "traceability": trace_rows,
        "naming_policy": (
            "Labels assigned from domain regime_families + CEAM thresholds when evidence scores clear gates; "
            "otherwise unnamed. Harbour membership uses campaign station roles, not hardcoded place names."
        ),
        "candidate_families_considered": list(ctx.regime_families),
    }
