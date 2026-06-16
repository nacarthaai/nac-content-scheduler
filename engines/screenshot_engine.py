"""
ScreenshotEngine — renders dark-theme data cards from live bot data.

Produces PNG assets for illustrated scenes in the video pipeline:
  - signal_card: top scanner signals (ticker, score, RSI, EMA)
  - trade_card:  paper trade log (entry, exit, P&L, win/loss)
  - equity_curve: portfolio value over time

All cards use a terminal-dark aesthetic (black bg, green/red/gold text)
to match the NacArtha brand and prove authenticity with real bot data.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np

log = logging.getLogger("screenshot_engine")

# ── Brand palette ────────────────────────────────────────────────────────────
_BG        = "#0A0A0A"
_PANEL     = "#111111"
_BORDER    = "#1E1E1E"
_GOLD      = "#C9A84C"
_GREEN     = "#00C853"
_RED       = "#FF1744"
_WHITE     = "#E8E8E8"
_GREY      = "#555555"
_MONO      = "DejaVu Sans Mono"
_SANS      = "DejaVu Sans"

_OUT_DIR   = Path(__file__).parent.parent / "output" / "screenshots"


def _stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _save(fig: plt.Figure, name: str) -> Path:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{name}_{_stamp()}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    log.info(f"Screenshot saved → {path.name}")
    return path


# ── Public API ────────────────────────────────────────────────────────────────

def render_signal_card(
    signals: list[dict],
    title: str = "SIGNAL SCANNER",
    subtitle: str = "Top signals this session",
    out_path: Optional[Path] = None,
) -> Path:
    """
    signals: list of dicts with keys: ticker, score, rsi, ema_align, strategy, action
    e.g. [{"ticker": "NVDA", "score": 87, "rsi": 42.1, "ema_align": True, "strategy": "momentum", "action": "BUY"}]
    """
    n = min(len(signals), 8)
    fig_h = max(4.0, 1.0 + n * 0.7)
    fig, ax = plt.subplots(figsize=(12, fig_h), facecolor=_BG)
    ax.set_facecolor(_BG)
    ax.axis("off")

    # Header
    fig.text(0.04, 0.94, "NacArtha AI", fontsize=10, color=_GOLD,
             fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
    fig.text(0.04, 0.88, title, fontsize=18, color=_WHITE,
             fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
    fig.text(0.04, 0.82, subtitle, fontsize=10, color=_GREY,
             fontfamily=_MONO, transform=fig.transFigure)

    # Separator
    line = plt.Line2D([0.04, 0.96], [0.79, 0.79], transform=fig.transFigure,
                      color=_GOLD, linewidth=0.8, alpha=0.5)
    fig.add_artist(line)

    # Column headers
    cols   = ["TICKER", "SCORE", "RSI", "EMA", "STRATEGY", "SIGNAL"]
    xs     = [0.04, 0.18, 0.30, 0.42, 0.54, 0.82]
    y_hdr  = 0.74
    for x, col in zip(xs, cols):
        fig.text(x, y_hdr, col, fontsize=8, color=_GREY,
                 fontfamily=_MONO, transform=fig.transFigure)

    # Rows
    row_h = 0.10
    for i, sig in enumerate(signals[:n]):
        y = y_hdr - (i + 1) * row_h
        if y < 0.05:
            break

        ticker   = sig.get("ticker", "---")
        score    = sig.get("score", 0)
        rsi      = sig.get("rsi", 0.0)
        ema_align = sig.get("ema_align", False)
        strategy = sig.get("strategy", "---")
        action   = sig.get("action", "---").upper()

        score_color = _GREEN if score >= 75 else (_GOLD if score >= 50 else _RED)
        action_color = _GREEN if "BUY" in action else (_RED if "SELL" in action else _GREY)
        ema_str  = "✓ ALIGNED" if ema_align else "✗ FLAT"
        ema_color = _GREEN if ema_align else _GREY

        # Row background
        rect = mpatches.FancyBboxPatch(
            (0.03, y - 0.02), 0.94, row_h - 0.01,
            boxstyle="round,pad=0.005", linewidth=0,
            facecolor=_PANEL, transform=fig.transFigure, zorder=0,
        )
        fig.add_artist(rect)

        fig.text(xs[0], y, ticker,          fontsize=11, color=_WHITE,    fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
        fig.text(xs[1], y, str(score),      fontsize=11, color=score_color, fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
        fig.text(xs[2], y, f"{rsi:.1f}",   fontsize=11, color=_WHITE,    fontfamily=_MONO, transform=fig.transFigure)
        fig.text(xs[3], y, ema_str,         fontsize=9,  color=ema_color,  fontfamily=_MONO, transform=fig.transFigure)
        fig.text(xs[4], y, strategy[:14],   fontsize=9,  color=_GREY,     fontfamily=_MONO, transform=fig.transFigure)

        # Action badge
        badge = mpatches.FancyBboxPatch(
            (xs[5] - 0.005, y - 0.015), 0.12, 0.055,
            boxstyle="round,pad=0.005", linewidth=1,
            edgecolor=action_color, facecolor=_BG,
            transform=fig.transFigure, zorder=1,
        )
        fig.add_artist(badge)
        fig.text(xs[5] + 0.01, y, action, fontsize=9, color=action_color,
                 fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)

    # Footer
    ts = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    fig.text(0.96, 0.03, ts, fontsize=7, color=_GREY, fontfamily=_MONO,
             ha="right", transform=fig.transFigure)
    fig.text(0.04, 0.03, "Paper Trading  ·  Not Financial Advice", fontsize=7,
             color=_GREY, fontfamily=_MONO, transform=fig.transFigure)

    path = out_path or _save(fig, "signal_card")
    if out_path:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        log.info(f"Screenshot saved → {out_path.name}")
    return path


def render_trade_card(
    trades: list[dict],
    title: str = "PAPER TRADES",
    subtitle: str = "Today's bot activity",
    out_path: Optional[Path] = None,
) -> Path:
    """
    trades: list of dicts with keys: ticker, side, entry, exit, pnl, pnl_pct, status
    e.g. [{"ticker": "AAPL", "side": "LONG", "entry": 189.50, "exit": 193.20,
            "pnl": 3.70, "pnl_pct": 1.95, "status": "CLOSED"}]
    """
    n = min(len(trades), 6)
    fig_h = max(4.0, 1.2 + n * 0.8)
    fig, ax = plt.subplots(figsize=(12, fig_h), facecolor=_BG)
    ax.set_facecolor(_BG)
    ax.axis("off")

    # Header
    fig.text(0.04, 0.94, "NacArtha AI", fontsize=10, color=_GOLD,
             fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
    fig.text(0.04, 0.87, title, fontsize=18, color=_WHITE,
             fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
    fig.text(0.04, 0.81, subtitle, fontsize=10, color=_GREY,
             fontfamily=_MONO, transform=fig.transFigure)

    line = plt.Line2D([0.04, 0.96], [0.78, 0.78], transform=fig.transFigure,
                      color=_GOLD, linewidth=0.8, alpha=0.5)
    fig.add_artist(line)

    # Summary stats
    wins   = sum(1 for t in trades if t.get("pnl", 0) > 0)
    losses = sum(1 for t in trades if t.get("pnl", 0) < 0)
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    pnl_color = _GREEN if total_pnl >= 0 else _RED
    pnl_sign  = "+" if total_pnl >= 0 else ""

    fig.text(0.04, 0.73, f"Wins: {wins}", fontsize=10, color=_GREEN, fontfamily=_MONO, transform=fig.transFigure)
    fig.text(0.18, 0.73, f"Losses: {losses}", fontsize=10, color=_RED, fontfamily=_MONO, transform=fig.transFigure)
    fig.text(0.36, 0.73, f"Total P&L: {pnl_sign}${total_pnl:.2f}", fontsize=10,
             color=pnl_color, fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)

    # Column headers
    cols = ["TICKER", "SIDE", "ENTRY", "EXIT", "P&L", "P&L %", "STATUS"]
    xs   = [0.04, 0.17, 0.28, 0.40, 0.52, 0.64, 0.78]
    y_hdr = 0.66
    for x, col in zip(xs, cols):
        fig.text(x, y_hdr, col, fontsize=8, color=_GREY,
                 fontfamily=_MONO, transform=fig.transFigure)

    row_h = 0.11
    for i, trade in enumerate(trades[:n]):
        y = y_hdr - (i + 1) * row_h
        if y < 0.05:
            break

        pnl      = trade.get("pnl", 0)
        pnl_pct  = trade.get("pnl_pct", 0.0)
        color    = _GREEN if pnl > 0 else (_RED if pnl < 0 else _GREY)
        sign     = "+" if pnl > 0 else ""
        status   = trade.get("status", "OPEN")

        rect = mpatches.FancyBboxPatch(
            (0.03, y - 0.025), 0.94, row_h - 0.01,
            boxstyle="round,pad=0.005", linewidth=0,
            facecolor=_PANEL, transform=fig.transFigure, zorder=0,
        )
        fig.add_artist(rect)

        fig.text(xs[0], y, trade.get("ticker", "---"), fontsize=11, color=_WHITE,
                 fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
        fig.text(xs[1], y, trade.get("side", "---"), fontsize=10, color=_GOLD,
                 fontfamily=_MONO, transform=fig.transFigure)
        fig.text(xs[2], y, f"${trade.get('entry', 0):.2f}", fontsize=10, color=_WHITE,
                 fontfamily=_MONO, transform=fig.transFigure)
        fig.text(xs[3], y, f"${trade.get('exit', 0):.2f}" if trade.get("exit") else "OPEN",
                 fontsize=10, color=_WHITE, fontfamily=_MONO, transform=fig.transFigure)
        fig.text(xs[4], y, f"{sign}${pnl:.2f}", fontsize=11, color=color,
                 fontfamily=_MONO, fontweight="bold", transform=fig.transFigure)
        fig.text(xs[5], y, f"{sign}{pnl_pct:.1f}%", fontsize=10, color=color,
                 fontfamily=_MONO, transform=fig.transFigure)
        fig.text(xs[6], y, status, fontsize=9, color=_GREY,
                 fontfamily=_MONO, transform=fig.transFigure)

    ts = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    fig.text(0.96, 0.03, ts, fontsize=7, color=_GREY, fontfamily=_MONO,
             ha="right", transform=fig.transFigure)
    fig.text(0.04, 0.03, "Paper Trading  ·  Not Financial Advice", fontsize=7,
             color=_GREY, fontfamily=_MONO, transform=fig.transFigure)

    path = out_path or _save(fig, "trade_card")
    if out_path:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        log.info(f"Screenshot saved → {out_path.name}")
    return path


def render_equity_curve(
    equity_values: list[float],
    labels: Optional[list[str]] = None,
    title: str = "PORTFOLIO EQUITY",
    subtitle: str = "Paper trading performance",
    out_path: Optional[Path] = None,
) -> Path:
    """
    equity_values: list of portfolio values over time (e.g., daily closes)
    labels: optional x-axis labels (dates or session numbers)
    """
    fig, ax = plt.subplots(figsize=(12, 5), facecolor=_BG)
    ax.set_facecolor(_BG)

    xs = np.arange(len(equity_values))
    ys = np.array(equity_values, dtype=float)

    start_val = ys[0] if len(ys) > 0 else 0
    final_val = ys[-1] if len(ys) > 0 else 0
    pnl       = final_val - start_val
    pnl_pct   = (pnl / start_val * 100) if start_val else 0
    line_color = _GREEN if pnl >= 0 else _RED

    # Fill under curve
    ax.fill_between(xs, ys, start_val, alpha=0.15, color=line_color)

    # Main equity line
    ax.plot(xs, ys, color=line_color, linewidth=2.0, zorder=3)

    # Start/end markers
    ax.scatter([0], [ys[0]], color=_GOLD, s=60, zorder=5)
    ax.scatter([xs[-1]], [ys[-1]], color=line_color, s=80, zorder=5)

    # Baseline
    ax.axhline(y=start_val, color=_GREY, linewidth=0.8, linestyle="--", alpha=0.5)

    # Axes styling
    ax.set_facecolor(_BG)
    for spine in ax.spines.values():
        spine.set_color(_BORDER)
    ax.tick_params(colors=_GREY, labelsize=8)
    ax.yaxis.set_tick_params(labelcolor=_GREY)
    ax.xaxis.set_tick_params(labelcolor=_GREY)
    if labels and len(labels) == len(ys):
        step = max(1, len(labels) // 8)
        ax.set_xticks(xs[::step])
        ax.set_xticklabels(labels[::step], rotation=30, ha="right",
                           fontsize=7, color=_GREY, fontfamily=_MONO)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.grid(color=_BORDER, linewidth=0.5, alpha=0.6)

    # Header text inside figure
    sign = "+" if pnl >= 0 else ""
    ax.set_title(
        f"NacArtha AI  ·  {title}  ·  {sign}${pnl:,.2f}  ({sign}{pnl_pct:.2f}%)",
        color=_WHITE, fontsize=13, fontfamily=_MONO, fontweight="bold", pad=12,
    )
    ax.set_xlabel(subtitle, color=_GREY, fontsize=8, fontfamily=_MONO)

    fig.text(0.96, 0.02, "Paper Trading  ·  Not Financial Advice",
             fontsize=7, color=_GREY, fontfamily=_MONO,
             ha="right", transform=fig.transFigure)

    fig.tight_layout()
    path = out_path or _save(fig, "equity_curve")
    if out_path:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        log.info(f"Screenshot saved → {out_path.name}")
    return path


# ── Quick smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    render_signal_card([
        {"ticker": "NVDA",  "score": 87, "rsi": 41.2, "ema_align": True,  "strategy": "momentum",     "action": "BUY"},
        {"ticker": "TSLA",  "score": 79, "rsi": 38.5, "ema_align": True,  "strategy": "breakout",     "action": "BUY"},
        {"ticker": "AAPL",  "score": 62, "rsi": 55.1, "ema_align": False, "strategy": "mean_revert",  "action": "WATCH"},
        {"ticker": "SPY",   "score": 48, "rsi": 61.3, "ema_align": False, "strategy": "trend_follow", "action": "SKIP"},
        {"ticker": "AMZN",  "score": 91, "rsi": 35.8, "ema_align": True,  "strategy": "momentum",     "action": "BUY"},
    ], subtitle="500 stocks scanned  ·  5 qualified")

    render_trade_card([
        {"ticker": "NVDA", "side": "LONG", "entry": 892.10, "exit": 908.40, "pnl": 16.30, "pnl_pct": 1.83, "status": "CLOSED"},
        {"ticker": "TSLA", "side": "LONG", "entry": 182.50, "exit": 179.20, "pnl": -3.30, "pnl_pct": -1.81, "status": "CLOSED"},
        {"ticker": "AMZN", "side": "LONG", "entry": 184.00, "exit": None,   "pnl": 0,     "pnl_pct": 0,     "status": "OPEN"},
    ], subtitle="Today's paper trades  ·  3 positions")

    render_equity_curve(
        [100000, 100820, 101200, 100900, 101500, 102300, 101800, 102900, 103400, 104100],
        labels=["Jun 6","Jun 7","Jun 8","Jun 9","Jun 10","Jun 11","Jun 12","Jun 13","Jun 14","Jun 15"],
        subtitle="10-day paper trading  ·  Week 1",
    )

    print("Screenshots saved to output/screenshots/")
