"""
NacArtha AI Studio — Full 38-Engine Shorts Pipeline
Run: railway run --service nac-content-scheduler python content-engine/run_full_shorts_studio.py

Engines (38 total):
─── Intelligence (8) ────────────────────────────────────────────────────────────
  1. Trade Intelligence Engine   yfinance + CSV
  2. Shorts Idea Engine          Claude
  3. Research Engine             Claude + yfinance
  4. Context Engine              Claude
  5. Story Angle Engine          Claude
  6. Audience Engine             Claude
  7. Goal Engine                 Claude
  8. Viral Moment Engine         Claude
─── Writing (6) ─────────────────────────────────────────────────────────────────
  9. Hook Engine                 Claude
 10. Micro Story Engine          Claude
 11. Script Engine               Claude
 12. Fact Validation Engine      Claude
 13. Retention Engine            Claude
 14. Conversation Engine         Claude (defines NAC voice)
─── Direction (5) ───────────────────────────────────────────────────────────────
 15. Creative Director Engine    Claude
 16. Director Engine             Claude
 17. Shot Planning Engine        Claude
 18. Visual Planning Engine      Claude
 19. Asset Planning Engine       Claude
─── Production (8) ──────────────────────────────────────────────────────────────
 20. NAC Performance Engine      HeyGen library clips
 21. Student Performance Engine  HeyGen library clips
 22. AI Visual Generation Engine PAI (Cloudflare tunnel)
 23. Dashboard Engine            yfinance + matplotlib
 24. Motion Graphics Engine      Remotion (kinetic text cards)
 25. VFX Engine                  ffmpeg zoompan + vignette
 26. SFX Engine                  ffmpeg lavfi (generated tones)
 27. Music Engine                assets/music/*.mp3
─── Post Production (6) ─────────────────────────────────────────────────────────
 28. Timeline Engine             ffmpeg assembly
 29. Camera Motion Engine        ffmpeg zoompan
 30. Caption Engine              SRT + ffmpeg subtitles
 31. Transition Engine           ffmpeg xfade
 32. Color Grading Engine        ffmpeg curves
 33. Render Engine               ffmpeg libx264 final
─── Publishing (5) ──────────────────────────────────────────────────────────────
 34. Cover Engine                Pillow (1280×720 thumbnail)
 35. Title & SEO Engine          Claude
 36. Publishing Engine           YouTube Data API v3
 37. Analytics Engine            placeholder (no data yet)
 38. Learning Engine             Claude
"""
from __future__ import annotations
import csv, json, logging, math, os, random, subprocess, sys, time, urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("studio")
sys.path.insert(0, str(Path(__file__).parent))

ASSETS         = Path(__file__).parent / "assets"
REMOTION       = Path(__file__).parent / "remotion"
CONTENT_ENGINE = Path(__file__).parent
MUSIC_DIR      = ASSETS / "music"
NAC_LOGO       = ASSETS / "nac_logo.png"
PAI_CLI        = Path(os.environ.get("PAI_CLI", "/Users/nachiketharaju/pai-pro/server/cli/generate_video.js"))
PAI_ROOT       = PAI_CLI.parent.parent.parent
PAI_PROJECT    = PAI_ROOT / "projects" / "nacartha-trailer"
PAI_CHAR_REF   = "image_4"   # NAC character sheet node ID in PAI canvas
OUT  = Path("/tmp/nacartha_full_studio")
OUT.mkdir(parents=True, exist_ok=True)

# ── Tiny Anthropic helper ──────────────────────────────────────────────────────
def _claude(system: str, user: str, max_tokens: int = 1500) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    r = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text.strip()

def _json_claude(system: str, user: str, max_tokens: int = 2000) -> dict:
    raw = _claude(system + " Respond ONLY with valid JSON. No markdown, no code blocks.", user, max_tokens)
    # Strip any remaining code fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            p = part.lstrip("json").strip()
            if p.startswith("{") or p.startswith("["):
                raw = p; break
    raw = raw.strip()
    # Attempt parse; if truncated, try to recover by closing open structures
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try appending closing braces to fix truncation
        for suffix in ('"}', '"}]}', '"]}', ']}', '}'):
            try:
                return json.loads(raw + suffix)
            except json.JSONDecodeError:
                pass
        # Last resort: return empty dict so pipeline continues
        log.warning("JSON parse failed — returning empty dict")
        return {}

def _run(cmd: list, timeout: int = 300, check: bool = True, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if check and r.returncode != 0:
        raise RuntimeError(f"Command failed:\n{r.stderr[-600:]}")
    return r

def _duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip()) if r.returncode == 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — INTELLIGENCE LAYER (Engines 1-8)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TradeData:
    ticker: str; direction: str; pnl: float; strategy: str; reason: str

@dataclass
class ShortIdea:
    category: str; topic: str; viral_angle: str; goal: str
    ticker: str; direction: str; pnl: float
    score: int = 65
    strategy: str = "AI Signal"

@dataclass
class Research:
    key_facts: List[str]; market_context: str; price_summary: str

@dataclass
class ProductionBrief:
    hook: str; micro_story: str; script: str; visual_style: str
    shots: List[Dict]; assets_needed: List[Dict]
    title: str; description: str; tags: List[str]
    viral_moment: str; retention_notes: str


def engine_1_trade_intelligence() -> List[TradeData]:
    log.info("[01] Trade Intelligence Engine — loading real trade data")
    csv_path = Path(__file__).parent.parent / "logs" / "trades_stocks.csv"
    trades = []
    if csv_path.exists():
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                try:
                    pnl = float(row.get("pnl", 0) or 0)
                    trades.append(TradeData(
                        ticker=row.get("symbol","?"),
                        direction=row.get("direction","long"),
                        pnl=pnl,
                        strategy=row.get("strategy",""),
                        reason=row.get("reason",""),
                    ))
                except Exception:
                    pass
    log.info(f"  → {len(trades)} trades loaded")
    return trades


_IDEA_HISTORY_FILE = Path.home() / ".nacartha_idea_history"

def _idea_load_history() -> dict:
    try:
        return json.loads(_IDEA_HISTORY_FILE.read_text()) if _IDEA_HISTORY_FILE.exists() else {}
    except Exception:
        return {}

def _idea_save_history(ticker: str, category: str, viral_angle: str):
    h = _idea_load_history()
    recent = h.get("recent", [])
    recent.append({"ticker": ticker, "category": category, "angle": viral_angle[:80]})
    recent = recent[-10:]  # keep last 10
    _IDEA_HISTORY_FILE.write_text(json.dumps({"recent": recent}, indent=2))


def engine_2_shorts_idea(trades: List[TradeData]) -> ShortIdea:
    log.info("[02] Shorts Idea Engine — selecting best short format")
    # Allow forced ticker/direction via env for testing
    forced_ticker = os.environ.get("FORCE_TICKER", "").upper()
    forced_dir    = os.environ.get("FORCE_DIRECTION", "SHORT").upper()
    if forced_ticker:
        log.info(f"  [OVERRIDE] Forced ticker: {forced_ticker} {forced_dir}")
        trade = TradeData(forced_ticker, forced_dir, -48.0, "AI Signal", "overbought + reversal")
    else:
        best = sorted([t for t in trades if t.pnl != 0], key=lambda t: abs(t.pnl), reverse=True)
        trade = best[0] if best else (trades[0] if trades else TradeData("TSLA","SHORT",-50,"intraday","TP1"))

    # Load recent idea history so Claude avoids repeating tickers/angles
    history = _idea_load_history()
    recent_str = json.dumps(history.get("recent", []))

    result = _json_claude(
        "You are the Shorts Idea Engine. Pick the best YouTube Shorts category and viral angle. "
        "NEVER repeat a ticker or angle that appears in the recent history. "
        "Each video must feel completely fresh — different story, different hook, different energy. "
        "Return JSON: {category, topic, viral_angle, goal}",
        f"Trade: {trade.ticker} {trade.direction} PnL={trade.pnl} strategy={trade.strategy} reason={trade.reason}. "
        "Categories: trade_of_day, why_not_buy, ai_explains, myth_busting, this_week_mistake, student_question. "
        f"RECENT HISTORY (avoid repeating): {recent_str}",
        max_tokens=500,
    )
    idea = ShortIdea(
        category=result.get("category","trade_of_day"),
        topic=result.get("topic",""),
        viral_angle=result.get("viral_angle",""),
        goal=result.get("goal",""),
        ticker=trade.ticker, direction=trade.direction, pnl=trade.pnl,
    )
    log.info(f"  → Category: {idea.category} | Angle: {idea.viral_angle[:60]}")
    _idea_save_history(idea.ticker, idea.category, idea.viral_angle)
    return idea


def engine_3_research(idea: ShortIdea) -> Research:
    log.info("[03] Research Engine — gathering facts via yfinance + Claude")
    price_data = {}
    try:
        import yfinance as yf, numpy as np
        hist = yf.Ticker(idea.ticker).history(period="5d", interval="1d")
        if not hist.empty:
            closes = np.array(hist["Close"].values, dtype=float)
            price_data = {
                "ticker": idea.ticker,
                "current": round(float(closes[-1]), 2),
                "5d_high": round(float(closes.max()), 2),
                "5d_low":  round(float(closes.min()), 2),
                "5d_change_pct": round((closes[-1]/closes[0]-1)*100, 2),
            }
    except Exception as e:
        log.warning(f"  yfinance error: {e}")

    result = _json_claude(
        "You are the Research Engine. Return JSON: {key_facts: [3 verified facts], market_context, price_summary}",
        f"Idea: {idea.viral_angle}. Ticker: {idea.ticker} {idea.direction}. Price data: {price_data}",
        max_tokens=600,
    )
    r = Research(
        key_facts=result.get("key_facts", []),
        market_context=result.get("market_context",""),
        price_summary=result.get("price_summary",""),
    )
    log.info(f"  → {len(r.key_facts)} key facts")
    return r


def engine_4_context(idea: ShortIdea, research: Research) -> str:
    log.info("[04] Context Engine — market backdrop")
    ctx = _claude(
        "You are the Context Engine. Write 2 sentences on current market conditions relevant to this trade.",
        f"Ticker: {idea.ticker}. Market context: {research.market_context}",
        max_tokens=200,
    )
    log.info(f"  → {ctx[:60]}...")
    return ctx


def engine_5_story_angle(idea: ShortIdea, research: Research, context: str) -> str:
    log.info("[05] Story Angle Engine — selecting narrative frame")
    result = _json_claude(
        "You are the Story Angle Engine. Return JSON: {selected_angle, framing_one_liner}",
        f"Idea: {idea.viral_angle}. Facts: {research.key_facts}. Context: {context}",
        max_tokens=300,
    )
    angle = result.get("selected_angle","")
    log.info(f"  → {angle[:70]}")
    return angle


def engine_6_audience(idea: ShortIdea) -> Dict:
    log.info("[06] Audience Engine — classifying viewer")
    result = _json_claude(
        "You are the Audience Engine. Return JSON: {segment, complexity_level, tone, pacing}",
        f"Category: {idea.category}. Goal: {idea.goal}",
        max_tokens=300,
    )
    log.info(f"  → segment: {result.get('segment','general')}, tone: {result.get('tone','direct')}")
    return result


def engine_7_goal(idea: ShortIdea) -> str:
    log.info("[07] Goal Engine — defining measurable viewer outcome")
    goal = _claude(
        "You are the Goal Engine. Define ONE measurable viewer outcome in one sentence.",
        f"Short category: {idea.category}. Topic: {idea.topic}.",
        max_tokens=150,
    )
    log.info(f"  → {goal[:80]}")
    return goal


def engine_8_viral_moment(idea: ShortIdea, research: Research) -> str:
    log.info("[08] Viral Moment Engine — identifying most shareable 3-second clip")
    moment = _claude(
        "You are the Viral Moment Engine. Identify the single most shareable 3-second moment in this short. "
        "Be specific — exactly what will be on screen and what will be said.",
        f"Angle: {idea.viral_angle}. Facts: {research.key_facts}. Ticker: {idea.ticker} PnL: {idea.pnl}",
        max_tokens=200,
    )
    log.info(f"  → {moment[:80]}")
    return moment


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — WRITING LAYER (Engines 9-14)
# ═══════════════════════════════════════════════════════════════════════════════

def engine_9_hook(idea: ShortIdea, angle: str, audience: Dict) -> str:
    log.info("[09] Hook Engine — writing scroll-stopping 3-second hook")
    hook = _claude(
        "You are the Hook Engine. Write ONE punchy hook line (under 12 words). No intro. Pure tension or surprise.",
        f"Angle: {angle}. Ticker: {idea.ticker} {idea.direction} PnL: {idea.pnl}. Audience: {audience.get('segment','general')}",
        max_tokens=80,
    )
    hook = hook.strip().strip('"')
    log.info(f"  → \"{hook}\"")
    return hook


def engine_10_micro_story(idea: ShortIdea, research: Research, hook: str, goal: str) -> str:
    log.info("[10] Micro Story Engine — building 55-second narrative arc")
    story = _claude(
        "You are the Micro Story Engine. Write a 55-second narrative arc for a YouTube Short. "
        "Structure: [Hook 0-5s] [Reveal 5-20s] [Insight 20-42s] [CTA 42-55s]. "
        "Write it as a timed narrator script. NAC speaks directly to camera. No headers.",
        f"Hook: {hook}. Facts: {research.key_facts}. Angle: {idea.viral_angle}. Goal: {goal}",
        max_tokens=600,
    )
    log.info(f"  → Story arc written ({len(story.split())} words)")
    return story


def engine_11_script(micro_story: str, idea: ShortIdea, viral_moment: str) -> Dict:
    log.info("[11] Script Engine — finalizing timed script with delivery cues")
    result = _json_claude(
        "You are the Script Engine for YouTube Shorts. "
        "Return ONLY a JSON object with these EXACT keys (no extras, keep all values SHORT): "
        "{\"hook_text\": \"<10 words>\", \"hook_subtext\": \"<8 words>\", \"reveal_stat\": \"<stat>\", "
        "\"body_narration\": \"<2 sentences>\", \"cta_text\": \"<5 words>\", "
        "\"full_narration\": \"<complete 55s narration, max 120 words>\", \"duration_seconds\": 55}",
        f"Story: {micro_story[:400]}\nTicker: {idea.ticker} PnL: {idea.pnl} Direction: {idea.direction}",
        max_tokens=900,
    )
    # Ensure duration is numeric
    raw_dur = result.get("duration_seconds", 55)
    if isinstance(raw_dur, str):
        import re; nums = re.findall(r"[\d.]+", raw_dur)
        raw_dur = float(nums[0]) if nums else 55.0
    result["duration_seconds"] = max(45.0, min(float(raw_dur), 60.0))
    log.info(f"  → Hook: \"{result.get('hook_text','')[:50]}\" | Duration: {result['duration_seconds']}s")
    return result


def engine_12_fact_validation(script: Dict, research: Research) -> Dict:
    log.info("[12] Fact Validation Engine — verifying all claims")
    result = _json_claude(
        "You are the Fact Validation Engine. Validate the script. "
        "Return JSON: {validated: true/false, corrections: [], confidence: 0-100}",
        f"Script: {script.get('full_narration','')}. Verified facts: {research.key_facts}",
        max_tokens=400,
    )
    log.info(f"  → Validated: {result.get('validated',True)} | Confidence: {result.get('confidence',90)}%")
    return result


def engine_13_retention(script: Dict, audience: Dict) -> Dict:
    log.info("[13] Retention Engine — optimizing pacing for viewer retention")
    result = _json_claude(
        "You are the Retention Engine. Analyze the script for drop-off risk. "
        "Return JSON: {risk_sections: [], re_hook_at_second: 0, energy_adjustments: [], optimized_narration}",
        f"Script: {script.get('full_narration','')}. Audience: {audience.get('segment','general')}",
        max_tokens=500,
    )
    # Use optimized narration if provided
    if result.get("optimized_narration"):
        script["full_narration"] = result["optimized_narration"]
    log.info(f"  → Re-hook at: {result.get('re_hook_at_second',25)}s | {len(result.get('risk_sections',[]))} risks fixed")
    return script


