"""Append-only KB store under knowledge_base/ (never writes configs/domains/)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KB_ROOT = ROOT / "knowledge_base"
ENTRIES_DIR = KB_ROOT / "entries"
PROPOSALS_DIR = KB_ROOT / "proposals"
AUDIT_LOG = KB_ROOT / "audit_log.jsonl"

GRADES = ("candidate", "supported", "contested", "retired")


@dataclass
class KnowledgeStore:
    root: Path = field(default_factory=lambda: KB_ROOT)

    def __post_init__(self) -> None:
        (self.root / "entries").mkdir(parents=True, exist_ok=True)
        (self.root / "proposals").mkdir(parents=True, exist_ok=True)
        if not (self.root / "audit_log.jsonl").exists():
            (self.root / "audit_log.jsonl").write_text("", encoding="utf-8")

    @property
    def entries_dir(self) -> Path:
        return self.root / "entries"

    @property
    def proposals_dir(self) -> Path:
        return self.root / "proposals"

    @property
    def audit_path(self) -> Path:
        return self.root / "audit_log.jsonl"

    def append_audit(self, event: str, payload: dict[str, Any]) -> None:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    def _latest_version(self, entry_id: str, base_path: Path) -> tuple[int, str]:
        """Highest version already on disk for `entry_id`, and the filename that holds it.

        The unversioned `{entry_id}.json` is only ever written once (at v1) and never
        rewritten in place, so re-reading it on every subsequent write always reports
        version=1 — that was the bug: every write after the second silently overwrote
        the same `_v2.json` file forever. Scan for the actual highest `_vN.json` on disk.
        """
        best_ver = 1
        best_name = base_path.name
        for p in self.entries_dir.glob(f"{entry_id}_v*.json"):
            suffix = p.stem.rsplit("_v", 1)[-1]
            if suffix.isdigit() and int(suffix) > best_ver:
                best_ver = int(suffix)
                best_name = p.name
        return best_ver, best_name

    def write_entry(self, entry: dict[str, Any]) -> Path:
        entry_id = str(entry["entry_id"])
        grade = entry.get("grade") or "candidate"
        if grade not in GRADES:
            raise ValueError(f"Invalid grade {grade}; expected one of {GRADES}")
        if not entry.get("provenance"):
            raise ValueError("KB entry requires provenance")
        base_path = self.entries_dir / f"{entry_id}.json"
        if base_path.exists():
            # Append-only: version bump rather than overwrite.
            prev_ver, prev_name = self._latest_version(entry_id, base_path)
            ver = prev_ver + 1
            entry = dict(entry)
            entry["version"] = ver
            entry["supersedes"] = prev_name
            path = self.entries_dir / f"{entry_id}_v{ver}.json"
        else:
            entry = dict(entry)
            entry.setdefault("version", 1)
            path = base_path
        path.write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")
        self.append_audit("entry_written", {"path": str(path), "entry_id": entry_id, "grade": grade})
        return path

    def write_domain_proposal(self, proposal: dict[str, Any]) -> Path:
        """Suggested domain YAML change — never auto-applied."""
        pid = str(proposal.get("proposal_id") or "proposal")
        path = self.proposals_dir / f"{pid}.json"
        n = 1
        while path.exists():
            n += 1
            path = self.proposals_dir / f"{pid}_{n}.json"
        proposal = dict(proposal)
        proposal["status"] = "pending_review"
        proposal["auto_applied"] = False
        path.write_text(json.dumps(proposal, indent=2, default=str), encoding="utf-8")
        self.append_audit("domain_proposal", {"path": str(path), "proposal_id": pid})
        return path

    def list_entries(self) -> list[dict[str, Any]]:
        out = []
        for p in sorted(self.entries_dir.glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return out


def load_store(root: Path | None = None) -> KnowledgeStore:
    return KnowledgeStore(root=Path(root) if root else KB_ROOT)
