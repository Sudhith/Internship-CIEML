"""Assemble a read-only evidence context for CEAM from upstream phase artifacts."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from cieml.domain import get_default_domain, load_campaign


def _j(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _c(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.ParserError, OSError):
        return pd.DataFrame()


@dataclass
class CEAMContext:
    domain_name: str
    campaign_id: str
    ceam_cfg: dict[str, Any]
    regime_families: list[str]
    station_roles: dict[str, str]
    harbour_roles: set[str]
    open_coast_roles: set[str]
    thresholds: dict[str, float]
    titles: dict[str, str]
    variable_keys: dict[str, str]
    # Upstream artifacts (never recomputed here)
    qa_report: dict[str, Any] = field(default_factory=dict)
    qa2_report: dict[str, Any] = field(default_factory=dict)
    physical_report: dict[str, Any] = field(default_factory=dict)
    regime_labels: pd.DataFrame = field(default_factory=pd.DataFrame)
    regime_profiles: pd.DataFrame = field(default_factory=pd.DataFrame)
    shap_drivers: pd.DataFrame = field(default_factory=pd.DataFrame)
    anomaly_report: dict[str, Any] = field(default_factory=dict)
    anomaly_catalog: pd.DataFrame = field(default_factory=pd.DataFrame)
    external_report: dict[str, Any] = field(default_factory=dict)
    meteo_enrichment: pd.DataFrame = field(default_factory=pd.DataFrame)
    spatial_report: dict[str, Any] = field(default_factory=dict)
    spatial_gradients: pd.DataFrame = field(default_factory=pd.DataFrame)
    transitions: pd.DataFrame = field(default_factory=pd.DataFrame)
    transition_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)
    ebsve: dict[str, Any] = field(default_factory=dict)
    uncertainty_ledger: dict[str, Any] = field(default_factory=dict)


def build_context(
    *,
    phase1_dir: Path | None = None,
    phase2_dir: Path | None = None,
    phase4_dir: Path | None = None,
    phase5_dir: Path | None = None,
    phase6_dir: Path | None = None,
    phase8_dir: Path | None = None,
    regime_labels: pd.DataFrame | None = None,
    regime_profiles: pd.DataFrame | None = None,
    shap_drivers: pd.DataFrame | None = None,
) -> CEAMContext:
    from cieml.config import (
        PHASE1_DIR,
        PHASE2_DIR,
        PHASE4_DIR,
        PHASE5_DIR,
        PHASE6_DIR,
        PHASE8_DIR,
    )

    p1 = Path(phase1_dir or PHASE1_DIR)
    p2 = Path(phase2_dir or PHASE2_DIR)
    p4 = Path(phase4_dir or PHASE4_DIR)
    p5 = Path(phase5_dir or PHASE5_DIR)
    p6 = Path(phase6_dir or PHASE6_DIR)
    p8 = Path(phase8_dir or PHASE8_DIR)

    # Domain/campaign — clear cached loaders if YAML changed in-process. Narrowed
    # to AttributeError (the only expected failure: cache_clear not present, e.g.
    # if load_domain/load_campaign are ever refactored off @lru_cache) — a bare
    # `except Exception` here would silently leave stale cached profiles in place
    # with no signal, which is worse than a crash: CEAM would read outdated
    # domain/campaign config indefinitely without anyone noticing.
    try:
        from cieml.domain.loader import load_campaign as _lc
        from cieml.domain.loader import load_domain as _ld

        _ld.cache_clear()
        _lc.cache_clear()
    except AttributeError:
        pass

    domain = get_default_domain()
    campaign = load_campaign()
    ceam_cfg = dict(domain.ceam or {})
    th = {k: float(v) for k, v in (ceam_cfg.get("thresholds") or {}).items()}
    titles = dict(ceam_cfg.get("titles") or {})
    vkeys = dict(ceam_cfg.get("variable_keys") or {})
    harbour_roles = set(ceam_cfg.get("harbour_station_roles") or ["harbour_embayment"])
    open_roles = set(ceam_cfg.get("open_coast_roles") or ["open_coast", "ambient_reference"])

    station_roles: dict[str, str] = {}
    for sid, meta in (campaign.stations or {}).items():
        role = (meta or {}).get("role") or "open_coast"
        station_roles[str(sid)] = str(role)

    families = list(domain.regime_families or [])
    if not families:
        families = list((ceam_cfg.get("titles") or {}).keys())
        families = [f for f in families if f != "insufficient_evidence_for_named_regime"]

    labels = regime_labels if regime_labels is not None else _c(p4 / "stage06_regime_labels.csv")
    profiles = regime_profiles if regime_profiles is not None else _c(p5 / "stage08_regime_z_profiles.csv")
    shap = shap_drivers if shap_drivers is not None else _c(p5 / "stage08_shap_driver_ranks.csv")

    ebsve = _j(p8 / "stage14_four_pillar_closure.json")
    if not ebsve:
        ebsve = {}

    return CEAMContext(
        domain_name=domain.name,
        campaign_id=campaign.campaign_id,
        ceam_cfg=ceam_cfg,
        regime_families=families,
        station_roles=station_roles,
        harbour_roles=harbour_roles,
        open_coast_roles=open_roles,
        thresholds=th,
        titles=titles,
        variable_keys=vkeys,
        qa_report=_j(p1 / "stage01_qa_report.json"),
        qa2_report=_j(p2 / "stage02_qa_report.json"),
        physical_report=_j(p2 / "stage03_physical_report.json"),
        regime_labels=labels,
        regime_profiles=profiles,
        shap_drivers=shap,
        anomaly_report=_j(p5 / "stage09_anomaly_report.json"),
        anomaly_catalog=_c(p5 / "stage09_anomaly_catalog.csv"),
        external_report=_j(p6 / "stage10_external_report.json"),
        meteo_enrichment=_c(p6 / "stage10_anomaly_external_enrichment.csv"),
        spatial_report=_j(p6 / "stage11_spatial_temporal_report.json"),
        spatial_gradients=_c(p6 / "stage11_spatial_gradients.csv"),
        transitions=_c(p6 / "stage11_regime_transitions.csv"),
        transition_matrix=_c(p6 / "stage11_transition_matrix.csv"),
        ebsve=ebsve,
        uncertainty_ledger=_j(p8 / "stage14_uncertainty_ledger.json"),
    )


def harbour_membership_share(ctx: CEAMContext, station_share: pd.Series) -> float:
    """Fraction of regime membership on stations with harbour roles (campaign config)."""
    if station_share is None or len(station_share) == 0:
        return 0.0
    total = 0.0
    for st, frac in station_share.items():
        role = ctx.station_roles.get(str(st), "")
        if role in ctx.harbour_roles:
            total += float(frac)
    return float(total)


def z_get(z: dict[str, float], ctx: CEAMContext, key: str, default: float = 0.0) -> float:
    col = ctx.variable_keys.get(key, key)
    if col in z:
        return float(z[col])
    # try bare name
    for k, v in z.items():
        if k == key or k.startswith(key):
            return float(v)
    return default