def engine_14_conversation(script: Dict, idea: ShortIdea) -> Dict:
    log.info("[14] Conversation Engine — defining NAC voice and delivery style")
    result = _json_claude(
        "You are the Conversation Engine. Define NAC's speaking style for this short. "
        "Return JSON: {pace, energy, pauses_at: [], emphasis_words: [], delivery_note}",
        f"Script: {script.get('full_narration','')}. Category: {idea.category}",
        max_tokens=300,
    )
    log.info(f"  → Pace: {result.get('pace','medium-fast')} | Energy: {result.get('energy','high')}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — DIRECTION LAYER (Engines 15-19)
# ═══════════════════════════════════════════════════════════════════════════════

def engine_15_creative_director(idea: ShortIdea, angle: str, audience: Dict, script: Dict) -> Dict:
    log.info("[15] Creative Director Engine — generating unique visual program")

    is_short = idea.direction.upper() == "SHORT"
    is_loss  = idea.pnl < 0
    dir_color = "#ef4444" if is_short else "#22c55e"
    bg_dark   = "#180000" if is_short else "#001408"

    result = _json_claude(
        f"""You are the Creative Director, Visual Programmer, AND Cinematographer for NacArtha AI trading Shorts.

Each video MUST feel completely different — different structure, different energy, different PAI footage, different story.

━━━ PAI CLIP DIRECTION (your most important job) ━━━
You control the actual footage that goes in the video via pai_clip_prompts.
NAC is an Indian male analyst with glasses — this is the character PAI will use for char_ref.

For char_ref_clip (8s, 9:16 vertical, NAC character MUST appear):
- VARY the ACTION: pointing at screen | sitting leaned in | turning to camera | head down analyzing | arms crossed watching | walking between screens | on phone looking at charts | jaw drop looking at chart
- VARY the LIGHTING: blood-red emergency glow | cold clinical blue monitor light | warm amber late-night lamp | purple neon reflections | strobing alert lights | single bright monitor backlight | green profit glow
- VARY the CAMERA: medium shot | extreme close-up face lit by screens | over-shoulder at monitors | wide establishing trading room | Dutch angle tense | low angle looking up at screens
- VARY the ENERGY (match the story): alarmed and urgent | calm and methodical | disappointed slumping | confident and decisive | shocked frozen staring | excited leaning forward | exhausted post-trade
- ALWAYS end with: "Indian male analyst with glasses, 9:16 vertical cinematic, 4K quality"

For broll_clip (6s, 9:16 vertical, ZERO people — empty environment):
- VARY the SUBJECT: single monitor close-up | keyboard macro | wide empty trading floor | desk bird's-eye | glass desk reflection | monitor wall row | coffee mug + scattered papers + screen | window with city view + screen reflection
- VARY chart content: blood-red crash in freefall | explosive green surge | volatile whipsawing | consolidation breaking down | gap down opening | sustained rally
- VARY color treatment: pure red glow | cold blue tech | amber warm | emergency red strobe | green profit cascade | purple neon
- ALWAYS include: "no people, no person, no human body parts" — CRITICAL for B-roll

━━━ REMOTION VISUAL PROGRAM ━━━
You control a layer-based Remotion interpreter. Layers render bottom to top.

AVAILABLE LAYER TYPES:
- bg:          {{colors: [hex, hex], angle: 0-360}} — gradient background
- grain:       {{opacity: 0.1-0.6}} — film grain
- vignette:    {{strength: 0.2-0.8}} — dark edges
- glow_orb:    {{x: px or "50%", y: px or "center" or "30%", size: 200-800, color: hex, opacity: 0.1-0.3}}
- text_block:  {{content: str, x: px or "center", y: px or "center" or "30%" or "center+N",
                 size: 40-140, weight: 400-900, color: hex, last_word_color: hex,
                 entry: "word_slam"|"slow_fade"|"type_in"|"all_at_once"|"slide_left"|"slide_right",
                 entry_frame: 0-30, stagger: 5-12, transform: "uppercase"|"none",
                 letter_spacing: -6 to 8, font: "Arial Black, Impact, sans-serif"|"Georgia, serif"}}
- ticker_bar:  {{position: "top"|"bottom", content: str, color: hex, text_color: hex, height: 40-60,
                 label: str (bold badge), scroll_speed: 1-3}}
- badge:       {{content: str, x: px, y: "center" or "30%", bg_color: hex, text_color: hex,
                 font_size: 18-36, entry_frame: 0-20, entry: "slide_left"|"scale"}}
- counter:     {{label: str, target: number (negative for loss), prefix: "$"|"", suffix: "",
                 color: hex, x: px, y: "center", size: 80-160,
                 entry_frame: 0, count_frames: 40-70, slam_frame: 50-80}}
- split_line:  {{orientation: "vertical"|"horizontal", position: "50%"|"40%"|"60%",
                 color: hex, entry_frame: 0-10, entry: "sweep"|"fade"}}
- data_grid:   {{rows: [{{label: str, value: str, color: hex}}, ...],
                 x: px, y: "center", value_size: 50-100, stagger: 12-20, accent_bar_color: hex}}
- accent_line: {{x: px, y: "bottom-80"|"bottom-120", length: 100-800, color: hex,
                 direction: "right"|"center", grow_frames: [start_f, end_f]}}
- scan_bar:    {{color: hex, speed: 0.3-1.0, opacity: 0.04-0.1}}
- glow_rect:   {{x: px, y: "center", width: px, height: px, color: hex, entry_frame: 0-20}}
- circle_ring: {{x: "50%", y: "center", size: 200-600, color: hex, pulse: true|false,
                 expand_frames: 30-60, entry_frame: 0}}

DESIGN RULES:
1. Always start with bg + grain + vignette (foundation)
2. Add 1-2 glow_orbs for atmosphere
3. The text_block with the hook IS the hero — make it BIG (size 90-130)
4. Pick a color palette with ONE strong accent: red for loss/short, green for win/long, amber/cyan/purple for neutral
5. Every video needs a different STRUCTURAL IDEA — pick from:
   - CONFESSION: slow_fade text, intimate, warm, word by word barely visible at first
   - THRILLER: multiple text_blocks hitting fast, ticker top+bottom, scan_bar
   - INVESTIGATION: data_grid with evidence, split_line left-aligned, cold cyan
   - IMPACT: counter counting to P&L, circle_ring expanding, huge number center
   - SPLIT: vertical split_line at 45%, badge left panel, text right panel
   - EDITORIAL: minimal, serif font, letter_spacing 4+, slow_fade, glow_rect border
   - BROADCAST: ticker_bar top with BREAKING label, text left-aligned, bottom ticker
   - WORD PUNCH: single word in text_block at size 140, then smaller support text at entry_frame 20

Return ONLY valid JSON with NO comments:
{{
  "visual_style": "<one sentence — what this video feels like>",
  "structural_idea": "<CONFESSION|THRILLER|INVESTIGATION|IMPACT|SPLIT|EDITORIAL|BROADCAST|WORD_PUNCH>",
  "music_mood": "<tension|urgency|dread|revelation|intrigue — pick by story energy>",
  "camera_style": "<confessional|investigative|broadcast|kinetic|cinematic|documentary — drives camera motion engine>",
  "sfx_profile": "<impact|tension|reveal|dramatic|soft — drives sfx engine>",
  "nac_performance_prompts": {{
    "hook_moment": "<4s PAI char-ref clip: NAC's first emotional reaction — shock/urgency/excitement matching story opening. Indian male analyst with glasses, 9:16 vertical, 4K>",
    "analysis_moment": "<6s PAI char-ref clip: NAC deeply analyzing the trade data — pointing at screen, leaning in, studying chart. Indian male analyst with glasses, 9:16 vertical, 4K>",
    "conclusion_moment": "<4s PAI char-ref clip: NAC's final reaction to the outcome — satisfied/surprised/contemplative. Indian male analyst with glasses, 9:16 vertical, 4K>"
  }},
  "broll_prompts": [
    "<B-roll prompt 1: establishing environment, no people, no person, 9:16 cinematic>",
    "<B-roll prompt 2: data detail / chart close-up, no people, no person, 9:16 cinematic>",
    "<B-roll prompt 3: mood/atmosphere shot, no people, no person, 9:16 cinematic>"
  ],
  "pai_clip_prompts": {{
    "char_ref": "<complete PAI prompt for 8s NAC char-ref clip — vary action+lighting+camera+energy to match this video's story. End with: Indian male analyst with glasses, 9:16 vertical cinematic, 4K quality>",
    "broll": "<complete PAI prompt for 6s B-roll, empty environment only. Vary subject+angle+color. Must include: no people, no person, no human body parts, 9:16 vertical cinematic, 4K>"
  }},
  "hook_program": {{
    "layers": [ ...layers for 3s hook card... ]
  }},
  "stat_program": {{
    "layers": [ ...layers for 6s stat/P&L card... ]
  }},
  "remotion_spec": {{
    "layout": "<for legacy fallback: cinematic_overlay|typo_slam|news_break|investigation|confession|split_tension>",
    "color_primary": "<main accent hex>",
    "bg_gradient_start": "<dark hex>",
    "bg_gradient_end": "<darker hex>",
    "grain": <0.2-0.5>,
    "vignette": <0.3-0.7>
  }}
}}""",
        f"Ticker: {idea.ticker} {idea.direction} PnL={idea.pnl}. "
        f"Hook text: \"{script.get('hook_text','')}\". "
        f"Category: {idea.category}. Angle: {angle}. Tone: {audience.get('tone','direct')}. "
        f"Direction color hint: {dir_color}. Background hint: {bg_dark}",
        max_tokens=4000,
    )
    spec  = result.get("remotion_spec", {})
    idea_ = result.get("structural_idea", "?")
    pai_prompts = result.get("pai_clip_prompts", {})
    nac_perf    = result.get("nac_performance_prompts", {})
    broll_list  = result.get("broll_prompts", [])
    log.info(f"  → Idea: {idea_} | Style: {result.get('visual_style','')[:50]}")
    log.info(f"  → Music: {result.get('music_mood','?')} | Camera: {result.get('camera_style','?')} | SFX: {result.get('sfx_profile','?')}")
    log.info(f"  → Color: {spec.get('color_primary','?')} | bg: {spec.get('bg_gradient_start','?')}")
    hook_layers = result.get("hook_program", {}).get("layers", [])
    stat_layers = result.get("stat_program", {}).get("layers", [])
    log.info(f"  → hook_program: {len(hook_layers)} layers | stat_program: {len(stat_layers)} layers")
    log.info(f"  → nac_perf: {len([v for v in nac_perf.values() if v])} clips | broll: {len(broll_list)} prompts")
    if pai_prompts.get("char_ref"):
        log.info(f"  → PAI char_ref: \"{pai_prompts['char_ref'][:80]}...\"")
    if pai_prompts.get("broll"):
        log.info(f"  → PAI broll:    \"{pai_prompts['broll'][:80]}...\"")
    return result


def engine_16_director(script: Dict, brief: Dict) -> Dict:
    log.info("[16] Director Engine — writing scene direction")
    result = _json_claude(
        "You are the Director. Write scene-by-scene direction for a 55s YouTube Short. "
        "Return JSON: {scenes: [{id, timing, mood, camera, transition}]}",
        f"Script sections: hook={script.get('hook_text','')}, reveal, body, cta. Style: {brief.get('visual_style','')}",
        max_tokens=600,
    )
    log.info(f"  → {len(result.get('scenes',[]))} scenes directed")
    return result


def engine_17_shot_planning(director: Dict, script: Dict) -> List[Dict]:
    log.info("[17] Shot Planning Engine — building shot list")
    result = _json_claude(
        "You are the Shot Planning Engine for YouTube Shorts (1080x1920). "
        "Return JSON: {shots: [{id, scene, type, movement, duration_s, visual_description}]}",
        f"Scenes: {director.get('scenes',[])}. Total duration: 55s.",
        max_tokens=600,
    )
    shots = result.get("shots", [])
    log.info(f"  → {len(shots)} shots planned")
    return shots


def engine_18_visual_planning(shots: List[Dict], script: Dict, idea: ShortIdea) -> List[Dict]:
    log.info("[18] Visual Planning Engine — assigning visuals to each shot")
    result = _json_claude(
        "You are the Visual Planning Engine. For each shot, specify the visual source. "
        "Sources: nac_library_clip, pai_cinematic, chart, motion_graphic, dashboard. "
        "Return JSON: {visual_plan: [{shot_id, source, spec}]}",
        f"Shots: {shots[:5]}. Ticker: {idea.ticker}. NAC library has: hook, conf, exp, norm, react, rev, cta clips.",
        max_tokens=700,
    )
    plan = result.get("visual_plan", [])
    log.info(f"  → {len(plan)} visual assignments")
    return plan


def engine_19_asset_planning(visual_plan: List[Dict], idea: ShortIdea) -> Dict:
    log.info("[19] Asset Planning Engine — generating asset production queue")
    result = _json_claude(
        "You are the Asset Planning Engine. Be VERY brief. "
        "Return ONLY this JSON (max 3 items each): "
        "{\"queue\":[{\"asset_id\":\"a1\",\"type\":\"chart\",\"priority\":1,\"spec\":\"TSLA 30d\"}],"
        "\"pai_clips\":[{\"description\":\"dark trading office with screens\",\"duration_s\":6}]}",
        f"Ticker: {idea.ticker}. Direction: {idea.direction}.",
        max_tokens=600,
    )
    log.info(f"  → {len(result.get('queue',[]))} assets queued, {len(result.get('pai_clips',[]))} PAI clips")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — PRODUCTION LAYER (Engines 20-27)
# ═══════════════════════════════════════════════════════════════════════════════

def engine_20_nac_performance(script: Dict, brief: Dict = None) -> List[Path]:
    """Generate NAC character performance clips via PAI (char-ref clips).
    Returns up to 3 clips: hook reaction, analysis moment, conclusion reaction.
    Falls back gracefully — timeline engine handles missing clips."""
    log.info("[20] NAC Performance Engine — generating PAI char-ref performance clips")
    brief = brief or {}
    clips = []

    try:
        _pai_tunnel_check()
    except RuntimeError as e:
        log.warning(f"  [20] PAI tunnel unavailable — skipping NAC performance clips: {e}")
        return clips

    nac_prompts = brief.get("nac_performance_prompts", {})
    structural  = brief.get("structural_idea", "")

    # Default performance prompts per structural idea (vary the NAC behavior)
    _HOOK_DEFAULTS = {
        "CONFESSION":    "Indian male analyst with glasses looking directly into camera with guilt, dim monitor backlight, close-up face, silent expression says everything, 9:16 vertical cinematic, 4K quality",
        "THRILLER":      "Indian male analyst with glasses suddenly turning to camera with alarmed expression, multiple screens flashing, urgent energy, medium shot, 9:16 vertical cinematic, 4K quality",
        "INVESTIGATION": "Indian male analyst with glasses leaning forward squinting at data, cold blue light, concentrated analytical expression, over-shoulder camera, 9:16 vertical cinematic, 4K quality",
        "IMPACT":        "Indian male analyst with glasses frozen staring at screen, jaw slightly open, pure screen backlight, Dutch angle, 9:16 vertical cinematic, 4K quality",
        "BROADCAST":     "Indian male analyst with glasses facing camera confidently, professional lighting, medium shot, authoritative posture, 9:16 vertical cinematic, 4K quality",
        "WORD_PUNCH":    "Extreme close-up Indian male analyst with glasses, intense focused stare into lens, half face in shadow, single screen glow, 9:16 vertical cinematic, 4K quality",
        "SPLIT":         "Indian male analyst with glasses pointing at two different screens, split energy, dramatic side lighting, 9:16 vertical cinematic, 4K quality",
        "EDITORIAL":     "Indian male analyst with glasses reading documents with furrowed brow, warm desk lamp, thoughtful serious expression, 9:16 vertical cinematic, 4K quality",
    }
    _ANALYSIS_DEFAULTS = {
        "CONFESSION":    "Indian male analyst with glasses sitting quietly at desk, head slightly down reviewing chart, regretful contemplation, amber monitor glow, 9:16 vertical cinematic, 4K quality",
        "THRILLER":      "Indian male analyst with glasses rapidly pointing at multiple screens, urgent kinetic movement, red alert lighting, 9:16 vertical cinematic, 4K quality",
        "INVESTIGATION": "Indian male analyst with glasses using finger to trace chart pattern on screen, clinical precision, cold blue light, 9:16 vertical cinematic, 4K quality",
        "IMPACT":        "Indian male analyst with glasses typing rapidly while watching live chart, high stress, multiple screens, white monitor glare, 9:16 vertical cinematic, 4K quality",
        "BROADCAST":     "Indian male analyst with glasses gesturing toward chart on screen beside him, explaining to camera, broadcast studio light, 9:16 vertical cinematic, 4K quality",
        "WORD_PUNCH":    "Indian male analyst with glasses pointing aggressively at single screen, intense conviction, dramatic backlight, 9:16 vertical cinematic, 4K quality",
        "SPLIT":         "Indian male analyst with glasses comparing two charts side by side, analytical focus, split-screen monitor setup, 9:16 vertical cinematic, 4K quality",
        "EDITORIAL":     "Indian male analyst with glasses writing notes while looking at chart, methodical analysis, desk lamp warm light, 9:16 vertical cinematic, 4K quality",
    }
    _CONCLUSION_DEFAULTS = {
        "CONFESSION":    "Indian male analyst with glasses looking at camera with honest expression, accepting outcome, soft side light, close-up, 9:16 vertical cinematic, 4K quality",
        "THRILLER":      "Indian male analyst with glasses watching final result, relief or tension depending on outcome, screen glow, 9:16 vertical cinematic, 4K quality",
        "INVESTIGATION": "Indian male analyst with glasses leaning back in chair, arms crossed, case closed body language, cool light, 9:16 vertical cinematic, 4K quality",
        "IMPACT":        "Indian male analyst with glasses standing back from screens, hands on desk, taking it in, dramatic pause, 9:16 vertical cinematic, 4K quality",
        "BROADCAST":     "Indian male analyst with glasses facing camera for final word, confident sign-off posture, broadcast light, 9:16 vertical cinematic, 4K quality",
        "WORD_PUNCH":    "Indian male analyst with glasses looking at camera with final conviction, intense eyes, dark background, 9:16 vertical cinematic, 4K quality",
        "SPLIT":         "Indian male analyst with glasses relaxing back from screens, conclusion posture, ambient monitor glow, 9:16 vertical cinematic, 4K quality",
        "EDITORIAL":     "Indian male analyst with glasses closing notebook, satisfied or reflective expression, warm lamp light, 9:16 vertical cinematic, 4K quality",
    }

    perf_specs = [
        ("hook",       4, nac_prompts.get("hook_moment")       or _HOOK_DEFAULTS.get(structural,       "Indian male analyst with glasses reacting with surprise to trading chart, dramatic expression, monitor backlight, 9:16 vertical cinematic, 4K quality")),
        ("analysis",   6, nac_prompts.get("analysis_moment")   or _ANALYSIS_DEFAULTS.get(structural,   "Indian male analyst with glasses deeply analyzing chart on screen, focused expression, cold monitor light, 9:16 vertical cinematic, 4K quality")),
        ("conclusion", 4, nac_prompts.get("conclusion_moment") or _CONCLUSION_DEFAULTS.get(structural, "Indian male analyst with glasses looking at camera with final expression, cinematic close-up, 9:16 vertical cinematic, 4K quality")),
    ]

    for name, dur, prompt in perf_specs:
        out_path = OUT / f"nac_perf_{name}.mp4"
        if not out_path.exists():
            try:
                _pai_generate(prompt, dur=dur, out_path=out_path, use_char_ref=True)
            except Exception as e:
                log.warning(f"  [20] NAC perf '{name}' clip failed: {e}")
        if out_path.exists():
            clips.append(out_path)
            log.info(f"  → nac_perf_{name}.mp4")

    log.info(f"  [20] Generated {len(clips)}/3 NAC performance clips")
    return clips


def engine_21_student_performance() -> Optional[Path]:
    log.info("[21] Student Performance Engine — selecting student clip (Shorts: solo NAC format)")
    # For Shorts, student clips are not used (solo NAC format)
    # Engine runs but returns None — documented as valid for Shorts
    log.info("  → Shorts format: solo NAC, student skipped")
    return None


def _pai_tunnel_check() -> str:
    """Read .tunnel_url, verify image_4 is reachable. Raises RuntimeError if not."""
    import urllib.request
    tunnel_file = PAI_ROOT / ".tunnel_url"
    if not tunnel_file.exists():
        raise RuntimeError(
            "PAI tunnel not configured — .tunnel_url missing.\n"
            "Fix: cd pai-pro && ./scripts/start.sh"
        )
    tunnel_url = tunnel_file.read_text().strip().rstrip("/")
    check_url = f"{tunnel_url}/projects/nacartha-trailer/assets/images/image_4.png"
    try:
        req = urllib.request.urlopen(check_url, timeout=8)
        status = req.getcode()
        if status != 200:
            raise RuntimeError(f"Tunnel returned HTTP {status} for image_4 — URL may be stale")
    except Exception as e:
        raise RuntimeError(
            f"PAI tunnel health check FAILED: {e}\n"
            f"  Tunnel URL in .tunnel_url: {tunnel_url}\n"
            f"  Checked: {check_url}\n"
            f"Fix: get new tunnel URL from .tunnel_url.7488.log, then:\n"
            f"  echo -n '<new-url>' > {tunnel_file}"
        )
    log.info(f"  ✓ PAI tunnel OK: {tunnel_url}")
    return tunnel_url


def _pai_generate(desc: str, dur: int, out_path: Path, use_char_ref: bool = True) -> Path:
    """Call PAI generate_video.js. Raises RuntimeError on failure."""
    desc = desc.replace("luxury","modern").replace("2 AM","night").replace("expensive","professional")
    pai_cmd = [
        "node", str(PAI_CLI),
        "--prompt", desc,
        "--duration", str(dur),
        "--aspect-ratio", "9:16",
        "--resolution", "720p",
        "--no-audio",
    ]
    if use_char_ref:
        pai_cmd += ["--ref-source-id", PAI_CHAR_REF]
    log.info(f"  PAI → \"{desc[:70]}\" ({dur}s, char_ref={use_char_ref})")
    r = subprocess.run(pai_cmd, capture_output=True, text=True, timeout=300, cwd=str(PAI_ROOT))
    result = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    if result.get("ok") and result.get("local_path"):
        src = PAI_PROJECT / result["local_path"]
        if not src.exists():
            src = PAI_ROOT / result["local_path"]
        import shutil; shutil.copy(str(src), out_path)
        log.info(f"  → {out_path.name} (from {src.name})")
        return out_path
    raise RuntimeError(f"PAI failed: {result.get('message', r.stderr[:300])}")


def engine_22_ai_visual_pai(asset_plan: Dict, idea: ShortIdea, brief: Dict = None) -> List[Path]:
    log.info("[22] AI Visual Generation Engine — PAI cinematic clips (char ref REQUIRED)")
    clips = []

    brief = brief or {}
    pai_prompts = brief.get("pai_clip_prompts", {})
    structural_idea = brief.get("structural_idea", "")

    # Pre-flight: verify tunnel is alive before spending any credits
    try:
        _pai_tunnel_check()
    except RuntimeError as e:
        log.error(f"  ✗ [22] TUNNEL PRE-FLIGHT FAILED — aborting PAI engine entirely:\n  {e}")
        return clips

    # ── Build prompts — AI-generated first, intelligent fallback if missing ────
    # Fallback prompt tables — vary by structural idea so even fallbacks differ
    _CHAR_REF_FALLBACKS = {
        "CONFESSION": (
            f"Indian male analyst with glasses sitting alone at desk, head slightly bowed, "
            f"single monitor glowing red in dark room, regret and contemplation, "
            f"intimate close-up, warm amber rim light, 9:16 vertical cinematic, 4K quality"
        ),
        "THRILLER": (
            f"Indian male analyst with glasses standing alert at multiple screens, "
            f"urgent body language, screens flashing red {idea.ticker} alerts, "
            f"emergency lighting, wide shot, high tension, 9:16 vertical cinematic, 4K quality"
        ),
        "INVESTIGATION": (
            f"Indian male analyst with glasses leaning forward examining data on screen, "
            f"pointing at chart detail, clinical cold blue monitor light, analytical focus, "
            f"over-shoulder camera angle, 9:16 vertical cinematic, 4K quality"
        ),
        "IMPACT": (
            f"Indian male analyst with glasses frozen staring at screen showing {idea.ticker} "
            f"chart, wide eyes, screen reflects on face in dark room, dramatic Dutch angle, "
            f"pure screen backlight only, 9:16 vertical cinematic, 4K quality"
        ),
        "BROADCAST": (
            f"Indian male analyst with glasses standing confidently in front of live trading "
            f"screens, gesturing toward charts, professional broadcast lighting, "
            f"medium shot, 9:16 vertical cinematic, 4K quality"
        ),
        "WORD_PUNCH": (
            f"Extreme close-up of Indian male analyst with glasses, face lit dramatically "
            f"by {idea.ticker} chart glow, intense focused expression, half face in shadow, "
            f"9:16 vertical cinematic, 4K quality"
        ),
    }
    _BROLL_FALLBACKS = {
        "CONFESSION": (
            f"Bird's eye view of empty trading desk at night, cold coffee mug, "
            f"scattered papers, single monitor glowing red with {idea.ticker} chart, "
            f"no people, no person, no human, dramatic overhead, 9:16 cinematic, 4K"
        ),
        "THRILLER": (
            f"Wide shot of empty trading floor, wall of monitors all showing red cascading "
            f"charts for {idea.ticker}, emergency red ambient light, no humans, no people, "
            f"cinematic depth of field, 9:16 vertical, 4K"
        ),
        "INVESTIGATION": (
            f"Extreme macro close-up of trading terminal screen showing {idea.ticker} "
            f"data points and chart pattern, cold blue light, no people, no person, "
            f"sharp focus on data, 9:16 cinematic, 4K"
        ),
        "IMPACT": (
            f"Reflection of crashing {idea.ticker} chart in glass desk surface, "
            f"dark room with glowing screens background, no people, no human, "
            f"macro lens, bokeh background, 9:16 cinematic, 4K"
        ),
        "BROADCAST": (
            f"Row of professional trading monitors showing {idea.ticker} live feed, "
            f"empty ergonomic chair, professional studio lighting, no people, no person, "
            f"wide establishing shot, 9:16 cinematic, 4K"
        ),
        "WORD_PUNCH": (
            f"Macro shot of computer mouse and keyboard with {idea.ticker} chart glowing "
            f"red/green on screen behind, dramatic depth of field, dark moody, "
            f"no people, no human, 9:16 cinematic, 4K"
        ),
    }

    # Generic fallbacks when structural_idea isn't set
    _dir = "SHORT" if idea.direction.upper() == "SHORT" else "LONG"
    _dir_word  = "blood-red collapsing" if _dir == "SHORT" else "explosive green surging"
    _mood_word = "alarmed, urgent" if _dir == "SHORT" else "excited, decisive"
    _light     = "emergency red warning glow" if _dir == "SHORT" else "triumphant green profit light"

    char_ref_prompt = (
        pai_prompts.get("char_ref")
        or _CHAR_REF_FALLBACKS.get(structural_idea)
        or (
            f"Indian male analyst with glasses, {_mood_word} expression, "
            f"dark trading terminal with {idea.ticker} {_dir} chart on screens, "
            f"{_light}, close-up cinematic, 9:16 vertical, 4K quality"
        )
    )

    broll_prompt = (
        pai_prompts.get("broll")
        or _BROLL_FALLBACKS.get(structural_idea)
        or (
            f"Cinematic {_dir_word} {idea.ticker} candlestick chart on trading terminal screen, "
            f"empty professional trading desk, no people, no person, no human body parts, "
            f"{_light}, depth of field, 9:16 cinematic, 4K"
        )
    )

    log.info(f"  Using: structural_idea={structural_idea or 'default'}")
    log.info(f"  char_ref prompt: \"{char_ref_prompt[:90]}\"")
    log.info(f"  broll prompt:    \"{broll_prompt[:90]}\"")

    # ── Clip 1: NAC character (char-ref MANDATORY) ────────────────────────────
    clip1 = OUT / "pai_clip_00.mp4"
    if not clip1.exists():
        try:
            _pai_generate(char_ref_prompt, dur=8, out_path=clip1, use_char_ref=True)
        except Exception as e:
            log.error(f"  ✗ [22] PAI char-ref clip FAILED — skipping (do NOT fallback): {e}")
            log.error(f"  ✗ ACTION NEEDED: check tunnel is up and image_4 is accessible")
    if clip1.exists():
        clips.append(clip1)
    else:
        log.warning("  [22] No NAC character clip — timeline will have gap at char-ref position")

    # ── Clip 2: B-roll — NO PEOPLE ────────────────────────────────────────────
    clip2 = OUT / "pai_clip_01.mp4"
    if not clip2.exists():
        try:
            _pai_generate(broll_prompt, dur=6, out_path=clip2, use_char_ref=False)
        except Exception as e:
            log.error(f"  ✗ [22] PAI B-roll clip failed: {e}")
    if clip2.exists():
        clips.append(clip2)

    log.info(f"  → {len(clips)} PAI clips (char-ref: {1 if clip1.exists() else 0})")
    return clips


def _compute_rsi(closes: list, period: int = 14) -> list:
    """Returns RSI values (None for first `period` entries)."""
    rsi = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(closes)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi[i] = round(100 - 100 / (1 + rs), 2)
    return rsi


def engine_23_dashboard(idea: ShortIdea) -> Dict:
    log.info("[23] Dashboard Engine — fetching OHLCV data for animated Remotion chart")
    cache_path = OUT / f"chart_data_{idea.ticker}.json"
    if cache_path.exists():
        log.info(f"  [cache] chart_data_{idea.ticker}.json")
        return json.loads(cache_path.read_text())

    import numpy as np, yfinance as yf

    hist = yf.Ticker(idea.ticker).history(period="1mo", interval="1d")
    if hist.empty:
        raise RuntimeError(f"[23] yfinance returned no data for {idea.ticker}")

    candles = []
    for row in hist.itertuples():
        candles.append({
            "o": round(float(row.Open),  2),
            "h": round(float(row.High),  2),
            "l": round(float(row.Low),   2),
            "c": round(float(row.Close), 2),
            "v": int(row.Volume),
        })

    closes   = [c["c"] for c in candles]
    rsi_vals = _compute_rsi(closes)
    n        = len(candles)

    # Entry ~80% through, exit ~95% through
    entry_idx = max(0, int(n * 0.80))
    exit_idx  = max(entry_idx + 1, int(n * 0.95))

    # Rough support/resistance from price range
    all_lows  = [c["l"] for c in candles]
    all_highs = [c["h"] for c in candles]
    support    = round(min(all_lows)    * 1.001, 2)
    resistance = round(max(all_highs)   * 0.999, 2)

    data = {
        "ticker":    idea.ticker,
        "direction": idea.direction.upper(),
        "pnl":       idea.pnl,
        "score":     65,
        "strategy":  "intraday",
        "entryIdx":  entry_idx,
        "exitIdx":   exit_idx,
        "support":   support,
        "resistance":resistance,
        "candles":   candles,
        "rsi":       rsi_vals,
    }
    cache_path.write_text(json.dumps(data))
    log.info(f"  → {n} candles, RSI computed, entry={entry_idx} exit={exit_idx}")
    return data


def _remotion_render(comp_id: str, fname: str, frames: int, props: dict) -> Path:
    out_path = OUT / fname
    if out_path.exists():
        log.info(f"  [cache] {fname}")
        return out_path
    log.info(f"  Remotion → {comp_id} ({frames}f = {frames/30:.1f}s)")
    _run([
        "npx", "remotion", "render",
        "remotion/src/index.js", comp_id, str(out_path),
        "--props", json.dumps(props),
        "--frames", f"0-{frames - 1}",
        "--width", "1080", "--height", "1920",
        "--concurrency", "1",
    ], timeout=420, cwd=str(CONTENT_ENGINE))
    log.info(f"  → {fname}")
    return out_path


_REMOTION_THEME_FILE = Path.home() / ".nacartha_remotion_theme"

# Layout → Remotion hook composition ID
_LAYOUT_TO_HOOK_COMP = {
    "cinematic_overlay": "FilmCard",
    "typo_slam":         "TypoSlam",
    "split_tension":     "SplitReveal",
    "data_burst":        "WordPunch",
    "character_moment":  "FilmCard",
    "news_break":        "NewsFlash",
    "investigation":     "GlitchHook",
    "confession":        "FilmCard",
}

# Layout → Remotion stat composition ID
_LAYOUT_TO_STAT_COMP = {
    "cinematic_overlay": "ImpactStat",
    "typo_slam":         "WinLoseSlam",
    "split_tension":     "DataReveal",
    "data_burst":        "DataReveal",
    "character_moment":  "ImpactStat",
    "news_break":        "WinLoseSlam",
    "investigation":     "DataReveal",
    "confession":        "ImpactStat",
}

# 6 distinct visual themes — never repeat consecutive runs
_REMOTION_THEMES = [
    # 0: deep red — tension/danger
    {"style": "tension",     "accent": "#ef4444", "bg": "#0d0000",
     "surface": "rgba(20,0,0,0.92)",   "textPrimary": "#ffffff", "textSecond": "#ef4444"},
    # 1: amber gold — confidence/wisdom
    {"style": "kinetic",     "accent": "#f59e0b", "bg": "#0a0800",
     "surface": "rgba(18,14,0,0.92)",  "textPrimary": "#ffffff", "textSecond": "#f59e0b"},
    # 2: cyan neon — tech/investigation
    {"style": "neon",        "accent": "#00e5ff", "bg": "#020610",
     "surface": "rgba(2,6,16,0.92)",   "textPrimary": "#ffffff", "textSecond": "#00e5ff"},
    # 3: hot orange — impact/urgency
    {"style": "impact",      "accent": "#fb923c", "bg": "#0e0400",
     "surface": "rgba(14,4,0,0.92)",   "textPrimary": "#ffffff", "textSecond": "#fb923c"},
    # 4: glitch purple — hacker energy
    {"style": "glitch",      "accent": "#a855f7", "bg": "#04040c",
     "surface": "rgba(10,0,20,0.92)",  "textPrimary": "#f0e0ff", "textSecond": "#a855f7"},
    # 5: bullish green — LONG plays
    {"style": "kinetic",     "accent": "#22c55e", "bg": "#020e06",
     "surface": "rgba(2,14,6,0.92)",   "textPrimary": "#ffffff", "textSecond": "#22c55e"},
]

def _pick_remotion_theme(idea: ShortIdea) -> dict:
    """Pick a unique visual theme, never the same as last run."""
    try:
        state = json.loads(_REMOTION_THEME_FILE.read_text()) if _REMOTION_THEME_FILE.exists() else {}
    except Exception:
        state = {}
    last  = state.get("last", -1)
    used  = set(state.get("used", []))
    # For LONG ideas, prefer the green theme (index 5) if not recently used
    if idea.direction.upper() == "LONG" and 5 not in used and last != 5:
        idx = 5
    else:
        if len(used) >= len(_REMOTION_THEMES):
            used = set()
        options = [i for i in range(len(_REMOTION_THEMES)) if i not in used and i != last]
        if not options:
            options = [i for i in range(len(_REMOTION_THEMES)) if i != last]
        idx = options[0]
    used.add(idx)
    _REMOTION_THEME_FILE.write_text(json.dumps({"last": idx, "used": list(used)}))
    theme = _REMOTION_THEMES[idx]
    log.info(f"  Remotion theme #{idx}: {theme['style']} / accent={theme['accent']}")
    return theme


def engine_24_motion_graphics(script: Dict, idea: ShortIdea, brief: Dict, chart_data: Dict) -> Dict[str, Path]:
    log.info("[24] Motion Graphics Engine — Remotion: AI-directed cinematic visuals")
    outputs = {}

    # ── Pull remotion_spec from creative director output ──────────────────────
    spec = brief.get("remotion_spec", {})
    if not spec:
        # Fallback spec if engine_15 didn't return one
        spec = {
            "layout": "cinematic_overlay",
            "bg_gradient_start": "#0a0a1a",
            "bg_gradient_end": "#000000",
            "color_primary": "#f59e0b",
            "color_secondary": "#ffffff",
            "typography": "ultra_heavy",
            "animation": "slam",
            "grain": 0.3,
            "vignette": 0.5,
            "text_position": "left",
            "hook_font_size": 100,
            "sfx_profile": "impact",
        }

    layout      = spec.get("layout", "cinematic_overlay")
    hook_comp   = _LAYOUT_TO_HOOK_COMP.get(layout, "FilmCard")
    stat_comp   = _LAYOUT_TO_STAT_COMP.get(layout, "ImpactStat")
    color1      = spec.get("color_primary", "#f59e0b")
    color2      = spec.get("color_secondary", "#ffffff")
    bg_start    = spec.get("bg_gradient_start", "#0a0a1a")
    bg_end      = spec.get("bg_gradient_end", "#000000")
    typography  = spec.get("typography", "ultra_heavy")
    animation   = spec.get("animation", "slam")
    grain       = spec.get("grain", 0.3)
    vignette    = spec.get("vignette", 0.5)
    text_pos    = spec.get("text_position", "left")
    font_size   = spec.get("hook_font_size", 100)

    log.info(f"  Remotion layout: {layout} → hook={hook_comp} stat={stat_comp} color={color1}")

    # ── Shared vis props (for preset fallback renders) ────────────────────────
    vis = {
        "colorPrimary":    color1,
        "colorSecondary":  color2,
        "bgGradientStart": bg_start,
        "bgGradientEnd":   bg_end,
        "typography":      typography,
        "animation":       animation,
        "grain":           grain,
        "vignette":        vignette,
        "textPosition":    text_pos,
        "layout":          layout,
    }

    # ── Pull AI-generated visual programs ─────────────────────────────────────
    hook_program = brief.get("hook_program", {})
    stat_program = brief.get("stat_program", {})

    # 1. Hook card (3s) — always use pre-built composition (DynamicScene too slow for hook)
    # DynamicScene has 10+ layers with blur/grain/ticker = 5s/frame × 90 frames = too long
    log.info(f"  → Using preset {hook_comp} for hook (AI-directed color+style)")
    outputs["HookCard"] = _remotion_render(hook_comp, "hook.mp4", 90, {
        "text":      script.get("hook_text", "THE AI KNEW"),
        "subtext":   script.get("hook_subtext", ""),
        "fontSize":  font_size,
        "ticker":    idea.ticker,
        "direction": idea.direction.upper(),
        **vis,
    })

    # 2. Trading chart (35s) — always rendered, themed with AI colors
    chart_props = dict(chart_data)
    chart_props["hudColor"]        = color1
    chart_props["bgGradientStart"] = bg_start
    chart_props["bgGradientEnd"]   = bg_end
    chart_props["grain"]           = grain
    chart_props["vignette"]        = vignette
    outputs["TradingChart"] = _remotion_render("TradingChart", "trading_chart.mp4", 1050, chart_props)

    # 3. Stat card (6s) — use DynamicStat only if ≤6 layers (more = too slow)
    stat_layers = stat_program.get("layers", [])
    if stat_layers and len(stat_layers) <= 6:
        log.info(f"  → Using DynamicStat for stat ({len(stat_layers)} layers)")
        outputs["StatCard"] = _remotion_render("DynamicStat", "stat.mp4", 180, {
            "program": stat_program,
        })
    else:
        log.info(f"  → Using preset {stat_comp} for stat")
        outputs["StatCard"] = _remotion_render(stat_comp, "stat.mp4", 180, {
            "ticker":    idea.ticker,
            "direction": idea.direction.upper(),
            "score":     chart_data.get("score", 65),
            "pnl":       idea.pnl,
            **vis,
        })

    # 4. CTA card (5s)
    outputs["CTACard"] = _remotion_render("CTACard", "cta_mg.mp4", 150, {
        "handle": "@nacartha",
        **vis,
    })

    return outputs


def engine_25_vfx(trading_chart_path: Path) -> Path:
    log.info("[25] VFX Engine — applying cinematic vignette + subtle push to animated chart")
    out = OUT / "chart_vfx.mp4"
    if out.exists():
        log.info("  [cache] chart_vfx.mp4")
        return out

    # TradingChart from Remotion is already animated — just add vignette for cinematic depth
    # No zoompan (would fight the chart's internal animations), just vignette + slight contrast
    _run([
        "ffmpeg", "-y", "-i", str(trading_chart_path),
        "-vf", "vignette=PI/5,eq=contrast=1.08:brightness=-0.02",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        str(out),
    ])
    log.info(f"  → chart_vfx.mp4 (vignette + contrast on Remotion animated chart)")
    return out


def engine_26_sfx(brief: Dict = None, idea=None) -> Dict[str, Path]:
    log.info("[26] SFX Engine — direction-aware sound design via ffmpeg lavfi")
    brief = brief or {}
    sfx_profile = (
        brief.get("sfx_profile")
        or brief.get("remotion_spec", {}).get("sfx_profile", "tension")
    ).lower()
    structural = brief.get("structural_idea", "").upper()

    # ── SFX profiles: each is a dict of {role: (lavfi_filter, filename)} ────
    _PROFILES = {
        "impact": {
            "ping":         ("aevalsrc='0.9*sin(2*PI*60*t)*exp(-10*t)':s=44100:d=0.5",                "ping.mp3"),
            "reveal":       ("aevalsrc='0.7*sin(2*PI*200*t)*exp(-3*t)+0.3*sin(2*PI*400*t)*exp(-5*t)':s=44100:d=0.6", "reveal.mp3"),
            "whoosh":       ("aevalsrc='0.5*sin(2*PI*(200+800*t/0.4)*t)*exp(-4*t)':s=44100:d=0.4",   "whoosh.mp3"),
            "notification": ("aevalsrc='0.6*sin(2*PI*440*t)*exp(-8*t)+0.4*sin(2*PI*880*t)*exp(-12*t)':s=44100:d=0.3", "notif.mp3"),
        },
        "tension": {
            "ping":         ("aevalsrc='0.4*sin(2*PI*220*t)*exp(-2*t)':s=44100:d=0.8",               "ping.mp3"),
            "reveal":       ("aevalsrc='0.3*sin(2*PI*110*t)+0.2*sin(2*PI*165*t)':s=44100:d=1.0",     "reveal.mp3"),
            "whoosh":       ("anoisesrc=d=0.6:c=pink:a=0.12",                                          "whoosh.mp3"),
            "notification": ("aevalsrc='0.5*sin(2*PI*330*t)*exp(-6*t)':s=44100:d=0.2",               "notif.mp3"),
        },
        "reveal": {
            "ping":         ("aevalsrc='0.6*sin(2*PI*880*t)*exp(-8*t)':s=44100:d=0.25",              "ping.mp3"),
            "reveal":       ("aevalsrc='0.4*sin(2*PI*(300+600*t/0.8)*t)*exp(-1.5*t)':s=44100:d=0.8", "reveal.mp3"),
            "whoosh":       ("aevalsrc='0.3*sin(2*PI*(100+1200*t/0.5)*t)*exp(-3*t)':s=44100:d=0.5",  "whoosh.mp3"),
            "notification": ("aevalsrc='0.7*sin(2*PI*1047*t)*exp(-10*t)':s=44100:d=0.15",            "notif.mp3"),
        },
        "dramatic": {
            "ping":         ("aevalsrc='0.8*sin(2*PI*55*t)*exp(-4*t)+0.3*sin(2*PI*110*t)*exp(-6*t)':s=44100:d=0.7", "ping.mp3"),
            "reveal":       ("aevalsrc='0.5*(sin(2*PI*80*t)+sin(2*PI*120*t))*exp(-1*t)':s=44100:d=1.2", "reveal.mp3"),
            "whoosh":       ("anoisesrc=d=0.8:c=brown:a=0.18",                                         "whoosh.mp3"),
            "notification": ("aevalsrc='0.6*sin(2*PI*440*t)*exp(-5*t)':s=44100:d=0.4",               "notif.mp3"),
        },
        "soft": {
            "ping":         ("aevalsrc='0.3*sin(2*PI*660*t)*exp(-5*t)':s=44100:d=0.4",               "ping.mp3"),
            "reveal":       ("aevalsrc='0.25*sin(2*PI*330*t)*exp(-2*t)':s=44100:d=0.6",              "reveal.mp3"),
            "whoosh":       ("anoisesrc=d=0.3:c=pink:a=0.08",                                          "whoosh.mp3"),
            "notification": ("aevalsrc='0.4*sin(2*PI*528*t)*exp(-7*t)':s=44100:d=0.2",               "notif.mp3"),
        },
    }

    # Override profile for specific structural ideas
    _IDEA_PROFILE_MAP = {
        "CONFESSION": "soft", "THRILLER": "tension", "INVESTIGATION": "reveal",
        "IMPACT": "impact",   "BROADCAST": "reveal",  "WORD_PUNCH": "dramatic",
        "SPLIT": "tension",   "EDITORIAL": "soft",
    }
    profile_key = _IDEA_PROFILE_MAP.get(structural, sfx_profile)
    profile     = _PROFILES.get(profile_key, _PROFILES["tension"])
    log.info(f"  SFX profile: {profile_key} (structural: {structural or 'default'})")

    # ── Action sounds — same for all profiles, context-placed in engine_33 ──
    # direction — SHORT=descending chart sweep, LONG=ascending
    _dir = (idea.direction.upper() if idea else "SHORT")
    _chart_sweep_freq = "(800-600*t/0.6)" if _dir == "SHORT" else "(200+600*t/0.6)"

    _ACTION_SOUNDS = {
        # keyboard_typing — 2s of rapid mechanical key clicks (~8 clicks/s)
        "keyboard_typing": (
            f"aevalsrc='0.35*sin(2*PI*2800*mod(t,0.11))*exp(-350*mod(t,0.11))+0.15*sin(2*PI*4200*mod(t,0.11))*exp(-500*mod(t,0.11))':s=44100:d=2.0",
            "keyboard_typing.mp3"
        ),
        # keyboard_typing_short — 0.5s burst (single sentence of typing)
        "keyboard_typing_short": (
            f"aevalsrc='0.3*sin(2*PI*3000*mod(t,0.12))*exp(-400*mod(t,0.12))':s=44100:d=0.5",
            "keyboard_short.mp3"
        ),
        # mouse_click — crisp single click
        "mouse_click": (
            f"aevalsrc='0.55*sin(2*PI*1400*t)*exp(-90*t)+0.2*sin(2*PI*2800*t)*exp(-180*t)':s=44100:d=0.08",
            "mouse_click.mp3"
        ),
        # double_click — two rapid clicks (opening chart, selecting trade)
        "double_click": (
            f"aevalsrc='0.5*(sin(2*PI*1400*t)*exp(-90*t)+sin(2*PI*1400*max(t-0.12,0))*exp(-90*max(t-0.12,0)))':s=44100:d=0.25",
            "double_click.mp3"
        ),
        # trade_execute — satisfying "order placed" thud + ring
        "trade_execute": (
            f"aevalsrc='0.75*(sin(2*PI*180*t)*exp(-12*t)+0.45*sin(2*PI*540*t)*exp(-20*t)+0.2*sin(2*PI*1080*t)*exp(-35*t))':s=44100:d=0.55",
            "trade_execute.mp3"
        ),
        # chart_move — price action sweep (direction-aware: SHORT=down, LONG=up)
        "chart_move": (
            f"aevalsrc='0.38*sin(2*PI*{_chart_sweep_freq}*t)*exp(-1.8*t)+0.18*sin(2*PI*{_chart_sweep_freq}*2*t)*exp(-2.5*t)':s=44100:d=0.65",
            "chart_move.mp3"
        ),
        # data_reveal — digital cascade, data populating on screen
        "data_reveal": (
            f"aevalsrc='0.28*sin(2*PI*(280+1100*t/0.75)*t)*exp(-0.9*t)+0.14*sin(2*PI*(140+550*t/0.75)*t)*exp(-1.3*t)':s=44100:d=0.75",
            "data_reveal.mp3"
        ),
        # screen_tap — sharp tap on glass/touchscreen (no random(), min 0.1s for valid mp3)
        "screen_tap": (
            f"aevalsrc='0.45*sin(2*PI*1600*t)*exp(-120*t)+0.2*sin(2*PI*3200*t)*exp(-200*t)':s=44100:d=0.12",
            "screen_tap.mp3"
        ),
        # chart_alert — AI signal detected electronic beep pair
        "chart_alert": (
            f"aevalsrc='0.48*(sin(2*PI*880*t)+0.6*sin(2*PI*1320*t))*exp(-9*t)':s=44100:d=0.28",
            "chart_alert.mp3"
        ),
        # scroll — scrolling through data/chart
        "scroll": (
            f"anoisesrc=d=0.18:c=pink:a=0.09",
            "scroll.mp3"
        ),
    }

    def _gen_sfx(lavfi_src: str, out: Path):
        if out.exists() and out.stat().st_size > 500:
            return
        out.unlink(missing_ok=True)
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", lavfi_src, "-ar", "44100", "-ac", "1", str(out)],
            capture_output=True, timeout=15,
        )
        if r.returncode != 0 or not out.exists() or out.stat().st_size < 500:
            log.warning(f"  SFX gen failed for {out.name} — using silence fallback")
            out.unlink(missing_ok=True)
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc=0:s=44100:d=0.1", "-ac", "1", str(out)],
                capture_output=True, timeout=10,
            )

    sfx = {}
    for name, (lavfi_src, fname) in profile.items():
        out = OUT / fname
        _gen_sfx(lavfi_src, out)
        sfx[name] = out
        log.info(f"  → {fname} [{profile_key}]")

    for name, (lavfi_src, fname) in _ACTION_SOUNDS.items():
        out = OUT / fname
        _gen_sfx(lavfi_src, out)
        sfx[name] = out
        log.info(f"  → {fname} [action]")

    return sfx


