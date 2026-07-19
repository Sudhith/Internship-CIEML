"""Detect and standardize variable names/units from heterogeneous sonde exports."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Pattern -> (canonical_name, unit)
# Order matters: more specific patterns first.
COLUMN_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^time\b", re.I), "time_raw", None),
    (re.compile(r"^date\b", re.I), "date_raw", None),
    (re.compile(r"file\s*name", re.I), "file_name", None),
    (re.compile(r"site\s*name", re.I), "site_code", None),
    (re.compile(r"user\s*id", re.I), "user_id", None),
    (re.compile(r"fault", re.I), "fault_code", None),
    (re.compile(r"barometer", re.I), "barometer_mmhg", "mmHg"),
    (re.compile(r"^cond\b(?!.*nlf)|conductivity", re.I), "conductivity_us_cm", "uS/cm"),
    (re.compile(r"spcond|specific\s*cond", re.I), "spcond_us_cm", "uS/cm"),
    (re.compile(r"nlf\s*cond", re.I), "nlf_cond_us_cm", "uS/cm"),
    (re.compile(r"\btds\b", re.I), "tds_mg_l", "mg/L"),
    (re.compile(r"\bsal\b|salinity", re.I), "salinity_psu", "PSU"),
    (re.compile(r"odo\s*%|do\s*%|sat", re.I), "do_sat_pct", "%"),
    (re.compile(r"odo\s*mg|do\s*mg|dissolved\s*oxygen", re.I), "do_mg_l", "mg/L"),
    (re.compile(r"^ph\s*mv$|ph\s*m\s*v", re.I), "ph_mv", "mV"),
    (re.compile(r"^ph$", re.I), "ph", "pH"),
    (re.compile(r"temp", re.I), "temperature_c", "degC"),
    (re.compile(r"turbidity|fnu|ntu", re.I), "turbidity_fnu", "FNU"),
    (re.compile(r"\btss\b", re.I), "tss_mg_l", "mg/L"),
]


def _normalize_header(name: str) -> str:
    # Strip encoding artifacts (e.g., micro symbol becoming replacement char)
    text = unicodedata.normalize("NFKD", str(name))
    text = text.replace("�", "u")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def map_column(raw_name: str) -> tuple[Optional[str], Optional[str], str]:
    """Return (canonical_name, unit, normalized_raw). Unmapped -> (None, None, raw)."""
    norm = _normalize_header(raw_name)
    for pattern, canonical, unit in COLUMN_PATTERNS:
        if pattern.search(norm):
            # Avoid matching PH MV as PH: PH pattern is ^ph$
            return canonical, unit, norm
    return None, None, norm


def standardize_columns(columns: list[str]) -> dict[str, str]:
    """Map raw column -> canonical. First match wins; collisions keep first."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for col in columns:
        canonical, _, _ = map_column(col)
        if canonical and canonical not in used:
            mapping[col] = canonical
            used.add(canonical)
    return mapping


# Legacy fallback aliases (prefer campaign profile via get_station_aliases)
STATION_ALIASES = {
    "fishing harbour": "Fishing_Harbour",
    "fishingharbor": "Fishing_Harbour",
    "kailasagiri": "Kailasagiri",
    "novotel": "Novotel",
    "rk beach": "RK_Beach",
    "rkbeach": "RK_Beach",
    "rushikonda": "Rushikonda",
    "sagarnagar": "Sagarnagar",
}


def get_station_aliases() -> dict[str, str]:
    """Campaign aliases first, then legacy fallback."""
    try:
        from cieml.domain import load_campaign

        camp = load_campaign()
        aliases = camp.station_aliases()
        if aliases:
            return aliases
    except Exception:
        pass
    return dict(STATION_ALIASES)


def detect_station_from_text(text: str) -> Optional[str]:
    low = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    compact = low.replace(" ", "")
    for alias, station in get_station_aliases().items():
        if alias in low or alias.replace(" ", "") in compact:
            return station
    return None
