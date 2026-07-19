"""Evaluate domain relationship catalog against observations."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from cieml.domain.loader import DomainProfile


def _spearman(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    m = pd.concat([x, y], axis=1).dropna()
    if len(m) < 30:
        return {"n": int(len(m)), "rho": np.nan, "p": np.nan, "ok": False, "reason": "insufficient_n"}
    if m.iloc[:, 0].nunique() < 2 or m.iloc[:, 1].nunique() < 2:
        return {"n": int(len(m)), "rho": np.nan, "p": np.nan, "ok": False, "reason": "constant_input"}
    rho, p = stats.spearmanr(m.iloc[:, 0], m.iloc[:, 1])
    return {"n": int(len(m)), "rho": float(rho), "p": float(p), "ok": True, "reason": "ok"}


def _classify_pair(
    expected_sign: str, rho: float, p: float, data_driven_thr: float, reason: str | None = None
) -> dict[str, Any]:
    if not np.isfinite(rho):
        if reason == "constant_input":
            return {"status": "Not_testable", "detail": "constant_input_no_dynamic_range"}
        return {"status": "Not_testable", "detail": reason or "insufficient_or_undefined"}
    sig = p < 0.05
    strong = abs(rho) >= data_driven_thr
    if expected_sign == "either":
        if sig and strong:
            return {"status": "Observed", "detail": "context_dependent_but_structured"}
        if sig:
            return {"status": "Weak", "detail": "significant_but_below_effect_threshold"}
        return {"status": "Unexpected", "detail": "no_stable_association"}

    sign_ok = (rho > 0 and expected_sign == "+") or (rho < 0 and expected_sign == "-")
    if sign_ok and sig and strong:
        return {"status": "Expected", "detail": "correct_sign_significant_practical"}
    if sign_ok and sig:
        return {"status": "Expected_weak", "detail": "correct_sign_significant_weak_effect"}
    if sign_ok and not sig:
        return {"status": "Unexpected", "detail": "correct_sign_not_significant"}
    if (not sign_ok) and sig:
        return {"status": "Broken", "detail": "wrong_sign_significant"}
    return {"status": "Broken", "detail": "wrong_sign_or_absent"}


def evaluate_physical_relationships(
    observations: pd.DataFrame,
    domain: DomainProfile,
) -> dict[str, Any]:
    catalog = domain.relationship_catalog()
    # Variables appearing in catalog (+ common extras for thr estimation)
    catalog_vars = sorted({v for rel in catalog for v in (rel["x"], rel["y"])})
    num_cols = [c for c in catalog_vars if c in observations.columns]

    abs_rhos = []
    for i, a in enumerate(num_cols):
        for b in num_cols[i + 1 :]:
            r = _spearman(observations[a], observations[b])
            if r["ok"] and np.isfinite(r["rho"]):
                abs_rhos.append(abs(r["rho"]))
    if abs_rhos:
        data_driven_thr = float(max(0.20, min(0.50, np.median(abs_rhos) * 0.5)))
    else:
        data_driven_thr = 0.30

    pair_rows = []
    for spec in catalog:
        x, y = spec["x"], spec["y"]
        base = {
            "id": spec.get("id"),
            "x": x,
            "y": y,
            "expected_sign": spec["expected_sign"],
            "mechanism": spec.get("mechanism"),
            "optional": bool(spec.get("optional", False)),
        }
        if x not in observations.columns or y not in observations.columns:
            pair_rows.append(
                {
                    **base,
                    "n": 0,
                    "rho": np.nan,
                    "p": np.nan,
                    "status": "Missing_variable",
                    "detail": "variable_absent",
                }
            )
            continue
        r = _spearman(observations[x], observations[y])
        cls = _classify_pair(spec["expected_sign"], r["rho"], r["p"], data_driven_thr, r.get("reason"))
        pair_rows.append({**base, "n": r["n"], "rho": r["rho"], "p": r["p"], **cls})

    return {
        "pairs": pair_rows,
        "data_driven_abs_rho_threshold": data_driven_thr,
        "n_relationships_evaluated": len(pair_rows),
        "domain": domain.name,
        "domain_version": domain.version,
    }