def engine_27_music(brief: Dict) -> Path:
    log.info("[27] Music Engine — selecting BGM from music library")
    mood = brief.get("music_mood", "urgency").lower()
    mood_map = {
        "tension":  "tension.mp3",  "urgency": "urgency.mp3",
        "dread":    "dread.mp3",    "revelation": "revelation.mp3",
        "intrigue": "intrigue.mp3",
    }
    fname = mood_map.get(mood, "urgency.mp3")
    music_path = MUSIC_DIR / fname
    if not music_path.exists():
        # fallback
        mp3s = list(MUSIC_DIR.glob("*.mp3"))
        music_path = mp3s[0] if mp3s else None
    if music_path:
        log.info(f"  → {music_path.name} [{mood}]")
    return music_path


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — POST PRODUCTION (Engines 28-33)
# ═══════════════════════════════════════════════════════════════════════════════

def engine_28_timeline(
    motion_clips: Dict[str, Path],
    nac_clip: Optional[Path],
    chart_vfx: Path,
    pai_clips: List[Path],
    narration: Path,
    nac_perf_clips: List[Path] = None,
    fmt: str = "short",
) -> Path:
    log.info(f"[28] Timeline Engine — assembling {fmt} master timeline")
    out = OUT / "timeline_raw.mp4"
    if out.exists():
        log.info("  [cache] timeline_raw.mp4")
        return out

    nac_perf_clips = nac_perf_clips or []
    concat_file    = OUT / "concat.txt"
    ordered: List[Path] = []

    def _add_clip(path: Optional[Path], label: str, trim_s: float = 0):
        if not path or not path.exists():
            return
        if trim_s > 0:
            tmp = OUT / f"trimmed_{path.stem}.mp4"
            if not tmp.exists():
                _run(["ffmpeg","-y","-i",str(path),"-t",str(trim_s),
                      "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                      "-c:v","libx264","-pix_fmt","yuv420p",str(tmp)])
            ordered.append(tmp)
        else:
            ordered.append(path)
        log.info(f"  + {label}")

    # ── Hook composition — DynamicScene or preset ────────────────────────────
    # DynamicScene trumps legacy HookCard if it was rendered
    for hook_key in ("DynamicScene", "HookCard", "FilmCard", "TypoSlam",
                     "GlitchHook", "SplitReveal", "WordPunch", "NewsFlash"):
        if hook_key in motion_clips and motion_clips[hook_key].exists():
            _add_clip(motion_clips[hook_key], f"{hook_key} (Remotion hook, 3s)")
            break

    # ── NAC hook reaction clip (engine_20 first clip, 4s) ───────────────────
    if nac_perf_clips:
        _add_clip(nac_perf_clips[0], "NAC hook reaction (PAI perf)", trim_s=4)

    # ── PAI cinematic B-roll clip 1 (char-ref clip, 8s trimmed to 6s) ───────
    if len(pai_clips) > 0:
        _add_clip(pai_clips[0], f"PAI char-ref ({pai_clips[0].stem})", trim_s=6)

    # ── NAC analysis clip (engine_20 second clip, 6s) ───────────────────────
    if len(nac_perf_clips) > 1 and fmt == "long":
        _add_clip(nac_perf_clips[1], "NAC analysis (PAI perf)", trim_s=6)

    # ── Chart VFX (core trade explanation ~35s) ──────────────────────────────
    _add_clip(chart_vfx, "Chart VFX (animated trading chart)", trim_s=0)

    # ── PAI B-roll clip 2 (environment, 6s) — adds visual break ─────────────
    if len(pai_clips) > 1:
        _add_clip(pai_clips[1], f"PAI B-roll ({pai_clips[1].stem})", trim_s=6)

    # ── Long format: NAC conclusion + more B-roll ────────────────────────────
    if fmt == "long":
        if len(nac_perf_clips) > 2:
            _add_clip(nac_perf_clips[2], "NAC conclusion (PAI perf)", trim_s=4)
        if len(pai_clips) > 2:
            _add_clip(pai_clips[2], f"PAI B-roll 3 ({pai_clips[2].stem})", trim_s=6)

    # ── Stat composition ─────────────────────────────────────────────────────
    for stat_key in ("DynamicStat", "ImpactStat", "WinLoseSlam", "DataReveal", "StatCard"):
        if stat_key in motion_clips and motion_clips[stat_key].exists():
            _add_clip(motion_clips[stat_key], f"{stat_key} (Remotion stat, 6s)")
            break

    # ── CTA card ─────────────────────────────────────────────────────────────
    _add_clip(motion_clips.get("CTACard"), "CTACard (Remotion CTA)")

    if not ordered:
        raise RuntimeError("[28] Timeline Engine: no clips to assemble — all production engines failed")

    # Normalize all clips to 1080x1920 before concat
    normalized = []
    for i, clip in enumerate(ordered):
        norm = OUT / f"norm_{i:02d}.mp4"
        if not norm.exists():
            _run([
                "ffmpeg", "-y", "-i", str(clip),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-an",  # strip audio - will add narration later
                str(norm),
            ])
        normalized.append(norm)

    with open(concat_file, "w") as f:
        for p in normalized:
            if Path(p).exists():
                f.write(f"file '{p}'\n")

    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        str(out),
    ])
    log.info(f"  → timeline_raw.mp4 ({_duration(out):.1f}s, {len(normalized)} clips)")
    return out


