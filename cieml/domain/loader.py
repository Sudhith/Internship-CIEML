"""Load and validate domain / campaign profiles."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOMAINS_DIR = ROOT / "configs" / "domains"
CAMPAIGNS_DIR = ROOT / "configs" / "campaigns"
DEFAULT_DOMAIN = "coastal"
DEFAULT_CAMPAIGN = "visakhapatnam_may2026"


@dataclass
class DomainProfile:
    name: str
    version: str
    raw: dict[str, Any]
    core_variables: list[str] = field(default_factory=list)
    plausibility_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    qa: dict[str, Any] = field(default_factory=dict)
    physical_equivalence_groups: list[set[str]] = field(default_factory=list)
    process_categories: dict[str, list[str]] = field(default_factory=dict)
    decision_keywords: dict[str, set[str]] = field(default_factory=dict)
    regime_families: list[str] = field(default_factory=list)
    applicability_notes: list[str] = field(default_factory=list)
    evidence_reliability: dict[str, Any] = field(default_factory=dict)
    ceam: dict[str, Any] = field(default_factory=dict)

    def relationship_catalog(self, domain_name: str | None = None) -> list[dict[str, Any]]:
        """Return relationships applicable to this domain (or declared name)."""
        dom = domain_name or self.name
        out = []
        for rel in self.relationships:
            apps = rel.get("applicable_domains") or [dom]
            if dom in apps or self.name in apps:
                out.append(dict(rel))
        return out


@dataclass
class CampaignProfile:
    campaign_id: str
    domain: str
    adapter: str
    data_dir: Path
    raw: dict[str, Any]
    region: dict[str, Any] = field(default_factory=dict)
    stations: dict[str, Any] = field(default_factory=dict)
    timezone: str | None = None
    claim_pack: str | None = None

    def station_aliases(self) -> dict[str, str]:
        """alias_text_lower -> canonical station id."""
        mapping: dict[str, str] = {}
        for station, meta in self.stations.items():
            mapping[station.lower().replace("_", " ")] = station
            for alias in meta.get("aliases") or []:
                mapping[str(alias).lower()] = station
                mapping[str(alias).lower().replace(" ", "")] = station
        return mapping


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_extends(data: dict[str, Any], stack: list[str] | None = None) -> dict[str, Any]:
    stack = list(stack or [])
    name = str(data.get("domain") or data.get("extends") or "")
    if data.get("extends"):
        parent_name = str(data["extends"])
        if parent_name in stack:
            raise ValueError(f"Circular domain extends: {stack + [parent_name]}")
        parent_path = DOMAINS_DIR / f"{parent_name}.yaml"
        if not parent_path.exists():
            raise FileNotFoundError(parent_path)
        parent = _resolve_extends(_read_yaml(parent_path), stack + [parent_name])
        merged = dict(parent)
        for k, v in data.items():
            if k == "extends":
                continue
            merged[k] = v
        return merged
    return data


SCHEMA_PATH = DOMAINS_DIR / "_schema.yaml"


@lru_cache(maxsize=1)
def _schema_required_keys() -> list[str]:
    """`_schema.yaml` is the single source of truth for required domain keys —
    read it rather than duplicating the list here, so the schema file and the
    validator can never silently drift apart (SC-DCL guarantee: incomplete
    profiles must fail validation; a hardcoded copy of this list previously did
    not include physical_equivalence_groups/process_categories, so a profile
    missing them loaded successfully instead of raising)."""
    if not SCHEMA_PATH.exists():
        return ["core_variables", "plausibility_ranges", "relationships", "qa"]
    schema = _read_yaml(SCHEMA_PATH)
    keys = list(schema.get("required_keys") or [])
    return keys or ["core_variables", "plausibility_ranges", "relationships", "qa"]


@lru_cache(maxsize=8)
def load_domain(name: str = DEFAULT_DOMAIN) -> DomainProfile:
    path = DOMAINS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Domain profile not found: {path}")
    data = _resolve_extends(_read_yaml(path))
    if data.get("status") == "stub" and data.get("extends"):
        # Stubs that only declare extends already merged; ensure identity
        data["domain"] = name

    ranges_raw = data.get("plausibility_ranges") or {}
    ranges = {k: (float(v[0]), float(v[1])) for k, v in ranges_raw.items()}

    groups = [set(g) for g in (data.get("physical_equivalence_groups") or [])]
    keywords = {k: set(v) for k, v in (data.get("decision_keywords") or {}).items()}

    required = _schema_required_keys()
    missing = [k for k in required if not data.get(k)]
    if missing and data.get("status") != "stub":
        raise ValueError(f"Domain '{name}' missing required keys: {missing}")

    return DomainProfile(
        name=str(data.get("domain") or name),
        version=str(data.get("version") or "0"),
        raw=data,
        core_variables=list(data.get("core_variables") or []),
        plausibility_ranges=ranges,
        relationships=list(data.get("relationships") or []),
        qa=dict(data.get("qa") or {}),
        physical_equivalence_groups=groups,
        process_categories=dict(data.get("process_categories") or {}),
        decision_keywords=keywords,
        regime_families=list(data.get("regime_families") or []),
        applicability_notes=list(data.get("applicability_notes") or []),
        evidence_reliability=dict(data.get("evidence_reliability") or {}),
        ceam=dict(data.get("ceam") or {}),
    )


def get_default_domain() -> DomainProfile:
    return load_domain(DEFAULT_DOMAIN)


@lru_cache(maxsize=8)
def load_campaign(name: str = DEFAULT_CAMPAIGN) -> CampaignProfile:
    path = CAMPAIGNS_DIR / f"{name}.yaml"
    if not path.exists():
        # Fallback: synthesize from legacy stations.yaml
        legacy = ROOT / "configs" / "stations.yaml"
        if legacy.exists():
            raw = _read_yaml(legacy)
            return CampaignProfile(
                campaign_id=name,
                domain=DEFAULT_DOMAIN,
                adapter="kor_ysi",
                data_dir=ROOT / "DATA",
                raw=raw,
                region=dict(raw.get("campaign_region") or {}),
                stations=dict(raw.get("stations") or {}),
                timezone=(raw.get("campaign_region") or {}).get("timezone"),
                claim_pack=raw.get("claim_pack") or "coastal_monitoring_v1",
            )
        raise FileNotFoundError(path)
    data = _read_yaml(path)
    data_dir = Path(data.get("data_dir") or "DATA")
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    return CampaignProfile(
        campaign_id=str(data.get("campaign_id") or name),
        domain=str(data.get("domain") or DEFAULT_DOMAIN),
        adapter=str(data.get("adapter") or "kor_ysi"),
        data_dir=data_dir,
        raw=data,
        region=dict(data.get("region") or {}),
        stations=dict(data.get("stations") or {}),
        timezone=data.get("timezone"),
        claim_pack=data.get("claim_pack") or "coastal_monitoring_v1",
    )
