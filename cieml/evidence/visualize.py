"""Figures for the evidence engine: radar charts, confidence bars, a maturity
matrix, an evidence heatmap, a pillar-contribution chart, a comparison dashboard,
and a reviewer summary table. Matches the project's existing figure conventions
(600 dpi, tight_layout, consistent palette).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PILLARS = ("statistical", "practical", "physical", "environmental")
CLASS_COLOR = {"DEFINITIVE": "#2e7d32", "PROVISIONAL": "#f9a825", "EXPLORATORY": "#c62828"}
CLASS_SCORE = {"DEFINITIVE": 1.0, "PROVISIONAL": 0.5, "EXPLORATORY": 0.0}


def _pillar_matrix(hypotheses: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for hid, h in hypotheses.items():
        row = {"hypothesis": hid}
        for p in PILLARS:
            row[p] = h["pillars"][p]["score"]
        rows.append(row)
    return pd.DataFrame(rows).set_index("hypothesis")


def plot_radar_charts(hypotheses: dict[str, Any], fig_dir: Path) -> str:
    n = len(hypotheses)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    angles = np.linspace(0, 2 * np.pi, len(PILLARS), endpoint=False).tolist()
    angles += angles[:1]

    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 4.2 * nrows), subplot_kw={"polar": True})
    axes = np.array(axes).reshape(-1)
    for ax, (hid, h) in zip(axes, hypotheses.items()):
        vals = [h["pillars"][p]["score"] for p in PILLARS]
        vals += vals[:1]
        color = CLASS_COLOR.get(h["classification"], "#607d8b")
        ax.plot(angles, vals, color=color, linewidth=1.8)
        ax.fill(angles, vals, color=color, alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(PILLARS, fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_title(f"{hid}\n{h['classification']} ({h['overall_confidence']:.0f}/100)", fontsize=9)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("Stage 14 — Evidence radar per hypothesis", y=1.02)
    fig.tight_layout()
    p = fig_dir / "fig_stage14_evidence_radar.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_confidence_bars(hypotheses: dict[str, Any], fig_dir: Path) -> str:
    df = pd.DataFrame(
        [{"hypothesis": hid, "confidence": h["overall_confidence"], "classification": h["classification"]} for hid, h in hypotheses.items()]
    ).sort_values("confidence")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = df["classification"].map(CLASS_COLOR).fillna("#607d8b")
    ax.barh(df["hypothesis"], df["confidence"], color=colors)
    ax.axvline(70, color="black", ls="--", lw=0.8, label="PROVISIONAL floor (70)")
    ax.axvline(90, color="black", ls=":", lw=0.8, label="DEFINITIVE floor (90)")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Overall confidence (0-100)")
    ax.set_title("Stage 14 — Hypothesis confidence")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = fig_dir / "fig_stage14_confidence_bars.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_maturity_matrix(hypotheses: dict[str, Any], fig_dir: Path) -> str:
    df = pd.DataFrame(
        [{"hypothesis": hid, "classification": h["classification"]} for hid, h in hypotheses.items()]
    ).set_index("hypothesis")
    df["score"] = df["classification"].map(CLASS_SCORE)
    fig, ax = plt.subplots(figsize=(5, max(3, 0.55 * len(df))))
    cmap = plt.matplotlib.colors.ListedColormap(["#c62828", "#f9a825", "#2e7d32"])
    im = ax.imshow(df[["score"]].to_numpy(), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df.index)
    ax.set_xticks([0])
    ax.set_xticklabels(["classification"])
    for i, (hid, row) in enumerate(df.iterrows()):
        ax.text(0, i, row["classification"], ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    ax.set_title("Stage 14 — Scientific maturity matrix")
    fig.tight_layout()
    p = fig_dir / "fig_stage14_maturity_matrix.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_evidence_heatmap(hypotheses: dict[str, Any], fig_dir: Path) -> str:
    mat = _pillar_matrix(hypotheses)
    fig, ax = plt.subplots(figsize=(7, max(3, 0.6 * len(mat))))
    sns.heatmap(mat, annot=True, fmt=".0f", cmap="RdYlGn", vmin=0, vmax=100, ax=ax, cbar_kws={"label": "pillar score"})
    ax.set_title("Stage 14 — Evidence heatmap (pillar scores)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    p = fig_dir / "fig_stage14_evidence_heatmap.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_pillar_contribution(hypotheses: dict[str, Any], fig_dir: Path) -> str:
    mat = _pillar_matrix(hypotheses)
    fig, ax = plt.subplots(figsize=(8, 5))
    mat.plot(kind="bar", stacked=False, ax=ax, colormap="tab10")
    ax.axhline(70, color="black", ls="--", lw=0.8)
    ax.axhline(90, color="black", ls=":", lw=0.8)
    ax.set_ylabel("Pillar score (0-100)")
    ax.set_title("Stage 14 — Pillar contribution per hypothesis")
    ax.legend(title="Pillar", fontsize=8)
    fig.tight_layout()
    p = fig_dir / "fig_stage14_pillar_contribution.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_comparison_dashboard(hypotheses: dict[str, Any], campaign_closure: str, fig_dir: Path) -> str:
    mat = _pillar_matrix(hypotheses)
    conf = pd.Series({hid: h["overall_confidence"] for hid, h in hypotheses.items()})
    cls = pd.Series({hid: h["classification"] for hid, h in hypotheses.items()})

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))

    colors = cls.map(CLASS_COLOR).fillna("#607d8b")
    axes[0].barh(conf.sort_values().index, conf.sort_values().values, color=colors[conf.sort_values().index])
    axes[0].axvline(70, color="black", ls="--", lw=0.8)
    axes[0].axvline(90, color="black", ls=":", lw=0.8)
    axes[0].set_title("Confidence")
    axes[0].set_xlim(0, 100)

    sns.heatmap(mat, annot=True, fmt=".0f", cmap="RdYlGn", vmin=0, vmax=100, ax=axes[1], cbar=False)
    axes[1].set_title("Pillar scores")
    axes[1].tick_params(axis="x", rotation=30)

    counts = cls.value_counts()
    axes[2].pie(
        counts.values,
        labels=counts.index,
        colors=[CLASS_COLOR.get(c, "#607d8b") for c in counts.index],
        autopct="%1.0f%%",
        startangle=90,
    )
    axes[2].set_title(f"Classification mix\ncampaign_closure={campaign_closure}")

    fig.suptitle("Stage 14 — Hypothesis comparison dashboard", y=1.03)
    fig.tight_layout()
    p = fig_dir / "fig_stage14_comparison_dashboard.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_reviewer_summary_table(hypotheses: dict[str, Any], fig_dir: Path) -> str:
    rows = []
    for hid, h in hypotheses.items():
        weakest = min(h["pillars"].values(), key=lambda p: p["score"])
        rows.append(
            [
                hid,
                h["classification"],
                f"{h['overall_confidence']:.0f}",
                h["evidence_strength"],
                f"{weakest['name']} ({weakest['score']:.0f})",
            ]
        )
    fig, ax = plt.subplots(figsize=(11, 0.42 * len(rows) + 0.8))
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=["Hypothesis", "Classification", "Confidence", "Evidence strength", "Weakest pillar"],
        cellLoc="left",
        bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for j, hid in enumerate([r[0] for r in rows]):
        color = CLASS_COLOR.get(hypotheses[hid]["classification"], "#ffffff")
        table[(j + 1, 1)].set_facecolor(color)
        table[(j + 1, 1)].get_text().set_color("white")
    ax.set_title("Stage 14 — Reviewer summary table", pad=16)
    fig.tight_layout()
    p = fig_dir / "fig_stage14_reviewer_summary_table.png"
    fig.savefig(p, dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def render_all(engine_result: dict[str, Any], fig_dir: Path) -> dict[str, str]:
    fig_dir = Path(fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    hyps = engine_result["hypotheses"]
    campaign_closure = engine_result["campaign_closure"]
    paths = {}
    try:
        paths["evidence_radar"] = plot_radar_charts(hyps, fig_dir)
        paths["confidence_bars"] = plot_confidence_bars(hyps, fig_dir)
        paths["maturity_matrix"] = plot_maturity_matrix(hyps, fig_dir)
        paths["evidence_heatmap"] = plot_evidence_heatmap(hyps, fig_dir)
        paths["pillar_contribution"] = plot_pillar_contribution(hyps, fig_dir)
        paths["comparison_dashboard"] = plot_comparison_dashboard(hyps, campaign_closure, fig_dir)
        paths["reviewer_summary_table"] = plot_reviewer_summary_table(hyps, fig_dir)
    except Exception as exc:  # noqa: BLE001
        paths["_render_error"] = f"{type(exc).__name__}: {exc}"
    return paths