def engine_29_camera_motion(video: Path, brief: Dict = None) -> Path:
    log.info("[29] Camera Motion Engine — direction-aware camera motion")
    out = OUT / "camera.mp4"
    if out.exists():
        log.info("  [cache] camera.mp4")
        return out

    brief = brief or {}
    camera_style  = brief.get("camera_style", "cinematic").lower()
    structural    = brief.get("structural_idea", "").upper()

    dur          = _duration(video)
    total_frames = int(dur * 30)
    if total_frames < 2:
        import shutil; shutil.copy(video, out); return out

    # ── Camera motion profiles ───────────────────────────────────────────────
    # confessional — very slow intimate push-in (1.00 → 1.03)
    # investigative — slow pull-back then push (1.04 → 1.00 → 1.03)
    # broadcast — stable, almost no motion (1.00 → 1.01)
    # kinetic — faster push with vertical drift (1.00 → 1.08, slight y drift)
    # cinematic — smooth push-in (1.00 → 1.05, center lock)
    # documentary — slight handheld simulation via zoompan jitter
    _IDEA_STYLE = {
        "CONFESSION":    "confessional",
        "THRILLER":      "kinetic",
        "INVESTIGATION": "investigative",
        "IMPACT":        "kinetic",
        "BROADCAST":     "broadcast",
        "WORD_PUNCH":    "kinetic",
        "SPLIT":         "cinematic",
        "EDITORIAL":     "confessional",
    }
    style = _IDEA_STYLE.get(structural, camera_style)
    log.info(f"  Camera style: {style} (structural: {structural or camera_style})")

    if style == "confessional":
        # very slow push-in 1.00 → 1.03
        vf = (
            f"zoompan=z='1+0.03*in/{total_frames}'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s=1080x1920:fps=30"
        )
    elif style == "investigative":
        # pull back then push: zoom starts at 1.03, goes to 1.00, then 1.035
        vf = (
            f"zoompan=z='if(lt(in,{total_frames//2}),1.03-0.03*in/{total_frames//2},1.0+0.035*(in-{total_frames//2})/{total_frames//2})'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s=1080x1920:fps=30"
        )
    elif style == "broadcast":
        # nearly static, micro-zoom 1.00 → 1.01
        vf = (
            f"zoompan=z='1+0.01*in/{total_frames}'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s=1080x1920:fps=30"
        )
    elif style == "kinetic":
        # faster push 1.00 → 1.08 with slight upward drift
        vf = (
            f"zoompan=z='1+0.08*in/{total_frames}'"
            f":x='iw/2-(iw/zoom/2)':y='max(0,ih/2-(ih/zoom/2)-{total_frames//4}*in/{total_frames})'"
            f":d=1:s=1080x1920:fps=30"
        )
    elif style == "documentary":
        # subtle hand-held feel — micro jitter via periodic oscillation
        vf = (
            f"zoompan=z='1.02+0.01*sin(2*PI*in/90)'"
            f":x='iw/2-(iw/zoom/2)+4*sin(2*PI*in/45)':y='ih/2-(ih/zoom/2)+3*sin(2*PI*in/60)'"
            f":d=1:s=1080x1920:fps=30"
        )
    else:
        # cinematic — smooth push 1.00 → 1.05
        vf = (
            f"zoompan=z='1+0.05*in/{total_frames}'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s=1080x1920:fps=30"
        )

    _run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ], check=False)
    if not out.exists():
        import shutil; shutil.copy(video, out)
        log.warning(f"  zoompan failed — copying unchanged")
    log.info(f"  → camera.mp4 (style: {style})")
    return out


