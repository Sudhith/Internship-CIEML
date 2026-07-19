"""Load DSS templates and sensor map from configs/decision/."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DECISION_DIR = ROOT / "configs" / "decision"


@lru_cache(maxsize=2)
def load_sensor_map() -> dict[str, dict[str, str]]:
    path = DECISION_DIR / "sensor_map.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(raw.get("map") or {})


@lru_cache(maxsize=2)
def load_templates() -> dict[str, Any]:
    path = DECISION_DIR / "templates.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
