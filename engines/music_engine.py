"""
MusicEngine — Selects background music by topic mood.

5 Kevin MacLeod tracks (CC BY 3.0 — incompetech.com) matched to emotional tone.
Tracks download on first use; falls back to existing music.mp3 if unavailable.
"""
import logging
from pathlib import Path

import requests

log = logging.getLogger("music_engine")

MUSIC_DIR = Path(__file__).parent.parent / "assets" / "music"

# Map topic_type (not topic_id) → mood, since topic IDs are too granular
TOPIC_TYPE_MOODS = {
    "bot":          "intrigue",    # brand/update — mysterious, confident
    "daily_recap":  "tension",     # today's trades — stakes, focus
    "weekly_recap": "revelation",  # weekly review — stepping back, perspective
    "news":         "urgency",     # breaking events — fast, reactive
    "educational":  "revelation",  # depth content — clarity, insight
}

# Legacy topic_id map kept for fallback (old content IDs)
TOPIC_MOODS = {
    "market_manipulation": "dread",
    "crypto_crash":        "tension",
    "fed_rate_hike":       "urgency",
    "inflation_trap":      "dread",
    "short_squeeze":       "urgency",
    "liquidity_crisis":    "dread",
    "options_expiry":      "tension",
    "insider_trading":     "intrigue",
    "retail_trap":         "tension",
    "wealth_gap":          "revelation",
    "passive_income_myth": "revelation",
    "debt_trap":           "dread",
    "bear_market_survival":"urgency",
    "black_swan":          "dread",
    "dollar_collapse":     "dread",
    "ipo_scam":            "tension",
    "gold_vs_bitcoin":     "intrigue",
    "pension_crisis":      "urgency",
    "bank_run":            "dread",
    "recession_signs":     "tension",
}

# Kevin MacLeod — CC BY 3.0 (incompetech.com)
# Attribution auto-appended to all descriptions in orchestrator.
TRACKS = {
    "dread":      ("Anguish",            "https://archive.org/download/Incompetech/mp3-royaltyfree/Anguish.mp3"),
    "tension":    ("Cipher",             "https://archive.org/download/Incompetech/mp3-royaltyfree/Cipher.mp3"),
    "urgency":    ("Volatile Reaction",  "https://archive.org/download/Incompetech/mp3-royaltyfree/Volatile%20Reaction.mp3"),
    "intrigue":   ("Perspectives",       "https://archive.org/download/Incompetech/mp3-royaltyfree/Perspectives.mp3"),
    "revelation": ("Crossing the Divide","https://archive.org/download/Incompetech/mp3-royaltyfree/Crossing%20the%20Divide.mp3"),
}


class MusicEngine:

    def select(self, topic_id: str, topic_type: str = "") -> Path:
        mood = (
            TOPIC_TYPE_MOODS.get(topic_type)
            or TOPIC_MOODS.get(topic_id)
            or "tension"
        )
        return self._get(mood)

    def _get(self, mood: str) -> Path:
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        out = MUSIC_DIR / f"{mood}.mp3"
        if out.exists():
            return out

        track_name, url = TRACKS[mood]
        log.info(f"Downloading music [{mood}]: {track_name}")
        try:
            r = requests.get(url, timeout=60, stream=True)
            r.raise_for_status()
            out.write_bytes(r.content)
            log.info(f"  Saved → {out.name} ({out.stat().st_size // 1024} KB)")
            return out
        except Exception as e:
            log.warning(f"  Music download failed [{mood}]: {e}")
            # Fallbacks in order
            for fallback in [MUSIC_DIR / "dread.mp3",
                             Path(__file__).parent.parent / "assets" / "music.mp3"]:
                if fallback.exists():
                    log.info(f"  Using fallback: {fallback.name}")
                    return fallback
            return None