def _generate_narration(narration_text: str) -> Path:
    out = OUT / "narration.mp3"
    if out.exists():
        log.info("  [cache] narration.mp3")
        return out
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID_NAC",
               os.environ.get("ELEVENLABS_VOICE_ID_EN","pNInz6obpgDQGcFmaJgB"))
    log.info(f"  ElevenLabs → narration.mp3 (voice: {voice_id[:8]}...)")
    payload = json.dumps({
        "text": narration_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.42, "similarity_boost": 0.82},
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=payload,
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out.write_bytes(resp.read())
    log.info(f"  → narration.mp3 ({out.stat().st_size//1024} KB)")
    return out


def engine_30_caption(video: Path, script: Dict, brief: Dict = None) -> Path:
    log.info("[30] Caption Engine — drawtext captions (no libass required)")
    out = OUT / "captioned.mp4"
    if out.exists():
        log.info("  [cache] captioned.mp4")
        return out

    brief        = brief or {}
    structural   = brief.get("structural_idea", "").upper()
    color_spec   = brief.get("remotion_spec", {})
    accent_hex   = color_spec.get("color_primary", "#f59e0b").lstrip("#")

    # accent_hex → drawtext color format 0xRRGGBB
    accent_draw = "0x" + accent_hex.upper()

    full_text = script.get("full_narration", "")
    words     = full_text.split()
    dur       = _duration(video)
    if not words or dur < 1:
        import shutil; shutil.copy(video, out); return out

    wps        = len(words) / dur
    chunk_size = 6   # words per caption line

    # ── Caption style per structural idea ────────────────────────────────────
    # Position: bottom-third (y = H*0.78), centered
    # Font: bold, white with black outline (works without libass)
    _CAPTION_STYLES = {
        "CONFESSION":    {"size": 44, "color": "white",        "shadow": 3},
        "THRILLER":      {"size": 48, "color": "white",        "shadow": 4},
        "INVESTIGATION": {"size": 40, "color": "0xE0F7FA",     "shadow": 3},
        "IMPACT":        {"size": 52, "color": "white",        "shadow": 5},
        "BROADCAST":     {"size": 44, "color": "white",        "shadow": 3},
        "WORD_PUNCH":    {"size": 56, "color": "white",        "shadow": 5},
        "SPLIT":         {"size": 44, "color": "white",        "shadow": 3},
        "EDITORIAL":     {"size": 38, "color": "0xFFFDE7",     "shadow": 2},
    }
    style = _CAPTION_STYLES.get(structural, {"size": 44, "color": "white", "shadow": 3})

    # Build drawtext filter chain — one overlay per caption block
    filters = []
    current_word = 0
    while current_word < len(words):
        chunk   = words[current_word:current_word + chunk_size]
        t_start = current_word / wps
        t_end   = min((current_word + len(chunk)) / wps, dur)
        text    = (
            " ".join(chunk)
            .replace("\\", "\\\\")   # backslash first
            .replace("'",  "’") # curly apostrophe — avoids shell quoting nightmare
            .replace(":",  "\\:")
            .replace(",",  "\\,")
            .replace("%",  "\\%")    # % is a format specifier in drawtext
            .replace("$",  "\\$")    # $ is a format specifier in drawtext
            .replace("[",  "\\[")
            .replace("]",  "\\]")
        )

        # every-other chunk: alternate white / accent color for visual rhythm
        color = accent_draw if (current_word // chunk_size) % 3 == 2 else style["color"]

        filters.append(
            f"drawtext=text='{text}'"
            f":fontsize={style['size']}"
            f":fontcolor={color}"
            f":borderw={style['shadow']}"
            f":bordercolor=black@0.85"
            f":x=(w-text_w)/2"
            f":y=h*0.78"
            f":enable='between(t,{t_start:.3f},{t_end:.3f})'"
        )
        current_word += chunk_size

    if not filters:
        import shutil; shutil.copy(video, out); return out

    vf_chain = ",".join(filters)
    r = _run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", vf_chain,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy",
        str(out),
    ], check=False)

    if not out.exists():
        import shutil; shutil.copy(video, out)
        log.warning(f"  Caption drawtext failed — ffmpeg stderr: {r.stderr[-300:]}")
    else:
        log.info(f"  → captioned.mp4 ({len(filters)} blocks, style: {structural or 'default'})")
    return out


def engine_31_transition(video: Path) -> Path:
    log.info("[31] Transition Engine — fade in (0.5s) + fade out (1s)")
    out = OUT / "transitioned.mp4"
    if out.exists():
        log.info("  [cache] transitioned.mp4")
        return out
    dur = _duration(video)
    fade_out_start = max(0, dur - 1.0)
    _run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_start:.2f}:d=1.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy",
        str(out),
    ])
    log.info(f"  → transitioned.mp4 (fade in + fade out)")
    return out


def engine_32_color_grade(video: Path) -> Path:
    log.info("[32] Color Grading Engine — NacArtha dark look + amber warmth")
    out = OUT / "graded.mp4"
    if out.exists():
        log.info("  [cache] graded.mp4")
        return out
    # Curves: lift blacks slightly, boost amber/warmth, increase contrast
    vf = (
        "eq=contrast=1.10:brightness=-0.03:saturation=1.15:gamma=0.93,"
        "curves=r='0/0 0.45/0.47 1/1'"
        ":g='0/0 0.5/0.50 1/1'"
        ":b='0/0 0.5/0.48 1/0.98'"
    )
    _run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy",
        str(out),
    ])
    log.info(f"  → graded.mp4 (dark look + amber warmth)")
    return out


def engine_32b_outro(script: Dict) -> tuple:
    """Render Remotion outro card + generate 'please follow for more' voiceover."""
    log.info("[32b] Outro Engine — NacArtha logo card + follow voiceover")
    outro_video = OUT / "outro.mp4"
    outro_audio = OUT / "outro_follow.mp3"

    # Render logo card via Remotion (use nnn.png NacArtha logo)
    if not outro_video.exists():
        props = {"logoPath": None, "handle": "@nacartha"}  # logo loaded via staticFile("nac_logo.png")
        _run([
            "npx", "remotion", "render",
            "remotion/src/index.js", "Outro", str(outro_video),
            "--props", json.dumps(props),
            "--width", "1080", "--height", "1920",
        ], timeout=90, cwd=str(CONTENT_ENGINE))
        log.info(f"  → outro.mp4 (Remotion logo card with nnn.png)")

    # Generate "please follow for more" voiceover
    if not outro_audio.exists():
        api_key = os.environ["ELEVENLABS_API_KEY"]
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID_NAC",
                   os.environ.get("ELEVENLABS_VOICE_ID_EN","pNInz6obpgDQGcFmaJgB"))
        log.info(f"  ElevenLabs → outro_follow.mp3")
        payload = json.dumps({
            "text": "Please follow NacArtha for more daily AI trading insights.",
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.50, "similarity_boost": 0.80},
        }).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=payload,
            headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            outro_audio.write_bytes(resp.read())
        log.info(f"  → outro_follow.mp3 ({outro_audio.stat().st_size//1024} KB)")

    return outro_video, outro_audio


