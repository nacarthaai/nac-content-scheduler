"""
ChartEngine — generates trading charts for NacArtha videos.

Sources:
  yfinance    → candlestick, volume, RSI, EMA, news market impact
  Trading API → P&L curve, equity curve, open positions, trade history

Dark NacArtha theme: black background, gold/teal candles, electric blue accents.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

log = logging.getLogger("chart_engine")

# NacArtha color palette
_BG      = "#0a0a0f"
_GRID    = "#1a1a2e"
_UP      = "#00d4aa"
_DOWN    = "#ff4757"
_GOLD    = "#ffd700"
_BLUE    = "#00b4ff"
_TEXT    = "#e8e8e8"
_MUTED   = "#888888"
_PANEL   = "#111120"

_STYLE = {
    "figure.facecolor":  _BG,
    "axes.facecolor":    _PANEL,
    "axes.edgecolor":    _GRID,
    "axes.labelcolor":   _TEXT,
    "axes.grid":         True,
    "grid.color":        _GRID,
    "grid.linewidth":    0.5,
    "xtick.color":       _MUTED,
    "ytick.color":       _MUTED,
    "text.color":        _TEXT,
    "font.family":       "monospace",
    "font.size":         11,
}


class ChartEngine:

    def candlestick(self, symbol: str, period: str = "1mo", out_path: Path = None) -> Path | None:
        """Candlestick chart with volume. period: 1d|5d|1mo|3mo|6mo|1y"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if df.empty:
                log.warning(f"  No data for {symbol}")
                return None

            out_path = out_path or Path(f"/tmp/{symbol}_candle.png")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            with plt.rc_context(_STYLE):
                fig = plt.figure(figsize=(14, 8), facecolor=_BG)
                gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1, 0], hspace=0.05)
                ax1 = fig.add_subplot(gs[0])
                ax2 = fig.add_subplot(gs[1], sharex=ax1)

                x = np.arange(len(df))
                for i, (idx, row) in enumerate(df.iterrows()):
                    color = _UP if row["Close"] >= row["Open"] else _DOWN
                    # Wick
                    ax1.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=0.8, alpha=0.7)
                    # Body
                    body_h = abs(row["Close"] - row["Open"]) or 0.01
                    body_y = min(row["Open"], row["Close"])
                    ax1.bar(i, body_h, bottom=body_y, color=color, width=0.7, alpha=0.9)

                # EMAs
                if len(df) >= 20:
                    ema20 = df["Close"].ewm(span=20).mean()
                    ax1.plot(x, ema20.values, color=_GOLD, linewidth=1.2, alpha=0.8, label="EMA20")
                if len(df) >= 50:
                    ema50 = df["Close"].ewm(span=50).mean()
                    ax1.plot(x, ema50.values, color=_BLUE, linewidth=1.2, alpha=0.8, label="EMA50")

                ax1.legend(loc="upper left", facecolor=_PANEL, edgecolor=_GRID, fontsize=9)
                ax1.set_title(f"{symbol}  ·  {period}", color=_GOLD, fontsize=14, fontweight="bold", pad=10)
                ax1.set_ylabel("Price (USD)", color=_TEXT)
                plt.setp(ax1.get_xticklabels(), visible=False)

                # Volume
                vol_colors = [_UP if df["Close"].iloc[i] >= df["Open"].iloc[i] else _DOWN for i in range(len(df))]
                ax2.bar(x, df["Volume"].values, color=vol_colors, alpha=0.6)
                ax2.set_ylabel("Volume", color=_TEXT)

                # X-axis labels — show every ~5th date
                step = max(1, len(df) // 8)
                ax2.set_xticks(x[::step])
                ax2.set_xticklabels([df.index[i].strftime("%b %d") for i in range(0, len(df), step)], rotation=30)

                _watermark(fig)
                plt.tight_layout(pad=0.5)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=_BG)
                plt.close(fig)

            log.info(f"  Chart saved → {out_path.name}")
            return out_path

        except Exception as e:
            log.error(f"  Candlestick chart failed: {e}", exc_info=True)
            return None

    def rsi_ema(self, symbol: str, period: str = "3mo", out_path: Path = None) -> Path | None:
        """Price with EMA9/21/50 + RSI(14) panel."""
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(period=period)
            if df.empty:
                return None

            out_path = out_path or Path(f"/tmp/{symbol}_rsi.png")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            close = df["Close"]
            ema9  = close.ewm(span=9).mean()
            ema21 = close.ewm(span=21).mean()
            ema50 = close.ewm(span=50).mean()

            # RSI
            delta  = close.diff()
            gain   = delta.clip(lower=0).rolling(14).mean()
            loss   = (-delta.clip(upper=0)).rolling(14).mean()
            rs     = gain / loss.replace(0, np.nan)
            rsi    = 100 - (100 / (1 + rs))

            with plt.rc_context(_STYLE):
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                                gridspec_kw={"height_ratios": [3, 1]},
                                                facecolor=_BG)
                x = np.arange(len(df))

                ax1.plot(x, close.values, color=_TEXT, linewidth=1.2, label="Price")
                ax1.plot(x, ema9.values,  color=_GOLD, linewidth=1,   label="EMA9",  alpha=0.85)
                ax1.plot(x, ema21.values, color=_BLUE, linewidth=1,   label="EMA21", alpha=0.85)
                ax1.plot(x, ema50.values, color="#ff6b6b", linewidth=1, label="EMA50", alpha=0.85)
                ax1.legend(loc="upper left", facecolor=_PANEL, edgecolor=_GRID, fontsize=9)
                ax1.set_title(f"{symbol}  ·  Price + RSI(14)", color=_GOLD, fontsize=14, fontweight="bold")
                ax1.set_ylabel("Price (USD)")

                ax2.plot(x, rsi.values, color=_BLUE, linewidth=1.2)
                ax2.axhline(70, color=_DOWN, linewidth=0.8, linestyle="--", alpha=0.7)
                ax2.axhline(30, color=_UP,   linewidth=0.8, linestyle="--", alpha=0.7)
                ax2.fill_between(x, rsi.values, 70, where=(rsi.values > 70), color=_DOWN, alpha=0.15)
                ax2.fill_between(x, rsi.values, 30, where=(rsi.values < 30), color=_UP,   alpha=0.15)
                ax2.set_ylim(0, 100)
                ax2.set_ylabel("RSI(14)")

                step = max(1, len(df) // 8)
                ax2.set_xticks(x[::step])
                ax2.set_xticklabels([df.index[i].strftime("%b %d") for i in range(0, len(df), step)], rotation=30)

                _watermark(fig)
                plt.tight_layout(pad=0.5)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=_BG)
                plt.close(fig)

            log.info(f"  RSI chart saved → {out_path.name}")
            return out_path

        except Exception as e:
            log.error(f"  RSI chart failed: {e}", exc_info=True)
            return None

    def news_impact(self, symbol: str, event_date: str, out_path: Path = None) -> Path | None:
        """Price ±10 days around a news event, with event marker."""
        try:
            import yfinance as yf
            from datetime import datetime
            ev = datetime.strptime(event_date, "%Y-%m-%d")
            start = (ev - timedelta(days=14)).strftime("%Y-%m-%d")
            end   = (ev + timedelta(days=14)).strftime("%Y-%m-%d")
            df = yf.Ticker(symbol).history(start=start, end=end)
            if df.empty:
                return None

            out_path = out_path or Path(f"/tmp/{symbol}_impact.png")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            with plt.rc_context(_STYLE):
                fig, ax = plt.subplots(figsize=(14, 6), facecolor=_BG)
                x = np.arange(len(df))
                ax.plot(x, df["Close"].values, color=_GOLD, linewidth=2)
                ax.fill_between(x, df["Close"].values, df["Close"].min(), alpha=0.08, color=_GOLD)

                # Event marker
                ev_idx = next((i for i, d in enumerate(df.index) if d.date() >= ev.date()), None)
                if ev_idx is not None:
                    ax.axvline(ev_idx, color=_DOWN, linewidth=1.5, linestyle="--", alpha=0.9)
                    ax.text(ev_idx + 0.3, df["Close"].max() * 0.98, "NEWS", color=_DOWN, fontsize=10, fontweight="bold")

                ax.set_title(f"{symbol}  ·  Market Impact — {event_date}", color=_GOLD, fontsize=14, fontweight="bold")
                ax.set_ylabel("Price (USD)")
                step = max(1, len(df) // 6)
                ax.set_xticks(x[::step])
                ax.set_xticklabels([df.index[i].strftime("%b %d") for i in range(0, len(df), step)], rotation=30)

                _watermark(fig)
                plt.tight_layout(pad=0.5)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=_BG)
                plt.close(fig)

            log.info(f"  News impact chart saved → {out_path.name}")
            return out_path

        except Exception as e:
            log.error(f"  News impact chart failed: {e}", exc_info=True)
            return None

    def pnl_curve(self, trades: list, out_path: Path = None) -> Path | None:
        """Cumulative P&L curve from bot trades. trades: [{time, pnl}]"""
        try:
            if not trades:
                return None
            out_path = out_path or Path("/tmp/pnl_curve.png")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            times  = [t.get("time", i) for i, t in enumerate(trades)]
            cumsum = np.cumsum([t.get("pnl", 0) for t in trades])

            with plt.rc_context(_STYLE):
                fig, ax = plt.subplots(figsize=(14, 6), facecolor=_BG)
                color = _UP if cumsum[-1] >= 0 else _DOWN
                ax.plot(range(len(cumsum)), cumsum, color=color, linewidth=2)
                ax.fill_between(range(len(cumsum)), cumsum, 0,
                                where=(cumsum >= 0), color=_UP, alpha=0.12)
                ax.fill_between(range(len(cumsum)), cumsum, 0,
                                where=(cumsum < 0),  color=_DOWN, alpha=0.12)
                ax.axhline(0, color=_MUTED, linewidth=0.8, linestyle="--")

                total = cumsum[-1]
                ax.set_title(f"NacArtha P&L  ·  Total: ${total:+.2f}", color=_GOLD, fontsize=14, fontweight="bold")
                ax.set_ylabel("Cumulative P&L (USD)")
                ax.set_xlabel("Trades")

                _watermark(fig)
                plt.tight_layout(pad=0.5)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=_BG)
                plt.close(fig)

            log.info(f"  P&L curve saved → {out_path.name}")
            return out_path

        except Exception as e:
            log.error(f"  P&L curve failed: {e}", exc_info=True)
            return None

    def equity_curve(self, equity_data: list, out_path: Path = None) -> Path | None:
        """Equity curve. equity_data: [{time, value}]"""
        try:
            if not equity_data:
                return None
            out_path = out_path or Path("/tmp/equity_curve.png")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            values = [d.get("value", 0) for d in equity_data]
            start  = values[0] if values[0] else 1
            pct    = [(v - start) / start * 100 for v in values]

            with plt.rc_context(_STYLE):
                fig, ax = plt.subplots(figsize=(14, 6), facecolor=_BG)
                color = _UP if pct[-1] >= 0 else _DOWN
                ax.plot(range(len(pct)), pct, color=color, linewidth=2)
                ax.fill_between(range(len(pct)), pct, 0,
                                where=(np.array(pct) >= 0), color=_UP, alpha=0.12)
                ax.fill_between(range(len(pct)), pct, 0,
                                where=(np.array(pct) < 0),  color=_DOWN, alpha=0.12)
                ax.axhline(0, color=_MUTED, linewidth=0.8, linestyle="--")

                ax.set_title(f"NacArtha Equity Curve  ·  {pct[-1]:+.2f}%", color=_GOLD, fontsize=14, fontweight="bold")
                ax.set_ylabel("Return (%)")

                _watermark(fig)
                plt.tight_layout(pad=0.5)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=_BG)
                plt.close(fig)

            log.info(f"  Equity curve saved → {out_path.name}")
            return out_path

        except Exception as e:
            log.error(f"  Equity curve failed: {e}", exc_info=True)
            return None

    def fetch_news_images(self, query: str, out_dir: Path, max_images: int = 5) -> list:
        """Download real news article images via NewsAPI. Returns list of Paths."""
        api_key = os.environ.get("NEWS_API_KEY", "")
        if not api_key:
            log.warning("  NEWS_API_KEY not set — news images skipped")
            return []

        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        try:
            import requests
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":        query,
                    "language": "en",
                    "sortBy":   "publishedAt",
                    "pageSize": max_images * 2,
                    "apiKey":   api_key,
                },
                timeout=30,
            )
            if r.status_code != 200:
                log.warning(f"  NewsAPI {r.status_code}: {r.text[:200]}")
                return []

            articles = r.json().get("articles", [])
            for i, article in enumerate(articles):
                img_url = article.get("urlToImage")
                if not img_url:
                    continue
                try:
                    img_r = requests.get(img_url, timeout=15)
                    if img_r.status_code == 200 and "image" in img_r.headers.get("content-type", ""):
                        p = out_dir / f"news_{i:02d}.jpg"
                        p.write_bytes(img_r.content)
                        paths.append(p)
                        log.info(f"  News image {i+1}: {article.get('source', {}).get('name', '?')} — {article.get('title', '')[:60]}")
                        if len(paths) >= max_images:
                            break
                except Exception:
                    continue
        except Exception as e:
            log.error(f"  News image fetch failed: {e}", exc_info=True)

        return paths


def _watermark(fig):
    fig.text(0.99, 0.01, "NACARTHA.AI", ha="right", va="bottom",
             color=_MUTED, fontsize=9, alpha=0.6, transform=fig.transFigure)
