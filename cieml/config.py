"""Paths and framework configuration.

Scientific priors (plausibility bands, core variables) are owned by the Domain
Configuration Layer (`configs/domains/`). Values below are loaded from the default
domain profile for backward compatibility with existing imports.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "DATA"
CONFIG_DIR = ROOT / "configs"
OUTPUT_DIR = ROOT / "outputs"
PHASE1_DIR = OUTPUT_DIR / "phase1"
PHASE2_DIR = OUTPUT_DIR / "phase2"
PHASE3_DIR = OUTPUT_DIR / "phase3"
PHASE4_DIR = OUTPUT_DIR / "phase4"
PHASE5_DIR = OUTPUT_DIR / "phase5"
PHASE6_DIR = OUTPUT_DIR / "phase6"
PHASE7_DIR = OUTPUT_DIR / "phase7"
PHASE8_DIR = OUTPUT_DIR / "phase8"

HYPOTHESES_PATH = CONFIG_DIR / "hypotheses.yaml"  # deprecated shim → claim pack
CLAIMS_DIR = CONFIG_DIR / "claims"
DEFAULT_CLAIM_PACK = "coastal_monitoring_v1"
CLAIM_PACK_PATH = CLAIMS_DIR / f"{DEFAULT_CLAIM_PACK}.yaml"
DEFAULT_DOMAIN = "coastal"
DEFAULT_CAMPAIGN = "visakhapatnam_may2026"


def _load_domain_priors():
    from cieml.domain import load_domain

    d = load_domain(DEFAULT_DOMAIN)
    return d.plausibility_ranges, list(d.core_variables), d


try:
    PLAUSIBILITY_RANGES, CORE_VARIABLES, ACTIVE_DOMAIN = _load_domain_priors()
except FileNotFoundError:  # pragma: no cover — bootstrap fallback if YAML is genuinely absent
    # Narrowed from a bare `except Exception` on purpose: a bare catch here would
    # also swallow ValueError from domain-profile schema validation (missing
    # required keys), silently reverting cieml.config to a stale hardcoded
    # duplicate instead of surfacing the exact failure the Domain Configuration
    # Layer exists to catch. Only "no profile file at all" degrades quietly;
    # every other load failure must propagate.
    import warnings

    warnings.warn(
        f"Domain profile '{DEFAULT_DOMAIN}' not found; cieml.config falling back to "
        "hardcoded legacy plausibility ranges. Run under configs/domains/ once Phase B "
        "assets are restored.",
        stacklevel=2,
    )
    ACTIVE_DOMAIN = None
    PLAUSIBILITY_RANGES = {
        "temperature_c": (0.0, 40.0),
        "salinity_psu": (0.0, 45.0),
        "ph": (6.0, 9.5),
        "do_mg_l": (0.0, 20.0),
        "do_sat_pct": (0.0, 200.0),
        "turbidity_fnu": (0.0, 4000.0),
        "conductivity_us_cm": (0.0, 80000.0),
        "tds_mg_l": (0.0, 50000.0),
        "barometer_mmhg": (650.0, 850.0),
    }
    CORE_VARIABLES = [
        "temperature_c",
        "salinity_psu",
        "ph",
        "do_mg_l",
        "do_sat_pct",
        "turbidity_fnu",
        "conductivity_us_cm",
        "spcond_us_cm",
        "tds_mg_l",
    ]
