"""Canonical observation schema (dataset-independent)."""
from __future__ import annotations

from typing import Any

# Logical keys every adapter should populate when available.
CANONICAL_KEYS = {
    "station": "Station / site identifier (campaign-canonical).",
    "timestamp": "Observation timestamp (timezone policy from campaign).",
    "sample_date": "Calendar date of the cast / sample (ISO date string).",
    "source_file": "Provenance path to the raw file.",
    "variable_columns": "Canonical environmental variables (temperature_c, …).",
}

META_COLUMNS = {"station", "timestamp", "sample_date", "source_file", "time_raw", "date_raw",
                "file_name", "site_code", "user_id", "fault_code"}


def describe_schema() -> dict[str, Any]:
    return {"canonical_keys": CANONICAL_KEYS, "meta_columns": sorted(META_COLUMNS)}
