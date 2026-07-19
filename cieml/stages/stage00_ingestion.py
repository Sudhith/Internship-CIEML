"""Stage 0: Data ingestion and standardization (Universal Ingestion — Phase C)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from cieml.config import CORE_VARIABLES, DATA_DIR, DEFAULT_CAMPAIGN, PHASE1_DIR
from cieml.domain import load_campaign, load_domain
from cieml.ingestion.registry import detect_and_read, discover_campaign_files


def run_stage00(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    campaign_id: str | None = None,
    domain_name: str | None = None,
) -> dict[str, Any]:
    campaign = load_campaign(campaign_id or DEFAULT_CAMPAIGN)
    domain = load_domain(domain_name or campaign.domain)
    data_dir = Path(data_dir or campaign.data_dir or DATA_DIR)
    output_dir = Path(output_dir or PHASE1_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    core_vars = domain.core_variables or list(CORE_VARIABLES)
    files = discover_campaign_files(data_dir)
    obs_frames: list[pd.DataFrame] = []
    file_inventory: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for path in files:
        try:
            result = detect_and_read(path, campaign_adapter=campaign.adapter)
        except Exception as exc:  # noqa: BLE001 — inventory must continue
            failures.append({"path": str(path), "error": str(exc)})
            continue

        df = result.observations.copy()
        obs_frames.append(df)

        meta = dict(result.metadata)
        meta.update(
            {
                "path": str(path.relative_to(data_dir)) if path.is_relative_to(data_dir) else str(path),
                "n_rows": len(df),
                "n_cols": int(df.shape[1]),
                "warnings": result.warnings,
                "has_summary_means": bool(result.summary_means),
                "summary_ph_mean": result.summary_means.get("ph"),
                "campaign_id": campaign.campaign_id,
                "domain": domain.name,
            }
        )
        file_inventory.append(meta)

        if result.summary_means:
            summary_rows.append(
                {
                    "path": meta["path"],
                    "station": meta.get("station"),
                    "date": meta.get("date"),
                    "stat": "mean",
                    **{k: v for k, v in result.summary_means.items()},
                }
            )
        if result.summary_stds:
            summary_rows.append(
                {
                    "path": meta["path"],
                    "station": meta.get("station"),
                    "date": meta.get("date"),
                    "stat": "std",
                    **{k: v for k, v in result.summary_stds.items()},
                }
            )

    if not obs_frames:
        raise RuntimeError(f"No readable data files under {data_dir}")

    observations = pd.concat(obs_frames, ignore_index=True)
    inventory_df = pd.DataFrame(file_inventory)
    summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()

    value_cols = [c for c in core_vars if c in observations.columns]
    extras = [
        c
        for c in observations.columns
        if c.endswith(("_us_cm", "_mg_l", "_psu", "_pct", "_fnu", "_c", "_mmhg", "_mv")) and c not in value_cols
    ]
    measure_cols = sorted(set(value_cols + extras))

    group_cols = [c for c in ["station", "sample_date"] if c in observations.columns]
    if group_cols and measure_cols:
        daily = observations.groupby(group_cols, dropna=False)[measure_cols].mean().reset_index()
    else:
        daily = pd.DataFrame()

    inv_path = output_dir / "stage00_file_inventory.csv"
    sum_path = output_dir / "stage00_file_summaries.csv"
    daily_path = output_dir / "stage00_daily_aggregates.csv"
    report_path = output_dir / "stage00_data_inventory_report.json"
    obs_parquet = output_dir / "stage00_observations.parquet"

    try:
        observations.to_parquet(obs_parquet, index=False)
        obs_out = str(obs_parquet)
    except Exception:
        obs_csv = output_dir / "stage00_observations.csv"
        observations.to_csv(obs_csv, index=False)
        obs_out = str(obs_csv)

    inventory_df.to_csv(inv_path, index=False)
    if len(summary_df):
        summary_df.to_csv(sum_path, index=False)
    if len(daily):
        daily.to_csv(daily_path, index=False)

    report = {
        "data_dir": str(data_dir),
        "campaign_id": campaign.campaign_id,
        "domain": domain.name,
        "domain_version": domain.version,
        "adapter": campaign.adapter,
        "n_files_discovered": len(files),
        "n_files_loaded": len(file_inventory),
        "n_files_failed": len(failures),
        "failures": failures,
        "n_observations": int(len(observations)),
        "stations": sorted(observations["station"].dropna().astype(str).unique().tolist())
        if "station" in observations.columns
        else [],
        "date_range": {
            "min": str(observations["sample_date"].min()) if "sample_date" in observations.columns else None,
            "max": str(observations["sample_date"].max()) if "sample_date" in observations.columns else None,
        },
        "canonical_variables_present": [c for c in core_vars if c in observations.columns],
        "canonical_variables_missing": [c for c in core_vars if c not in observations.columns],
        "all_measure_columns": measure_cols,
        "outputs": {
            "observations": obs_out,
            "inventory": str(inv_path),
            "summaries": str(sum_path) if len(summary_df) else None,
            "daily": str(daily_path) if len(daily) else None,
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "observations": observations,
        "inventory": inventory_df,
        "summaries": summary_df,
        "daily": daily,
        "report": report,
        "domain": domain,
        "campaign": campaign,
    }
