"""Uncertainty visualizations for reviewer audit -- v2 (§10 of
docs/uncertainty/EVIDENCE_RELIABILITY_REDESIGN.md).

Replaces the v1 4-panel dashboard, two of whose panels were rendered
uninformative by v1's ceiling-saturation bug, with 5 panels that each expose a
distinct part of the v2 model: the Inherited/Resolved/New/Remaining budget
identity, variance-decomposed source contribution, the declared-correlation
structure, per-engine comparison, and the 3-axis Confidence x Measurement
Uncertainty x Evidence Reliability picture that the whole redesign exists to
make legible (v1 collapsed everything to a single point at uncertainty=~100).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cieml.uncertainty.propagate import _dedup_by_provenance
from cieml.uncertainty.models import UncertaintyComponent, UncertaintyKind

MAIN_CHAIN_ORDER = [
    "qa",
    "measurement",
    "sensor",
    "statistical",
    "model",
    "explainability",
    "anomaly",
    "environmental",
    "policy",
    "decision",
]


def _packets_frame(ledger: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for p in ledger.get("packets") or []:
        u = p.get("uncertainty") or {}
        rows.append(
            {
                "engine": p.get("engine"),
                "object_type": p.get("object_type"),
                "result_ref": p.get("result_ref"),
                "confidence": p.get("confidence"),
                "inherited": u.get("inherited"),
                "resolved": u.get("resolved"),
                "new_uncertainty": u.get("new_uncertainty"),
                "remaining": u.get("remaining"),
                "raw_total": u.get("raw_total"),
                "evidence_reliability": p.get("evidence_reliability"),
                "caution": p.get("caution"),
                "rule_id": u.get("rule_id"),
                "n_dedup_warnings": len(u.get("dedup_warnings") or []),
            }
        )
    return pd.DataFrame(rows)


def _packet_components(
    ledger: dict[str, Any], object_type: str | None = None, result_ref: str | None = None
) -> list[UncertaintyComponent]:
    """Reconstruct UncertaintyComponent objects for a specific packet (matched
    by `result_ref` if given, else the first packet of `object_type`), so the
    same `_dedup_by_provenance` used at combination time also drives the
    visualization -- the chart must decompose what was actually combined for
    THAT packet, not a re-derived approximation of a same-type packet."""
    for p in ledger.get("packets") or []:
        if result_ref is not None:
            if p.get("result_ref") != result_ref:
                continue
        elif p.get("object_type") != object_type:
            continue
        comps = []
        for c in (p.get("uncertainty") or {}).get("components") or []:
            comps.append(
                UncertaintyComponent(
                    kind=c.get("kind", UncertaintyKind.RANDOM.value),
                    value=c.get("value", 0.0),
                    source=c.get("source", ""),
                    rationale=c.get("rationale", ""),
                    provenance_id=c.get("provenance_id", "unspecified"),
                    resolves_upstream=c.get("resolves_upstream", False),
                )
            )
        return comps
    return []


def fig_budget_waterfall(ledger: dict[str, Any], path: Path) -> Path:
    """Panel 1 -- Inherited / -Resolved / +New / =Remaining per engine, as
    floating waterfall bars, so a reviewer sees where doubt was added or
    removed at a glance instead of only a cumulative total. The final bar is
    drawn twice (as the telescoping endpoint, and as an independent check from
    0) so any drift between the two would be visible as a mismatch."""
    df = _packets_frame(ledger)
    panels = [(obj, df[df["object_type"] == obj].iloc[0]) for obj in MAIN_CHAIN_ORDER if (df["object_type"] == obj).any()]
    claims = df[df["object_type"] == "scientific_claim"]
    if len(claims):
        mean_row = claims[["inherited", "resolved", "new_uncertainty", "remaining"]].mean()
        mean_row["object_type"] = "scientific_claim (mean)"
        panels.append(("scientific_claim (mean)", mean_row))

    n = len(panels)
    ncols = min(4, n) or 1
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.1 * ncols, 3.0 * nrows), squeeze=False)

    for i, (name, row) in enumerate(panels):
        ax = axes[i // ncols][i % ncols]
        inherited = float(row["inherited"] or 0.0)
        resolved = float(row["resolved"] or 0.0)
        new_u = float(row["new_uncertainty"] or 0.0)
        remaining = float(row["remaining"] or 0.0)

        steps = [
            ("Inherited", 0.0, inherited, "#455a64"),
            ("-Resolved", inherited - resolved, inherited, "#2e7d32"),
            ("+New", inherited - resolved, inherited - resolved + new_u, "#c62828"),
            ("=Remaining", 0.0, remaining, "#1f4e79"),
        ]
        for j, (label, lo, hi, color) in enumerate(steps):
            ax.bar(j, hi - lo, bottom=lo, color=color, width=0.65)
        ax.set_xticks(range(4))
        ax.set_xticklabels(["Inh", "-Res", "+New", "=Rem"], fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_title(name, fontsize=9)
        ax.axhline(remaining, color="#1f4e79", ls=":", lw=0.7, alpha=0.6)

    for i in range(n, nrows * ncols):
        axes[i // ncols][i % ncols].axis("off")

    fig.suptitle("Uncertainty budget waterfall -- Inherited - Resolved + New = Remaining", y=1.02, fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return path


def _contribution_shares(components: list[UncertaintyComponent]) -> tuple[list[str], list[float]]:
    if not components:
        return [], []
    deduped, _ = _dedup_by_provenance(components)
    sq = [c.value ** 2 for c in deduped]
    total = sum(sq)
    if total <= 0:
        return [], []
    labels = [f"{c.provenance_id}\n({c.kind.value})" for c in deduped]
    shares = [100.0 * s / total for s in sq]
    order = np.argsort(shares)[::-1]
    return [labels[i] for i in order], [shares[i] for i in order]


def fig_source_contribution(ledger: dict[str, Any], path: Path) -> Path:
    """Panel 2 -- variance-decomposed source contribution (Saltelli-style):
    contribution_i = sigma_i^2 / sum_j sigma_j^2 per deduplicated provenance
    pool, for the two packets where the composition of doubt is most
    scientifically interesting: the worst (highest-remaining) packet overall,
    and the Discovery/Model packet specifically (the corroborating-evidence
    precision-fusion case). Always sums to 100% by construction."""
    df = _packets_frame(ledger)
    worst_ref, worst_obj = None, None
    if len(df):
        worst_row = df.loc[df["remaining"].idxmax()]
        worst_ref, worst_obj = worst_row["result_ref"], worst_row["object_type"]
    targets = []
    if worst_ref is not None:
        targets.append((f"Highest-uncertainty packet: {worst_obj}/{worst_ref}", worst_obj, worst_ref))
    if worst_obj != "model":
        targets.append(("Discovery / Model (precision-fusion case)", "model", None))

    fig, axes = plt.subplots(1, len(targets), figsize=(6.5 * len(targets), 5), squeeze=False)
    for i, (title, obj, ref) in enumerate(targets):
        ax = axes[0][i]
        comps = _packet_components(ledger, obj, ref)
        labels, shares = _contribution_shares(comps)
        if not labels:
            ax.text(0.5, 0.5, "No components", ha="center")
            ax.axis("off")
            continue
        colors = sns.color_palette("crest", n_colors=len(labels))
        ax.barh(range(len(labels)), shares, color=colors)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Contribution to sigma^2 (%)")
        ax.set_xlim(0, max(shares) * 1.15 if shares else 100)
        ax.set_title(title, fontsize=10)
        for j, s in enumerate(shares):
            ax.text(s + max(shares) * 0.02, j, f"{s:.0f}%", va="center", fontsize=8)

    fig.suptitle("Source contribution -- variance decomposition per provenance pool", y=1.03, fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_correlation_graph(ledger: dict[str, Any], path: Path, correlations: dict | None = None) -> Path:
    """Panel 3 -- nodes = distinct provenance pools across the ledger, edges =
    declared correlation coefficients (rho), per §4. Makes "which doubts are
    secretly the same doubt" inspectable instead of implicit. When no explicit
    `correlations` map is supplied (the current default everywhere in
    assemble.py, i.e. rho=0 / independence assumed for all cross-engine
    pairs), the graph renders nodes only, with an explicit note -- this is
    honest about what the model currently assumes rather than fabricating
    edges that were never declared."""
    all_ids: dict[str, str] = {}
    for p in ledger.get("packets") or []:
        for c in (p.get("uncertainty") or {}).get("components") or []:
            pid = c.get("provenance_id", "unspecified")
            if pid != "unspecified":
                all_ids[pid] = c.get("kind", "")

    ids = list(all_ids.keys())
    n = len(ids)
    fig, ax = plt.subplots(figsize=(max(10, 0.55 * n), max(10, 0.55 * n)))
    if n == 0:
        ax.text(0.5, 0.5, "No provenance-tagged components", ha="center")
        ax.axis("off")
        fig.savefig(path, dpi=600, bbox_inches="tight")
        plt.close(fig)
        return path

    radius = max(3.0, 0.5 * n / np.pi)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pos = {pid: (radius * np.cos(a), radius * np.sin(a)) for pid, a in zip(ids, angles)}

    n_edges = 0
    if correlations:
        for key, rho in correlations.items():
            pair = list(key) if isinstance(key, (set, frozenset)) else key
            if len(pair) != 2 or pair[0] not in pos or pair[1] not in pos:
                continue
            x0, y0 = pos[pair[0]]
            x1, y1 = pos[pair[1]]
            ax.plot([x0, x1], [y0, y1], color="#c62828", lw=1.0 + 3.0 * float(rho), alpha=0.7, zorder=1)
            ax.annotate(f"rho={float(rho):.2f}", ((x0 + x1) / 2, (y0 + y1) / 2), fontsize=7, color="#c62828")
            n_edges += 1

    for pid, (x, y) in pos.items():
        ax.scatter([x], [y], s=220, color="#1f4e79", zorder=3)
        angle = np.arctan2(y, x)
        lx, ly = x + 0.35 * np.cos(angle), y + 0.35 * np.sin(angle)
        ha = "left" if np.cos(angle) >= 0 else "right"
        ax.annotate(pid, (x, y), xytext=(lx, ly), ha=ha, va="center", fontsize=7.5, color="#1a1a1a", zorder=4)

    lim = radius + 1.6
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axis("off")
    subtitle = f"{n_edges} declared correlation(s)" if n_edges else "No correlations declared -- default rho=0 (independence) assumed for every pair"
    ax.set_title(f"Correlation graph -- provenance pools\n{subtitle}", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_engine_contribution(ledger: dict[str, Any], path: Path) -> Path:
    """Panel 4 -- mean Remaining (M) by engine/object type. Analogous to v1's
    panel A but now genuinely discriminative: totals no longer cluster at the
    ceiling under v2's saturate-once-at-report-time rule."""
    df = _packets_frame(ledger)
    g = df.groupby("object_type", as_index=False)["remaining"].mean().sort_values("remaining")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = sns.color_palette("crest", n_colors=len(g))
    ax.barh(g["object_type"], g["remaining"], color=colors)
    for i, v in enumerate(g["remaining"]):
        ax.text(v + 1, i, f"{v:.1f}", va="center", fontsize=8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Mean Remaining uncertainty (M, 0-100)")
    ax.set_title("Engine contribution -- mean Remaining M by object type")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_confidence_reliability_uncertainty_scatter(ledger: dict[str, Any], path: Path) -> Path:
    """Panel 5 -- the redesign's concrete acceptance test (§9.6/§11 step 5):
    Confidence (x) vs. Measurement & Model Uncertainty / Remaining (y), with
    point size AND color both encoding Evidence Reliability (R) so the third
    axis reads even in grayscale. Points must show visible spread rather than
    clustering at uncertainty~100 -- if they cluster, the v2 migration has not
    actually fixed the ceiling-saturation problem it was built to fix."""
    df = _packets_frame(ledger).dropna(subset=["confidence", "remaining"]).copy()
    fig, ax = plt.subplots(figsize=(8, 6.5))
    if not len(df):
        ax.text(0.5, 0.5, "No packets with both confidence and uncertainty", ha="center")
        ax.axis("off")
        fig.savefig(path, dpi=600, bbox_inches="tight")
        plt.close(fig)
        return path

    has_r = df["evidence_reliability"].notna()
    sizes = np.where(has_r, 40 + 1.6 * df["evidence_reliability"].fillna(0), 45)
    sc = ax.scatter(
        df.loc[has_r, "confidence"], df.loc[has_r, "remaining"], s=sizes[has_r],
        c=df.loc[has_r, "evidence_reliability"], cmap="viridis", vmin=0, vmax=100,
        alpha=0.85, edgecolors="#263238", linewidths=0.6, label="R known",
    )
    if (~has_r).any():
        ax.scatter(
            df.loc[~has_r, "confidence"], df.loc[~has_r, "remaining"], s=70,
            c="#bdbdbd", alpha=0.6, edgecolors="#616161", linewidths=0.6, label="R unavailable",
        )
    offsets = [(14, 10), (14, -10), (-14, 14), (14, 26), (-14, -14), (14, -26), (-14, 26), (-14, -26)]
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        ox, oy = offsets[i % len(offsets)]
        ha = "left" if ox > 0 else "right"
        ax.annotate(
            str(r["result_ref"])[-22:], (r["confidence"], r["remaining"]), fontsize=6.5, alpha=0.9, ha=ha,
            xytext=(ox, oy), textcoords="offset points",
            arrowprops=dict(arrowstyle="-", color="#9e9e9e", lw=0.5, alpha=0.6),
        )

    if has_r.any():
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label("Evidence Reliability (R, 0-100)")

    ax.set_xlabel("Confidence (EBSVE, 0-100)")
    ax.set_ylabel("Measurement & Model Uncertainty -- Remaining (0-100)")
    ax.set_xlim(-2, 102)
    ax.set_ylim(-2, 102)
    ax.axhline(50, color="#9e9e9e", ls=":", lw=0.7)
    ax.axvline(70, color="#9e9e9e", ls=":", lw=0.7)
    ax.set_title("Confidence x Measurement Uncertainty x Evidence Reliability")
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return path


def render_uncertainty_figures(ledger: dict[str, Any], fig_dir: Path, correlations: dict | None = None) -> dict[str, str]:
    fig_dir = Path(fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    return {
        "budget_waterfall": str(fig_budget_waterfall(ledger, fig_dir / "fig_uncertainty_budget_waterfall.png")),
        "source_contribution": str(fig_source_contribution(ledger, fig_dir / "fig_uncertainty_source_contribution.png")),
        "correlation_graph": str(fig_correlation_graph(ledger, fig_dir / "fig_uncertainty_correlation_graph.png", correlations)),
        "engine_contribution": str(fig_engine_contribution(ledger, fig_dir / "fig_uncertainty_engine_contribution.png")),
        "confidence_reliability_scatter": str(
            fig_confidence_reliability_uncertainty_scatter(ledger, fig_dir / "fig_uncertainty_confidence_reliability_scatter.png")
        ),
    }
