import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output"

# ── API Keys ──────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY      = os.environ.get("OPENAI_API_KEY", "")
D_ID_API_KEY        = os.environ.get("D_ID_API_KEY", "")
AI4BHARAT_API_KEY   = os.environ.get("AI4BHARAT_API_KEY", "")
DEEPL_API_KEY       = os.environ.get("DEEPL_API_KEY", "")

# ── Trading Bot (Railway) ─────────────────────────────────────
RAILWAY_URL         = os.environ.get("RAILWAY_URL", "https://nacartha-trading-system-production.up.railway.app")
RAILWAY_TOKEN       = os.environ.get("RAILWAY_TOKEN", "")

# ── YouTube ───────────────────────────────────────────────────
YOUTUBE_CLIENT_ID       = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET   = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

# Per-channel refresh tokens — one OAuth token per YouTube channel
YOUTUBE_REFRESH_TOKENS = {
    "en": os.environ.get("YOUTUBE_REFRESH_TOKEN_EN", ""),
    "hi": os.environ.get("YOUTUBE_REFRESH_TOKEN_HI", ""),
    "te": os.environ.get("YOUTUBE_REFRESH_TOKEN_TE", ""),
}

# ── Telegram ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Claude model ─────────────────────────────────────────────
CLAUDE_MODEL = "claude-opus-4-7"

# ── Video settings ────────────────────────────────────────────
VIDEO_WIDTH   = 1920
VIDEO_HEIGHT  = 1080
VIDEO_FPS     = 30
CHART_DPI     = 150

# ── Target languages ─────────────────────────────────────────
LANGUAGES = {
    "en": {"name": "English", "deepl_code": "EN"},
    "hi": {"name": "Hindi",   "deepl_code": None},
    "te": {"name": "Telugu",  "deepl_code": None},
}

# ── Content categories ────────────────────────────────────────
CHANNEL_NAME     = "NacArtha"
CHANNEL_HANDLE   = "@NacArtha"
CHANNEL_TAGLINE  = "Real AI Trading Bot. Real Data. Real Results."
