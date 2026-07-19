"""Uncertainty Model v2 -- Measurement & Model Uncertainty (SC-MMU) +
Evidence Reliability (SC-REL), both distinct from EBSVE Confidence (SC-EBSVE).

Confidence != Uncertainty != Evidence Reliability. This package models typed
uncertainty budgets with correlation-aware, provenance-deduplicated
propagation (no arbitrary averaging), an Evidence Reliability coverage
scorer, campaign ledgers, and reviewer visualizations. See
docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md for the full model.
"""
from __future__ import annotations

from cieml.uncertainty.assemble import build_campaign_uncertainty_ledger
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
from cieml.uncertainty.reliability import (
    ReliabilityDimension,
    build_reliability_dimensions,
    score_evidence_reliability,
)
from cieml.uncertainty.visualize import render_uncertainty_figures

__all__ = [
    "UncertaintyKind",
    "UncertaintyObject",
    "UncertaintyComponent",
    "UncertaintyBudget",
    "EngineUncertaintyPacket",
    "combine_correlated",
    "combine_raw",
    "fuse_precision",
    "propagate_engine",
    "root_budget",
    "saturate",
    "caution_index",
    "ReliabilityDimension",
    "build_reliability_dimensions",
    "score_evidence_reliability",
    "build_campaign_uncertainty_ledger",
    "render_uncertainty_figures",
]
