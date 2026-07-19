"""Scientific Failure Mode Framework (SC-FMF) — detect, assess, message."""
from __future__ import annotations

from cieml.failure.assess import FailureAssessment, assess_engine, assess_campaign
from cieml.failure.catalog import FailureMode, load_failure_catalog
from cieml.failure.models import FailureModeHit, Severity
from cieml.failure.report import build_failure_report

__all__ = [
    "FailureAssessment",
    "FailureMode",
    "FailureModeHit",
    "Severity",
    "assess_campaign",
    "assess_engine",
    "build_failure_report",
    "load_failure_catalog",
]
