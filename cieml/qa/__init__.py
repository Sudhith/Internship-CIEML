"""Scientific QA Engine registry (Phase D) — SC-QA."""
from __future__ import annotations

from cieml.qa.engine import run_qa_checks
from cieml.qa.registry import get_check, list_checks

__all__ = ["run_qa_checks", "get_check", "list_checks"]
