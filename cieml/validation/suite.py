"""Execute configs/validation/suite.yaml checks."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from cieml.failure import build_failure_report

ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = ROOT / "configs" / "validation" / "suite.yaml"


def _load_suite(path: Path | None = None) -> dict[str, Any]:
    p = path or SUITE_PATH
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def run_validation_suite(suite_path: Path | None = None) -> dict[str, Any]:
    suite = _load_suite(suite_path)
    results = []
    for spec in suite.get("tests") or []:
        fn = globals().get(f"test_{spec['id']}")
        if fn is None:
            results.append(_result(spec, "skip", f"No implementation for {spec['id']}"))
            continue
        try:
            ok, detail = fn()
            results.append(_result(spec, "pass" if ok else "fail", detail))
        except Exception as exc:  # noqa: BLE001
            results.append(_result(spec, "fail", f"raised: {exc}"))

    critical_fails = [r for r in results if r["status"] == "fail" and r.get("critical")]
    if critical_fails:
        status = "NOT_READY"
    elif any(r["status"] == "fail" for r in results):
        status = "CONDITIONAL"
    elif any(r["status"] == "skip" and r.get("critical") for r in results):
        status = "CONDITIONAL"
    else:
        status = "CERTIFIED"

    # SC-FMF: Framework Validation Engine failure assessment. No test-to-catalog-
    # mode mapping is implemented yet (that mapping is itself the compliance-matrix
    # per-contract fill-in the SC-FVE contract flags as a future extension), so
    # today every critical suite failure is, by construction, unmapped to a
    # catalog mode — integ_contract_failure_unmapped fires whenever any exist.
    critical_fail_ids = [r["id"] for r in critical_fails]
    failure_report = build_failure_report(
        "framework_validation",
        {
            "validation_suite": bool(critical_fail_ids),
            "validation_suite_detail": (
                f"{len(critical_fail_ids)} critical suite failure(s) with no catalog mode mapping: {critical_fail_ids}"
                if critical_fail_ids
                else None
            ),
        },
    )

    return {
        "suite_version": suite.get("version"),
        "certification_status": status,
        "primary_demonstration": suite.get("primary_demonstration"),
        "n_pass": sum(1 for r in results if r["status"] == "pass"),
        "n_fail": sum(1 for r in results if r["status"] == "fail"),
        "n_skip": sum(1 for r in results if r["status"] == "skip"),
        "critical_fails": critical_fail_ids,
        "results": results,
        "failure_report": failure_report,
    }


def _result(spec: dict[str, Any], status: str, detail: str) -> dict[str, Any]:
    return {
        "id": spec["id"],
        "group": spec.get("group"),
        "category": spec.get("category"),
        "critical": bool(spec.get("critical")),
        "description": spec.get("description"),
        "status": status,
        "detail": detail,
    }


# ----- individual tests -----

def test_arch_artifact_contract_covers_loaders() -> tuple[bool, str]:
    from cieml.evidence.artifacts import ARTIFACT_SPECS
    from cieml.evidence.loaders import build_evidence_bundle

    # Build empty bundle; keys (minus meta) must match specs
    bundle = build_evidence_bundle(None, None, None, None, None, None, None)
    spec_keys = {s.key for s in ARTIFACT_SPECS}
    bundle_keys = {k for k in bundle if not k.startswith("_")}
    missing = spec_keys - bundle_keys
    extra = bundle_keys - spec_keys
    ok = not missing
    return ok, f"missing={sorted(missing)} extra={sorted(extra)}"


def test_arch_claim_pack_drives_ebsve() -> tuple[bool, str]:
    from cieml.claims import load_claim_pack, validators_for_pack

    pack = load_claim_pack("coastal_monitoring_v1")
    pairs = validators_for_pack(pack)
    ok = len(pairs) == 6 and all(cid.startswith("H") for cid, _ in pairs)
    return ok, f"n={len(pairs)} ids={[c for c,_ in pairs]}"


def test_arch_domain_priors_not_in_scoring() -> tuple[bool, str]:
    path = ROOT / "cieml" / "evidence" / "scoring.py"
    text = path.read_text(encoding="utf-8").lower()
    banned = ["visakhapatnam", "rushikonda", "fishing_harbour", "rk_beach"]
    found = [b for b in banned if b in text]
    return not found, f"banned_hits={found}"


def test_acc_default_campaign_loads() -> tuple[bool, str]:
    from cieml.claims import load_claim_pack
    from cieml.domain import load_campaign, load_domain

    d = load_domain("coastal")
    c = load_campaign("visakhapatnam_may2026")
    p = load_claim_pack(c.claim_pack or "coastal_monitoring_v1")
    return True, f"domain={d.name} campaign={c.campaign_id} pack={p.pack_id}"


def test_acc_phase_runners_exist() -> tuple[bool, str]:
    missing = []
    for i in range(1, 9):
        p = ROOT / "scripts" / f"run_phase{i}.py"
        if not p.exists():
            missing.append(p.name)
    return not missing, f"missing={missing}"


def test_evid_claim_pack_id_schema() -> tuple[bool, str]:
    from cieml.claims import load_claim_pack

    p = load_claim_pack("coastal_monitoring_v1")
    ok = bool(p.pack_id) and all(c.claim_id for c in p.claims)
    return ok, f"pack_id={p.pack_id} n_claims={len(p.claims)}"


def test_sci_uncertainty_no_complement_rule() -> tuple[bool, str]:
    """Fail only on executable complement assignments, not prose forbidding them."""
    bad = []
    # Real anti-pattern: assigning uncertainty from 100 - confidence (not docs saying "never").
    assign_patterns = [
        re.compile(r"(?:remaining_)?uncertainty\s*=\s*100\s*-\s*(?:confidence|\bc\b)", re.I),
        re.compile(r"\bu_mm\s*=\s*100\s*-\s*", re.I),
    ]
    for path in (ROOT / "cieml" / "uncertainty").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "never" in stripped.lower() and "100" in stripped:
                continue  # explicit prohibition prose / assert messages
            if any(p.search(stripped) for p in assign_patterns):
                bad.append(f"{path.name}:{i}")
    return not bad, f"complement_assigns={bad}"


def test_sci_failure_catalog_nonempty() -> tuple[bool, str]:
    from cieml.failure import load_failure_catalog

    cat = load_failure_catalog()
    ok = len(cat.modes) >= 5 and bool(cat.policy.get("confidence_multipliers"))
    return ok, f"n_modes={len(cat.modes)} version={cat.version}"


def test_reg_visakhapatnam_claim_classes() -> tuple[bool, str]:
    baseline_path = ROOT / "configs" / "validation" / "baselines" / "claim_classes.json"
    closure_path = ROOT / "outputs" / "phase8" / "stage14_four_pillar_closure.json"
    if not baseline_path.exists():
        return False, "baseline missing"
    if not closure_path.exists():
        return False, "phase8 closure missing — run demonstration first"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    hyps = closure.get("hypotheses") or {}
    expected = baseline.get("classifications") or {}
    mismatches = []
    for hid, cls in expected.items():
        got = (hyps.get(hid) or {}).get("classification")
        if got != cls:
            mismatches.append(f"{hid}:{got}!={cls}")
    camp_ok = closure.get("campaign_closure") == baseline.get("campaign_closure")
    ok = not mismatches and camp_ok
    return ok, f"mismatches={mismatches} campaign_ok={camp_ok}"


def test_ext_domain_stub_loads() -> tuple[bool, str]:
    from cieml.domain import load_domain

    d = load_domain("harbour")
    ok = d.name == "harbour" and len(d.core_variables) > 0
    return ok, f"domain={d.name} n_core={len(d.core_variables)}"


def test_acc_phase_k_engines_import() -> tuple[bool, str]:
    from cieml.applicability import build_applicability_domain
    from cieml.decision import build_decision_support, gate_recommendations
    from cieml.knowledge import load_store

    app = build_applicability_domain(domain_name="coastal", recommendation_ids=["M1"])
    store = load_store()
    ok = bool(app.get("transfer_rule")) and store.entries_dir.exists()
    _ = build_decision_support
    _ = gate_recommendations
    return ok, f"applies={len(app.get('applies_to') or [])} kb_root={store.root}"
