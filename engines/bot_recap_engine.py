"""
BotRecapEngine — Fetches today's trading activity from Alpaca for daily recap videos.

Pulls filled orders, open positions, and portfolio P&L directly from the broker API.
Returns a structured summary that gets injected into the Claude script prompt.
Falls back to a minimal placeholder if the API is unavailable.
"""
import logging
import os
from datetime import datetime, timezone, timedelta

import requests

log = logging.getLogger("bot_recap_engine")

NY_OFFSET = timedelta(hours=-4)  # EDT; close enough (APScheduler handles DST elsewhere)


def fetch_today_summary() -> dict:
    """
    Returns a dict describing what the bot did today:
    {
        account_equity, account_pnl_today, account_pnl_pct,
        trades: [{symbol, side, qty, price, pnl_approx}],
        open_positions: [{symbol, side, qty, unrealized_pnl_pct}],
        signals_scanned, top_winner, top_loser,
        market_summary,  # string description of broad market day
        available: bool  # False if API failed
    }
    """
    api_key    = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url   = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not api_secret:
        log.warning("ALPACA_API_KEY/SECRET not set — using placeholder recap data")
        return _placeholder()

    headers = {
        "Apca-Api-Key-Id":     api_key,
        "Apca-Api-Secret-Key": api_secret,
    }

    try:
        account   = _get(f"{base_url}/v2/account",   headers)
        positions = _get(f"{base_url}/v2/positions",  headers) or []
        orders    = _filled_orders_today(base_url, headers)
        history   = _portfolio_history_today(base_url, headers)

        equity         = float(account.get("equity",          0))
        last_equity    = float(account.get("last_equity",     equity))
        pnl_today      = round(equity - last_equity, 2)
        pnl_pct        = round((pnl_today / last_equity * 100) if last_equity else 0, 2)

        trades = []
        for o in orders:
            filled_qty   = float(o.get("filled_qty", 0))
            filled_price = float(o.get("filled_avg_price") or 0)
            trades.append({
                "symbol": o.get("symbol", ""),
                "side":   o.get("side", ""),
                "qty":    filled_qty,
                "price":  filled_price,
            })

        open_pos = []
        for p in positions:
            open_pos.append({
                "symbol":             p.get("symbol", ""),
                "side":               p.get("side", "long"),
                "qty":                float(p.get("qty", 0)),
                "unrealized_pnl":     float(p.get("unrealized_pl", 0)),
                "unrealized_pnl_pct": round(float(p.get("unrealized_plpc", 0)) * 100, 2),
            })

        # Sort positions to find top winner and loser
        sorted_pos = sorted(open_pos, key=lambda x: x["unrealized_pnl_pct"], reverse=True)
        top_winner = sorted_pos[0]  if sorted_pos else None
        top_loser  = sorted_pos[-1] if len(sorted_pos) > 1 else None

        return {
            "available":       True,
            "account_equity":  round(equity, 2),
            "pnl_today":       pnl_today,
            "pnl_pct":         pnl_pct,
            "trades_today":    len(trades),
            "trades":          trades[:10],  # cap for prompt size
            "open_positions":  len(open_pos),
            "positions":       open_pos[:8],
            "top_winner":      top_winner,
            "top_loser":       top_loser,
        }

    except Exception as e:
        log.warning(f"Alpaca recap fetch failed: {e}")
        return _placeholder()


