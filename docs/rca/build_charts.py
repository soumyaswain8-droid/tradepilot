"""Generate RCA charts for 2026-04-30 VEDL demerger incident."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "charts"
OUT.mkdir(parents=True, exist_ok=True)

# Brand palette
NAVY = "#1e1b4b"
INDIGO = "#4f46e5"
GREEN = "#16a34a"
RED = "#dc2626"
AMBER = "#f59e0b"
SLATE = "#475569"
BG = "#ffffff"

plt.rcParams.update({
    "font.family": "Helvetica Neue",
    "axes.edgecolor": "#cbd5e1",
    "axes.labelcolor": "#1e293b",
    "xtick.color": "#475569",
    "ytick.color": "#475569",
    "axes.titleweight": "bold",
    "axes.titlesize": 14,
})

# ---------- Chart 1: Reported vs Adjusted P&L per variant ----------
variants = ["v4", "v5", "v5_classic", "v5_6", "v5_7", "v5_8", "v6"]
reported = [-32543, -16734, -14640, -13221, -15080, -11327, -15136]  # from user's table
adjusted = [-13203, -2211, -2000, -1000, -1000, -4870, -1000]

x = np.arange(len(variants))
w = 0.38

fig, ax = plt.subplots(figsize=(11, 5.2), dpi=150)
b1 = ax.bar(x - w/2, reported, w, label="As reported (with VEDL)", color=RED, edgecolor="#7f1d1d", linewidth=0.5)
b2 = ax.bar(x + w/2, adjusted, w, label="Adjusted (VEDL stripped)", color=AMBER, edgecolor="#92400e", linewidth=0.5)

ax.axhline(0, color="#1e293b", linewidth=1)
ax.set_xticks(x)
ax.set_xticklabels(variants, fontsize=11)
ax.set_ylabel("Net P&L (Rs)", fontsize=12)
ax.set_title("2026-04-30 P&L by Variant — Reported vs VEDL-Adjusted", pad=14)
ax.legend(loc="lower right", framealpha=0.95)
ax.grid(axis="y", linestyle="--", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

for bars, vals in [(b1, reported), (b2, adjusted)]:
    for bar, v in zip(bars, vals):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h - 1500 if h < 0 else h + 500,
                f"{v/1000:+.1f}K", ha="center", va="top" if h < 0 else "bottom",
                fontsize=8.5, color="#1e293b", fontweight="bold")

plt.tight_layout()
plt.savefig(OUT / "01_pnl_comparison.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

# ---------- Chart 2: VEDL price collapse (the fictitious -64%) ----------
fig, ax = plt.subplots(figsize=(11, 4.8), dpi=150)
times = ["Apr 28\nClose", "Apr 29\nClose", "Apr 30\n09:09\n(entry)", "Apr 30\n09:15", "Apr 30\n10:00", "Apr 30\n13:00", "Apr 30\nClose"]
price = [770.20, 773.60, 773.60, 312.0, 285.5, 278.2, 277.0]

ax.plot(range(len(times)), price, color=NAVY, linewidth=2.4, marker="o", markersize=9,
        markerfacecolor=NAVY, markeredgecolor="white", markeredgewidth=1.5)
ax.fill_between(range(len(times)), price, 250, color=NAVY, alpha=0.08)

# Highlight entry & ex-date drop
ax.axvspan(1.5, 2.5, color=GREEN, alpha=0.12, label="Engines entered LONG @ 773.6")
ax.axvspan(2.5, 3.5, color=RED, alpha=0.15, label="Demerger ex-date opens (-64% fictitious)")

# Annotations
ax.annotate("Entry @ Rs 773.60\n(09:09:51, all 7 engines)",
            xy=(2, 773.6), xytext=(0.4, 600),
            arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.4),
            fontsize=10, color=GREEN, fontweight="bold")
ax.annotate("Ex-demerger open Rs ~312\n(value moved to 4 demerged ISINs)",
            xy=(3, 312), xytext=(3.4, 500),
            arrowprops=dict(arrowstyle="->", color=RED, lw=1.4),
            fontsize=10, color=RED, fontweight="bold")
ax.annotate("EOD Rs 277\n(SL hit on every engine)",
            xy=(6, 277), xytext=(4.8, 430),
            arrowprops=dict(arrowstyle="->", color=SLATE, lw=1.4),
            fontsize=10, color=SLATE, fontweight="bold")

ax.set_xticks(range(len(times)))
ax.set_xticklabels(times, fontsize=9.5)
ax.set_ylabel("VEDL Price (Rs)", fontsize=12)
ax.set_title("VEDL — The 'Loss' That Wasn't (1:1 Demerger ex-date)", pad=14)
ax.set_ylim(220, 850)
ax.legend(loc="upper right", framealpha=0.95, fontsize=9.5)
ax.grid(axis="y", linestyle="--", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(OUT / "02_vedl_price.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

# ---------- Chart 3: VEDL impact share — donut ----------
fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=150)
sizes = [93571, 24429]
labels = ["VEDL fictitious loss\n(corp action)", "Real strategy losses\n(other 6 stocks)"]
colors = [RED, SLATE]
wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct="%1.0f%%",
       startangle=90, wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
       textprops=dict(fontsize=11, color="#1e293b"))
for at in autotexts:
    at.set_color("white")
    at.set_fontweight("bold")
    at.set_fontsize(13)
ax.text(0, 0.05, "Rs 1.18L", ha="center", va="center", fontsize=22, fontweight="bold", color=NAVY)
ax.text(0, -0.15, "total reported loss", ha="center", va="center", fontsize=10, color=SLATE)
ax.set_title("Where Today's 'Loss' Came From (across all 7 engines)", pad=18)
plt.tight_layout()
plt.savefig(OUT / "03_loss_share.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

# ---------- Chart 4: Risk-cap ladder — shows the gap ----------
fig, ax = plt.subplots(figsize=(11, 5), dpi=150)

caps = [
    ("Per-trade SL\n(missing)",            None,  "MISSING — only v5_2 has Rs 5K cap", RED),
    ("Per-position daily\n(missing)",       None,  "MISSING — no per-stock daily cap", RED),
    ("SWING pool daily\n(missing)",         None,  "daily=None in POOL_LIMITS", RED),
    ("INTRADAY pool daily",                10000, "Rs 10K (2% of Rs 5L pool)", AMBER),
    ("Portfolio daily\n(too coarse)",      50000, "Rs 50K (1% of Rs 50L) — VEDL never close", AMBER),
    ("SWING pool weekly",                 150000, "Rs 1.5L (3% of Rs 50L)", GREEN),
    ("Portfolio monthly",                 350000, "Rs 3.5L (7% of Rs 50L)", GREEN),
]

actual_loss = 14039
y = np.arange(len(caps))
labels = [c[0] for c in caps]
vals = [c[1] if c[1] is not None else 0 for c in caps]
notes = [c[2] for c in caps]
colors_ = [c[3] for c in caps]

bars = ax.barh(y, vals, color=colors_, edgecolor="#0f172a", linewidth=0.4, alpha=0.85)
ax.axvline(actual_loss, color=NAVY, linestyle="--", linewidth=2, label=f"Actual VEDL loss = Rs {actual_loss:,}")

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=10)
ax.invert_yaxis()
ax.set_xlabel("Cap threshold (Rs)", fontsize=11)
ax.set_title("Risk-Cap Ladder — Why No Guard Triggered Today", pad=14)
ax.set_xlim(0, 380000)
ax.legend(loc="lower right", framealpha=0.95)
ax.grid(axis="x", linestyle="--", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

for bar, note, v in zip(bars, notes, vals):
    if v == 0:
        ax.text(2000, bar.get_y() + bar.get_height()/2, note,
                va="center", fontsize=9, color=RED, fontweight="bold")
    else:
        ax.text(v + 5000, bar.get_y() + bar.get_height()/2, note,
                va="center", fontsize=9, color="#1e293b")

plt.tight_layout()
plt.savefig(OUT / "04_risk_caps.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

# ---------- Chart 5: Shared signal pipeline ----------
fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
ax.axis("off")

def box(x, y, w, h, text, fc, tc="white"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                       facecolor=fc, edgecolor="#0f172a", linewidth=1.2)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=10.5, color=tc, fontweight="bold")

def arrow(x1, y1, x2, y2, color="#475569"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.6))

# Source layer
box(0.5, 4.2, 2.4, 0.9, "stock_universe.py\n(VEDL in NIFTY_METAL)", SLATE)
box(0.5, 2.9, 2.4, 0.9, "data_engine.py\n(no corp-action filter)", SLATE)

# Scorer
box(4.0, 3.55, 2.6, 1.05, "v4.composite_scorer\nscore_all_stocks()", INDIGO)

# Variants
variant_boxes = [
    (8.0, 5.6, "v4 paper-trade", "#7c3aed"),
    (8.0, 4.7, "v5 / v5_2 / v5_3", "#7c3aed"),
    (8.0, 3.8, "v5_6 / v5_7", "#7c3aed"),
    (8.0, 2.9, "v5_8 (slot patch)", "#a855f7"),
    (8.0, 2.0, "v6 (direct v4)", "#a855f7"),
]
for vx, vy, vt, vc in variant_boxes:
    box(vx, vy, 2.6, 0.7, vt, vc)
    arrow(6.6, 4.07, vx, vy + 0.35)

arrow(2.9, 4.65, 4.0, 4.2)
arrow(2.9, 3.35, 4.0, 3.95)

# All converge: VEDL pick
box(11.2, 3.55, 2.4, 1.05, "VEDL pick @ 09:09:51\n(all 7 engines)", RED)
for vx, vy, vt, vc in variant_boxes:
    arrow(vx + 2.6, vy + 0.35, 11.2, 4.07, color=RED)

ax.set_xlim(0, 14)
ax.set_ylim(1.7, 6.5)
ax.text(7, 6.2, "Shared Signal Pipeline — Why All 7 Engines Picked VEDL at the Same Tick",
        ha="center", fontsize=13, fontweight="bold", color=NAVY)
plt.tight_layout()
plt.savefig(OUT / "05_signal_pipeline.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

# ---------- Chart 6: SIDEWAYS regime LONG bias ----------
fig, ax = plt.subplots(figsize=(11, 4.8), dpi=150)
configs = ["v5_6\n(15/5 partition\nactive)", "v5_7\n(15/5 partition\nactive)", "v5_8\n(20/20 OVERRIDDEN)", "v6\n(no partition,\nv4 absolute thresholds)"]
longs = [18, 23, 28, 17]
shorts = [1, 1, 0, 0]
expected_long = [15, 15, 15, 15]

x = np.arange(len(configs))
w = 0.27
ax.bar(x - w, expected_long, w, label="Expected LONG cap (15)", color="#94a3b8", edgecolor="#475569")
ax.bar(x, longs, w, label="Actual LONGs", color=GREEN, edgecolor="#14532d")
ax.bar(x + w, shorts, w, label="Actual SHORTs", color=RED, edgecolor="#7f1d1d")

ax.set_xticks(x)
ax.set_xticklabels(configs, fontsize=10)
ax.set_ylabel("Trades placed today", fontsize=11)
ax.set_title("SIDEWAYS Regime — LONG/SHORT Trade Counts vs Expected Cap", pad=14)
ax.legend(loc="upper left", framealpha=0.95)
ax.grid(axis="y", linestyle="--", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

for i, (l, s) in enumerate(zip(longs, shorts)):
    ax.text(i, l + 0.6, str(l), ha="center", fontsize=10, fontweight="bold", color=GREEN)
    ax.text(i + w, s + 0.6, str(s), ha="center", fontsize=10, fontweight="bold", color=RED)

plt.tight_layout()
plt.savefig(OUT / "06_regime_bias.png", dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()

print("Generated:", sorted(p.name for p in OUT.glob("*.png")))
