"""Generate the RC-1 release manifest: module inventory + checksums, config
versions, dependency versions, and config file hashes. Read-only — writes only
to docs/release/. Run: python scripts/generate_release_manifest.py
"""
from __future__ import annotations

import hashlib
import importlib.metadata as ilmd
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "release"

DEPENDENCIES = [
    "numpy", "pandas", "scipy", "scikit-learn", "matplotlib", "seaborn",
    "PyYAML", "openpyxl", "statsmodels", "tqdm", "pyarrow", "shap", "xgboost",
    "lightgbm", "requests", "hdbscan",
]

CONFIG_FILES = [
    "configs/framework.yaml",
    "configs/domains/coastal.yaml",
    "configs/domains/_schema.yaml",
    "configs/claims/coastal_monitoring_v1.yaml",
    "configs/failure/catalog.yaml",
    "configs/validation/suite.yaml",
    "configs/campaigns/visakhapatnam_may2026.yaml",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _dep_version(name: str) -> str | None:
    try:
        return ilmd.version(name)
    except ilmd.PackageNotFoundError:
        return None


def _git_info() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    return {
        "commit": run("rev-parse", "HEAD"),
        "commit_short": run("rev-parse", "--short", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": run("status", "--porcelain") != "",
    }


def _module_inventory() -> list[dict]:
    modules = []
    for pkg in ["cieml"]:
        for p in sorted((ROOT / pkg).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(ROOT)
            modules.append({
                "path": str(rel).replace("\\", "/"),
                "sha256": _sha256(p),
                "size_bytes": p.stat().st_size,
                "lines": len(p.read_text(encoding="utf-8").splitlines()),
            })
    return modules


def _config_versions() -> dict:
    out = {}
    for rel in CONFIG_FILES:
        p = ROOT / rel
        if not p.exists():
            out[rel] = {"exists": False}
            continue
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        version = data.get("version")
        if version is None and "framework" in data:
            version = data["framework"].get("version")
        out[rel] = {"exists": True, "version": version, "sha256": _sha256(p)}
    return out


def build_manifest() -> dict:
    fw_path = ROOT / "configs" / "framework.yaml"
    fw = yaml.safe_load(fw_path.read_text(encoding="utf-8")) or {}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "framework_version": (fw.get("framework") or {}).get("version"),
        "redesign_phase": (fw.get("framework") or {}).get("redesign_phase"),
        "artifact_contract_version": (fw.get("artifact_contract") or {}).get("version"),
        "scientific_contracts_version": (fw.get("scientific_contracts") or {}).get("version"),
        "git": _git_info(),
        "python_version": sys.version,
        "dependencies": {name: _dep_version(name) for name in DEPENDENCIES},
        "config_versions": _config_versions(),
        "module_inventory": _module_inventory(),
        "n_modules": None,
    }
    manifest["n_modules"] = len(manifest["module_inventory"])
    return manifest


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    (OUT_DIR / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "# CIEML Release Manifest",
        "",
        f"- Generated (UTC): {manifest['generated_at']}",
        f"- Framework version: `{manifest['framework_version']}`",
        f"- Git commit: `{manifest['git']['commit_short']}` on `{manifest['git']['branch']}`"
        + (" (dirty working tree)" if manifest['git']['dirty'] else " (clean working tree)"),
        f"- Python: {manifest['python_version'].splitlines()[0]}",
        f"- Modules inventoried: {manifest['n_modules']}",
        "",
        "## Dependencies",
        "",
        "| Package | Installed version |",
        "|---|---|",
    ]
    for name, ver in manifest["dependencies"].items():
        lines.append(f"| {name} | {ver or '_not installed_'} |")
    lines += ["", "## Config file versions", "", "| File | Version | SHA-256 (first 12) |", "|---|---|---|"]
    for rel, info in manifest["config_versions"].items():
        if not info.get("exists"):
            lines.append(f"| {rel} | _missing_ | - |")
        else:
            lines.append(f"| {rel} | {info.get('version')} | `{info['sha256'][:12]}` |")
    lines += ["", "Full module-level checksums: see `RELEASE_MANIFEST.json` (`module_inventory`)."]
    (OUT_DIR / "RELEASE_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'RELEASE_MANIFEST.json'} and .md ({manifest['n_modules']} modules)")


if __name__ == "__main__":
    main()
