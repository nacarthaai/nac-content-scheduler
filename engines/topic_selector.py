"""
TopicSelector — Weekday-based content schedule for NacArtha.

Mon / Tue / Wed  →  NacArtha bot updates & live trading recap  (brand building, 3/7 ≈ 43%)
Thu / Fri        →  Trending finance news                       (current events,  2/7 ≈ 29%)
Sat              →  Weekly bot performance review               (educational,     1/7 ≈ 14%)
Sun              →  Educational depth content                   (educational,     1/7 ≈ 14%)
"""
import logging
import os
from datetime import date

import requests

log = logging.getLogger("topic_selector")

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")

# ── Mon/Tue/Wed: NacArtha Bot Brand & Update Topics ───────────────────────────
# Performance, transparency, decisions, brand building.
# Tuesday always uses live Alpaca data (daily_recap). Mon/Wed rotate these.
BOT_BRAND_TOPICS = [
    {"id": "bot_today_signals",     "title": "The Signals My Bot Fired Today — And What It Decided"},
    {"id": "bot_position_update",   "title": "My Current Open Positions — Why I Entered Each One"},
    {"id": "bot_refused_trade",     "title": "The Trade My Bot Refused Today — Risk Management in Action"},
    {"id": "bot_win_loss_update",   "title": "My Bot's Win/Loss This Month — Honest, Unfiltered Numbers"},
    {"id": "bot_how_decides",       "title": "How I Decide Whether to Trade — My Signal Scoring System"},
    {"id": "bot_momentum_today",    "title": "Momentum Signals I'm Watching Right Now"},
    {"id": "bot_risk_in_action",    "title": "How My 2% Risk Rule Saved Me From a Bad Trade Today"},
    {"id": "bot_paper_progress",    "title": "Paper Trading Progress Update — Week by Week Breakdown"},
    {"id": "bot_500_scan",          "title": "I Scanned 500 Stocks This Morning — Here's What I Found"},
    {"id": "bot_forex_update",      "title": "My Forex Bot's Session Results — What the Algorithm Saw"},
    {"id": "bot_live_transition",   "title": "When My Bot Goes Live — What Has to Be True First"},
    {"id": "bot_stops_triggered",   "title": "Stop Losses That Triggered This Week — What They Protected"},
    {"id": "bot_position_sizing",   "title": "How I Calculate Exactly How Much to Buy — Real Numbers"},
    {"id": "bot_drawdown_check",    "title": "My Drawdown This Month — How I Track and Control It"},
    {"id": "bot_scan_universe",     "title": "How I Built My 500-Stock Universe and Why These Stocks"},
]

# ── Sun: Educational Depth Topics (framed through the bot's lens) ─────────────
# Deep content — what the bot uses, how it works, the math behind it.
EDUCATIONAL_TOPICS = [
    # Strategies
    {"id": "edu_momentum",          "title": "Momentum Strategy: The Core Algorithm Inside My Bot"},
    {"id": "edu_mean_reversion",    "title": "Mean Reversion: How I Fade Overreactions for Profit"},
    {"id": "edu_breakout",          "title": "Breakout Detection: How My Bot Catches Big Moves Early"},
    {"id": "edu_trend_follow",      "title": "Trend Following: The Strategy That Needs No Prediction"},
    {"id": "edu_pairs_trading",     "title": "Pairs Trading: Two Stocks, One Market-Neutral Signal"},
    # Coding
    {"id": "edu_rsi_code",          "title": "How to Calculate RSI in Python — Exactly How My Bot Does It"},
    {"id": "edu_pandas_signals",    "title": "Pandas Rolling Windows: How I Compute Every Signal"},
    {"id": "edu_backtesting",       "title": "How I Backtest My Strategy Before Risking Real Money"},
    {"id": "edu_alpaca_api",        "title": "Alpaca API Tutorial: How My Bot Places Orders in Python"},
    {"id": "edu_asyncio",           "title": "Asyncio in Trading Bots: Why Async Makes Everything Better"},
    {"id": "edu_yfinance",          "title": "Getting Clean Stock Data With yfinance — My Data Pipeline"},
    # Quant / Stats
    {"id": "edu_sharpe",            "title": "Sharpe Ratio: The Only Performance Metric That Matters"},
    {"id": "edu_drawdown",          "title": "Max Drawdown: How I Measure and Limit My Worst Days"},
    {"id": "edu_kelly",             "title": "Kelly Criterion: The Formula My Bot Uses for Position Sizing"},
    {"id": "edu_expected_value",    "title": "Expected Value: The Math Behind Every Trade My Bot Takes"},
    {"id": "edu_monte_carlo",       "title": "Monte Carlo Simulation: How I Stress-Test My Strategy"},
    {"id": "edu_zscore",            "title": "Z-Score: How I Identify Statistically Extreme Price Moves"},
    # Indicators
    {"id": "edu_rsi_use",           "title": "RSI — How My Bot Uses It (Not How Most Retail Traders Do)"},
    {"id": "edu_macd",              "title": "MACD Deep Dive: The Signal My Bot Watches Every Day"},
    {"id": "edu_bollinger",         "title": "Bollinger Band Squeeze: The Setup My Bot Scans for Daily"},
    {"id": "edu_vwap",              "title": "VWAP: The Institutional Level That Anchors My Intraday Bot"},
    {"id": "edu_atr_stops",         "title": "ATR: How My Bot Sizes Every Stop Loss Using Volatility"},
    {"id": "edu_adx",               "title": "ADX: How I Measure Trend Strength Before Any Entry"},
    # Building
    {"id": "edu_architecture",      "title": "Inside My Architecture: How All the Bot's Parts Connect"},
    {"id": "edu_risk_system",       "title": "My Risk Management System: Built In, Not Bolted On"},
    {"id": "edu_deploy_cloud",      "title": "Deploying a Trading Bot 24/7 — My Railway Cloud Setup"},
    {"id": "edu_signal_engine",     "title": "Building a Signal Engine From Scratch: My Exact Process"},
]


