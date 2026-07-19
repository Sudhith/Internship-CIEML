"""Stage 10: External environmental validation of anomalies and regimes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
import yaml
from scipy import stats
from statsmodels.stats.multitest import multipletests

from cieml.config import CONFIG_DIR, DATA_DIR, DEFAULT_CAMPAIGN, PHASE6_DIR, ROOT
from cieml.failure import build_failure_report

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def _meteo_cache_candidates(campaign_id: str) -> list[Path]:
    """Offline fallbacks for System B / air-gapped runs (committed under DATA/external/)."""
    cid = campaign_id or DEFAULT_CAMPAIGN
    return [
        DATA_DIR / "external" / f"open_meteo_archive_{cid}.csv",
        ROOT / "outputs" / "phase6" / "stage10_meteo_daily.csv",
    ]


def _load_meteo_cache(campaign_id: str, start: str, end: str) -> tuple[pd.DataFrame | None, str | None]:
    for path in _meteo_cache_candidates(campaign_id):
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
            if "sample_date" not in df.columns:
                continue
            df = df.copy()
            df["sample_date"] = pd.to_datetime(df["sample_date"]).dt.strftime("%Y-%m-%d")
            mask = (df["sample_date"] >= start) & (df["sample_date"] <= end)
            clipped = df.loc[mask].reset_index(drop=True)
            if len(clipped) == 0:
                continue
            if "meteo_source" not in clipped.columns:
                clipped["meteo_source"] = f"offline_cache:{path.name}"
            return clipped, str(path)
        except Exception:  # noqa: BLE001
            continue
    return None, None


def _campaign_region() -> dict:
    try:
        from cieml.domain import load_campaign
        camp = load_campaign()
        region = dict(camp.region or {})
        if region.get('latitude') is not None:
            return region
    except Exception:
        pass
    path = CONFIG_DIR / "stations.yaml"
    if path.exists():
        import yaml
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return dict(raw.get("campaign_region") or {})
    return {"latitude": 17.72, "longitude": 83.30}


def _load_region_meta() -> dict[str, Any]:
    """Prefer campaign profile; fall back to legacy stations.yaml."""
    try:
        from cieml.domain import load_campaign

        camp = load_campaign()
        return {
            "campaign_region": dict(camp.region or {}),
            "stations": dict(camp.stations or {}),
            "campaign_id": camp.campaign_id,
        }
    except Exception:
        pass
    path = CONFIG_DIR / "stations.yaml"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "campaign_region": {"latitude": 17.72, "longitude": 83.30, "name": "unspecified"},
    }


def fetch_open_meteo_daily(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """Fetch daily meteorology from Open-Meteo archive (no API key)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(
            [
                "precipitation_sum",
                "rain_sum",
                "temperature_2m_mean",
                "temperature_2m_max",
                "temperature_2m_min",
                "relative_humidity_2m_mean",
                "windspeed_10m_max",
                "windspeed_10m_mean",
                "winddirection_10m_dominant",
                "shortwave_radiation_sum",
                "et0_fao_evapotranspiration",
            ]
        ),
        "timezone": "auto",
    }
    r = requests.get(OPEN_METEO_ARCHIVE, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    daily = payload.get("daily", {})
    if not daily or "time" not in daily:
        raise RuntimeError(f"Open-Meteo returned no daily block: {payload}")
    df = pd.DataFrame(daily)
    df = df.rename(columns={"time": "sample_date"})
    df["sample_date"] = pd.to_datetime(df["sample_date"]).dt.strftime("%Y-%m-%d")
    df["meteo_source"] = "open_meteo_archive"
    df["meteo_latitude"] = lat
    df["meteo_longitude"] = lon
    return df


def _cross_corr_table(env: pd.DataFrame, meteo: pd.DataFrame, env_cols: list[str], meteo_cols: list[str], max_lag: int = 3) -> pd.DataFrame:
    merged = env.merge(meteo, on="sample_date", how="inner")
    rows = []
    for e in env_cols:
        if e not in merged.columns:
            continue
        for m in meteo_cols:
            if m not in merged.columns:
                continue
            a = pd.to_numeric(merged[e], errors="coerce")
            b = pd.to_numeric(merged[m], errors="coerce")
            for lag in range(0, max_lag + 1):
                if lag == 0:
                    aa, bb = a, b
                else:
                    aa = a.iloc[lag:].reset_index(drop=True)
                    bb = b.iloc[:-lag].reset_index(drop=True)
                mask = aa.notna() & bb.notna()
                if mask.sum() < 10:
                    continue
                rho, p = stats.spearmanr(aa[mask], bb[mask])
                rows.append(
                    {
                        "env_var": e,
                        "meteo_var": m,
                        "lag_days_meteo_leads": lag,
                        "rho": float(rho),
                        "p": float(p),
                        "n": int(mask.sum()),
                        "significant_05": bool(p < 0.05),
                    }
                )
    return pd.DataFrame(rows)


def run_stage10(
    regime_labels: pd.DataFrame,
    anomaly_flags: pd.DataFrame | None = None,
    anomaly_catalog: pd.DataFrame | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir or PHASE6_DIR)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    meta = _load_region_meta()
    region = meta.get("campaign_region", {})
    lat = float(region.get("latitude", 17.72))
    lon = float(region.get("longitude", 83.30))

    labels = regime_labels.copy()
    labels["sample_date"] = pd.to_datetime(labels["sample_date"]).dt.strftime("%Y-%m-%d")
    start = str(labels["sample_date"].min())
    end = str(labels["sample_date"].max())

    campaign_id = str(meta.get("campaign_id") or DEFAULT_CAMPAIGN)
    fetch_notes = []
    try:
        meteo = fetch_open_meteo_daily(lat, lon, start, end)
        fetch_notes.append("open_meteo_ok")
    except Exception as exc:  # noqa: BLE001
        fetch_notes.append(f"open_meteo_failed:{exc}")
        cached, cache_path = _load_meteo_cache(campaign_id, start, end)
        if cached is not None:
            meteo = cached
            fetch_notes.append(f"open_meteo_cache_ok:{cache_path}")
        else:
            meteo = pd.DataFrame()
            fetch_notes.append("open_meteo_cache_miss")

    # Coastline daily environmental aggregates from sonde labels
    feat_cols = [
        c for c in labels.columns
        if c not in {"station", "sample_date", "regime", "regime_algorithm", "regime_k", "pc1", "pc2", "consensus_regime"}
        and pd.api.types.is_numeric_dtype(labels[c])
    ]
    daily_env = labels.groupby("sample_date")[feat_cols].mean().reset_index()
    # Anomaly rate by day
    if anomaly_flags is not None and len(anomaly_flags) and "anomaly_consensus" in anomaly_flags.columns:
        af = anomaly_flags.copy()
        af["sample_date"] = pd.to_datetime(af["sample_date"]).dt.strftime("%Y-%m-%d")
        ar = af.groupby("sample_date")["anomaly_consensus"].mean().rename("anomaly_rate").reset_index()
        daily_env = daily_env.merge(ar, on="sample_date", how="left")
    else:
        daily_env["anomaly_rate"] = np.nan

    meteo_cols = [
        c for c in [
            "precipitation_sum", "rain_sum", "temperature_2m_mean", "relative_humidity_2m_mean",
            "windspeed_10m_max", "windspeed_10m_mean", "shortwave_radiation_sum",
        ]
        if len(meteo) and c in meteo.columns
    ]
    # Test every retained mean/index feature against meteorology — do not silently
    # truncate the list. An earlier `[:8]` cap here dropped temperature_c__mean and
    # turbidity_fnu__mean purely because of alphabetical column order, which is exactly
    # backwards: turbidity is the variable this study's own storm-lag anomaly narrative
    # hinges on, so it must never be excluded from the external-validation cross-correlation.
    env_for_corr = [c for c in feat_cols if c.endswith("__mean") or c.startswith("idx_")]
    if "anomaly_rate" in daily_env.columns:
        env_for_corr = env_for_corr + ["anomaly_rate"]

    if len(meteo) and meteo_cols:
        xcorr = _cross_corr_table(daily_env, meteo, env_for_corr, meteo_cols, max_lag=3)
        if len(xcorr):
            # Many env x meteo x lag combinations are tested simultaneously — at alpha=0.05
            # uncorrected, chance alone predicts roughly 5% "significant" hits regardless of
            # any real relationship. Add Benjamini-Hochberg FDR correction so the report
            # distinguishes real signal from multiple-testing noise.
            rej, p_fdr, _, _ = multipletests(xcorr["p"].to_numpy(), alpha=0.05, method="fdr_bh")
            xcorr["p_fdr"] = p_fdr
            xcorr["significant_fdr_05"] = rej
    else:
        xcorr = pd.DataFrame()

    # Event matching: high-precip / high-wind days vs anomaly days
    event_rows = []
    if len(meteo) and "precipitation_sum" in meteo.columns:
        m = meteo.copy()
        precip = pd.to_numeric(m["precipitation_sum"], errors="coerce")
        wind = pd.to_numeric(m.get("windspeed_10m_max", pd.Series(index=m.index)), errors="coerce")
        # Data-driven event thresholds: top quartile within campaign
        p_thr = float(precip.quantile(0.75)) if precip.notna().any() else np.nan
        w_thr = float(wind.quantile(0.75)) if wind.notna().any() else np.nan
        m["precip_event"] = (precip >= p_thr).astype(int) if np.isfinite(p_thr) else 0
        m["wind_event"] = (wind >= w_thr).astype(int) if np.isfinite(w_thr) else 0
        merged = daily_env.merge(m, on="sample_date", how="left")
        anom = (merged.get("anomaly_rate", 0).fillna(0) > 0).astype(int)
        for ev_name in ["precip_event", "wind_event"]:
            ev = merged[ev_name].fillna(0).astype(int)
            # contingency enrichment
            both = int(((ev == 1) & (anom == 1)).sum())
            ev_only = int(((ev == 1) & (anom == 0)).sum())
            anom_only = int(((ev == 0) & (anom == 1)).sum())
            neither = int(((ev == 0) & (anom == 0)).sum())
            # Fisher exact
            oddsratio, p_fisher = stats.fisher_exact([[both, ev_only], [anom_only, neither]])
            event_rows.append(
                {
                    "event": ev_name,
                    "threshold": p_thr if "precip" in ev_name else w_thr,
                    "n_event_days": int(ev.sum()),
                    "n_anomaly_days": int(anom.sum()),
                    "n_cooccurrence": both,
                    "odds_ratio": float(oddsratio) if np.isfinite(oddsratio) else np.nan,
                    "fisher_p": float(p_fisher),
                    "consistent_with_driver": bool(p_fisher < 0.05 and both > 0),
                }
            )
            # Lagged match: anomaly day after event (0-2 days). Uses the same Fisher exact
            # test as lag 0 rather than a bare "co-occurrence count > 0" check — with only
            # ~9-10 event/anomaly days out of 31, at least one overlapping day is likely
            # even under pure chance, so "any overlap" is not evidence of a real lagged
            # relationship. This previously let e.g. wind_event_lag0/1/2 report
            # consistent_with_driver=true in the same run where the properly-tested
            # wind_event (identical lag-0 data) reported false — a direct contradiction.
            for lag in range(0, 3):
                shifted = ev.shift(lag).fillna(0).astype(int)
                both_l = int(((shifted == 1) & (anom == 1)).sum())
                ev_only_l = int(((shifted == 1) & (anom == 0)).sum())
                anom_only_l = int(((shifted == 0) & (anom == 1)).sum())
                neither_l = int(((shifted == 0) & (anom == 0)).sum())
                or_l, p_l = stats.fisher_exact([[both_l, ev_only_l], [anom_only_l, neither_l]])
                event_rows.append(
                    {
                        "event": f"{ev_name}_lag{lag}",
                        "threshold": p_thr if "precip" in ev_name else w_thr,
                        "n_event_days": int(ev.sum()),
                        "n_anomaly_days": int(anom.sum()),
                        "n_cooccurrence": both_l,
                        "odds_ratio": float(or_l) if np.isfinite(or_l) else np.nan,
                        "fisher_p": float(p_l),
                        "consistent_with_driver": bool(p_l < 0.05 and both_l > 0),
                    }
                )
    events_df = pd.DataFrame(event_rows)

    # Per-anomaly catalog enrichment
    enriched = []
    if anomaly_catalog is not None and len(anomaly_catalog) and len(meteo):
        cat = anomaly_catalog.copy()
        cat["sample_date"] = pd.to_datetime(cat["sample_date"]).dt.strftime("%Y-%m-%d")
        mm = meteo.set_index("sample_date")
        for _, row in cat.iterrows():
            d = row["sample_date"]
            rec = row.to_dict()
            if d in mm.index:
                for c in meteo_cols:
                    rec[f"meteo_{c}"] = mm.loc[d, c]
                # previous day precip
                prev = (pd.to_datetime(d) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                if prev in mm.index and "precipitation_sum" in mm.columns:
                    rec["meteo_precip_lag1"] = mm.loc[prev, "precipitation_sum"]
            # Consistency label. Both same-day and lag-1 precipitation are judged against
            # the same data-driven top-quartile threshold (p_thr) used everywhere else in
            # this function — a separate hardcoded "1.0mm" constant here would apply a
            # different, arbitrary bar to the lag-1 case than to every other wet-weather check.
            precip_now = rec.get("meteo_precipitation_sum", np.nan)
            precip_lag1 = rec.get("meteo_precip_lag1", np.nan)
            wind_now = rec.get("meteo_windspeed_10m_max", np.nan)
            phys = str(rec.get("physical_class", ""))
            precip_thr = events_df.loc[events_df["event"] == "precip_event", "threshold"].iloc[0] if len(events_df) else 1e9
            wind_thr = events_df.loc[events_df["event"] == "wind_event", "threshold"].iloc[0] if len(events_df) else 1e9
            if (np.isfinite(precip_now) and precip_now >= precip_thr) or (
                np.isfinite(precip_lag1) and precip_lag1 >= precip_thr
            ):
                if "turbidity" in phys or "multivariate" in phys or "salinity" in phys:
                    rec["external_consistency"] = "supported_by_wet_weather"
                else:
                    rec["external_consistency"] = "wet_weather_present_mechanism_unclear"
            elif np.isfinite(wind_now) and wind_now >= wind_thr:
                rec["external_consistency"] = "supported_by_high_wind"
            else:
                rec["external_consistency"] = "no_strong_meteo_match_sensor_or_local_process"
            enriched.append(rec)
    enriched_df = pd.DataFrame(enriched)

    # H5 update based on external consistency
    if len(enriched_df):
        support_frac = float((enriched_df["external_consistency"].str.startswith("supported")).mean())
        if support_frac >= 0.3:
            h5_status, h5_verdict = "PROVISIONAL_SUPPORT", "lean_alternative_partial_external_support"
        elif support_frac > 0:
            h5_status, h5_verdict = "MIXED_EVIDENCE", "exploratory_partial_external_support"
        else:
            h5_status, h5_verdict = "MIXED_EVIDENCE", "exploratory_no_meteo_match"
    elif len(meteo):
        h5_status, h5_verdict = "MIXED_EVIDENCE", "meteo_available_but_no_anomaly_catalog"
    else:
        h5_status, h5_verdict = "UNTESTED_EXTERNAL", "meteo_fetch_failed"

    # Figures
    fig_paths: dict[str, str] = {}
    if len(meteo) and "precipitation_sum" in meteo.columns:
        fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
        x = pd.to_datetime(meteo["sample_date"])
        axes[0].bar(x, meteo["precipitation_sum"], color="#1f4e79", width=0.8)
        axes[0].set_ylabel("Precip (mm)")
        axes[0].set_title("Stage 10 — Regional meteorology (Open-Meteo)")
        if "windspeed_10m_max" in meteo.columns:
            axes[1].plot(x, meteo["windspeed_10m_max"], color="#2e7d4f", marker="o", ms=3)
            axes[1].set_ylabel("Wind max (m/s)")
        if "anomaly_rate" in daily_env.columns:
            axes[2].plot(pd.to_datetime(daily_env["sample_date"]), daily_env["anomaly_rate"], color="#c62828", marker="o", ms=3)
            axes[2].set_ylabel("Anomaly rate")
        fig.autofmt_xdate()
        fig.tight_layout()
        p = fig_dir / "fig_stage10_meteo_vs_anomalies.png"
        fig.savefig(p, dpi=600, bbox_inches="tight")
        plt.close(fig)
        fig_paths["meteo_vs_anomalies"] = str(p)

    if len(xcorr):
        # best lag=0 heatmap for significant pairs
        sub = xcorr[xcorr["lag_days_meteo_leads"] == 0].copy()
        if len(sub):
            pivot = sub.pivot(index="env_var", columns="meteo_var", values="rho")
            fig, ax = plt.subplots(figsize=(9, 5))
            sns.heatmap(pivot, cmap="RdBu_r", center=0, annot=True, fmt=".2f", ax=ax)
            ax.set_title("Stage 10 — Spearman rho (lag 0) env × meteo")
            fig.tight_layout()
            p2 = fig_dir / "fig_stage10_crosscorr_heatmap.png"
            fig.savefig(p2, dpi=600, bbox_inches="tight")
            plt.close(fig)
            fig_paths["crosscorr"] = str(p2)

        # Lag response for top |rho| pair involving precipitation or wind
        focus = xcorr.copy()
        focus["abs_rho"] = focus["rho"].abs()
        focus = focus.sort_values("abs_rho", ascending=False)
        if len(focus):
            top = focus.iloc[0]
            curve = xcorr[(xcorr["env_var"] == top["env_var"]) & (xcorr["meteo_var"] == top["meteo_var"])]
            fig, ax = plt.subplots(figsize=(6, 3.5))
            ax.plot(curve["lag_days_meteo_leads"], curve["rho"], marker="o", color="#1f4e79")
            ax.axhline(0, color="black", lw=0.8)
            ax.set_xlabel("Lag (meteo leads, days)")
            ax.set_ylabel("Spearman rho")
            ax.set_title(f"Stage 10 — Lag response: {top['meteo_var']} → {top['env_var']}")
            fig.tight_layout()
            p3 = fig_dir / "fig_stage10_lag_response.png"
            fig.savefig(p3, dpi=600, bbox_inches="tight")
            plt.close(fig)
            fig_paths["lag_response"] = str(p3)

    support_frac = float((enriched_df["external_consistency"].str.startswith("supported")).mean()) if len(enriched_df) else None

    # SC-FMF: supplementary Anomaly Intelligence failure check. Stage 9 already
    # evaluated anom_zero_consensus at its own completion; anom_no_external_validation
    # can only be evaluated here, once anomaly_external_support_frac exists (Stage 10
    # runs after Stage 9). Stage 14 consolidates both into one final failure report
    # for engine_id="anomaly_intelligence" — this is not a duplicate assessment of
    # the same evidence, it is the first time this specific mode's evidence exists.
    failure_report = build_failure_report("anomaly_intelligence", {"anomaly_external_support_frac": support_frac})

    report = {
        "region": region,
        "date_range": {"start": start, "end": end},
        "fetch_notes": fetch_notes,
        "n_meteo_days": int(len(meteo)),
        "meteo_variables": meteo_cols,
        "n_crosscorr_tests": int(len(xcorr)),
        "n_significant_crosscorr_05": int(xcorr["significant_05"].sum()) if len(xcorr) else 0,
        "n_significant_crosscorr_fdr_05": int(xcorr["significant_fdr_05"].sum()) if len(xcorr) and "significant_fdr_05" in xcorr else 0,
        "event_tests": events_df.to_dict(orient="records") if len(events_df) else [],
        "anomaly_external_support_frac": support_frac,
        "h5_update": {
            "hypothesis": "H5_anomaly_reality",
            "status": h5_status,
            "verdict_lean": h5_verdict,
            "note": "External validation uses Open-Meteo regional meteorology; satellite/tide/discharge not yet integrated.",
        },
        "limitations": [
            "Single regional meteo point — not station-resolved.",
            "No independent tide/wave/river/satellite layers in this run.",
            "Association does not prove causation.",
        ],
        "failure_report": failure_report,
        "figures": fig_paths,
    }

    if len(meteo):
        meteo.to_csv(output_dir / "stage10_meteo_daily.csv", index=False)
    daily_env.to_csv(output_dir / "stage10_daily_env_means.csv", index=False)
    if len(xcorr):
        xcorr.to_csv(output_dir / "stage10_crosscorr_lags.csv", index=False)
    if len(events_df):
        events_df.to_csv(output_dir / "stage10_event_matching.csv", index=False)
    if len(enriched_df):
        enriched_df.to_csv(output_dir / "stage10_anomaly_external_enrichment.csv", index=False)
    report_path = output_dir / "stage10_external_report.json"
    report["outputs"] = {"meteo": str(output_dir / "stage10_meteo_daily.csv") if len(meteo) else None}
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (output_dir / "stage10_failure_report.json").write_text(
        json.dumps(failure_report, indent=2, default=str), encoding="utf-8"
    )

    return {
        "meteo": meteo,
        "daily_env": daily_env,
        "crosscorr": xcorr,
        "events": events_df,
        "enriched_anomalies": enriched_df,
        "report": report,
        "failure_report": failure_report,
    }
