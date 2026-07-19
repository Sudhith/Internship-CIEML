"""Coastal Environmental Analysis Module (CEAM) — Stage 12 interpretation layer.

Consumes upstream CIEML artifacts; does not re-run QA, physics, discovery, XAI,
anomaly detection, or EBSVE scoring.
"""
from __future__ import annotations

from cieml.ceam.engine import run_ceam

__all__ = ["run_ceam"]
