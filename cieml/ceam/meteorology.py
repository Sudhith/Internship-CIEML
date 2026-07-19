"""Meteorological interpretation from Stage 10 only — never invent weather."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext
from cieml.ceam.models import InterpretationUnit, evidence_item


def interpret_meteorology(ctx: CEAMContext) -> list[dict[str, Any]]:
    units: list[InterpretationUnit] = []
    rep = ctx.external_report or {}
    th_p = ctx.thresholds.get("meteo_event_p_max", 0.05)

    if not rep:
        units.append(
            InterpretationUnit(
                topic="meteorology",
                observation="Stage 10 external report is absent.",
                interpretation="Meteorological influence cannot be assessed.",
                supporting_evidence=[],
                confidence="exploratory",
                uncertainty="No meteo evidence.",
                limitations=["Do not infer rainfall, wind, or storms."],
                level="observation",
                rejected=True,
                reject_reason="Missing Stage 10 artifacts.",
            )
        )
        return [u.to_dict() for u in units]

    events = rep.get("event_tests") or []
    supported = [e for e in events if e.get("consistent_with_driver") and float(e.get("fisher_p") or 1) <= th_p]
    precip = [e for e in supported if "precip" in str(e.get("event", "")).lower()]
    wind = [e for e in supported if "wind" in str(e.get("event", "")).lower()]

    units.append(
        InterpretationUnit(
            topic="rainfall_influence",
            observation=(
                f"Stage 10 event tests: {len(events)} total; {len(precip)} precip events consistent with anomaly co-occurrence "
                f"(fisher_p≤{th_p}). anomaly_external_support_frac={rep.get('anomaly_external_support_frac')}."
            ),
            interpretation=(
                "Precipitation events are statistically associated with consensus anomaly days for this campaign."
                if precip
                else "No precip event cleared the Stage 10 consistency gate; rainfall influence on anomalies is not supported."
            ),
            supporting_evidence=[
                evidence_item("stage_10", "stage10_external_report.json", "event_tests", precip[:5] or events[:3], "Event matching / Fisher tests", "strong" if precip else "moderate"),
                evidence_item(
                    "stage_10",
                    "stage10_external_report.json",
                    "anomaly_external_support_frac",
                    rep.get("anomaly_external_support_frac"),
                    "External support fraction",
                    "moderate",
                ),
            ],
            confidence="provisional" if precip else "supported",
            uncertainty="Association is not mechanism proof; lag structure may vary by station.",
            limitations=["Reduced salinity alone does not prove rainfall — requires Stage 10 consistency."],
            alternatives=["Local processes or sensor events without meteo match."],
            level="interpretation" if precip else "observation",
            rejected=False if rep else True,
        )
    )

    units.append(
        InterpretationUnit(
            topic="wind_storm_influence",
            observation=f"{len(wind)} wind-related Stage 10 events consistent with anomalies.",
            interpretation=(
                "Wind forcing shows evidence of association with anomaly days."
                if wind
                else "Wind/storm influence on anomalies is not supported by Stage 10 consistency tests."
            ),
            supporting_evidence=[
                evidence_item("stage_10", "stage10_external_report.json", "event_tests", wind[:5], "Wind event tests", "moderate"),
            ],
            confidence="provisional" if wind else "supported",
            uncertainty="Regional Open-Meteo point is not station-resolved.",
            limitations=["Do not claim storm surge without water-level evidence."],
            level="interpretation" if wind else "observation",
        )
    )

    # Enrichment table — only if present
    enr = ctx.meteo_enrichment
    if enr is not None and len(enr):
        wet = 0
        if "external_consistency" in enr.columns:
            wet = int(enr["external_consistency"].astype(str).str.contains("wet", case=False).sum())
        units.append(
            InterpretationUnit(
                topic="anomaly_meteo_cooccurrence",
                observation=f"Stage 10 enrichment rows={len(enr)}; wet-weather consistency tags≈{wet}.",
                interpretation="Consensus anomalies are annotated with same-day meteo fields for interpretive context.",
                supporting_evidence=[
                    evidence_item("stage_10", "stage10_anomaly_external_enrichment.csv", "n_rows", len(enr), "Anomaly×meteo join", "moderate"),
                ],
                confidence="provisional",
                uncertainty="Tags such as wet_weather_present_mechanism_unclear are observational, not causal.",
                limitations=["CEAM does not re-fit cross-correlations."],
                level="observation",
            )
        )

    return [u.to_dict() for u in units]
