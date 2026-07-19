"""Universal Ingestion layer (Phase C) — SC-ING."""
from __future__ import annotations

from cieml.ingestion.registry import detect_and_read, read_path
from cieml.ingestion.schema import CANONICAL_KEYS, describe_schema

__all__ = ["detect_and_read", "read_path", "CANONICAL_KEYS", "describe_schema"]