def engine_33_render(
    video: Path,
    narration: Path,
    music_path: Optional[Path],
    sfx: Dict[str, Path],
    script: Dict,
    outro_video: Path,
    outro_audio: Path,
) -> Path:
    log.info("[33] Render Engine — final audio mix + outro + encode at quality settings")
    out = OUT / "final.mp4"
    if out.exists():
        log.info("  [cache] final.mp4")
        return out

    dur     = script.get("duration_seconds", 55.0)
    nar_dur = _duration(narration)

    # ── Dynamic SFX timeline — every sound placed at the right story moment ──
    # Each tuple: (sfx_name, fraction_of_dur 0.0-1.0, volume 0.0-1.0)
    # Fraction × dur = absolute placement time in seconds.
    _SFX_PLAN = [
        # Opening — NAC starts working / hook lands
        ("keyboard_typing",       0.00,  0.38),
        ("chart_alert",           0.04,  0.55),   # AI signal detected
        ("ping",                  0.06,  0.48),   # hook card slam
        # B-roll / setup
        ("reveal",                0.14,  0.42),   # visual reveal / B-roll in
        ("scroll",                0.19,  0.32),   # scrolling chart data
        ("mouse_click",           0.22,  0.50),   # selecting trade
        # Trade execution
        ("double_click",          0.27,  0.52),   # confirming order
        ("trade_execute",         0.30,  0.62),   # ORDER PLACED — loudest moment
        # Chart appears on screen
        ("whoosh",                0.36,  0.38),   # chart sweeps in
        ("keyboard_typing_short", 0.42,  0.30),   # typing mid-analysis
        ("screen_tap",            0.46,  0.40),   # touching chart point
        # Market moves
        ("chart_move",            0.55,  0.50),   # price moves (direction-aware)
        ("scroll",                0.60,  0.28),   # scrolling through result
        ("keyboard_typing_short", 0.63,  0.26),   # more typing
        # Stats reveal
        ("data_reveal",           0.68,  0.45),   # data populates on screen
        ("screen_tap",            0.72,  0.38),   # tapping data point
        ("notification",          0.78,  0.52),   # result notification
        # Trade close
        ("mouse_click",           0.84,  0.42),   # reviewing
        ("double_click",          0.87,  0.48),   # confirming exit
        ("trade_execute",         0.90,  0.60),   # TRADE CLOSED
        ("chart_alert",           0.94,  0.38),   # final AI summary beep
    ]

    # Extra events for long format (>200s) — fill the middle sections
    _SFX_EXTRA_LONG = [
        ("keyboard_typing",       0.33,  0.30),
        ("chart_move",            0.43,  0.44),
        ("screen_tap",            0.50,  0.32),
        ("data_reveal",           0.57,  0.38),
        ("scroll",                0.65,  0.26),
        ("keyboard_typing_short", 0.70,  0.24),
        ("chart_alert",           0.75,  0.42),
    ]

    sfx_plan = list(_SFX_PLAN) + (_SFX_EXTRA_LONG if dur > 200 else [])

    sfx_inputs  = []
    sfx_filters = []
    sfx_streams = []
    sfx_map_idx = 2  # 0=video, 1=narration, 2+=sfx/music

    for sfx_name, fraction, vol in sorted(sfx_plan, key=lambda x: x[1]):
        t_start = fraction * dur
        if t_start >= dur - 0.3 or sfx_name not in sfx or not sfx[sfx_name].exists():
            continue
        delay_ms = int(t_start * 1000)
        label    = f"sfx{sfx_map_idx}"
        sfx_inputs  += ["-i", str(sfx[sfx_name])]
        sfx_filters.append(
            f"[{sfx_map_idx}:a]adelay={delay_ms}|{delay_ms},volume={vol:.2f}[{label}]"
        )
        sfx_streams.append(f"[{label}]")
        sfx_map_idx += 1

    log.info(f"  SFX: {len(sfx_streams)} sound events across {dur:.0f}s timeline")
    inputs = ["-i", str(video), "-i", str(narration)] + sfx_inputs

    # Music input
    if music_path and music_path.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]
        music_label = f"[{sfx_map_idx}:a]"
        fade_s = max(0, dur - 3.0)
        sfx_filters.append(
            f"{music_label}volume=0.12,afade=t=in:st=0:d=2,afade=t=out:st={fade_s:.1f}:d=3[bgm]"
        )
        sfx_streams.append("[bgm]")

    # Mix narration + all sfx + bgm
    all_audio = ["[1:a]volume=1.0[nar]"] + sfx_filters
    mix_inputs = "[nar]" + "".join(sfx_streams)
    n_mix = 1 + len(sfx_streams)
    all_audio.append(f"{mix_inputs}amix=inputs={n_mix}:duration=longest[aout]")

    fc = ";".join(all_audio)
    body_out = OUT / "body.mp4"
    _run([
        "ffmpeg", "-y",
    ] + inputs + [
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[aout]",
        "-t", str(dur),
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(body_out),
    ])

    # Add outro (logo card + follow voiceover) at the end
    outro_with_audio = OUT / "outro_final.mp4"
    outro_dur = _duration(outro_video)
    _run([
        "ffmpeg", "-y",
        "-i", str(outro_video),
        "-i", str(outro_audio),
        "-map", "0:v",
        "-map", "1:a",
        "-t", str(outro_dur),
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(outro_with_audio),
    ])

    # Concatenate body + outro
    concat_file = OUT / "final_concat.txt"
    concat_file.write_text(f"file '{body_out}'\nfile '{outro_with_audio}'\n")
    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(out),
    ])

    size_mb = out.stat().st_size / 1_000_000
    total_dur = _duration(out)
    log.info(f"  → final.mp4 ({size_mb:.1f} MB, {total_dur:.1f}s, body {dur:.1f}s + outro {outro_dur:.1f}s)")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — PUBLISHING LAYER (Engines 34-38)
# ═══════════════════════════════════════════════════════════════════════════════

_COVER_HISTORY_FILE = Path.home() / ".nacartha_cover_history"
_COVER_DIRECTIONS = [
    "Documentary", "AI Command Center", "Cinematic Poster", "Breaking News",
    "Dashboard Focus", "Strategy Blueprint", "Portfolio Story",
    "Market Investigation", "AI Laboratory", "Financial Intelligence",
]

def _cover_load_history() -> dict:
    try:
        return json.loads(_COVER_HISTORY_FILE.read_text()) if _COVER_HISTORY_FILE.exists() else {}
    except Exception:
        return {}

def _cover_save_history(direction: str, colors: str, layout: str):
    h = _cover_load_history()
    recent = h.get("recent", [])
    recent.append({"direction": direction, "colors": colors, "layout": layout})
    recent = recent[-8:]  # keep last 8
    _COVER_HISTORY_FILE.write_text(json.dumps({"recent": recent}))

def _cover_ai_direction(script: Dict, idea: ShortIdea, research) -> dict:
    """Ask Claude to act as Cover Engine Creative Director and decide the design."""
    history = _cover_load_history()
    recent_str = json.dumps(history.get("recent", []))
    hook = script.get("hook_text", "")
    narration = script.get("full_narration", "")[:300]

    SYSTEM = """You are the Cover Engine Creative Director for NacArtha AI Studio.
Your job: design a unique, story-driven YouTube cover (1280×720) that maximizes click-through.

Rules:
- NEVER repeat a direction/layout/color combo from recent history
- Story comes first — the cover must communicate the episode in 1 second
- NAC avatar: use ONLY for educational, AI explanation, weekly report, build-in-public, strategy videos
- NAC avatar: NEVER for pure trade recaps, chart stories, or news-driven shorts
- Logo: always present, never dominant
- Feel like a movie poster, not a thumbnail template

Available directions: Documentary, AI Command Center, Cinematic Poster, Breaking News, Dashboard Focus, Strategy Blueprint, Portfolio Story, Market Investigation, AI Laboratory, Financial Intelligence

Respond ONLY with valid JSON."""

    USER = f"""Episode:
Ticker: {idea.ticker} | Direction: {idea.direction} | PnL: {idea.pnl:+.0f} | Score: {idea.score}%
Strategy: {idea.strategy} | Category: {idea.category}
Hook: {hook}
Story: {narration}

Recent covers (AVOID repeating): {recent_str}

Choose a creative direction and return:
{{
  "direction": "<one of the 10 directions>",
  "use_nac_avatar": false,
  "color_theme": "<bearish|bullish|ai|crypto|forex|innovation>",
  "primary_focus": "<what viewer sees first in 1 word>",
  "headline": "<max 4 words, all caps, punchy>",
  "sub_headline": "<max 5 words, supports headline>",
  "tag_chip": "<3-4 word chip label e.g. AI CAUGHT THIS>",
  "use_chart_bg": true,
  "use_stat_grid": false,
  "layout_style": "<split|overlay|minimal|grid|poster>",
  "reason": "<one sentence why this direction fits this story>"
}}"""

    result = _json_claude(SYSTEM, USER, max_tokens=600)
    log.info(f"  Cover AI direction: {result.get('direction')} | layout: {result.get('layout_style')}")
    log.info(f"  Reason: {result.get('reason','')[:100]}")
    return result

def _cover_extract_frame(video_path: Path, t: float = 1.5) -> Optional[Path]:
    """Extract a still frame from a video at time t seconds."""
    if not video_path or not video_path.exists():
        return None
    out = OUT / f"_cover_frame_{video_path.stem}.png"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path),
             "-frames:v", "1", "-q:v", "2", str(out)],
            capture_output=True, timeout=15
        )
        return out if out.exists() else None
    except Exception:
        return None
    return idx


def _cover_fonts(font_path: str):
    from PIL import ImageFont
    try:
        return {
            "xs":  ImageFont.truetype(font_path, 18),
            "sm":  ImageFont.truetype(font_path, 24),
            "md":  ImageFont.truetype(font_path, 32),
            "lg":  ImageFont.truetype(font_path, 48),
            "xl":  ImageFont.truetype(font_path, 64),
            "xxl": ImageFont.truetype(font_path, 96),
            "h":   ImageFont.truetype(font_path, 130),
        }
    except Exception:
        d = ImageFont.load_default()
        return {k: d for k in ["xs","sm","md","lg","xl","xxl","h"]}


def _cover_sparkline(draw, prices, x, y, w, h, dir_color, show_labels=True):
    """Draw a glowing sparkline with entry/exit dots."""
    from PIL import ImageFont
    if len(prices) < 2:
        return
    mn, mx = min(prices), max(prices)
    rng = mx - mn or 1
    pts = [(x + int(i / (len(prices)-1) * w),
            y + h - int((p - mn) / rng * h))
           for i, p in enumerate(prices)]
    # Fill
    fp = pts + [(pts[-1][0], y + h), (pts[0][0], y + h)]
    draw.polygon(fp, fill=(*dir_color, 25))
    # Glow line
    for off in range(-3, 4):
        draw.line(pts, fill=(*dir_color, max(0, 180 - abs(off)*55)), width=abs(off)*2 + 1)
    # Grid
    for gy in range(1, 4):
        yy = y + int(gy * h / 3)
        draw.line([(x, yy), (x + w, yy)], fill=(255, 255, 255, 12), width=1)
    if show_labels:
        ei = max(0, int(len(pts) * 0.78))
        xi = min(len(pts)-1, int(len(pts) * 0.94))
        draw.ellipse([(pts[ei][0]-9, pts[ei][1]-9), (pts[ei][0]+9, pts[ei][1]+9)],
                     fill=(34, 197, 94), outline=(255, 255, 255, 200))
        draw.ellipse([(pts[xi][0]-9, pts[xi][1]-9), (pts[xi][0]+9, pts[xi][1]+9)],
                     fill=(239, 68, 68), outline=(255, 255, 255, 200))
        try:
            f = ImageFont.truetype(str(ASSETS / "font.ttf"), 20)
        except Exception:
            f = ImageFont.load_default()
        draw.text((pts[ei][0]+12, pts[ei][1]-12), f"${prices[ei]:.0f}", font=f, fill=(34, 197, 94))
        draw.text((pts[xi][0]+12, pts[xi][1]-12), f"${prices[xi]:.0f}", font=f, fill=(239, 68, 68))


