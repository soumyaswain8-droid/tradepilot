"""Generate 5 root-cause analysis charts for 2026-04-27 deep-dive."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

OUT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/reports/2026-04-27/charts")
OUT.mkdir(parents=True, exist_ok=True)

# Color palette
COLOR_V5    = "#4f46e5"
COLOR_V5_6  = "#16a34a"
COLOR_V5_7  = "#dc2626"
COLOR_BG    = "#fafafa"
COLOR_GRID  = "#e5e7eb"
COLOR_TODAY = "#fbbf24"

plt.rcParams.update({
    "font.family": "Avenir Next",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.edgecolor": "#9ca3af",
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.grid": True,
    "grid.color": COLOR_GRID,
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# Data: 5-day P&L per engine (Rs)
days = ["04-22\nElite", "04-23\nDecline", "04-24\nPoor", "04-27\nWorst"]
v5_pnl    = [44612, 16438, 4331,   737]
v5_6_pnl  = [61284, 11761, 7411,   880]
v5_7_pnl  = [61552,  3029, 5303,   435]

# Win rate %
v5_wr    = [89, 68, 54, 50]
v5_6_wr  = [92, 62, 63, 48]
v5_7_wr  = [92, 49, 61, 46]

# ---- Chart 1: 5-day trend line chart ----
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(days))
ax.plot(x, v5_pnl,   marker='o', linewidth=2.5, markersize=10, color=COLOR_V5,   label="v5")
ax.plot(x, v5_6_pnl, marker='s', linewidth=2.5, markersize=10, color=COLOR_V5_6, label="v5_6")
ax.plot(x, v5_7_pnl, marker='^', linewidth=2.5, markersize=10, color=COLOR_V5_7, label="v5_7")

# Highlight today
ax.axvspan(2.5, 3.5, alpha=0.18, color=COLOR_TODAY, label="Today (worst)")

# Labels
for i, (a, b, c) in enumerate(zip(v5_pnl, v5_6_pnl, v5_7_pnl)):
    ax.annotate(f"Rs {a/1000:.1f}K", (i, a), textcoords="offset points", xytext=(8,6), fontsize=8, color=COLOR_V5)
    ax.annotate(f"Rs {b/1000:.1f}K", (i, b), textcoords="offset points", xytext=(8,-12), fontsize=8, color=COLOR_V5_6)
    ax.annotate(f"Rs {c/1000:.1f}K", (i, c), textcoords="offset points", xytext=(8,6), fontsize=8, color=COLOR_V5_7)

ax.set_xticks(x)
ax.set_xticklabels(days)
ax.set_ylabel("Realized P&L (Rs)")
ax.set_title("5-Day P&L Decline — April 22-27", pad=12)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{int(y/1000)}K"))
ax.legend(loc="upper right", frameon=True, framealpha=0.95)
ax.set_ylim(bottom=-3000)
plt.tight_layout()
plt.savefig(OUT / "chart1_5day_trend.png", dpi=150, bbox_inches="tight")
plt.close()

# ---- Chart 2: Win-rate decline bar chart ----
fig, ax = plt.subplots(figsize=(9, 5))
width = 0.27
x = np.arange(len(days))
b1 = ax.bar(x - width, v5_wr,    width, label="v5",   color=COLOR_V5)
b2 = ax.bar(x,         v5_6_wr,  width, label="v5_6", color=COLOR_V5_6)
b3 = ax.bar(x + width, v5_7_wr,  width, label="v5_7", color=COLOR_V5_7)
for bars in (b1, b2, b3):
    ax.bar_label(bars, fmt="%d%%", padding=3, fontsize=9)
ax.axhline(60, ls="--", color="#9ca3af", linewidth=1, label="60% baseline")
ax.set_xticks(x)
ax.set_xticklabels(days)
ax.set_ylabel("Win Rate (%)")
ax.set_title("Win Rate Decline — Each Engine Lost ~40 Percentage Points", pad=12)
ax.set_ylim(0, 105)
ax.legend(loc="upper right")
plt.tight_layout()
plt.savefig(OUT / "chart2_wr_decline.png", dpi=150, bbox_inches="tight")
plt.close()

# ---- Chart 3: Today's W/L stacked bar ----
fig, ax = plt.subplots(figsize=(9, 5))
engines = ["v5", "v5_6", "v5_7"]
wins   = [23, 28, 22]
losses = [23, 30, 26]
x = np.arange(len(engines))
b1 = ax.bar(x, wins,   color="#16a34a", label="Wins",   edgecolor="white")
b2 = ax.bar(x, losses, bottom=wins, color="#dc2626", label="Losses", edgecolor="white")
for i, (w, l) in enumerate(zip(wins, losses)):
    ax.text(i, w/2, f"{w}", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
    ax.text(i, w + l/2, f"{l}", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
    wr = 100 * w / (w + l)
    ax.text(i, w + l + 1.5, f"WR {wr:.0f}%", ha="center", fontsize=10, color="#374151")
ax.set_xticks(x); ax.set_xticklabels(engines, fontsize=11)
ax.set_ylabel("Trade Count")
ax.set_title("Today's W/L Split — Coin-Flip Outcomes Across All 3 Engines", pad=12)
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(OUT / "chart3_today_wl_split.png", dpi=150, bbox_inches="tight")
plt.close()

# ---- Chart 4: LONG vs SHORT P&L today ----
fig, ax = plt.subplots(figsize=(9, 5))
long_pnl  = [1528, 1927, 1202]
short_pnl = [-789, -1042, -765]
x = np.arange(len(engines))
width = 0.38
b1 = ax.bar(x - width/2, long_pnl,  width, color="#16a34a", label="LONG side")
b2 = ax.bar(x + width/2, short_pnl, width, color="#dc2626", label="SHORT side")
ax.bar_label(b1, fmt="Rs %+d", padding=3, fontsize=10)
ax.bar_label(b2, fmt="Rs %+d", padding=-15, fontsize=10, color="white", fontweight="bold")
ax.axhline(0, color="#374151", linewidth=0.8)
ax.set_xticks(x); ax.set_xticklabels(engines, fontsize=11)
ax.set_ylabel("P&L (Rs)")
ax.set_title("LONG vs SHORT P&L — SHORTs Bled in +0.63% Nifty Tape", pad=12)
ax.legend(loc="upper right")

# Annotation
ax.annotate("Net P&L would be 2x higher\nwithout the SHORT bleed",
            xy=(2 + width/2, -765), xytext=(1.5, -1700),
            fontsize=9, color="#7c2d12",
            arrowprops=dict(arrowstyle="->", color="#7c2d12", lw=1.2),
            ha="center")
plt.tight_layout()
plt.savefig(OUT / "chart4_long_vs_short_pnl.png", dpi=150, bbox_inches="tight")
plt.close()

# ---- Chart 5: 04-22 baseline vs 04-27 today ----
fig, ax = plt.subplots(figsize=(9, 5))
baseline = [44612, 61284, 61552]
today    = [737, 880, 435]
x = np.arange(len(engines))
width = 0.38
b1 = ax.bar(x - width/2, baseline, width, color="#16a34a", label="04-22 (Elite, 92% WR)")
b2 = ax.bar(x + width/2, today,    width, color="#dc2626", label="04-27 (Worst, 47% WR)")
ax.bar_label(b1, fmt="Rs %d", padding=3, fontsize=9)
ax.bar_label(b2, fmt="Rs %d", padding=3, fontsize=9)
ax.set_xticks(x); ax.set_xticklabels(engines, fontsize=11)
ax.set_ylabel("Realized P&L (Rs)")
ax.set_title("Elite Day (04-22) vs Worst Day (04-27) — 98% Drop", pad=12)
ax.legend(loc="upper right")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{int(y/1000)}K" if y >= 1000 else f"{int(y)}"))

# Annotate the gap
for i, (b, t) in enumerate(zip(baseline, today)):
    drop = (1 - t/b) * 100
    ax.text(i, b + 2500, f"-{drop:.1f}%", ha="center", fontsize=11, color="#7c2d12", fontweight="bold")
plt.tight_layout()
plt.savefig(OUT / "chart5_baseline_vs_today.png", dpi=150, bbox_inches="tight")
plt.close()

print("All 5 charts written to", OUT)
for p in sorted(OUT.glob("*.png")):
    print(" -", p.name, p.stat().st_size, "bytes")