class TopicSelector:

    def select(self, force_type: str = "") -> dict:
        today   = date.today()
        weekday = today.weekday()   # 0=Mon … 6=Sun
        day     = today.timetuple().tm_yday  # for within-category cycling

        # ── Determine type ────────────────────────────────────────────────────
        if force_type:
            t = force_type
        elif weekday == 1:          # Tuesday → always live daily recap
            t = "daily_recap"
        elif weekday in (0, 2):     # Mon, Wed → bot brand/update
            t = "bot"
        elif weekday in (3, 4):     # Thu, Fri → trending news
            t = "news"
        elif weekday == 5:          # Saturday → weekly performance review
            t = "weekly_recap"
        else:                       # Sunday → educational depth
            t = "educational"

        # ── Resolve topic ─────────────────────────────────────────────────────
        if t == "daily_recap":
            log.info("Topic type: DAILY_RECAP — live bot performance today")
            return {"id": "daily_recap", "title": "What My Trading Bot Did Today — Live Results", "type": "daily_recap"}

        if t == "weekly_recap":
            log.info("Topic type: WEEKLY_RECAP — weekly bot performance review")
            return {"id": "weekly_recap", "title": "NacArtha Bot This Week — Full Performance Review", "type": "weekly_recap"}

        if t == "bot":
            topic = dict(BOT_BRAND_TOPICS[day % len(BOT_BRAND_TOPICS)], type="bot")
            log.info(f"Topic type: BOT — {topic['title']}")
            return topic

        if t == "news":
            topic = self._news_topic(day)
            if topic:
                log.info(f"Topic type: NEWS — {topic['title']}")
                return topic
            log.warning("NewsAPI unavailable — falling back to bot brand topic")
            topic = dict(BOT_BRAND_TOPICS[day % len(BOT_BRAND_TOPICS)], type="bot")
            return topic

        # educational (Sunday)
        topic = dict(EDUCATIONAL_TOPICS[day % len(EDUCATIONAL_TOPICS)], type="educational")
        log.info(f"Topic type: EDUCATIONAL — {topic['title']}")
        return topic

    def _news_topic(self, day: int) -> dict:
        if not NEWSAPI_KEY:
            return None
        try:
            r = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "category": "business",
                    "language": "en",
                    "pageSize": 10,
                    "apiKey":   NEWSAPI_KEY,
                },
                timeout=15,
            )
            r.raise_for_status()
            articles = [a for a in r.json().get("articles", []) if a.get("title") and a.get("description")]
            if not articles:
                return None
            article = articles[day % len(articles)]
            return {
                "id":             f"news_{day}",
                "title":          article.get("title", ""),
                "type":           "news",
                "news_headline":  article.get("title", ""),
                "news_summary":   article.get("description", ""),
                "news_source":    article.get("source", {}).get("name", ""),
            }
        except Exception as e:
            log.warning(f"NewsAPI error: {e}")
            return None
