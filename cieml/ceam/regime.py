"""Environmental regime interpretation from Stage 6/8 fingerprints (domain-driven)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cieml.ceam.context import CEAMContext, harbour_membership_share, z_get
from cieml.ceam.models import InterpretationUnit, evidence_item


def _ensure_profiles(ctx: CEAMContext) -> pd.DataFrame:
    df = ctx.regime_labels
    if ctx.regime_profiles is not None and len(ctx.regime_profiles):
        return ctx.regime_profiles
    if df is None or not len(df) or "regime" not in df.columns:
        return pd.DataFrame()
    feat_cols = [
        c
        for c in df.columns
        if c not in {"station", "sample_date", "regime", "regime_algorithm", "regime_k", "pc1", "pc2", "consensus_regime"}
        and pd.api.types.is_numeric_dtype(df[c])
    ]
    gmean = df[feat_cols].mean()
    gstd = df[feat_cols].std(ddof=0).replace(0, 1)
    rows = []
    for reg, g in df.groupby("regime"):
        z = ((g[feat_cols].mean() - gmean) / gstd).to_dict()
        rows.append({"regime": int(reg), "n": int(len(g)), **{f"z__{k}": float(v) for k, v in z.items()}})
    return pd.DataFrame(rows)


def _z_cols(profile_row: pd.Series) -> dict[str, float]:
    return {str(k)[3:]: float(v) for k, v in profile_row.items() if str(k).startswith("z__")}


def interpret_regimes(ctx: CEAMContext) -> list[dict[str, Any]]:
    profiles = _ensure_profiles(ctx)
    df = ctx.regime_labels
    th = ctx.thresholds
    families = [f for f in ctx.regime_families if f != "insufficient_evidence_for_named_regime"]
    if not families:
        families = [
            "high_energy_coastal_regime",
            "harbour_regime",
            "freshwater_influenced_regime",
            "sediment_resuspension_regime",
            "hypoxic_regime",
            "mixed_transitional_regime",
            "offshore_marine_regime",
        ]

    campaign_drivers = []
    if ctx.shap_drivers is not None and len(ctx.shap_drivers):
        campaign_drivers = ctx.shap_drivers.loc[
            ctx.shap_drivers["tier"].isin(["Dominant", "Secondary"]), "feature"
        ].tolist()

    out: list[dict[str, Any]] = []
    for _, prow in profiles.iterrows():
        rid = int(prow["regime"])
        n = int(prow.get("n", 0) or 0)
        sub = df[df["regime"] == rid] if len(df) and "regime" in df.columns else pd.DataFrame()
        share = (
            sub["station"].value_counts(normalize=True)
            if len(sub) and "station" in sub.columns
            else pd.Series(dtype=float)
        )
        z = _z_cols(prow)
        rec = _score_regime(ctx, rid, n, z, share, families, campaign_drivers, th)
        out.append(rec)
    return out


def _score_regime(
    ctx: CEAMContext,
    regime_id: int,
    n: int,
    z: dict[str, float],
    station_share: pd.Series,
    families: list[str],
    campaign_drivers: list[str],
    th: dict[str, float],
) -> dict[str, Any]:
    do = z_get(z, ctx, "do")
    ph = z_get(z, ctx, "ph")
    sal = z_get(z, ctx, "salinity")
    turb = z_get(z, ctx, "turbidity")
    temp = z_get(z, ctx, "temperature")

    harbour_frac = harbour_membership_share(ctx, station_share)
    scores = {fam: 0.0 for fam in families}
    evidence_lines: list[str] = []
    units: list[InterpretationUnit] = []

    if harbour_frac >= th.get("harbour_membership_strong", 0.7):
        if "harbour_regime" in scores:
            scores["harbour_regime"] += 3.0
        evidence_lines.append(f"Station-role membership concentrated on harbour roles ({harbour_frac:.0%}).")
    elif harbour_frac >= th.get("harbour_membership_partial", 0.3):
        if "harbour_regime" in scores:
            scores["harbour_regime"] += 1.0
        evidence_lines.append(f"Partial harbour-role membership ({harbour_frac:.0%}).")

    if do <= th.get("do_depressed_strong", -1.5):
        if "hypoxic_regime" in scores:
            scores["hypoxic_regime"] += 3.0
        evidence_lines.append(f"Strongly depressed DO (z={do:+.2f}).")
    elif do <= th.get("do_depressed_mod", -0.8):
        if "hypoxic_regime" in scores:
            scores["hypoxic_regime"] += 1.5
        evidence_lines.append(f"Moderately depressed DO (z={do:+.2f}).")

    if sal <= th.get("salinity_fresh_strong", -1.0):
        if "freshwater_influenced_regime" in scores:
            scores["freshwater_influenced_regime"] += 3.0
        evidence_lines.append(f"Salinity depressed relative to campaign (z={sal:+.2f}).")
    elif sal <= th.get("salinity_fresh_mod", -0.5):
        if "freshwater_influenced_regime" in scores:
            scores["freshwater_influenced_regime"] += 1.0
        evidence_lines.append(f"Mild salinity depression (z={sal:+.2f}).")

    if sal >= th.get("salinity_marine_strong", 0.8):
        if "offshore_marine_regime" in scores:
            scores["offshore_marine_regime"] += 2.5
        evidence_lines.append(f"Elevated salinity relative to campaign (z={sal:+.2f}) — marine-influenced endmember candidate.")

    if turb >= th.get("turbidity_elevated_strong", 1.0):
        if "sediment_resuspension_regime" in scores:
            scores["sediment_resuspension_regime"] += 2.5
        evidence_lines.append(f"Elevated turbidity (z={turb:+.2f}).")
    elif turb >= th.get("turbidity_elevated_mod", 0.5):
        if "sediment_resuspension_regime" in scores:
            scores["sediment_resuspension_regime"] += 1.0
        evidence_lines.append(f"Moderately elevated turbidity (z={turb:+.2f}).")

    if (
        turb >= th.get("turbidity_open_coast", 0.8)
        and harbour_frac < th.get("harbour_membership_partial", 0.3)
        and do > th.get("do_depressed_strong", -1.5)
    ):
        if "high_energy_coastal_regime" in scores:
            scores["high_energy_coastal_regime"] += 2.0
        evidence_lines.append("Turbid open-coast signature without harbour-role concentration.")

    core = [abs(do), abs(ph), abs(sal), abs(turb)]
    if np.mean(core) < th.get("ambient_mean_abs_z", 0.45) and n >= int(th.get("ambient_min_n", 50)):
        if "mixed_transitional_regime" in scores:
            scores["mixed_transitional_regime"] += 2.5
        evidence_lines.append("Near-campaign-mean multivariate state with large membership — ambient/mixed baseline.")
    elif np.mean(core) < th.get("ambient_loose_mean_abs_z", 0.7):
        if "mixed_transitional_regime" in scores:
            scores["mixed_transitional_regime"] += 1.0

    if ph <= th.get("ph_depressed_strong", -1.5) and do <= th.get("do_depressed_mod", -0.8):
        evidence_lines.append(
            f"Co-occurring low pH (z={ph:+.2f}) with low DO — consistent with respiration/organic loading under restricted flushing."
        )
        if "harbour_regime" in scores:
            scores["harbour_regime"] += 1.0
        if "hypoxic_regime" in scores:
            scores["hypoxic_regime"] += 0.5

    if sal <= th.get("salinity_fresh_strong", -1.0) and turb >= th.get("turbidity_elevated_strong", 1.0):
        evidence_lines.append("Joint low-salinity and high-turbidity evidence.")
        if "freshwater_influenced_regime" in scores:
            scores["freshwater_influenced_regime"] += 0.5

    best_fam = max(scores, key=scores.get) if scores else "insufficient_evidence_for_named_regime"
    best_score = float(scores.get(best_fam, 0.0))
    min_score = th.get("min_family_score", 2.0)
    supported_cut = th.get("supported_family_score", 3.5)

    if best_score < min_score:
        label = "insufficient_evidence_for_named_regime"
        confidence = "exploratory"
        evidence_lines.append("No candidate family cleared the minimum evidence score; left unnamed.")
    else:
        label = best_fam
        confidence = "supported" if best_score >= supported_cut else "provisional"

    titles = ctx.titles
    if label == "harbour_regime" and scores.get("hypoxic_regime", 0) >= 3:
        title = "Harbour low-oxygen regime"
        evidence_lines.append("Joint harbour-role membership and hypoxic fingerprint.")
    elif label == "freshwater_influenced_regime" and scores.get("sediment_resuspension_regime", 0) >= 2.0:
        title = "Freshwater-influenced turbid coastal regime"
    else:
        title = titles.get(label, label.replace("_", " "))

    units.append(
        InterpretationUnit(
            topic="regime_family",
            observation=(
                f"Regime {regime_id} (n={n}) fingerprint DO z={do:+.2f}, salinity z={sal:+.2f}, "
                f"turbidity z={turb:+.2f}, harbour-role share={harbour_frac:.0%}."
            ),
            interpretation=f"Most plausible family: {title} ({label}).",
            supporting_evidence=[
                evidence_item("stage_06", "stage06_regime_labels.csv", "regime", regime_id, "Cluster assignment from Discovery", "strong"),
                evidence_item(
                    "stage_08",
                    "stage08_regime_z_profiles.csv",
                    "z_fingerprint",
                    {"do": do, "sal": sal, "turb": turb, "ph": ph, "temp": temp},
                    "Campaign-relative fingerprint",
                    "strong",
                ),
                evidence_item(
                    "stage_08",
                    "stage08_shap_driver_ranks.csv",
                    "drivers",
                    campaign_drivers[:6],
                    "Campaign-wide Dominant/Secondary SHAP drivers (not regime-specific)",
                    "moderate",
                ),
            ],
            confidence=confidence,
            uncertainty="Family labels are fingerprint heuristics; they are not hydrodynamic simulations or causal attribution.",
            limitations=[
                "SHAP drivers are campaign-wide, not per-regime importances.",
                "No pollutant-source attribution beyond water-quality fingerprints.",
            ],
            alternatives=[
                "Unnamed multivariate state if thresholds are judged too permissive.",
                "Adjacent family with next-highest score if domain thresholds differ.",
            ],
            level="interpretation",
        )
    )

    return {
        "regime": int(regime_id),
        "n": int(n),
        "interpretive_family": label,
        "title": title,
        "confidence": confidence,
        "evidence_score": float(best_score),
        "family_scores": scores,
        "station_membership_share": station_share.to_dict() if len(station_share) else {},
        "harbour_role_membership_share": harbour_frac,
        "z_fingerprint": z,
        "campaign_wide_shap_drivers": campaign_drivers,
        "evidence": evidence_lines,
        "speculation_excluded": [
            "No rainfall causation asserted without Stage 10 event consistency for this regime specifically.",
            "No pollutant source attribution beyond water-quality fingerprints.",
            "No industrial/river discharge claims without independent tracers.",
        ],
        "four_level": [u.to_dict() for u in units],
        "temperature_z": temp,
    }
