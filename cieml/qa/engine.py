"""Run enabled QA checks from a domain profile."""
from __future__ import annotations

from typing import Any

import pandas as pd

from cieml.domain.loader import DomainProfile
from cieml.qa.registry import get_check


def run_qa_checks(
    observations: pd.DataFrame,
    domain: DomainProfile,
    check_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    qa = domain.qa or {}
    enabled = list(check_ids or qa.get("enabled_checks") or ["range_magnitude_overshoot"])
    issues: list[dict[str, Any]] = []
    for check_id in enabled:
        fn = get_check(check_id)
        params = dict(qa.get(check_id) or {})
        if check_id == "range_magnitude_overshoot":
            issues.extend(
                fn(
                    observations=observations,
                    plausibility_ranges=domain.plausibility_ranges,
                    core_variables=domain.core_variables,
                    params=params,
                )
            )
        else:
            issues.extend(fn(observations=observations, domain=domain, params=params))
    return issues
