"""Multi-format readers with automatic encoding and Kor sonde export support."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .naming import detect_station_from_text, standardize_columns


@dataclass
class FileReadResult:
    path: Path
    observations: pd.DataFrame
    summary_means: dict[str, Any] = field(default_factory=dict)
    summary_stds: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _detect_encoding(path: Path) -> str:
    raw = path.read_bytes()[:4]
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"


def _parse_kor_export(path: Path, text: str) -> FileReadResult:
    lines = text.splitlines()
    warnings: list[str] = []
    metadata: dict[str, Any] = {
        "source_format": "kor_measurement_export",
        "path": str(path),
    }

    for line in lines[:20]:
        if line.upper().startswith("FILE CREATED:"):
            metadata["file_created"] = line.split(":", 1)[-1].lstrip(",").strip()
        if "KOR MEASUREMENT" in line.upper():
            metadata["export_banner"] = line.strip()

    mean_line = next((L for L in lines if L.startswith("MEAN VALUE:")), None)
    std_line = next((L for L in lines if L.startswith("STANDARD DEVIATION:")), None)
    sensor_line = next((L for L in lines if L.startswith("SENSOR SERIAL")), None)
    header_i = next((i for i, L in enumerate(lines) if L.startswith("TIME (")), None)
    if header_i is None:
        raise ValueError(f"No TIME header found in {path}")

    header = lines[header_i].split(",")
    colmap = standardize_columns(header)

    def parse_summary(line: Optional[str]) -> dict[str, Any]:
        if not line:
            return {}
        # Kor mean/std rows omit FAULT CODE: 5 empties then sensor values
        parts = line.split(",")[1:]
        if len(parts) < 6:
            return {}
        # Rebuild aligned to raw header by inserting empty FAULT slot
        aligned = parts[:5] + [""] + parts[5:]
        while len(aligned) < len(header):
            aligned.append("")
        out: dict[str, Any] = {}
        for raw, val in zip(header, aligned):
            canon = colmap.get(raw)
            if not canon:
                continue
            token = str(val).strip()
            if token.upper() in {"", "NA", "NAN", "N/A", "#N/A"}:
                out[canon] = float("nan")
            else:
                try:
                    out[canon] = float(token)
                except ValueError:
                    out[canon] = token
        return out

    means = parse_summary(mean_line)
    stds = parse_summary(std_line)
    if sensor_line:
        metadata["sensor_serial_raw"] = sensor_line

    df = pd.read_csv(StringIO("\n".join(lines[header_i:])))
    rename = {c: colmap[c] for c in df.columns if c in colmap}
    df = df.rename(columns=rename)

    # Timestamp
    if "date_raw" in df.columns and "time_raw" in df.columns:
        ts = pd.to_datetime(
            df["date_raw"].astype(str) + " " + df["time_raw"].astype(str),
            errors="coerce",
        )
        df.insert(0, "timestamp", ts)
    elif "date_raw" in df.columns:
        df.insert(0, "timestamp", pd.to_datetime(df["date_raw"], errors="coerce"))

    station = detect_station_from_text(path.stem) or detect_station_from_text(path.parent.name)
    if station is None and "site_code" in df.columns and len(df):
        station = detect_station_from_text(str(df["site_code"].iloc[0]))
    if station is None:
        station = "UNKNOWN"
        warnings.append("station_unresolved")

    # Date from folder/filename/rows
    date_guess = None
    if "timestamp" in df.columns and df["timestamp"].notna().any():
        date_guess = pd.Timestamp(df["timestamp"].dropna().iloc[0]).normalize()
    metadata["station"] = station
    metadata["date"] = None if date_guess is None else date_guess.date().isoformat()
    metadata["n_rows"] = int(len(df))
    metadata["raw_columns"] = list(header)
    metadata["canonical_columns"] = list(rename.values())

    df["station"] = station
    df["source_file"] = str(path)
    if date_guess is not None:
        df["sample_date"] = date_guess.date().isoformat()

    # Coerce numerics for canonical env variables
    numeric_candidates = [
        c for c in df.columns
        if c not in {"time_raw", "date_raw", "file_name", "site_code", "user_id",
                     "station", "source_file", "sample_date", "timestamp"}
    ]
    for c in numeric_candidates:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return FileReadResult(
        path=path,
        observations=df,
        summary_means=means,
        summary_stds=stds,
        metadata=metadata,
        warnings=warnings,
    )


def read_data_file(path: Path) -> FileReadResult:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
        colmap = standardize_columns(list(df.columns))
        df = df.rename(columns={c: colmap[c] for c in df.columns if c in colmap})
        station = detect_station_from_text(path.stem) or "UNKNOWN"
        df["station"] = station
        df["source_file"] = str(path)
        return FileReadResult(path=path, observations=df, metadata={"source_format": "excel", "station": station})

    encoding = _detect_encoding(path)
    try:
        text = path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin1")
        encoding = "latin1"

    if "KOR MEASUREMENT" in text.upper() or any(L.startswith("MEAN VALUE:") for L in text.splitlines()[:30]):
        result = _parse_kor_export(path, text)
        result.metadata["encoding"] = encoding
        return result

    # Generic delimited
    df = pd.read_csv(path, encoding=encoding)
    colmap = standardize_columns(list(df.columns))
    df = df.rename(columns={c: colmap[c] for c in df.columns if c in colmap})
    station = detect_station_from_text(path.stem) or "UNKNOWN"
    df["station"] = station
    df["source_file"] = str(path)
    return FileReadResult(
        path=path,
        observations=df,
        metadata={"source_format": "generic_csv", "encoding": encoding, "station": station},
    )


def discover_files(data_dir: Path) -> list[Path]:
    data_dir = Path(data_dir)
    patterns = ("*.csv", "*.CSV", "*.xlsx", "*.xls", "*.txt", "*.TXT")
    files: list[Path] = []
    for pat in patterns:
        files.extend(data_dir.rglob(pat))
    # Prefer unique resolved paths
    uniq = sorted({p.resolve() for p in files})
    return uniq
