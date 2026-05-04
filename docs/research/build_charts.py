"""Charts for the Independent-Engines Architecture Research PDF."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "charts"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#1e1b4b"
INDIGO = "#4f46e5"
INDIGO_LT = "#a5b4fc"
PURPLE = "#7c3aed"
GREEN = "#16a34a"
GREEN_LT = "#86efac"
RED = "#dc2626"
RED_LT = "#fca5a5"
AMBER = "#f59e0b"
AMBER_LT = "#fcd34d"
SLATE = "#475569"
SLATE_LT = "#cbd5e1"
BG = "#ffffff"

plt.rcParams.update({
    "font.family": "Helvetica Neue",
    "axes.edgecolor": "#cbd5e1",
    "axes.labelcolor": "#1e293b",
    "xtick.color": "#475569",
    "ytick.color": "#475569",
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
})


def rounded(ax, x, y, w, h, text, fc, tc="white", fs=10, bold=True):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.07",
                       facecolor=fc, edgecolor="#0f172a", linewidth=0.9)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=fs, color=tc, fontweight="bold" if bold else "normal")


def arrow(ax, x1, y1, x2, y2, color="#475569", lw=1.4, style="->"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw))


# ------------------------------------------------------------------
# Chart 1: TODAY'S architecture — 11 variants, 1 brain bottleneck
# ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6.5), dpi=150)
ax.axis("off")

variants = [
    ("v4", 0.5),
    ("v5", 1.4),
    ("v5_classic", 2.3),
    ("v5_2", 3.2),
    ("v5_3", 4.1),
    ("v5_4", 5.0),
    ("v5_5", 5.9),
    ("v5_6", 6.8),
    ("v5_7", 7.7),
    ("v5_8", 8.6),
    ("v6", 9.5),
]
for name, x in variants:
    color = AMBER if name == "v4" else (RED if name in ("v5_2", "v5_3", "v6") else PURPLE)
    rounded(ax, x, 5.6, 0.85, 0.6, name, color, fs=8.5)

# Middle layer — shared scorer
rounded(ax, 3.5, 4.0, 3.0, 0.8, "v5.signal_engine\n(shared by 8 variants)", INDIGO, fs=10.5)
rounded(ax, 0.5, 4.0, 1.5, 0.8, "v4.composite_scorer\n(2 variants)", AMBER, fs=9.5)
rounded(ax, 7.0, 4.0, 1.6, 0.8, "v5_2.options_engine\n(1 variant)", RED, fs=9.0)
rounded(ax, 8.8, 4.0, 1.4, 0.8, "v5_3.staged_entry\n(1 variant)", RED, fs=9.0)

# Lines variant -> brain
def line(ax, x1, y1, x2, y2, c=SLATE_LT, lw=0.8):
    ax.plot([x1, x2], [y1, y2], color=c, linewidth=lw, alpha=0.7, zorder=0)

# Each variant connects to its brain
brain_map = {
    "v4": (1.25, 4.8),
    "v5": (5.0, 4.8), "v5_classic": (5.0, 4.8), "v5_4": (5.0, 4.8),
    "v5_5": (5.0, 4.8), "v5_6": (5.0, 4.8), "v5_7": (5.0, 4.8),
    "v5_8": (5.0, 4.8),
    "v5_2": (7.8, 4.8), "v5_3": (9.5, 4.8),
    "v6": (1.25, 4.8),  # v6 → v4.composite_scorer directly
}
for name, x in variants:
    bx, by = brain_map[name]
    line(ax, x + 0.42, 5.6, bx, by)

# Bottom layer — risk_manager (8 variants), regime_detector (10), pool_manager (8)
rounded(ax, 1.8, 2.0, 2.0, 0.7, "v5.risk_manager\n(shared by 8)", GREEN, fs=9.5)
rounded(ax, 4.2, 2.0, 2.0, 0.7, "v5.regime_detector\n(shared by 10)", GREEN, fs=9.5)
rounded(ax, 6.6, 2.0, 1.8, 0.7, "v5.pool_manager\n(shared by 8)", GREEN, fs=9.5)
rounded(ax, 8.6, 2.0, 1.6, 0.7, "v5.comparator\n(shared by 9)", GREEN, fs=9.5)

# brain -> risk
arrow(ax, 5.0, 4.0, 2.8, 2.7, color=SLATE_LT)
arrow(ax, 5.0, 4.0, 5.2, 2.7, color=SLATE_LT)
arrow(ax, 5.0, 4.0, 7.5, 2.7, color=SLATE_LT)
arrow(ax, 5.0, 4.0, 9.4, 2.7, color=SLATE_LT)

# Bottom: data layer
rounded(ax, 3.0, 0.5, 4.5, 0.7, "Single shared data feed (no corp-action filter until 2026-05-01)", SLATE, fs=10)
arrow(ax, 5.0, 2.0, 5.2, 1.2, color=SLATE_LT)

# Annotation banners
ax.text(5.0, 6.8, "11 'engines' on top — but only 4 distinct strategy brains beneath",
        ha="center", fontsize=12, fontweight="bold", color=NAVY)
ax.text(5.0, 1.65, "All 11 variants share regime detection, risk gates, pool management, and the SAME data feed.",
        ha="center", fontsize=9.5, color=SLATE, style="italic")

# Legend
ax.add_patch(Rectangle((10.6, 5.6), 0.3, 0.3, fc=AMBER, ec="black", lw=0.5)); ax.text(11.0, 5.75, "v4 family", fontsize=8.5, va="center")
ax.add_patch(Rectangle((10.6, 5.1), 0.3, 0.3, fc=PURPLE, ec="black", lw=0.5)); ax.text(11.0, 5.25, "v5 wrappers", fontsize=8.5, va="center")
ax.add_patch(Rectangle((10.6, 4.6), 0.3, 0.3, fc=RED, ec="black", lw=0.5)); ax.text(11.0, 4.75, "specialised", fontsize=8.5, va="center")

ax.set_xlim(-0.2, 12)
ax.set_ylim(0, 7.4)
plt.tight_layout()
plt.savefig(OUT / "01_today_bottleneck.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()


# ------------------------------------------------------------------
# Chart 2: TARGET architecture — independent engines, shared infra
# ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6.5), dpi=150)
ax.axis("off")

# Top tier — independent engines (each with its own scorer + model)
engines = [
    ("v4 BULL\nspecialist", AMBER),
    ("v5_4 SIDEWAYS\nbalanced", PURPLE),
    ("v5_6 BULL\nbreakout", PURPLE),
    ("v5_7 SIDEWAYS\nmean-revert", PURPLE),
    ("v5_2 BEAR\noptions hedge", RED),
    ("v6 BEAR\nshort-bias", PURPLE),
]
n = len(engines)
for i, (name, color) in enumerate(engines):
    x = 0.6 + i * 1.85
    rounded(ax, x, 5.5, 1.65, 1.0, name + "\n+ own ML model", color, fs=9.5)

# Tier 2 — shared strategy router (regime → engine)
rounded(ax, 3.5, 3.9, 5.0, 0.8, "Regime Router\n(picks engine + weights based on detected regime)", INDIGO, fs=11)
for i in range(n):
    x = 0.6 + i * 1.85 + 0.825
    arrow(ax, x, 5.5, x, 4.7, color=INDIGO_LT, lw=1.0, style="->")
arrow(ax, 6.0, 3.9, 6.0, 3.4, color=NAVY, lw=2.2)

# Tier 3 — shared risk + data layer
rounded(ax, 1.0, 2.4, 3.2, 0.7, "Shared risk_manager\n(blacklist, kill-switch)", GREEN, fs=10)
rounded(ax, 4.4, 2.4, 3.2, 0.7, "Shared regime_detector\n(BULL / SIDEWAYS / BEAR)", GREEN, fs=10)
rounded(ax, 7.8, 2.4, 3.2, 0.7, "Shared pool_manager\n(capital allocation)", GREEN, fs=10)

# Tier 4 — shared data layer with corp action filter
rounded(ax, 1.0, 0.7, 10.0, 0.8, "Shared data layer + corp-action filter (NEW) + universe management", SLATE, fs=10.5)

# Connectors
arrow(ax, 6.0, 2.4, 6.0, 1.5, color=SLATE_LT, lw=1.2)

ax.text(6.0, 6.85, "Target: 6 specialist engines, 1 router, 1 shared infrastructure stack",
        ha="center", fontsize=12, fontweight="bold", color=NAVY)
ax.text(6.0, 5.35, "INDEPENDENT (own scorer + own ML model)", ha="center", fontsize=9, color=PURPLE, fontweight="bold")
ax.text(6.0, 3.7, "ROUTING (regime-aware)", ha="center", fontsize=9, color=INDIGO, fontweight="bold")
ax.text(6.0, 2.2, "SHARED INFRASTRUCTURE (one source of truth)", ha="center", fontsize=9, color=GREEN, fontweight="bold")

ax.set_xlim(0, 12)
ax.set_ylim(0, 7.3)
plt.tight_layout()
plt.savefig(OUT / "02_target_architecture.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()


# ------------------------------------------------------------------
# Chart 3: Regime-fit HEATMAP (11 variants × 3 regimes)
# ------------------------------------------------------------------
variants_list = ["v4", "v5", "v5_classic", "v5_2", "v5_3", "v5_4", "v5_5", "v5_6", "v5_7", "v5_8", "v6"]
regimes = ["BULL", "SIDEWAYS", "BEAR"]
# Fit scores 0=poor, 1=meh, 2=ok, 3=strong (based on regime-fit agent's analysis)
scores = np.array([
    [3, 1, 0],   # v4: BULL specialist
    [1, 2, 3],   # v5: BEAR (slot partition favours shorts)
    [1, 2, 3],   # v5_classic: same as v5
    [1, 3, 3],   # v5_2: SIDEWAYS/BEAR options
    [2, 2, 2],   # v5_3: ANY (waits for confirmation)
    [1, 3, 1],   # v5_4: SIDEWAYS (balanced direction budget)
    [2, 3, 1],   # v5_5: SIDEWAYS/BULL
    [3, 1, 2],   # v5_6: BULL (Darvas breakout)
    [1, 3, 1],   # v5_7: SIDEWAYS (mean reversion)
    [2, 0, 0],   # v5_8: BULL only (slot cap disabled)
    [1, 1, 3],   # v6: BEAR (mechanical short gate)
])

fig, ax = plt.subplots(figsize=(7.5, 7.5), dpi=150)
cmap_colors = ["#fee2e2", "#fef3c7", "#bbf7d0", "#16a34a"]
from matplotlib.colors import ListedColormap
cmap = ListedColormap(cmap_colors)

im = ax.imshow(scores, cmap=cmap, aspect="auto", vmin=0, vmax=3)
ax.set_xticks(np.arange(len(regimes)))
ax.set_yticks(np.arange(len(variants_list)))
ax.set_xticklabels(regimes, fontsize=11, fontweight="bold")
ax.set_yticklabels(variants_list, fontsize=10.5, family="monospace")

labels = {0: "poor", 1: "weak", 2: "ok", 3: "strong"}
for i in range(len(variants_list)):
    for j in range(len(regimes)):
        v = scores[i, j]
        ax.text(j, i, labels[v], ha="center", va="center",
                fontsize=9, fontweight="bold",
                color="white" if v == 3 else "#1e293b")

ax.set_title("Regime ↔ Engine Fit Map", pad=14)
ax.set_xlabel("Market Regime", fontsize=11)
ax.set_ylabel("Engine Variant", fontsize=11)

# Legend strip
from matplotlib.patches import Patch
legend = [
    Patch(facecolor=cmap_colors[3], label="Strong fit (deploy)"),
    Patch(facecolor=cmap_colors[2], label="OK"),
    Patch(facecolor=cmap_colors[1], label="Weak"),
    Patch(facecolor=cmap_colors[0], label="Poor (avoid)"),
]
ax.legend(handles=legend, bbox_to_anchor=(1.02, 1), loc="upper left", framealpha=0.95)

ax.set_xticks(np.arange(scores.shape[1]) - 0.5, minor=True)
ax.set_yticks(np.arange(scores.shape[0]) - 0.5, minor=True)
ax.grid(which="minor", color="white", linewidth=2)
ax.tick_params(which="minor", length=0)

plt.tight_layout()
plt.savefig(OUT / "03_regime_fit_heatmap.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()


# ------------------------------------------------------------------
# Chart 4: OSS framework comparison — bar chart of "fit for our use case"
# ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5.2), dpi=150)
frameworks = ["Freqtrade\n(FreqAI)", "PyBroker", "NautilusTrader", "vectorbt", "Backtrader", "Zipline-Reloaded", "Lean"]
# Multi-criteria: strategy isolation, ML support, regime aware, live ready, India-friendly
criteria = ["Strategy isolation", "ML integration", "Regime support", "Live trading", "Borrow potential"]
data = np.array([
    # Freqtrade
    [4, 5, 3, 5, 5],
    # PyBroker
    [4, 5, 1, 3, 4],
    # NautilusTrader
    [5, 2, 2, 5, 4],
    # vectorbt
    [3, 3, 1, 1, 2],
    # Backtrader
    [3, 1, 1, 3, 2],
    # Zipline
    [2, 2, 1, 2, 2],
    # Lean
    [4, 2, 3, 5, 3],
])

x = np.arange(len(frameworks))
w = 0.16
colors = [INDIGO, GREEN, PURPLE, AMBER, NAVY]
for i, c in enumerate(criteria):
    offset = (i - 2) * w
    ax.bar(x + offset, data[:, i], w, label=c, color=colors[i], edgecolor="white", linewidth=0.4)

ax.set_xticks(x)
ax.set_xticklabels(frameworks, fontsize=10)
ax.set_ylabel("Fit score (1-5)", fontsize=11)
ax.set_title("OSS Trading Frameworks — Fit for Independent-Engine + ML Architecture", pad=14)
ax.legend(loc="upper right", framealpha=0.95, fontsize=9, ncol=5, bbox_to_anchor=(1.0, 1.13))
ax.set_ylim(0, 6)
ax.grid(axis="y", linestyle="--", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

# Highlight Freqtrade as winner
ax.axvspan(-0.5, 0.5, color=GREEN_LT, alpha=0.2, zorder=0)
ax.text(0, 5.6, "BEST FIT", ha="center", fontsize=9, fontweight="bold", color=GREEN)

plt.tight_layout()
plt.savefig(OUT / "04_oss_comparison.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()


# ------------------------------------------------------------------
# Chart 5: Migration phases timeline
# ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 4.5), dpi=150)
ax.axis("off")

phases = [
    ("Weekend\n(2 days)", "Phase 1: Hygiene", GREEN,
     "• Per-position SL\n• Per-stock cool-off\n• Lab pruning (retire wrappers)"),
    ("Week 1-2", "Phase 2: Extract", AMBER,
     "• Fork v5_6 → own scorer\n• Fork v5_7 → own scorer\n• Define IStrategy contract"),
    ("Week 3-4", "Phase 3: Train", PURPLE,
     "• Per-engine ML pipelines\n• Backtest on Apr 20-30 data\n• Regime-fit validation"),
    ("Week 5-6", "Phase 4: Router", INDIGO,
     "• Regime → engine router\n• A/B vs current v5\n• Deploy live"),
]

w = 2.4
for i, (when, title, color, body) in enumerate(phases):
    x = 0.4 + i * 2.7
    rounded(ax, x, 1.8, w, 0.8, title, color, fs=11)
    ax.text(x + w/2, 2.95, when, ha="center", fontsize=10, fontweight="bold", color=NAVY)
    ax.text(x + 0.1, 1.5, body, ha="left", va="top", fontsize=9, color="#1e293b")
    if i < len(phases) - 1:
        arrow(ax, x + w + 0.05, 2.2, x + w + 0.25, 2.2, color=NAVY, lw=2)

ax.text(5.5, 3.7, "Migration Plan — From 11 Wrappers to 6 Independent Engines",
        ha="center", fontsize=13, fontweight="bold", color=NAVY)

ax.set_xlim(0, 11.5)
ax.set_ylim(0, 4.2)
plt.tight_layout()
plt.savefig(OUT / "05_migration.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()


# ------------------------------------------------------------------
# Chart 6: ML training pipeline — V3 hybrid recommendation
# ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
ax.axis("off")

# Left column — historical data
rounded(ax, 0.3, 3.4, 2.0, 0.8, "Historical EOD\nApr 16-30 trades", SLATE, fs=10)
rounded(ax, 0.3, 2.2, 2.0, 0.8, "Regime labels\n(BULL/SIDE/BEAR)", SLATE, fs=10)
rounded(ax, 0.3, 1.0, 2.0, 0.8, "Market features\n(RSI, vol, VIX)", SLATE, fs=10)

# Middle — per-engine training
rounded(ax, 3.5, 3.4, 2.4, 0.8, "v4 BULL trainer", AMBER, fs=10)
rounded(ax, 3.5, 2.2, 2.4, 0.8, "v5_4 SIDEWAYS trainer", PURPLE, fs=10)
rounded(ax, 3.5, 1.0, 2.4, 0.8, "v5_2 BEAR trainer", RED, fs=10)

# Models
rounded(ax, 6.7, 3.4, 1.4, 0.8, "BULL\nmodel.pkl", AMBER, fs=10)
rounded(ax, 6.7, 2.2, 1.4, 0.8, "SIDEWAYS\nmodel.pkl", PURPLE, fs=10)
rounded(ax, 6.7, 1.0, 1.4, 0.8, "BEAR\nmodel.pkl", RED, fs=10)

# Router
rounded(ax, 8.8, 2.2, 2.0, 0.8, "Regime Router\n(runtime)", INDIGO, fs=11)

# Arrows
for y in [3.8, 2.6, 1.4]:
    arrow(ax, 2.3, y, 3.5, y, color=SLATE_LT)
    arrow(ax, 5.9, y, 6.7, y, color=SLATE_LT)
    arrow(ax, 8.1, y, 8.8, y, color=INDIGO_LT)

# Live signal
rounded(ax, 8.8, 0.3, 2.0, 0.6, "Today's regime →\npicks model", INDIGO, fs=9.5)
arrow(ax, 9.8, 2.2, 9.8, 0.95, color=INDIGO, lw=1.2)

ax.text(5.5, 4.6, "V3 Hybrid: Per-Regime Models with Lightweight Slot-Allocation Classifier",
        ha="center", fontsize=12, fontweight="bold", color=NAVY)
ax.text(5.5, 0.3, "Training is offline; runtime is just a dictionary lookup. Cold-start fallback = today's fixed slot partition.",
        ha="center", fontsize=9, color=SLATE, style="italic")

ax.set_xlim(0, 11)
ax.set_ylim(-0.1, 5)
plt.tight_layout()
plt.savefig(OUT / "06_ml_pipeline.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

print("Generated:", sorted(p.name for p in OUT.glob("*.png")))
