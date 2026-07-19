"""Spatial interpretation from Stage 11 (+ regime membership roles)."""
from __future__ import annotations

from typing import Any

from cieml.ceam.context import CEAMContext
from cieml.ceam.models import InterpretationUnit, evidence_item


def interpret_spatial(ctx: CEAMContext, regimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[InterpretationUnit] = []
    rep = ctx.spatial_report or {}
    grads = ctx.spatial_gradients

    if not rep and (grads is None or not len(grads)):
        units.append(
            InterpretationUnit(
                topic="spatial_structure",
                observation="Stage 11 spatial products are absent.",
                interpretation="Spatial coastal structure cannot be assessed beyond regime membership shares.",
                supporting_evidence=[],
                confidence="exploratory",
                uncertainty="Missing Stage 11.",
                limitations=["Do not invent harbour–open-coast gradients."],
                level="observation",
                rejected=True,
                reject_reason="Missing Stage 11 artifacts.",
            )
        )
    else:
        n_sig = 0
        if grads is not None and len(grads) and "significant_05" in grads.columns:
            n_sig = int(grads["significant_05"].astype(bool).sum())
        units.append(
            InterpretationUnit(
                topic="coastal_gradients",
                observation=(
                    f"Stage 11: n_stations={rep.get('n_stations')}, network_edges={rep.get('n_network_edges')}, "
                    f"significant gradients (p<0.05)={n_sig}. Caveat: {rep.get('spatial_gradient_caveat', '')[:160]}"
                ),
                interpretation=(
                    "Statistically significant spatial gradients are limited; treat strong |rho| without significance as noise at small n."
                    if n_sig == 0
                    else "Some spatial gradients clear p<0.05; interpret cautiously given small station count."
                ),
                supporting_evidence=[
                    evidence_item("stage_11", "stage11_spatial_temporal_report.json", "n_network_edges", rep.get("n_network_edges"), "Similarity network", "moderate"),
                    evidence_item("stage_11", "stage11_spatial_gradients.csv", "n_significant_05", n_sig, "Gradient significance", "strong"),
                ],
                confidence="provisional",
                uncertainty=str(rep.get("spatial_gradient_caveat") or "Small-n spatial tests are fragile."),
                limitations=["n_stations is small for Spearman gradients."],
                level="interpretation",
            )
        )

    # Harbour vs open coast from roles × membership
    harbour_dom = [r for r in regimes if float(r.get("harbour_role_membership_share") or 0) >= ctx.thresholds.get("harbour_membership_partial", 0.3)]
    units.append(
        InterpretationUnit(
            topic="harbour_vs_open_coast",
            observation=(
                f"{len(harbour_dom)} regime(s) have harbour-role membership ≥ partial gate; "
                f"station roles from campaign config: {ctx.station_roles}."
            ),
            interpretation=(
                "Environmental structure separates harbour-role stations from open-coast/ambient roles for at least one regime."
                if harbour_dom
                else "No regime is dominated by harbour-role stations under domain gates."
            ),
            supporting_evidence=[
                evidence_item("campaign", "configs/campaigns/*.yaml", "station.role", ctx.station_roles, "Role vocabulary (not place-name heuristics)", "strong"),
                evidence_item("stage_06", "membership shares", "harbour_role_membership_share", [r.get("harbour_role_membership_share") for r in regimes], "Role-aggregated membership", "strong"),
            ],
            confidence="provisional" if harbour_dom else "supported",
            uncertainty="Roles are campaign metadata; mislabeled roles would mislead CEAM.",
            limitations=["Nearshore vs offshore not resolved without depth/distance layers."],
            level="interpretation",
        )
    )

    return [u.to_dict() for u in units]