def engine_34_cover(script: Dict, idea: ShortIdea, research=None,
                    pai_clips: Optional[List[Path]] = None,
                    chart_video: Optional[Path] = None) -> Path:
    log.info("[34] Cover Engine — AI Creative Director (1280×720)")
    out = OUT / "cover.jpg"
    if out.exists():
        log.info("  [cache] cover.jpg")
        return out
    try:
        from PIL import Image, ImageDraw, ImageFont
        import yfinance as yf

        W, H = 1280, 720
        is_short  = idea.direction.upper() == "SHORT"
        dir_arrow = "▼" if is_short else "▲"
        pnl_str   = f"${idea.pnl:+.0f}"
        font_path = str(ASSETS / "font.ttf")
        F         = _cover_fonts(font_path)

        # ── 1. AI Creative Director decides everything ─────────────────────
        ai = _cover_ai_direction(script, idea, research)
        direction    = ai.get("direction", "Dashboard Focus")
        headline     = ai.get("headline", idea.ticker).upper()
        sub_headline = ai.get("sub_headline", idea.direction).upper()
        tag_chip     = ai.get("tag_chip", "AI SIGNAL").upper()
        layout_style = ai.get("layout_style", "split")
        use_chart_bg = ai.get("use_chart_bg", True)
        use_stat_grid= ai.get("use_stat_grid", False)
        use_nac      = ai.get("use_nac_avatar", False)
        color_theme  = ai.get("color_theme", "bearish" if is_short else "bullish")

        # ── 2. Color palette from theme ────────────────────────────────────
        PALETTES = {
            "bearish":     {"accent": (239, 68, 68),   "glow": (180, 30, 30),  "bg": (8, 4, 4)},
            "bullish":     {"accent": (34, 197, 94),   "glow": (20, 100, 40),  "bg": (4, 8, 4)},
            "ai":          {"accent": (0, 229, 255),   "glow": (0, 80, 120),   "bg": (4, 6, 16)},
            "crypto":      {"accent": (249, 115, 22),  "glow": (120, 50, 10),  "bg": (8, 5, 2)},
            "forex":       {"accent": (99, 102, 241),  "glow": (40, 40, 120),  "bg": (4, 4, 14)},
            "innovation":  {"accent": (168, 85, 247),  "glow": (70, 20, 120),  "bg": (6, 4, 12)},
        }
        pal = PALETTES.get(color_theme, PALETTES["bearish"])
        AC  = pal["accent"]    # main accent color
        BG  = pal["bg"]        # deep background
        AMB = (245, 159, 11)   # always-amber brand
        dir_color = (239, 68, 68) if is_short else (34, 197, 94)
        pnl_color = (239, 68, 68) if idea.pnl < 0 else (34, 197, 94)

        # ── 3. Fetch price data ────────────────────────────────────────────
        try:
            hist   = yf.Ticker(idea.ticker).history(period="1mo", interval="1d")
            prices = [float(r.Close) for r in hist.itertuples()]
        except Exception:
            prices = []

        # ── 4. Extract visual assets ───────────────────────────────────────
        nac_frame = None
        if use_nac and pai_clips:
            for clip in pai_clips:
                nac_frame = _cover_extract_frame(clip, t=2.0)
                if nac_frame:
                    break

        chart_frame = None
        if use_chart_bg and chart_video:
            chart_frame = _cover_extract_frame(chart_video, t=5.0)

        # ── 5. Shared drawing helpers ──────────────────────────────────────
        img  = Image.new("RGBA", (W, H), (*BG, 255))
        draw = ImageDraw.Draw(img, "RGBA")

        def _bg_grid(spacing=60, alpha=5):
            for yy in range(0, H, spacing):
                draw.line([(0, yy), (W, yy)], fill=(255,255,255,alpha), width=1)
            for xx in range(0, W, spacing):
                draw.line([(xx, 0), (xx, H)], fill=(255,255,255,alpha), width=1)

        def _glow_radial(cx, cy, radius, color, max_alpha=60):
            for r in range(radius, 0, -10):
                a = max(0, int(max_alpha * (1 - r/radius)))
                draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(*color, a))

        def _bottom_bar():
            draw.rectangle([(0, H-54), (W, H)], fill=(8, 8, 16))
            draw.rectangle([(0, H-54), (5, H)], fill=AC)
            if NAC_LOGO.exists():
                logo = Image.open(str(NAC_LOGO)).convert("RGBA").resize((44, 44))
                img.paste(logo, (W-64, H-49), mask=logo.split()[3])
            draw.text((18, H-40), "NacArtha AI Lab  ·  nacartha.ai", font=F["sm"], fill=(160, 150, 120))

        def _tag(text, x, y, bg_color=None, text_color=(6,6,12)):
            bc = bg_color or (*AMB, 230)
            w2 = len(text) * 11 + 18
            draw.rounded_rectangle([(x, y), (x+w2, y+30)], radius=5, fill=bc)
            draw.text((x+9, y+5), text, font=F["xs"], fill=text_color)

        def _text_lines(text, max_chars=22):
            words, lines, cur = text.split(), [], []
            for w in words:
                if sum(len(x)+1 for x in cur+[w]) <= max_chars:
                    cur.append(w)
                else:
                    if cur: lines.append(" ".join(cur))
                    cur = [w]
            if cur: lines.append(" ".join(cur))
            return lines[:2]

        def _stat_box(bx, by, bw, bh, val, lbl, clr):
            draw.rounded_rectangle([(bx, by), (bx+bw, by+bh)], radius=10,
                                   fill=(0,0,0,140), outline=(*clr, 150))
            draw.text((bx+14, by+8),  lbl, font=F["xs"], fill=(130,130,130))
            draw.text((bx+14, by+32), str(val)[:14], font=F["lg"], fill=clr)

        # ── 6. Render by layout_style ──────────────────────────────────────

        # ── SPLIT — chart right, text left ────────────────────────────────
        if layout_style == "split":
            _glow_radial(W, 0, 500, AC, 50)
            _bg_grid(60, 5)
            # Composite chart frame or sparkline on right
            if chart_frame and chart_frame.exists():
                cf = Image.open(str(chart_frame)).convert("RGBA").resize((580, H-80))
                img.paste(cf, (680, 40), mask=cf.split()[3])
                draw.rectangle([(680, 0), (W, H)], fill=(0,0,0,80))
            elif prices:
                draw.rectangle([(650, 50), (W-10, H-60)], fill=(10,10,22))
                _cover_sparkline(draw, prices, 660, 60, 590, H-130, dir_color)
            _tag(tag_chip, 28, 26, bg_color=(*AMB,230))
            hl = _text_lines(headline, 20)
            for li, ln in enumerate(hl):
                draw.text((28, 70+li*66), ln, font=F["xl"],
                          fill=(255,255,255) if li==0 else AMB)
            draw.text((28, 218), idea.ticker, font=F["h"], fill=(255,255,255))
            draw.rounded_rectangle([(28, 368), (320, 434)], radius=11, fill=dir_color)
            draw.text((46, 375), f"{dir_arrow}  {idea.direction.upper()}", font=F["lg"], fill=(255,255,255))
            draw.rounded_rectangle([(336, 368), (490, 434)], radius=11,
                                   fill=(0,0,0,160), outline=(*AMB,255))
            draw.text((348, 375), f"AI {idea.score}%", font=F["lg"], fill=AMB)
            draw.text((28, 452), pnl_str, font=F["xxl"], fill=pnl_color)
            draw.text((28, 562), f"{sub_headline}  ·  @nacartha", font=F["md"], fill=(150,150,150))

        # ── OVERLAY — full bleed bg + text punched through ─────────────────
        elif layout_style == "overlay":
            if chart_frame and chart_frame.exists():
                cf = Image.open(str(chart_frame)).convert("RGB").resize((W, H))
                img.paste(cf, (0, 0))
                draw.rectangle([(0,0),(W,H)], fill=(0,0,0,165))
            elif prices:
                _cover_sparkline(draw, prices, 0, 60, W, H-120, dir_color, show_labels=False)
                draw.rectangle([(0,0),(W,H)], fill=(0,0,0,150))
            draw.rectangle([(0,0),(8,H)], fill=AC)
            draw.rectangle([(0,0),(W,6)], fill=AMB)
            _tag(tag_chip, 20, 16, bg_color=(*AC,220), text_color=(255,255,255))
            hl = _text_lines(headline, 26)
            for li, ln in enumerate(hl):
                draw.text((20, 60+li*68), ln, font=F["xl"],
                          fill=(255,255,255) if li==0 else AMB)
            draw.text((20, 216), idea.ticker, font=F["h"], fill=(255,255,255))
            draw.rounded_rectangle([(20, 364), (250, 432)], radius=10, fill=(*dir_color,220))
            draw.text((34, 374), f"{dir_arrow} {idea.direction.upper()}", font=F["lg"], fill=(255,255,255))
            draw.rounded_rectangle([(268, 364), (430, 432)], radius=10,
                                   fill=(0,0,0,170), outline=(*AMB,255))
            draw.text((280, 374), f"AI {idea.score}%", font=F["lg"], fill=AMB)
            draw.text((20, 446), pnl_str, font=F["xxl"], fill=pnl_color)
            if prices and len(prices)>2:
                ei = max(0, int(len(prices)*0.78))
                xi = min(len(prices)-1, int(len(prices)*0.94))
                draw.text((20,556), f"Entry ${prices[ei]:.0f}  →  Exit ${prices[xi]:.0f}",
                          font=F["md"], fill=(170,170,170))

        # ── MINIMAL — typographic, no chart ───────────────────────────────
        elif layout_style == "minimal":
            _glow_radial(W//2, H//2, 600, AC, 35)
            for yy in range(0, H, 80):
                draw.line([(0,yy),(W,yy)], fill=(255,255,255,3), width=1)
            draw.rectangle([(0,0),(W,8)], fill=AC)
            draw.rectangle([(0,0),(8,H)], fill=AMB)
            _tag(tag_chip, 20, 18, bg_color=(*AC,220), text_color=(255,255,255))
            draw.text((20, 70), headline, font=F["xxl"], fill=(255,255,255))
            draw.text((20, 200), idea.ticker, font=F["h"], fill=AC)
            draw.text((20, 360), pnl_str, font=F["h"], fill=pnl_color)
            draw.text((20, 500), sub_headline, font=F["xl"], fill=AMB)
            draw.text((20, 578), f"AI Score {idea.score}%  ·  @nacartha", font=F["md"], fill=(150,150,150))
            if prices:
                _cover_sparkline(draw, prices, W-360, H-280, 340, 240, dir_color, show_labels=False)

        # ── GRID — 2-column stat dashboard ────────────────────────────────
        elif layout_style == "grid":
            _bg_grid(40, 14)
            draw.rectangle([(0,0),(W,8)], fill=AMB)
            draw.rectangle([(0,0),(8,H)], fill=dir_color)
            draw.text((W//2+20, 16), idea.direction.upper(), font=F["h"],
                      fill=(*dir_color, 18))
            _tag(tag_chip, 20, 18)
            hl = _text_lines(headline, 28)
            for li, ln in enumerate(hl):
                draw.text((20, 60+li*54), ln, font=F["lg"],
                          fill=AMB if li==0 else (210,210,210))
            draw.text((20, 178), idea.ticker, font=F["h"], fill=(255,255,255))
            boxes = [
                (f"{dir_arrow} {idea.direction}", "DIRECTION", dir_color),
                (pnl_str,                         "P&L",       pnl_color),
                (f"{idea.score}%",                "AI SCORE",  AMB),
                (idea.strategy or "AI Signal",    "STRATEGY",  (100,180,255)),
            ]
            for bi, (val, lbl, clr) in enumerate(boxes):
                bx = 20 + (bi%2) * 306
                by = 360 + (bi//2) * 134
                _stat_box(bx, by, 290, 120, val, lbl, clr)
            if prices:
                _cover_sparkline(draw, prices, W-350, 180, 330, 350, dir_color, show_labels=False)

        # ── POSTER — cinematic, NAC character frame if available ───────────
        else:
            if nac_frame and nac_frame.exists():
                nf = Image.open(str(nac_frame)).convert("RGBA")
                # Scale to fill right 55% of frame
                nf = nf.resize((700, H))
                img.paste(nf, (580, 0), mask=nf.split()[3])
                draw.rectangle([(570,0),(630,H)], fill=(0,0,0,200))
            elif chart_frame and chart_frame.exists():
                cf = Image.open(str(chart_frame)).convert("RGBA").resize((580, H-60))
                img.paste(cf, (680, 30), mask=cf.split()[3])
                draw.rectangle([(660,0),(W,H)], fill=(0,0,0,90))
            _glow_radial(180, H//2, 400, AC, 40)
            draw.rectangle([(0,0),(8,H)], fill=AC)
            _tag(tag_chip, 20, 20, bg_color=(*AMB,230))
            hl = _text_lines(headline, 18)
            for li, ln in enumerate(hl):
                draw.text((20, 68+li*70), ln, font=F["xl"],
                          fill=(255,255,255) if li==0 else AMB)
            draw.text((20, 230), idea.ticker, font=F["h"], fill=(255,255,255))
            draw.rounded_rectangle([(20, 388), (300, 452)], radius=12, fill=dir_color)
            draw.text((36, 396), f"{dir_arrow}  {idea.direction.upper()}", font=F["lg"], fill=(255,255,255))
            draw.text((20, 464), pnl_str, font=F["xxl"], fill=pnl_color)
            draw.text((20, 570), f"AI {idea.score}%  ·  {sub_headline}", font=F["lg"], fill=AMB)

        # ── 7. Always: NAC logo subtle bottom-right, brand bar ─────────────
        _bottom_bar()

        # ── 8. Save + record history ───────────────────────────────────────
        img = img.convert("RGB")
        img.save(out, "JPEG", quality=96)
        _cover_save_history(direction, color_theme, layout_style)
        log.info(f"  → cover.jpg [{direction} / {layout_style} / {color_theme}]")
    except Exception as e:
        log.warning(f"  Cover error: {e}")
        import traceback; log.warning(traceback.format_exc())
    return out


def engine_35_title_seo(script: Dict, idea: ShortIdea, research: Research) -> Dict:
    log.info("[35] Title & SEO Engine — generating YouTube title + description + tags")
    result = _json_claude(
        "You are the Title & SEO Engine for NacArtha AI Lab YouTube Shorts. "
        "Generate an SEO-optimized title and description. "
        "Return JSON: {title, description, tags: []}",
        f"Hook: {script.get('hook_text','')}. Category: {idea.category}. "
        f"Ticker: {idea.ticker} {idea.direction} PnL: {idea.pnl}. "
        f"Facts: {research.key_facts[:2]}. Add #Shorts to title. Max title 70 chars.",
        max_tokens=700,
    )
    result["tags"] = result.get("tags", []) + [
        "NacArtha","AI Trading","Algo Trading","Shorts","Stock Market",
        "Trading Bot","Build In Public",idea.ticker,
    ]
    log.info(f"  → Title: {result.get('title','')[:70]}")
    log.info(f"  → {len(result['tags'])} tags")
    return result


def engine_36_publish(video: Path, seo: Dict, cover: Path) -> Optional[str]:
    log.info("[36] Publishing Engine — uploading to YouTube EN with duplicate check")
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token= os.environ["YOUTUBE_REFRESH_TOKEN_EN"],
        client_id=     os.environ["YOUTUBE_CLIENT_ID"],
        client_secret= os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri=     "https://oauth2.googleapis.com/token",
    )
    yt = build("youtube", "v3", credentials=creds)

    title = seo.get("title", "NacArtha AI Short #Shorts")[:100]
    # Duplicate check
    try:
        res = yt.search().list(part="snippet", forMine=True, q=title[:50], type="video", maxResults=5).execute()
        for item in res.get("items", []):
            if item["snippet"]["title"].strip() == title.strip():
                url = f"https://youtu.be/{item['id']['videoId']}"
                log.info(f"  Duplicate found — {url}")
                return url
    except Exception as e:
        log.warning(f"  Duplicate check error: {e}")

    req = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":       title,
                "description": seo.get("description","")[:5000],
                "tags":        seo.get("tags",[])[:500],
                "categoryId":  "27",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True),
    )
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            log.info(f"  Upload {int(status.progress()*100)}%")
    url = f"https://youtu.be/{resp['id']}"
    log.info(f"  → Uploaded: {url}")

    # Upload thumbnail
    try:
        if cover.exists():
            yt.thumbnails().set(videoId=resp["id"], media_body=MediaFileUpload(str(cover))).execute()
            log.info(f"  → Thumbnail uploaded")
    except Exception as e:
        log.warning(f"  Thumbnail upload failed: {e}")

    return url


def engine_37_analytics(url: Optional[str]) -> Dict:
    log.info("[37] Analytics Engine — initializing tracking record")
    if not url:
        return {}
    video_id = url.split("youtu.be/")[-1].split("?")[0] if url and "youtu.be" in url else ""
    record = {
        "video_id":    video_id,
        "url":         url,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note":        "Analytics data available after 24h via YouTube Analytics API",
        "metrics_to_track": ["views","averageViewDuration","averageViewPercentage","likes","subscribersGained"],
    }
    log.info(f"  → Tracking {video_id} — data available in 24h")
    return record


def engine_38_learning(url: Optional[str], script: Dict, idea: ShortIdea) -> str:
    log.info("[38] Learning Engine — extracting production lessons")
    lessons = _claude(
        "You are the Learning Engine. This short video just completed production. "
        "Write 3 brief learnings for next time — what to improve in script, visuals, or distribution.",
        f"Category: {idea.category}. Hook: {script.get('hook_text','')}. "
        f"Ticker: {idea.ticker} PnL: {idea.pnl}. URL: {url}",
        max_tokens=300,
    )
    log.info(f"  → {lessons[:100]}...")
    return lessons


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 70)
    log.info("NacArtha AI Studio — 38-Engine Full Shorts Pipeline")
    log.info("=" * 70)
    t0 = time.time()

    # ── Clear per-run outputs so nothing is reused from last run ──────────────
    import shutil as _shutil
    _stale = [
        "pai_clip_00.mp4", "pai_clip_01.mp4", "pai_clip_02.mp4",
        "nac_perf_hook.mp4", "nac_perf_analysis.mp4", "nac_perf_conclusion.mp4",
        # Remotion renders — new AI brief must drive fresh renders each run
        "hook.mp4", "stat.mp4", "cta_mg.mp4", "outro.mp4", "trading_chart.mp4",
        "timeline_raw.mp4", "camera.mp4",
        "chart_vfx.mp4",
        "captioned.mp4", "transitioned.mp4", "graded.mp4",
        "body.mp4", "final.mp4",
        "chart_move.mp3",
    ]
    for _f in _stale:
        _p = OUT / _f
        if _p.exists():
            _p.unlink()
            log.info(f"  cleared stale: {_f}")

    # ── INTELLIGENCE LAYER ────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━ INTELLIGENCE LAYER ━━━━━━━━━━━━━━━━━━━")
    trades        = engine_1_trade_intelligence()
    idea          = engine_2_shorts_idea(trades)
    research      = engine_3_research(idea)
    context       = engine_4_context(idea, research)
    angle         = engine_5_story_angle(idea, research, context)
    audience      = engine_6_audience(idea)
    goal          = engine_7_goal(idea)
    viral_moment  = engine_8_viral_moment(idea, research)

    # ── WRITING LAYER ─────────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━━ WRITING LAYER ━━━━━━━━━━━━━━━━━━━━━━")
    hook          = engine_9_hook(idea, angle, audience)
    micro_story   = engine_10_micro_story(idea, research, hook, goal)
    script        = engine_11_script(micro_story, idea, viral_moment)
    validation    = engine_12_fact_validation(script, research)
    script        = engine_13_retention(script, audience)
    voice_style   = engine_14_conversation(script, idea)

    # ── DIRECTION LAYER ───────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ DIRECTION LAYER ━━━━━━━━━━━━━━━━━━━━━")
    brief         = engine_15_creative_director(idea, angle, audience, script)
    director      = engine_16_director(script, brief)
    shots         = engine_17_shot_planning(director, script)
    visual_plan   = engine_18_visual_planning(shots, script, idea)
    asset_plan    = engine_19_asset_planning(visual_plan, idea)

    # ── PRODUCTION LAYER ──────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ PRODUCTION LAYER ━━━━━━━━━━━━━━━━━━━━")
    nac_perf_clips = engine_20_nac_performance(script, brief)
    _              = engine_21_student_performance()
    pai_clips      = engine_22_ai_visual_pai(asset_plan, idea, brief)
    chart_data     = engine_23_dashboard(idea)
    motion_clips   = engine_24_motion_graphics(script, idea, brief, chart_data)
    chart_vfx      = engine_25_vfx(motion_clips["TradingChart"])
    sfx            = engine_26_sfx(brief, idea)
    music_path     = engine_27_music(brief)

    # ── POST PRODUCTION ───────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━ POST PRODUCTION ━━━━━━━━━━━━━━━━━━━━━━")
    narration = _generate_narration(script.get("full_narration", micro_story))

    timeline      = engine_28_timeline(motion_clips, None, chart_vfx, pai_clips, narration,
                                       nac_perf_clips=nac_perf_clips, fmt="short")
    camera        = engine_29_camera_motion(timeline, brief)
    captioned     = engine_30_caption(camera, script, brief)
    transitioned  = engine_31_transition(captioned)
    graded        = engine_32_color_grade(transitioned)
    outro_video, outro_audio = engine_32b_outro(script)
    final         = engine_33_render(graded, narration, music_path, sfx, script, outro_video, outro_audio)

    # ── PUBLISHING LAYER ──────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ PUBLISHING LAYER ━━━━━━━━━━━━━━━━━━━━")
    cover         = engine_34_cover(script, idea, research,
                                   pai_clips=pai_clips,
                                   chart_video=chart_vfx)
    seo           = engine_35_title_seo(script, idea, research)
    url           = engine_36_publish(final, seo, cover)
    analytics     = engine_37_analytics(url)
    lessons       = engine_38_learning(url, script, idea)

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    log.info("\n" + "=" * 70)
    log.info(f"PIPELINE COMPLETE — {elapsed:.1f}s")
    log.info(f"  Video:   {final} ({final.stat().st_size/1e6:.1f} MB)")
    log.info(f"  YouTube: {url or 'FAILED'}")
    log.info(f"  Title:   {seo.get('title','')}")
    log.info(f"  Engines: 38/38 ran")
    log.info("=" * 70)
    return url


