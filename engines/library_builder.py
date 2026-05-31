"""
LibraryBuilder — run ONCE to generate the HeyGen + Veo clip library.

Usage:
  python -m engines.library_builder --heygen    # build HeyGen clips only
  python -m engines.library_builder --veo       # build Veo background clips only
  python -m engines.library_builder             # build both

Outputs to assets/library/ and updates assets/library/library_index.json.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

import requests

from engines.veo_engine import VeoEngine

log = logging.getLogger("library_builder")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

LIBRARY_DIR  = Path(__file__).parent.parent / "assets" / "library"
INDEX_PATH   = LIBRARY_DIR / "library_index.json"

# ── HeyGen clip definitions ───────────────────────────────────────────────────
# Each entry: id, character, category, emotion, text
# character: nac | student
# category: hook | confident | explain | reveal | cta | react | question | normal

NAC_CLIPS = [
    # Hook (6 clips)
    {"id": "nac_hook_001", "category": "hook", "emotion": "confidence", "text": "Hey. Nac here. Welcome to my trading world."},
    {"id": "nac_hook_002", "category": "hook", "emotion": "excitement", "text": "The algorithm just made a decision you need to see."},
    {"id": "nac_hook_003", "category": "hook", "emotion": "tension",    "text": "Three signals. One trade. Let me show you exactly why."},
    {"id": "nac_hook_004", "category": "hook", "emotion": "confidence", "text": "I trade every day. Today was different."},
    {"id": "nac_hook_005", "category": "hook", "emotion": "excitement", "text": "The market moved. My algorithm was ready."},
    {"id": "nac_hook_006", "category": "hook", "emotion": "tension",    "text": "I want to show you something most traders never see."},

    # Confident (8 clips)
    {"id": "nac_conf_001", "category": "confident", "emotion": "confidence", "text": "Here is exactly what the data showed."},
    {"id": "nac_conf_002", "category": "confident", "emotion": "clarity",    "text": "The momentum score crossed seventy-five. That is the trigger."},
    {"id": "nac_conf_003", "category": "confident", "emotion": "focus",      "text": "Risk management blocked it. And that was the right call."},
    {"id": "nac_conf_004", "category": "confident", "emotion": "clarity",    "text": "The algorithm does not guess. It calculates."},
    {"id": "nac_conf_005", "category": "confident", "emotion": "confidence", "text": "Every trade has a reason. Let me show you this one."},
    {"id": "nac_conf_006", "category": "confident", "emotion": "insight",    "text": "Win rate means nothing without proper risk sizing."},
    {"id": "nac_conf_007", "category": "confident", "emotion": "focus",      "text": "Position size was reduced. The system protected capital first."},
    {"id": "nac_conf_008", "category": "confident", "emotion": "confidence", "text": "Drawdown controlled. That is the real measure of any strategy."},

    # Explain (10 clips)
    {"id": "nac_exp_001",  "category": "explain", "emotion": "clarity",  "text": "Let me explain exactly how this works."},
    {"id": "nac_exp_002",  "category": "explain", "emotion": "focus",    "text": "The formula is simpler than you think. Watch."},
    {"id": "nac_exp_003",  "category": "explain", "emotion": "insight",  "text": "This is what most traders completely miss."},
    {"id": "nac_exp_004",  "category": "explain", "emotion": "clarity",  "text": "The bot uses RSI fourteen, EMA nine and twenty-one, and volume surge."},
    {"id": "nac_exp_005",  "category": "explain", "emotion": "insight",  "text": "A two percent maximum risk per trade. That is non-negotiable."},
    {"id": "nac_exp_006",  "category": "explain", "emotion": "clarity",  "text": "The momentum score is a composite of four indicators."},
    {"id": "nac_exp_007",  "category": "explain", "emotion": "focus",    "text": "When volume spikes before price, that is institutional activity."},
    {"id": "nac_exp_008",  "category": "explain", "emotion": "insight",  "text": "Volatility is not the enemy. Unmanaged volatility is."},
    {"id": "nac_exp_009",  "category": "explain", "emotion": "clarity",  "text": "A good stop loss is not just a number. It is a plan."},
    {"id": "nac_exp_010",  "category": "explain", "emotion": "focus",    "text": "Backtesting tells you what worked. Forward testing tells you what works now."},

    # Reveal (6 clips)
    {"id": "nac_rev_001",  "category": "reveal", "emotion": "insight",    "text": "And that number? It changed everything."},
    {"id": "nac_rev_002",  "category": "reveal", "emotion": "tension",    "text": "This is the exact moment the system flagged the risk."},
    {"id": "nac_rev_003",  "category": "reveal", "emotion": "excitement", "text": "The signal was right. The timing was not. Here is why."},
    {"id": "nac_rev_004",  "category": "reveal", "emotion": "insight",    "text": "The P and L curve tells the whole story."},
    {"id": "nac_rev_005",  "category": "reveal", "emotion": "insight",    "text": "The equity curve does not lie."},
    {"id": "nac_rev_006",  "category": "reveal", "emotion": "tension",    "text": "This is the exact moment risk management made the difference."},

    # React (6 clips)
    {"id": "nac_react_001", "category": "react", "emotion": "focus",    "text": "When news like this hits, the algorithm responds in seconds."},
    {"id": "nac_react_002", "category": "react", "emotion": "clarity",  "text": "This changes the momentum landscape completely."},
    {"id": "nac_react_003", "category": "react", "emotion": "tension",  "text": "Most algo systems would have missed this. Mine did not."},
    {"id": "nac_react_004", "category": "react", "emotion": "focus",    "text": "The Fed announcement hit. The bot was already positioned."},
    {"id": "nac_react_005", "category": "react", "emotion": "insight",  "text": "Earnings beat. The algorithm caught the pre-market signal."},
    {"id": "nac_react_006", "category": "react", "emotion": "tension",  "text": "Market opened gap down. The bot skipped three signals. That was correct."},

    # CTA (4 clips)
    {"id": "nac_cta_001",  "category": "cta", "emotion": "confidence", "text": "Subscribe to NacArtha. I trade every day. You should know what I know. Follow the algorithm. See you tomorrow."},
    {"id": "nac_cta_002",  "category": "cta", "emotion": "confidence", "text": "Follow NacArtha. The algorithm runs twenty-four seven. So should your knowledge."},
    {"id": "nac_cta_003",  "category": "cta", "emotion": "confidence", "text": "That is all for today. Follow NacArtha for the next trade."},
    {"id": "nac_cta_004",  "category": "cta", "emotion": "excitement", "text": "The algorithm runs every market day. Be here when it matters."},

    # Normal (10 clips)
    {"id": "nac_norm_001", "category": "normal", "emotion": "clarity",  "text": "Here is what happened next."},
    {"id": "nac_norm_002", "category": "normal", "emotion": "focus",    "text": "Let me pull up the chart."},
    {"id": "nac_norm_003", "category": "normal", "emotion": "insight",  "text": "The pattern was clear in hindsight."},
    {"id": "nac_norm_004", "category": "normal", "emotion": "focus",    "text": "Watch what happens next."},
    {"id": "nac_norm_005", "category": "normal", "emotion": "clarity",  "text": "Now let me show you the result."},
    {"id": "nac_norm_006", "category": "normal", "emotion": "focus",    "text": "This part is important. Pay attention."},
    {"id": "nac_norm_007", "category": "normal", "emotion": "insight",  "text": "The data makes it clear."},
    {"id": "nac_norm_008", "category": "normal", "emotion": "clarity",  "text": "One more thing before we wrap up."},
    {"id": "nac_norm_009", "category": "normal", "emotion": "focus",    "text": "Let me break this down step by step."},
    {"id": "nac_norm_010", "category": "normal", "emotion": "clarity",  "text": "The setup was there. Here is what the bot saw."},
]

STUDENT_CLIPS = [
    # Questions (12 clips)
    {"id": "stu_q_001",  "category": "question", "emotion": "curiosity", "text": "But why did the bot skip that trade?"},
    {"id": "stu_q_002",  "category": "question", "emotion": "curiosity", "text": "What does the RSI number actually mean?"},
    {"id": "stu_q_003",  "category": "question", "emotion": "curiosity", "text": "How does the algorithm decide when to sell?"},
    {"id": "stu_q_004",  "category": "question", "emotion": "curiosity", "text": "Wait. So the bot refused the profit on purpose?"},
    {"id": "stu_q_005",  "category": "question", "emotion": "curiosity", "text": "What is a momentum score exactly?"},
    {"id": "stu_q_006",  "category": "question", "emotion": "curiosity", "text": "How is this different from regular technical analysis?"},
    {"id": "stu_q_007",  "category": "question", "emotion": "curiosity", "text": "So the bot never second-guesses itself?"},
    {"id": "stu_q_008",  "category": "question", "emotion": "curiosity", "text": "What happens when two signals contradict each other?"},
    {"id": "stu_q_009",  "category": "question", "emotion": "curiosity", "text": "Does the bot ever hold positions overnight?"},
    {"id": "stu_q_010",  "category": "question", "emotion": "curiosity", "text": "How does news affect the algorithm's decisions?"},
    {"id": "stu_q_011",  "category": "question", "emotion": "curiosity", "text": "Can retail traders replicate this kind of system?"},
    {"id": "stu_q_012",  "category": "question", "emotion": "curiosity", "text": "Why do most algo traders fail?"},

    # Reactions (8 clips)
    {"id": "stu_react_001", "category": "normal", "emotion": "focus",      "text": "Okay. That makes sense now."},
    {"id": "stu_react_002", "category": "normal", "emotion": "excitement", "text": "So the system knew before the price moved?"},
    {"id": "stu_react_003", "category": "normal", "emotion": "insight",    "text": "I never thought about it that way."},
    {"id": "stu_react_004", "category": "normal", "emotion": "clarity",    "text": "That is actually simpler than I expected."},
    {"id": "stu_react_005", "category": "normal", "emotion": "insight",    "text": "So consistency matters more than any single trade."},
    {"id": "stu_react_006", "category": "normal", "emotion": "excitement", "text": "I had no idea algorithms worked at this speed."},
    {"id": "stu_react_007", "category": "normal", "emotion": "insight",    "text": "So discipline is built directly into the code itself."},
    {"id": "stu_react_008", "category": "normal", "emotion": "insight",    "text": "So every loss is a calculated decision, not a failure."},
]

# ── Veo background clip definitions ──────────────────────────────────────────
# These are ANIMATED video clips (5s), not static images
VEO_BACKGROUNDS = [
    # Trading room
    {"id": "veo_trade_001", "category": "trading", "prompt": "Cinematic slow push-in toward Bloomberg terminal array, gold and electric-blue market data cascading on screens, dark luxury hedge-fund trading room, city skyline glowing through floor-to-ceiling glass at night, photorealistic, 4K"},
    {"id": "veo_trade_002", "category": "trading", "prompt": "Close-up of trading screens with live candlestick charts ticking in real time, cursor moving over red and green candles, warm gold light reflecting on glass, dark professional trading room"},
    {"id": "veo_trade_003", "category": "trading", "prompt": "Slow aerial tilt-down revealing dark luxury trading command center, multiple glowing screens with financial data, city lights visible through panoramic windows at night, cinematic"},
    {"id": "veo_trade_004", "category": "trading", "prompt": "Hands typing rapidly on mechanical keyboard, Bloomberg terminal glow reflecting off fingertips, dark trading desk, gold and electric-blue ambient light, slow cinematic dolly"},
    {"id": "veo_trade_005", "category": "trading", "prompt": "Financial data visualization: numbers and charts flowing across multiple screens in a dark room, electric blue and gold light pulses, cinematic camera drift, professional trading environment"},
    {"id": "veo_trade_006", "category": "trading", "prompt": "Slow pan across empty luxury trading room at night, three curved monitors showing live market data in gold and blue, city skyline shimmering outside glass walls, atmospheric fog, cinematic"},
    {"id": "veo_trade_007", "category": "trading", "prompt": "Extreme close-up of stock ticker symbols scrolling across a dark screen, red and green numbers updating in real time, shallow depth of field, gold light bokeh in background"},

    # Classroom / Educational
    {"id": "veo_class_001", "category": "classroom", "prompt": "Slow zoom into a glass whiteboard with RSI and EMA financial formulas written in marker, dark modern meeting room, focused overhead spotlight, cinematic depth of field"},
    {"id": "veo_class_002", "category": "classroom", "prompt": "Overhead shot slowly rotating over a trading desk with open notebook, printed candlestick charts, laptop showing Python code, warm desk lamp, cinematic"},
    {"id": "veo_class_003", "category": "classroom", "prompt": "Dark luxury seminar room, empty glass table with Bloomberg terminal visible in background glowing blue and gold, slow dolly forward, cinematic atmosphere"},
    {"id": "veo_class_004", "category": "classroom", "prompt": "Close-up of a hand drawing a stock chart on glass whiteboard with marker, formula being written step by step, dark academic atmosphere, warm focused light"},
    {"id": "veo_class_005", "category": "classroom", "prompt": "Laptop screen showing algorithmic trading Python code with green syntax highlighting, fingers scrolling through code, dark desk, shallow depth of field, cinematic"},

    # Trading (2 more = 9 total)
    {"id": "veo_trade_008", "category": "trading", "prompt": "Slow tilt-up from dark trading desk to panoramic window revealing glowing city skyline at night, Bloomberg terminal reflected in glass, cinematic atmospheric haze"},
    {"id": "veo_trade_009", "category": "trading", "prompt": "Close-up of candlestick chart on curved monitor, green candles forming a breakout pattern, cursor hovering, electric blue and gold ambient light, shallow depth of field"},

    # Classroom (1 more = 6 total)
    {"id": "veo_class_006", "category": "classroom", "prompt": "Slow push-in toward a dark minimalist desk with a single open trading book, gold desk lamp casting warm light, blurred Bloomberg terminal in background, cinematic and focused"},

    # News (2 more = 5 total)
    {"id": "veo_news_001", "category": "news", "prompt": "Financial news broadcast studio, multiple screens showing market data and news headlines, red breaking news banner, dark professional environment, slow cinematic pan"},
    {"id": "veo_news_002", "category": "news", "prompt": "Newspaper front page with bold financial headline being revealed by camera pull-back, dramatic directional spotlight, dark background, cinematic high contrast"},
    {"id": "veo_news_003", "category": "news", "prompt": "Global stock market visualization: world map with data overlays, stock indices ticking, currency pairs moving, dark atmospheric room, slow cinematic drift"},
    {"id": "veo_news_004", "category": "news", "prompt": "Slow dolly through dark office corridor toward wall of TV screens showing live financial news broadcasts, red tickers scrolling, cinematic depth of field"},
    {"id": "veo_news_005", "category": "news", "prompt": "Close-up of smartphone screen showing stock alert notification, blurred trading room in background with glowing monitors, cinematic shallow focus, gold and blue ambient light"},
]


class LibraryBuilder:

    def __init__(self):
        self._heygen_key  = os.environ.get("HEYGEN_API_KEY", "")
        self._nac_avatar  = os.environ.get("HEYGEN_AVATAR_ID_NAC", "")
        self._stu_avatar  = os.environ.get("HEYGEN_AVATAR_ID_STUDENT", "")
        self._stu_avatar2 = os.environ.get("HEYGEN_AVATAR_ID_STUDENT_2", "")
        self._nac_voice   = os.environ.get("HEYGEN_VOICE_ID_EN", "")
        self._veo         = VeoEngine()
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

    # ── HeyGen clips ─────────────────────────────────────────────────────────

    def build_heygen(self, force: bool = False):
        if not self._heygen_key:
            log.error("HEYGEN_API_KEY not set")
            return

        index = _load_index()
        existing_ids = {c["id"] for c in index}

        # Alternate between two student avatars across 9 clips for visual variety
        stu_avatars = [a for a in [self._stu_avatar, self._stu_avatar2] if a]
        student_entries = [
            (c, "student", stu_avatars[i % len(stu_avatars)] if stu_avatars else "")
            for i, c in enumerate(STUDENT_CLIPS)
        ]

        all_clips = (
            [(c, "nac", self._nac_avatar) for c in NAC_CLIPS] +
            student_entries
        )

        for clip_def, character, avatar_id in all_clips:
            cid = clip_def["id"]
            if cid in existing_ids and not force:
                log.info(f"  [{cid}] already in library — skip")
                continue
            if not avatar_id:
                log.warning(f"  [{cid}] no avatar ID for {character} — set HEYGEN_AVATAR_ID_{'NAC' if character=='nac' else 'STUDENT'}")
                continue

            out_dir = LIBRARY_DIR / "heygen" / character
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{cid}.mp4"

            log.info(f"  Generating [{cid}]: {clip_def['text'][:50]}…")
            path = self._generate_heygen_clip(clip_def["text"], avatar_id, out_path)
            if not path:
                continue

            entry = {
                "id":        cid,
                "type":      "heygen",
                "character": character,
                "category":  clip_def["category"],
                "emotion":   clip_def["emotion"],
                "text":      clip_def["text"],
                "path":      str(out_path.relative_to(LIBRARY_DIR)),
            }
            index = [c for c in index if c["id"] != cid]
            index.append(entry)
            _save_index(index)
            log.info(f"  [{cid}] saved ✓")
            time.sleep(2)  # rate limit buffer

    def _generate_heygen_clip(self, text: str, avatar_id: str, out_path: Path) -> Path | None:
        try:
            # Submit video generation
            r = requests.post(
                "https://api.heygen.com/v2/video/generate",
                headers={"X-Api-Key": self._heygen_key, "Content-Type": "application/json"},
                json={
                    "video_inputs": [{
                        "character": {
                            "type":         "avatar",
                            "avatar_id":    avatar_id,
                            "avatar_style": "normal",
                        },
                        "voice": {
                            "type":       "text",
                            "input_text": text,
                            "voice_id":   self._nac_voice,
                            "speed":      1.0,
                        },
                        "background": {
                            "type":  "color",
                            "value": "#0a0a0f",
                        },
                    }],
                    "dimension": {"width": 1280, "height": 720},
                },
                timeout=30,
            )
            if r.status_code not in (200, 201):
                log.warning(f"  HeyGen submit {r.status_code}: {r.text[:200]}")
                return None

            video_id = r.json().get("data", {}).get("video_id")
            if not video_id:
                log.warning(f"  No video_id in HeyGen response: {r.json()}")
                return None

            log.info(f"  HeyGen job {video_id} — polling…")
            return self._poll_heygen(video_id, out_path)

        except Exception as e:
            log.error(f"  HeyGen generate error: {e}", exc_info=True)
            return None

    def _poll_heygen(self, video_id: str, out_path: Path, max_wait: int = 600) -> Path | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(10)
            try:
                r = requests.get(
                    f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                    headers={"X-Api-Key": self._heygen_key},
                    timeout=20,
                )
                data   = r.json().get("data", {})
                status = data.get("status", "")
                if status == "completed":
                    video_url = data.get("video_url")
                    if not video_url:
                        log.warning("  HeyGen: no video_url in completed response")
                        return None
                    vr = requests.get(video_url, timeout=120)
                    vr.raise_for_status()
                    out_path.write_bytes(vr.content)
                    size_mb = out_path.stat().st_size / (1024 * 1024)
                    log.info(f"  HeyGen downloaded → {out_path.name} ({size_mb:.1f} MB)")
                    return out_path
                if status == "failed":
                    log.warning(f"  HeyGen failed: {data.get('error', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  HeyGen [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  HeyGen poll error: {e}")
        log.warning(f"  HeyGen timeout ({max_wait}s)")
        return None

    # ── Veo background clips ──────────────────────────────────────────────────

    def build_veo(self, force: bool = False):
        if not self._veo.is_ready():
            log.error("Veo not ready — check GOOGLE_API_KEY and google-genai install")
            return

        index = _load_index()
        existing_ids = {c["id"] for c in index}

        for bg in VEO_BACKGROUNDS:
            bid = bg["id"]
            if bid in existing_ids and not force:
                log.info(f"  [{bid}] already in library — skip")
                continue

            out_dir = LIBRARY_DIR / "veo" / bg["category"]
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{bid}.mp4"

            log.info(f"  Generating [{bid}]: {bg['prompt'][:60]}…")
            path = self._veo.generate(bg["prompt"], out_path, orientation="landscape", duration=5)
            if not path:
                log.warning(f"  [{bid}] Veo generation failed — skipping")
                continue

            entry = {
                "id":       bid,
                "type":     "veo",
                "category": bg["category"],
                "prompt":   bg["prompt"],
                "path":     str(out_path.relative_to(LIBRARY_DIR)),
            }
            index = [c for c in index if c["id"] != bid]
            index.append(entry)
            _save_index(index)
            log.info(f"  [{bid}] saved ✓")
            time.sleep(5)  # brief pause between Veo jobs


def _load_index() -> list:
    if not INDEX_PATH.exists():
        return []
    try:
        return json.loads(INDEX_PATH.read_text())
    except Exception:
        return []


def _save_index(clips: list):
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(clips, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--heygen", action="store_true", help="Build HeyGen clips only")
    parser.add_argument("--veo",    action="store_true", help="Build Veo background clips only")
    parser.add_argument("--force",  action="store_true", help="Re-generate existing clips")
    parser.add_argument("--test",   action="store_true", help="Test API connections only — no generation")
    args = parser.parse_args()

    builder = LibraryBuilder()

    if args.test:
        log.info("=== Testing API connections ===")
        # HeyGen
        if builder._heygen_key:
            r = requests.get(
                "https://api.heygen.com/v2/user/remaining_quota",
                headers={"X-Api-Key": builder._heygen_key},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                log.info(f"  HeyGen ✓  credits remaining: {data.get('remaining_quota', '?')}")
            else:
                log.error(f"  HeyGen ✗  status={r.status_code}: {r.text[:100]}")
        else:
            log.error("  HeyGen ✗  HEYGEN_API_KEY not set")

        # Avatar IDs
        log.info(f"  NAC avatar:      {'✓ set' if builder._nac_avatar  else '✗ NOT SET'}")
        log.info(f"  STUDENT avatar1: {'✓ set' if builder._stu_avatar  else '✗ NOT SET'}")
        log.info(f"  STUDENT avatar2: {'✓ set' if builder._stu_avatar2 else '✗ NOT SET'}")
        log.info(f"  Voice EN:        {'✓ set' if builder._nac_voice   else '✗ NOT SET'}")

        # Veo
        log.info(f"  Veo engine:      {'✓ ready' if builder._veo.is_ready() else '✗ NOT READY — check GOOGLE_API_KEY'}")

        log.info("=== Test complete ===")
        import sys; sys.exit(0)

    build_all = not args.heygen and not args.veo

    if args.heygen or build_all:
        log.info("=== Building HeyGen clip library ===")
        builder.build_heygen(force=args.force)

    if args.veo or build_all:
        log.info("=== Building Veo background clip library ===")
        builder.build_veo(force=args.force)

    log.info("=== Library build complete ===")
