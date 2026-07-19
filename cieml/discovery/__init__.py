"""Discovery Engine surface (Phase G) — SC-DISC.

Stages 6–7 remain the implementation. This package exposes a stable API and
selection-trace helpers so callers never assume a fixed algorithm or K.
"""
from __future__ import annotations

from cieml.discovery.api import build_selection_trace, discovery_contract_block

__all__ = ["build_selection_trace", "discovery_contract_block"]
