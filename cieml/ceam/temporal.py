"""Temporal interpretation from Stage 11 transitions (+ anomaly timing context)."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext
from cieml.ceam.models import InterpretationUnit, evidence_item


def interpret_temporal(ctx: CEAMContext, regimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[InterpretationUnit] = []
    rep = ctx.spatial_report or {}
    trans = ctx.transitions

    n_trans = int(rep.get("n_regime_transitions") or (len(trans) if trans is not None else 0))
    # Persistent = largest regime n share
    total_n = sum(int(r.get("n") or 0) for r in regimes) or 1
    persistent = max(regimes, key=lambda r: int(r.get("n") or 0)) if regimes else None

    if persistent:
        units.append(
            InterpretationUnit(
                topic="persistent_regimes",
                observation=(
                    f"Largest regime {persistent.get('regime')} ({persistent.get('title')}) covers "
                    f"{int(persistent.get('n') or 0)}/{total_n} station-days ({int(persistent.get('n') or 0)/total_n:.0%})."
                ),
                interpretation="A dominant persistent multivariate state organizes much of the campaign.",
                supporting_evidence=[
                    evidence_item("stage_06", "stage06_regime_labels.csv", "regime_counts", {r["regime"]: r["n"] for r in regimes}, "Membership sizes", "strong"),
                ],
                confidence="supported",
                uncertainty="Persistence is within a one-month window only.",
                limitations=["Seasonal persistence untested."],
                level="interpretation",
            )
        )

    units.append(
        InterpretationUnit(
            topic="transient_events_and_transitions",
            observation=f"Stage 11 recorded n_regime_transitions={n_trans}.",
            interpretation=(
                "Regimes are not fully static; transitions indicate transient switches between environmental states."
                if n_trans > 0
                else "No regime transitions recorded — either fully persistent labels or missing Stage 11 products."
            ),
            supporting_evidence=[
                evidence_item("stage_11", "stage11_spatial_temporal_report.json", "n_regime_transitions", n_trans, "Transition count", "strong"),
                evidence_item(
                    "stage_11",
                    "stage11_regime_transitions.csv",
                    "n_rows",
                    len(trans) if trans is not None else 0,
                    "Transition table",
                    "moderate",
                ),
            ],
            confidence="provisional" if n_trans else "exploratory",
            uncertainty="Transition counts depend on labeling granularity and sampling cadence.",
            limitations=["Recovery timescales are not modeled beyond discrete transitions."],
            level="interpretation" if n_trans else "observation",
            rejected=False if (rep or (trans is not None and len(trans))) else True,
            reject_reason=None if (rep or (trans is not None and len(trans))) else "Missing Stage 11 temporal products.",
        )
    )

    anom = ctx.anomaly_report or {}
    if anom:
        units.append(
            InterpretationUnit(
                topic="recurring_anomalies",
                observation=(
                    f"Stage 9: n_consensus_anomalies={anom.get('n_consensus_anomalies')}, "
                    f"consensus_rate={anom.get('consensus_rate')}, categories={anom.get('category_counts')}."
                ),
                interpretation="Consensus anomalies mark episodic multivariate excursions relative to the campaign.",
                supporting_evidence=[
                    evidence_item("stage_09", "stage09_anomaly_report.json", "n_consensus_anomalies", anom.get("n_consensus_anomalies"), "Consensus anomaly count", "strong"),
                ],
                confidence="provisional",
                uncertainty="Anomaly ≠ ecological impact without Stage 10/CEAM ecological module.",
                limitations=["CEAM does not re-detect anomalies."],
                level="observation",
            )
        )

    return [u.to_dict() for u in units]
