"""Automatic detectors for catalogued failure modes.

Detectors read a generic `bundle` dict (artifacts + live metrics). Missing inputs
skip softly unless the mode requires presence.
"""
from __future__ import annotations

from typing import Any

from cieml.failure.catalog import FailureCatalog, FailureMode
from cieml.failure.models import FailureModeHit, Severity


def _sev(name: str) -> Severity:
    return Severity[str(name).upper()]


def detect_hits(catalog: FailureCatalog, bundle: dict[str, Any]) -> list[FailureModeHit]:
    hits: list[FailureModeHit] = []
    th = catalog.thresholds
    for mode in catalog.modes:
        hit = _detect_one(mode, bundle, th)
        if hit is not None:
            hits.append(hit)
    return hits


def _detect_one(mode: FailureMode, bundle: dict[str, Any], th: dict[str, Any]) -> FailureModeHit | None:
    d = mode.detection
    if not d:
        return None

    if d == "n_stations":
        n = bundle.get("n_stations")
        if n is None:
            return None
        n = int(n)
        hard = int(th.get("min_stations_hard", 3))
        warn = int(th.get("min_stations_warn", 5))
        if n < hard:
            sev = _sev(mode.raw.get("severity_if", {}).get("n_stations_lt_hard") or "CRITICAL")
        elif n < warn:
            sev = _sev(mode.severity)
        else:
            return None
        return _hit(mode, sev, {"n_stations": n, "min_stations_hard": hard, "min_stations_warn": warn})

    if d == "selected_silhouette":
        sil = bundle.get("selected_silhouette")
        if sil is None:
            return None
        sil = float(sil)
        crit = float(th.get("silhouette_critical", 0.10))
        warn = float(th.get("silhouette_warn", 0.25))
        if sil < crit:
            sev = Severity.CRITICAL
        elif sil < warn:
            sev = _sev(mode.severity)
        else:
            return None
        return _hit(mode, sev, {"selected_silhouette": sil, "silhouette_warn": warn})

    if d == "top_driver_abs_corr":
        corr = bundle.get("max_abs_driver_corr")
        if corr is None:
            return None
        corr = float(corr)
        gate = float(th.get("driver_abs_corr_warn", 0.90))
        if corr < gate:
            return None
        return _hit(mode, _sev(mode.severity), {"max_abs_driver_corr": corr, "threshold": gate})

    if d == "external_support_missing_or_low":
        if "anomaly_external_support_frac" not in bundle:
            # Key genuinely absent (e.g. Stage 9 running before Stage 10 has
            # computed it yet) -- soft-skip like every other detector, not a
            # finding. Distinct from the key being PRESENT but null/NaN below,
            # which means external validation ran and genuinely found nothing.
            return None
        support = bundle.get("anomaly_external_support_frac")
        if support is None or (isinstance(support, float) and support != support):
            return _hit(mode, _sev(mode.severity), {"anomaly_external_support_frac": None, "reason": "missing"})
        support = float(support)
        floor = float(th.get("external_support_floor", 0.20))
        if support >= floor:
            return None
        return _hit(mode, _sev(mode.severity), {"anomaly_external_support_frac": support, "floor": floor})

    if d == "consensus_empty":
        n = bundle.get("n_consensus_anomalies")
        if n is None:
            return None
        if int(n) > 0:
            return None
        return _hit(mode, _sev(mode.severity), {"n_consensus_anomalies": int(n)})

    if d == "ebsve_confidence_or_class":
        conf = bundle.get("campaign_mean_confidence")
        closure_classes = bundle.get("claim_classifications") or {}
        floor = float(th.get("claim_confidence_floor_for_dss", 70.0))
        allowed = set(th.get("dss_allow_if_classification_in") or ["PROVISIONAL", "DEFINITIVE"])
        weak = False
        evidence: dict[str, Any] = {}
        if conf is not None and float(conf) < floor:
            weak = True
            evidence["campaign_mean_confidence"] = float(conf)
            evidence["floor"] = floor
        # Also weak if no claim reaches allowed classifications
        if closure_classes:
            if not any(c in allowed for c in closure_classes.values()):
                weak = True
                evidence["claim_classifications"] = dict(closure_classes)
        if not weak:
            return None
        return _hit(mode, _sev(mode.severity), evidence)

    if d == "applicability_thin":
        domain = bundle.get("applicability_domain") or {}
        applies = domain.get("applies_to") or []
        excludes = domain.get("does_not_apply_to") or []
        if len(applies) >= 2 and len(excludes) >= 1:
            return None
        return _hit(mode, _sev(mode.severity), {"n_applies": len(applies), "n_excludes": len(excludes)})

    if d == "claim_pack_empty":
        n = bundle.get("n_claims")
        if n is None:
            return None
        if int(n) > 0:
            return None
        return _hit(mode, Severity.FATAL, {"n_claims": int(n)})

    if d == "evidence_bundle_key_absent":
        missing = bundle.get("missing_evidence_keys") or []
        if not missing:
            return None
        return _hit(mode, _sev(mode.severity), {"missing_evidence_keys": list(missing)})

    # stage14_noise_or_stability / shap_vs_permutation_discord / validation_suite:
    # require explicit bundle flags from callers until fully wired.
    if d in {"stage14_noise_or_stability", "shap_vs_permutation_discord", "validation_suite"}:
        flag = bundle.get(d)
        if not flag:
            return None
        return _hit(mode, _sev(mode.severity), {"flag": True, "detail": bundle.get(f"{d}_detail")})

    return None


def _hit(mode: FailureMode, severity: Severity, evidence: dict[str, Any]) -> FailureModeHit:
    return FailureModeHit(
        mode_id=mode.mode_id,
        engine_id=mode.engine_id,
        severity=severity,
        title=mode.title,
        evidence=evidence,
        recovery_applied=list(mode.recovery),
        message=mode.title,
        pillar_impact=mode.raw.get("pillar_impact"),
    )
