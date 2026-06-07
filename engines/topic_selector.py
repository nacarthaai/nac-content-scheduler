"""
TopicSelector — Weekday-based content schedule for NacArtha.

80% = AI Bot Story Videos  (Mon / Tue / Wed / Thu / Fri / Sat)
20% = Educational          (Sun only)

The AI Bot is the hero. Every video answers "What did the bot do today?" — not "What happened in the market?"
"""
import logging
import os
from datetime import date

import requests

log = logging.getLogger("topic_selector")

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")

# ── Mon / Wed / Thu / Fri / Sat: AI Bot Story Topics ─────────────────────────
# Every title uses emotional outcome framing. The bot is the character.
# Pattern: "My Bot [Action]" / "The [Thing] My Bot [Did]" / "My Algorithm [Outcome]"
BOT_BRAND_TOPICS = [
    {"id": "bot_refused_trade",     "title": "The Trade My Bot Refused Today"},
    {"id": "bot_rare_signal",       "title": "My Algorithm Triggered a Rare Alert This Morning"},
    {"id": "bot_caught_breakout",   "title": "My Bot Caught This Before Everyone Else"},
    {"id": "bot_risk_saved",        "title": "My Bot's Risk System Just Saved Me From a Big Loss"},
    {"id": "bot_silent_day",        "title": "My Bot Went Silent Today — Here's What That Means"},
    {"id": "bot_wrong_call",        "title": "My Bot Got This Trade Wrong — The Full Story"},
    {"id": "bot_spotted_first",     "title": "My Algorithm Spotted This Before Wall Street Did"},
    {"id": "bot_500_one_signal",    "title": "My Bot Scanned 500 Stocks — Only One Made It Through"},
    {"id": "bot_bearish_flip",      "title": "The Day My Bot Went Bearish — What It Saw"},
    {"id": "bot_worst_day",         "title": "My Bot's Worst Day This Month — Honest Numbers"},
    {"id": "bot_ai_watching",       "title": "What My AI Is Watching Tomorrow — The Setup Is Building"},
    {"id": "bot_stop_triggered",    "title": "My Bot Triggered a Stop Loss Today — The Full Story"},
    {"id": "bot_mistake",           "title": "My Algorithm Made a Mistake. Here's What I Found."},
    {"id": "bot_big_move",          "title": "My Bot Caught a 34% Move Before It Happened"},
    {"id": "bot_forex_warning",     "title": "My Forex Bot Triggered a Warning Signal Last Night"},
    {"id": "bot_risk_rejected",     "title": "My Bot Saw the Signal — Then Risk Management Said No"},
    {"id": "bot_seven_signals",     "title": "Seven Signals This Week. My Bot Took One."},
    {"id": "bot_rare_pattern",      "title": "My Bot Caught a Pattern That Forms Once a Month"},
    {"id": "bot_live_countdown",    "title": "My Bot Is One Decision Away From Going Live"},
    {"id": "bot_cost_signal",       "title": "The Signal That Almost Cost My Bot $200"},
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

        # ── Determine type — 80% bot story, 20% educational ─────────────────
        if force_type:
            t = force_type
        elif weekday == 1:              # Tuesday → live daily recap (bot story with real data)
            t = "daily_recap"
        elif weekday == 5:              # Saturday → weekly performance review (bot story)
            t = "weekly_recap"
        elif weekday == 6:              # Sunday only → educational (20%)
            t = "educational"
        else:                           # Mon / Wed / Thu / Fri → AI bot story (80%)
            t = "bot"

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

        # educational (Sunday only)
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
