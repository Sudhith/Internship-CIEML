"""QA check registry."""
from __future__ import annotations

from typing import Any, Callable

from cieml.qa.checks.range_magnitude_overshoot import run_range_magnitude_overshoot

CheckFn = Callable[..., list[dict[str, Any]]]

_REGISTRY: dict[str, CheckFn] = {
    "range_magnitude_overshoot": run_range_magnitude_overshoot,
}


def list_checks() -> list[str]:
    return sorted(_REGISTRY)


def get_check(check_id: str) -> CheckFn:
    if check_id not in _REGISTRY:
        raise KeyError(f"Unknown QA check: {check_id}. Known: {list_checks()}")
    return _REGISTRY[check_id]


def register_check(check_id: str, fn: CheckFn) -> None:
    _REGISTRY[check_id] = fn
