"""Adapter registry — select reader without assuming column names."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from cieml.utils.io import FileReadResult, discover_files, read_data_file


ADAPTERS = {
    "kor_ysi": "YSI Kor measurement export (auto-detected by banner / MEAN VALUE).",
    "generic_csv": "Delimited table with header row; columns mapped via synonyms.",
    "excel": "Excel workbook; columns mapped via synonyms.",
    "auto": "Detect from content (default).",
}


def read_path(path: Path, adapter: str = "auto") -> FileReadResult:
    """Read one file. Today delegates to cieml.utils.io with adapter hint in metadata."""
    path = Path(path)
    result = read_data_file(path)
    # Honor explicit adapter tagging for inventory / downstream
    if adapter and adapter != "auto":
        result.metadata["requested_adapter"] = adapter
        if adapter == "generic_csv" and result.metadata.get("source_format") == "kor_measurement_export":
            result.warnings.append("requested_generic_csv_but_detected_kor")
    result.metadata["adapter_resolved"] = result.metadata.get("source_format", adapter)
    return result


def detect_and_read(path: Path, campaign_adapter: str | None = None) -> FileReadResult:
    return read_path(path, adapter=campaign_adapter or "auto")


def discover_campaign_files(data_dir: Path) -> list[Path]:
    return discover_files(data_dir)