def _get(url: str, headers: dict) -> dict:
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def _filled_orders_today(base_url: str, headers: dict) -> list:
    now_ny    = datetime.now(timezone.utc) + NY_OFFSET
    today_str = now_ny.strftime("%Y-%m-%dT00:00:00-04:00")
    try:
        r = requests.get(
            f"{base_url}/v2/orders",
            headers=headers,
            params={"status": "filled", "after": today_str, "limit": 50, "direction": "desc"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        log.warning(f"Orders fetch failed: {e}")
        return []


def _portfolio_history_today(base_url: str, headers: dict) -> dict:
    try:
        r = requests.get(
            f"{base_url}/v2/portfolio/history",
            headers=headers,
            params={"period": "1D", "timeframe": "1H"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json() or {}
    except Exception as e:
        log.warning(f"Portfolio history fetch failed: {e}")
        return {}


def fetch_week_summary() -> dict:
    """Same as fetch_today_summary but uses 1-week portfolio history."""
    api_key    = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url   = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not api_secret:
        log.warning("ALPACA_API_KEY/SECRET not set — using placeholder weekly recap")
        return _placeholder()

    headers = {
        "Apca-Api-Key-Id":     api_key,
        "Apca-Api-Secret-Key": api_secret,
    }

    try:
        account  = _get(f"{base_url}/v2/account", headers)
        positions = _get(f"{base_url}/v2/positions", headers) or []

        # 1-week filled orders
        now_ny    = datetime.now(timezone.utc) + NY_OFFSET
        week_start = (now_ny - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00-04:00")
        r = requests.get(
            f"{base_url}/v2/orders",
            headers=headers,
            params={"status": "filled", "after": week_start, "limit": 200, "direction": "asc"},
            timeout=15,
        )
        r.raise_for_status()
        orders = r.json() or []

        equity      = float(account.get("equity", 0))
        last_equity = float(account.get("last_equity", equity))
        pnl_today   = round(equity - last_equity, 2)
        pnl_pct     = round((pnl_today / last_equity * 100) if last_equity else 0, 2)

        trades = [
            {
                "symbol": o.get("symbol", ""),
                "side":   o.get("side", ""),
                "qty":    float(o.get("filled_qty", 0)),
                "price":  float(o.get("filled_avg_price") or 0),
            }
            for o in orders
        ]

        open_pos = [
            {
                "symbol":             p.get("symbol", ""),
                "side":               p.get("side", "long"),
                "qty":                float(p.get("qty", 0)),
                "unrealized_pnl":     float(p.get("unrealized_pl", 0)),
                "unrealized_pnl_pct": round(float(p.get("unrealized_plpc", 0)) * 100, 2),
            }
            for p in positions
        ]

        sorted_pos = sorted(open_pos, key=lambda x: x["unrealized_pnl_pct"], reverse=True)

        return {
            "available":      True,
            "period":         "week",
            "account_equity": round(equity, 2),
            "pnl_today":      pnl_today,
            "pnl_pct":        pnl_pct,
            "trades_today":   len(trades),
            "trades":         trades[:15],
            "open_positions": len(open_pos),
            "positions":      open_pos[:8],
            "top_winner":     sorted_pos[0]  if sorted_pos else None,
            "top_loser":      sorted_pos[-1] if len(sorted_pos) > 1 else None,
        }

    except Exception as e:
        log.warning(f"Alpaca weekly recap fetch failed: {e}")
        return _placeholder()


def _placeholder() -> dict:
    """Used when API keys are missing or unavailable — generates generic but honest content."""
    return {
        "available":      False,
        "account_equity": None,
        "pnl_today":      None,
        "pnl_pct":        None,
        "trades_today":   None,
        "trades":         [],
        "open_positions": None,
        "positions":      [],
        "top_winner":     None,
        "top_loser":      None,
    }


def format_for_prompt(summary: dict) -> str:
    """Converts the summary dict into a readable string for injection into the Claude prompt."""
    if not summary.get("available"):
        return (
            "Note: Live trading data is unavailable today. Generate a transparent recap explaining "
            "that the bot is in paper trading mode and describe the typical daily decision-making "
            "process — what signals were likely scanned, what risk rules were applied, and what "
            "the bot looks for before taking a trade. Be honest that specific numbers are not available today."
        )

    lines = [
        f"TODAY'S TRADING DATA (real data from Alpaca paper trading account):",
        f"- Portfolio equity: ${summary['account_equity']:,.2f}",
        f"- Day P&L: ${summary['pnl_today']:+.2f} ({summary['pnl_pct']:+.2f}%)",
        f"- Trades executed today: {summary['trades_today']}",
        f"- Open positions: {summary['open_positions']}",
    ]

    if summary["trades"]:
        lines.append("\nTrades taken today:")
        for t in summary["trades"]:
            lines.append(f"  {t['side'].upper()} {t['qty']} {t['symbol']} @ ${t['price']:.2f}")

    if summary["positions"]:
        lines.append("\nCurrent open positions:")
        for p in summary["positions"]:
            lines.append(
                f"  {p['symbol']} ({p['side']}) — {p['unrealized_pnl_pct']:+.2f}% unrealized"
            )

    if summary["top_winner"]:
        w = summary["top_winner"]
        lines.append(f"\nBest position today: {w['symbol']} at {w['unrealized_pnl_pct']:+.2f}%")

    if summary["top_loser"] and summary["top_loser"] != summary["top_winner"]:
        l = summary["top_loser"]
        lines.append(f"Worst position today: {l['symbol']} at {l['unrealized_pnl_pct']:+.2f}%")

    return "\n".join(lines)
