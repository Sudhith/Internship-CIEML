"""Knowledge Base (Phase K / SC-KB) — append-only scientific memory."""
from __future__ import annotations

from cieml.knowledge.propose import propose_from_campaign
from cieml.knowledge.store import KnowledgeStore, load_store

__all__ = ["KnowledgeStore", "load_store", "propose_from_campaign"]
