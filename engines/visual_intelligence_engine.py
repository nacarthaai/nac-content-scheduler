"""
VisualIntelligenceEngine — NAC Memory Rule implementation.

For every scene narration:
  1. Extract stock tickers → yfinance chart
  2. Extract company names → Pexels company/industry images
  3. Detect strategy patterns → Pexels or generated diagram
  4. News context → NewsAPI article image

Returns a prioritised list of image/video paths for the scene assembler.
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("visual_intelligence")

# ── Stock ticker pattern ────────────────────────────────────────────────────────
_TICKER_RE = re.compile(
    r'\b([A-Z]{2,5})\b(?=\s*(?:stock|shares|broke|surged|dropped|rose|fell|'
    r'earnings|revenue|gap|signal|position|trade|chart|moved|up|down|%|'
    r'resistance|support|breakout|oversold|overbought))',
)
_KNOWN_TICKERS = {
    "NVDA","AAPL","MSFT","TSLA","AMZN","GOOGL","GOOG","META","AMD","INTC",
    "MU","QCOM","AVGO","ARM","SMCI","PLTR","SOFI","RIVN","LCID","NIO",
    "BABA","JD","PDD","MELI","SQ","PYPL","SHOP","COIN","HOOD","RBLX",
    "UBER","LYFT","ABNB","DASH","SNAP","PINS","TWTR","SPOT","NFLX","DIS",
    "SPY","QQQ","IWM","GLD","SLV","TLT","XLK","XLF","XLE","XBI","ARKK",
    "JPM","GS","MS","BAC","C","WFC","BRK","V","MA","AXP",
    "XOM","CVX","COP","OXY","SLB","HAL",
    "LMT","RTX","NOC","BA","GE","CAT","DE",
    "QBTS","POET","IONQ","RGTI","QUBT",
}

# ── Strategy / pattern keywords → search terms ─────────────────────────────────
_STRATEGY_KEYWORDS = {
    "bull flag":        "bull flag chart pattern trading",
    "bear flag":        "bear flag chart pattern trading",
    "cup and handle":   "cup and handle chart pattern",
    "head and shoulders": "head and shoulders reversal pattern chart",
    "double top":       "double top chart pattern resistance",
    "double bottom":    "double bottom chart pattern support",
    "rsi":              "RSI indicator oversold overbought chart",
    "macd":             "MACD indicator crossover chart",
    "ema":              "EMA exponential moving average chart",
    "vwap":             "VWAP volume weighted average price chart",
    "support":          "support resistance level chart trading",
    "resistance":       "support resistance level chart trading",
    "breakout":         "breakout chart pattern stock market",
    "momentum":         "momentum trading strategy chart",
    "gap up":           "gap up stock chart premarket",
    "gap down":         "gap down stock chart premarket",
    "short squeeze":    "short squeeze stock chart gamma",
    "options":          "options chain trading puts calls",
    "algo":             "algorithmic trading computer code terminal",
    "machine learning": "machine learning algorithm data visualization",
    "earnings":         "earnings report financial results quarterly",
    "fed":              "federal reserve interest rate policy",
    "inflation":        "inflation economy consumer price index chart",
    "recession":        "recession economy stock market decline",
    "semiconductor":    "semiconductor chip manufacturing cleanroom",
    "ai":               "artificial intelligence data center server rack",
    "crypto":           "cryptocurrency bitcoin blockchain digital",
    "forex":            "forex currency trading terminal global",
}

# ── Company name → search query ────────────────────────────────────────────────
_COMPANY_IMAGES = {
    "nvidia":   "NVIDIA GPU chip semiconductor",
    "apple":    "Apple iPhone product store",
    "microsoft":"Microsoft office software cloud",
    "tesla":    "Tesla electric car factory",
    "amazon":   "Amazon warehouse fulfillment logistics",
    "google":   "Google Alphabet campus technology",
    "meta":     "Meta Facebook social media campus",
    "amd":      "AMD processor chip semiconductor",
    "intel":    "Intel semiconductor chip fabrication",
    "micron":   "Micron memory chip semiconductor",
    "qualcomm": "Qualcomm mobile chip wireless",
    "broadcom": "Broadcom semiconductor networking",
    "palantir": "Palantir data analytics software",
    "sofi":     "SoFi digital banking fintech",
    "rivian":   "Rivian electric truck vehicle",
    "coinbase": "Coinbase cryptocurrency exchange",
    "shopify":  "Shopify ecommerce merchant store",
    "netflix":  "Netflix streaming entertainment",
    "disney":   "Disney media entertainment park",
    "jpmorgan": "JPMorgan Chase bank financial",
    "goldman":  "Goldman Sachs investment bank",
}


class VisualIntelligenceEngine:

    def __init__(self):
        self._pexels_key = os.environ.get("PEXELS_API_KEY", "")
        self._news_key   = os.environ.get("NEWS_API_KEY", "")
        self._cache: dict[str, list[Path]] = {}

    def get_scene_visuals(
        self,
        narration: str,
        scene_type: str,
        out_dir: Path,
        scene_id: str,
        news_headline: str = "",
        max_images: int = 3,
    ) -> list[Path]:
        """
        Return ordered list of visual paths for this scene.
        Priority: stock chart > news image > strategy/company image > generic
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        visuals: list[Path] = []
        text = (narration or "").lower()

        # 1. Stock chart — highest priority
        tickers = self._extract_tickers(narration)
        for ticker in tickers[:2]:
            chart = self._yfinance_chart(ticker, out_dir, scene_id)
            if chart:
                visuals.append(chart)
                if len(visuals) >= max_images:
                    return visuals

        # 2. News image
        if news_headline and len(visuals) < max_images:
            img = self._news_image(news_headline, out_dir, scene_id)
            if img:
                visuals.append(img)

        # 3. Strategy / pattern image
        if len(visuals) < max_images:
            for keyword, query in _STRATEGY_KEYWORDS.items():
                if keyword in text:
                    img = self._pexels_image(query, out_dir, f"{scene_id}_strat_{keyword[:6]}")
                    if img:
                        visuals.append(img)
                    break

        # 4. Company image
        if len(visuals) < max_images:
            for company, query in _COMPANY_IMAGES.items():
                if company in text:
                    img = self._pexels_image(query, out_dir, f"{scene_id}_co_{company[:6]}")
                    if img:
                        visuals.append(img)
                    break

        # 5. Scene-type generic fallback
        if not visuals:
            fallback_query = {
                "nac_face":   "trading terminal bloomberg financial dark",
                "illustrated":"stock market financial trading technology",
                "student":    "student learning whiteboard classroom",
                "news":       "financial news broadcast screen",
            }.get(scene_type, "financial market trading technology")
            img = self._pexels_image(fallback_query, out_dir, f"{scene_id}_fallback")
            if img:
                visuals.append(img)

        return visuals

    # ── Ticker extraction ──────────────────────────────────────────────────────

    def _extract_tickers(self, text: str) -> list[str]:
        found = []
        # Known tickers first (most reliable)
        for t in _KNOWN_TICKERS:
            if re.search(rf'\b{t}\b', text):
                found.append(t)
        # Pattern-matched tickers
        for m in _TICKER_RE.finditer(text):
            t = m.group(1)
            if t not in found and t not in {"I","A","AT","IT","BE","AS","AN","OR","IN","IS","TO"}:
                found.append(t)
        return found[:3]

    # ── yfinance chart ─────────────────────────────────────────────────────────

    def _yfinance_chart(self, ticker: str, out_dir: Path, scene_id: str) -> Optional[Path]:
        out = out_dir / f"{scene_id}_chart_{ticker}.png"
        if out.exists():
            return out
        try:
            import yfinance as yf
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            df = yf.download(ticker, period="30d", interval="1d", progress=False)
            if df is None or len(df) < 5:
                return None

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7),
                                            gridspec_kw={"height_ratios": [3, 1]},
                                            facecolor="#0a0a12")
            fig.suptitle(ticker, color="#f0b429", fontsize=22, fontweight="bold", y=0.98)

            close = df["Close"].squeeze()
            vol   = df["Volume"].squeeze()
            color = "#10b981" if close.iloc[-1] >= close.iloc[0] else "#ef4444"

            # Price line
            ax1.set_facecolor("#0a0a12")
            ax1.plot(df.index, close, color=color, linewidth=2.5)
            ax1.fill_between(df.index, close, close.min(), alpha=0.15, color=color)
            ax1.set_ylabel("Price ($)", color="#9ca3af", fontsize=11)
            ax1.tick_params(colors="#9ca3af")
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
            ax1.spines[:].set_color("#1f2937")
            ax1.grid(color="#1f2937", linestyle="--", alpha=0.5)

            # Price change annotation
            pct = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100
            ax1.annotate(f"${close.iloc[-1]:.2f}  {pct:+.1f}%",
                         xy=(df.index[-1], close.iloc[-1]),
                         color=color, fontsize=13, fontweight="bold",
                         xytext=(-80, 15), textcoords="offset points")

            # Volume bars
            ax2.set_facecolor("#0a0a12")
            bar_colors = [color if c >= o else "#ef4444"
                          for c, o in zip(df["Close"].squeeze(), df["Open"].squeeze())]
            ax2.bar(df.index, vol, color=bar_colors, alpha=0.7, width=0.8)
            ax2.set_ylabel("Volume", color="#9ca3af", fontsize=10)
            ax2.tick_params(colors="#9ca3af")
            ax2.spines[:].set_color("#1f2937")
            ax2.grid(color="#1f2937", linestyle="--", alpha=0.3)

            plt.tight_layout(rect=[0, 0, 1, 0.97])
            plt.savefig(str(out), dpi=150, bbox_inches="tight",
                        facecolor="#0a0a12", edgecolor="none")
            plt.close(fig)
            log.info(f"  Chart [{ticker}] → {out.name}")
            return out

        except Exception as e:
            log.warning(f"  Chart [{ticker}] failed: {e}")
            return None

    # ── Pexels image ───────────────────────────────────────────────────────────

    def _pexels_image(self, query: str, out_dir: Path, label: str) -> Optional[Path]:
        if not self._pexels_key:
            return None
        cache_key = query[:40]
        out = out_dir / f"{label}.jpg"
        if out.exists():
            return out
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self._pexels_key},
                params={"query": query, "per_page": 5, "orientation": "landscape"},
                timeout=15,
            )
            photos = r.json().get("photos", [])
            if not photos:
                return None
            url = photos[0]["src"]["large2x"]
            img_r = requests.get(url, timeout=30)
            img_r.raise_for_status()
            out.write_bytes(img_r.content)
            log.info(f"  Pexels [{query[:30]}] → {out.name}")
            time.sleep(0.3)
            return out
        except Exception as e:
            log.warning(f"  Pexels [{query[:30]}] failed: {e}")
            return None

    # ── News image ─────────────────────────────────────────────────────────────

    def _news_image(self, headline: str, out_dir: Path, scene_id: str) -> Optional[Path]:
        if not self._news_key:
            return None
        out = out_dir / f"{scene_id}_news.jpg"
        if out.exists():
            return out
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={"q": headline[:80], "pageSize": 3, "language": "en",
                        "apiKey": self._news_key},
                timeout=15,
            )
            articles = r.json().get("articles", [])
            for a in articles:
                url = a.get("urlToImage")
                if url and url.startswith("http"):
                    img_r = requests.get(url, timeout=20)
                    if img_r.status_code == 200:
                        out.write_bytes(img_r.content)
                        log.info(f"  News image → {out.name}")
                        return out
        except Exception as e:
            log.warning(f"  News image failed: {e}")
        return None