def engine_11_long_script(micro_story: str, idea: ShortIdea, viral_moment: str) -> Dict:
    """Long-format script engine — generates 5-8 minute structured narration."""
    log.info("[11L] Long Script Engine — generating 5-8 minute structured script")
    result = _json_claude(
        "You are the Long-Format Script Engine for YouTube. "
        "Generate a 6-minute video script (target: 900 words of narration at 150 wpm). "
        "Be thorough, storytelling-rich, and educational. DO NOT rush. "
        "Return ONLY valid JSON with these keys: "
        "{\"hook_text\": \"<8 words max>\", "
        "\"hook_subtext\": \"<12 words>\", "
        "\"intro_narration\": \"<60 words — dramatic scene-setting, pull viewer in>\", "
        "\"reveal_stat\": \"<key stat>\", "
        "\"body_section_1\": \"<120 words — the market context and setup, what was happening>\", "
        "\"body_section_2\": \"<120 words — the AI signal: what it detected and why it mattered>\", "
        "\"body_section_3\": \"<120 words — the trade decision, entry, and live execution>\", "
        "\"body_section_4\": \"<100 words — the market reaction, what unfolded after entry>\", "
        "\"body_section_5\": \"<100 words — the exit, the result, and what the AI got right>\", "
        "\"analysis_narration\": \"<80 words — deep dive: what humans missed, what AI saw>\", "
        "\"lesson_narration\": \"<60 words — what this trade teaches us about AI trading>\", "
        "\"cta_text\": \"<10 words>\", "
        "\"full_narration\": \"<complete 5-8 min narration, 850-1000 words, natural flowing speech>\", "
        "\"duration_seconds\": 380}",
        f"Story: {micro_story[:800]}\nTicker: {idea.ticker} PnL: {idea.pnl:+.0f} "
        f"Direction: {idea.direction} Strategy: {idea.strategy} Score: {idea.score}\n"
        f"Viral moment: {viral_moment}",
        max_tokens=4000,
    )
    raw_dur = result.get("duration_seconds", 380)
    if isinstance(raw_dur, str):
        import re as _re; nums = _re.findall(r"[\d.]+", str(raw_dur))
        raw_dur = float(nums[0]) if nums else 380.0
    result["duration_seconds"] = max(300.0, min(float(raw_dur), 480.0))
    word_count = len(result.get("full_narration", "").split())
    log.info(f"  → Hook: \"{result.get('hook_text','')[:50]}\" | Duration: {result['duration_seconds']}s | Words: {word_count}")
    return result


def main_long() -> Optional[str]:
    """Long-format (3-5 min) YouTube video pipeline — full 38 engines."""
    log.info("=" * 70)
    log.info("NacArtha AI Studio — LONG FORMAT (3-5 min) Pipeline")
    log.info("=" * 70)
    t0 = time.time()

    # Clear per-run outputs
    import shutil as _sl
    _stale_long = [
        "pai_clip_00.mp4", "pai_clip_01.mp4", "pai_clip_02.mp4",
        "nac_perf_hook.mp4", "nac_perf_analysis.mp4", "nac_perf_conclusion.mp4",
        # Remotion renders — new AI brief must drive fresh renders each run
        "hook.mp4", "stat.mp4", "cta_mg.mp4", "outro.mp4", "trading_chart.mp4",
        "timeline_raw.mp4", "camera.mp4",
        "chart_vfx.mp4",
        "captioned.mp4", "transitioned.mp4", "graded.mp4",
        "body.mp4", "final.mp4", "narration.mp3",
    ]
    for _f in _stale_long:
        _p = OUT / _f
        if _p.exists():
            _p.unlink()
            log.info(f"  cleared stale: {_f}")

    # ── INTELLIGENCE LAYER ────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━ INTELLIGENCE LAYER ━━━━━━━━━━━━━━━━━━━")
    trades       = engine_1_trade_intelligence()
    idea         = engine_2_shorts_idea(trades)
    research     = engine_3_research(idea)
    context      = engine_4_context(idea, research)
    angle        = engine_5_story_angle(idea, research, context)
    audience     = engine_6_audience(idea)
    goal         = engine_7_goal(idea)
    viral_moment = engine_8_viral_moment(idea, research)

    # ── WRITING LAYER — long-format script ───────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━ WRITING LAYER (long) ━━━━━━━━━━━━━━━━━━━")
    hook        = engine_9_hook(idea, angle, audience)
    micro_story = engine_10_micro_story(idea, research, hook, goal)
    script      = engine_11_long_script(micro_story, idea, viral_moment)
    validation  = engine_12_fact_validation(script, research)
    script      = engine_13_retention(script, audience)
    voice_style = engine_14_conversation(script, idea)

    # ── DIRECTION LAYER ───────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ DIRECTION LAYER ━━━━━━━━━━━━━━━━━━━━━")
    brief      = engine_15_creative_director(idea, angle, audience, script)
    director   = engine_16_director(script, brief)
    shots      = engine_17_shot_planning(director, script)
    visual_plan = engine_18_visual_planning(shots, script, idea)
    asset_plan  = engine_19_asset_planning(visual_plan, idea)

    # ── PRODUCTION LAYER — long format uses more clips ───────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━ PRODUCTION LAYER (long) ━━━━━━━━━━━━━━")
    nac_perf_clips = engine_20_nac_performance(script, brief)
    _              = engine_21_student_performance()
    # Generate 3 B-roll clips for long format
    pai_clips      = engine_22_ai_visual_pai(asset_plan, idea, brief)
    # Generate extra B-roll from broll_prompts if available
    broll_extra_prompts = brief.get("broll_prompts", [])
    for i, extra_prompt in enumerate(broll_extra_prompts[:2]):  # max 2 extra
        extra_out = OUT / f"pai_clip_0{i+2}.mp4"
        if not extra_out.exists() and extra_prompt:
            try:
                _pai_generate(extra_prompt, dur=6, out_path=extra_out, use_char_ref=False)
                pai_clips.append(extra_out)
                log.info(f"  [extra B-roll {i+1}] {extra_out.name}")
            except Exception as e:
                log.warning(f"  Extra B-roll {i+1} failed: {e}")

    chart_data   = engine_23_dashboard(idea)
    motion_clips = engine_24_motion_graphics(script, idea, brief, chart_data)
    chart_vfx    = engine_25_vfx(motion_clips["TradingChart"])
    sfx          = engine_26_sfx(brief, idea)
    music_path   = engine_27_music(brief)

    # ── POST PRODUCTION ───────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━ POST PRODUCTION (long) ━━━━━━━━━━━━━━━━━")
    narration    = _generate_narration(script.get("full_narration", micro_story))
    timeline     = engine_28_timeline(motion_clips, None, chart_vfx, pai_clips, narration,
                                      nac_perf_clips=nac_perf_clips, fmt="long")
    camera       = engine_29_camera_motion(timeline, brief)
    captioned    = engine_30_caption(camera, script, brief)
    transitioned = engine_31_transition(captioned)
    graded       = engine_32_color_grade(transitioned)
    outro_video, outro_audio = engine_32b_outro(script)
    final        = engine_33_render(graded, narration, music_path, sfx, script, outro_video, outro_audio)

    # ── PUBLISHING LAYER ──────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ PUBLISHING LAYER ━━━━━━━━━━━━━━━━━━━━")
    cover    = engine_34_cover(script, idea, research, pai_clips=pai_clips, chart_video=chart_vfx)
    seo      = engine_35_title_seo(script, idea, research)
    url      = engine_36_publish(final, seo, cover)
    analytics = engine_37_analytics(url)
    lessons  = engine_38_learning(url, script, idea)

    elapsed = time.time() - t0
    log.info("\n" + "=" * 70)
    log.info(f"LONG FORMAT PIPELINE COMPLETE — {elapsed:.1f}s")
    log.info(f"  Video:   {final} ({final.stat().st_size/1e6:.1f} MB)")
    log.info(f"  YouTube: {url or 'FAILED'}")
    log.info(f"  Engines: 38/38 ran")
    log.info("=" * 70)
    return url


def main_test() -> Path:
    """30-second test run — all 38 engines, no YouTube publish, minimal PAI spend."""
    import sys as _sys
    log.info("=" * 70)
    log.info("NacArtha AI Studio — TEST RUN (30s, all engines, no publish)")
    log.info("=" * 70)
    t0 = time.time()

    # Clear stale outputs
    import shutil as _sl
    _stale_t = [
        # PAI clips (restored from cache each run)
        "pai_clip_00.mp4", "pai_clip_01.mp4", "pai_clip_02.mp4",
        "nac_perf_hook.mp4", "nac_perf_analysis.mp4", "nac_perf_conclusion.mp4",
        # Chart data — must refresh so candles are different each run
        "chart_data_TSLA.json", "chart_data_AAPL.json", "chart_data_NVDA.json",
        # Remotion renders — must regenerate so new AI brief takes effect
        "hook.mp4", "stat.mp4", "cta_mg.mp4", "outro.mp4", "trading_chart.mp4",
        # Pipeline
        "timeline_raw.mp4", "camera.mp4", "chart_vfx.mp4",
        "captioned.mp4", "transitioned.mp4", "graded.mp4",
        "body.mp4", "final.mp4", "narration.mp3", "chart_move.mp3",
        # SFX — regenerate each run so corrupted files don't persist
        "screen_tap.mp3", "keyboard_typing.mp3", "keyboard_short.mp3",
        "mouse_click.mp3", "double_click.mp3", "trade_execute.mp3",
        "data_reveal.mp3", "chart_alert.mp3", "scroll.mp3",
    ]
    for _f in _stale_t:
        _p = OUT / _f
        if _p.exists():
            _p.unlink()

    # ── INTELLIGENCE ──────────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━ INTELLIGENCE LAYER ━━━━━━━━━━━━━━━━━━━")
    trades       = engine_1_trade_intelligence()
    idea         = engine_2_shorts_idea(trades)
    research     = engine_3_research(idea)
    context      = engine_4_context(idea, research)
    angle        = engine_5_story_angle(idea, research, context)
    audience     = engine_6_audience(idea)
    goal         = engine_7_goal(idea)
    viral_moment = engine_8_viral_moment(idea, research)

    # ── WRITING — 30s script ─────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━━ WRITING LAYER ━━━━━━━━━━━━━━━━━━━━━━")
    hook        = engine_9_hook(idea, angle, audience)
    micro_story = engine_10_micro_story(idea, research, hook, goal)
    # Override script to 30 seconds
    script = _json_claude(
        "You are the Script Engine for a 30-second YouTube test video. "
        "Return ONLY JSON: {\"hook_text\": \"<8 words>\", \"hook_subtext\": \"<6 words>\", "
        "\"reveal_stat\": \"<stat>\", \"body_narration\": \"<1 sentence>\", "
        "\"cta_text\": \"<4 words>\", "
        "\"full_narration\": \"<complete 30s narration, max 55 words>\", "
        "\"duration_seconds\": 30}",
        f"Story: {micro_story[:300]}\nTicker: {idea.ticker} PnL: {idea.pnl} Direction: {idea.direction}",
        max_tokens=600,
    )
    script["duration_seconds"] = 30.0
    log.info(f"  → Hook: \"{script.get('hook_text','')[:50]}\" | 30s test script")
    validation  = engine_12_fact_validation(script, research)
    script      = engine_13_retention(script, audience)
    voice_style = engine_14_conversation(script, idea)

    # ── DIRECTION ─────────────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ DIRECTION LAYER ━━━━━━━━━━━━━━━━━━━━━")
    brief       = engine_15_creative_director(idea, angle, audience, script)
    director    = engine_16_director(script, brief)
    shots       = engine_17_shot_planning(director, script)
    visual_plan = engine_18_visual_planning(shots, script, idea)
    asset_plan  = engine_19_asset_planning(visual_plan, idea)

    # ── PRODUCTION — use cached PAI clips, no new PAI spend ─────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ PRODUCTION LAYER ━━━━━━━━━━━━━━━━━━━━")
    _PAI_CACHE = Path(__file__).parent / "pai_cache"
    _CACHE_MAP = {
        "nac_perf_hook.mp4":        OUT / "nac_perf_hook.mp4",
        "nac_perf_analysis.mp4":    OUT / "nac_perf_analysis.mp4",
        "nac_perf_conclusion.mp4":  OUT / "nac_perf_conclusion.mp4",
        "pai_clip_00.mp4":          OUT / "pai_clip_00.mp4",
    }
    for src_name, dst in _CACHE_MAP.items():
        src = _PAI_CACHE / src_name
        if src.exists() and not dst.exists():
            import shutil; shutil.copy2(src, dst)
    nac_perf_clips = [OUT / f for f in ("nac_perf_hook.mp4", "nac_perf_analysis.mp4", "nac_perf_conclusion.mp4") if (OUT / f).exists()]
    log.info(f"  [20] NAC Performance — using {len(nac_perf_clips)} cached clips (0 PAI credits)")
    _ = engine_21_student_performance()

    pai_clips = [OUT / "pai_clip_00.mp4"] if (OUT / "pai_clip_00.mp4").exists() else []
    log.info(f"  [22] AI Visual — using {len(pai_clips)} cached clip(s) (0 PAI credits)")
    chart_data     = engine_23_dashboard(idea)
    motion_clips   = engine_24_motion_graphics(script, idea, brief, chart_data)
    chart_vfx      = engine_25_vfx(motion_clips["TradingChart"])
    sfx            = engine_26_sfx(brief, idea)
    music_path     = engine_27_music(brief)

    # ── POST PRODUCTION ───────────────────────────────────────────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━ POST PRODUCTION ━━━━━━━━━━━━━━━━━━━━━━")
    narration    = _generate_narration(script.get("full_narration", micro_story))
    timeline     = engine_28_timeline(motion_clips, None, chart_vfx, pai_clips, narration,
                                      nac_perf_clips=nac_perf_clips, fmt="short")
    camera       = engine_29_camera_motion(timeline, brief)
    captioned    = engine_30_caption(camera, script, brief)
    transitioned = engine_31_transition(captioned)
    graded       = engine_32_color_grade(transitioned)
    outro_video, outro_audio = engine_32b_outro(script)
    final        = engine_33_render(graded, narration, music_path, sfx, script, outro_video, outro_audio)

    # ── PUBLISHING — SKIPPED in test, run cover + SEO only ───────────────────
    log.info("\n━━━━━━━━━━━━━━━━━━━━ PUBLISHING LAYER (test — no upload) ━━")
    cover    = engine_34_cover(script, idea, research, pai_clips=pai_clips, chart_video=chart_vfx)
    seo      = engine_35_title_seo(script, idea, research)
    log.info(f"  [TEST] Skipping engine_36 publish — file at {final}")
    analytics = engine_37_analytics(None)
    lessons   = engine_38_learning(None, script, idea)

    elapsed = time.time() - t0
    log.info("\n" + "=" * 70)
    log.info(f"TEST RUN COMPLETE — {elapsed:.1f}s")
    log.info(f"  Video:  {final}")
    log.info(f"  Size:   {final.stat().st_size/1e6:.1f} MB")
    log.info(f"  Cover:  {cover}")
    log.info(f"  Title:  {seo.get('title','')}")
    log.info(f"  Idea:   {brief.get('structural_idea','?')} | {brief.get('visual_style','')[:60]}")
    log.info(f"  SFX:    {brief.get('sfx_profile','?')} | Music: {brief.get('music_mood','?')}")
    log.info(f"  Camera: {brief.get('camera_style','?')}")
    log.info("=" * 70)
    return final


if __name__ == "__main__":
    import sys
    if "--long" in sys.argv:
        main_long()
    elif "--test" in sys.argv:
        main_test()
    else:
        main()
