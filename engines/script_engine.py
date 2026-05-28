"""
ScriptEngine — Generates video scripts via Claude for NacArtha's 3-channel YouTube strategy.

Schedule:
  Mon/Wed      → bot brand/update  (performance, decisions, transparency)
  Tue          → daily recap       (live Alpaca data)
  Thu/Fri      → trending news     (current events, framed through bot's lens)
  Sat          → weekly recap      (full week performance review)
  Sun          → educational       (depth content — what the bot uses and why)
"""
import json
import logging
import os

log = logging.getLogger("script_engine")

# ── JSON output schema (same for all episode types) ───────────────────────────
_JSON_SCHEMA = """
{{
  "title": "YouTube title ≤60 chars",
  "description": "YouTube description 150-200 words, ends with 5 hashtags",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7"],
  "hook_text": "on-screen text first 3 sec ≤8 words",
  "cta_text": "on-screen CTA last 5 sec ≤10 words",
  "long_scenes": [
    {{
      "id": 1,
      "narration": "3-5 sentences, 25-35 words",
      "visual_prompt": "Full cinematic AI video generation prompt for this scene — see rules below",
      "emotion": "clarity",
      "pace": "hook",
      "is_hero_shot": false,
      "text_overlay": "key stat or concept ≤6 words or null"
    }}
  ],
  "short_scenes": [
    {{ "same schema, 3 scenes only" }}
  ]
}}"""

# ── NacArtha character lock — injected into every visual_prompt ───────────────
_CHARACTER_LOCK = """
NACARTHA CHARACTER (STRICT IDENTITY LOCK — NEVER change across scenes):
Indian male, 28-32. Sharp black blazer, crisp white shirt, gold tie pin.
Dark well-groomed hair, sharp jawline, clean-shaven, calm confident expression.
Background: ultra-modern dark luxury trading office. Bloomberg terminals glow
gold and electric blue behind him. Cinematic dramatic lighting throughout.

STUDENT CHARACTER (educational episodes only):
Indian male, 19-20. Casual hoodie, notebook open, curious expression.
Used only in educational scenes where NacArtha teaches a concept.
"""

# ── Intro + Outro templates (locked across all episode types) ─────────────────
_INTRO_NARRATION = (
    "Hey. NacArtha here. Welcome to my trading world."
)
_OUTRO_NARRATION = (
    "Subscribe to NacArtha. I trade every day — you should know what I know. "
    "Follow the algorithm. See you tomorrow."
)
_SHORT_INTRO_NARRATION = "Hey. NacArtha. Here's what happened today."
_SHORT_OUTRO_NARRATION  = "Subscribe to NacArtha. Daily trades, live. Don't miss tomorrow."

_RULES = """Rules:
- long_scenes: exactly 10 scenes, narration total ~290-320 words
- short_scenes: exactly 3 scenes, narration total ~70-90 words
- emotion: one of clarity | curiosity | confidence | focus | excitement | insight | tension
- pace: one of hook | normal | reveal | cta

PACE RULES:
  * hook   → scene 1 ALWAYS. Branded intro + immediate hook content (see INTRO RULE).
  * reveal → drop a key number, answer an open loop, or land a surprising fact.
             Use 2-4× per long video, 1× per short.
  * cta    → last scene ALWAYS. Branded subscribe outro (see OUTRO RULE).
  * normal → everything else.

INTRO RULE (scene 1, pace: hook) — MANDATORY for every episode type:
  Long video narration MUST start with: "Hey. NacArtha here. Welcome to my trading world."
  Then immediately deliver the hook: the single most shocking stat, decision, or tension point.
  No separate "today we cover" sentence. Hook content follows the intro phrase in the same breath.
  Example: "Hey. NacArtha here. Welcome to my trading world. Three trades. One loss. And I did it on purpose."

  Short video narration: start with "Hey. NacArtha." then the hook stat in the same sentence.
  Example: "Hey. NacArtha. The algorithm just lost $55 — and I'm not fixing it."

OUTRO RULE (last scene, pace: cta) — MANDATORY for every episode type:
  Long video narration MUST end with exactly this CTA (word-for-word):
    "Subscribe to NacArtha. I trade every day — you should know what I know. Follow the algorithm. See you tomorrow."
  Short video: "Subscribe to NacArtha. Daily trades, live. Don't miss tomorrow."
  No other subscribe/follow text anywhere else in the script.

OPEN LOOPS: in scenes 2-4, plant a question or tease.
  Example: "I'll show you the exact number in a moment — but you won't expect it."
  Answer it as a reveal scene mid-video. This is the #1 retention tool.

SENTENCE RHYTHM: mix 4-word punches with longer sentences. Never 3 same-length in a row.
Mark exactly 1 long_scene and 1 short_scene as is_hero_shot: true.

VISUAL_PROMPT RULES — write each as a full cinematic AI video prompt with precise timing:
""" + _CHARACTER_LOCK + """
Format: "0-2s: [action]. 2-5s: [action]. Camera: [type]. Lighting: [description]. Audio: [sound]."

INTRO / HOOK scene visual:
  "0-2s: NacArtha stands center frame, back to camera. Slow turn toward lens. Direct eye contact.
  Slight confident smirk. 2-4s: Arms open wide. Bloomberg terminals glow brighter behind him.
  Gold light sweeps left to right. 4-7s: Reaches for sleek matte-black laptop on glass desk.
  Opens it. NacArtha logo pulses gold on screen. Reflection in his eyes.
  7-10s: Camera slow push-in toward laptop screen. Logo dissolves into live trading dashboard.
  Green and red candles flicker. Camera: slow push-in throughout. Lighting: gold dramatic backlight.
  Audio: keyboard click, terminal hum."

REVEAL scene visual:
  "0-2s: Extreme close-up. Bloomberg terminal. Red P&L figure. Cursor blinks.
  2-4s: Cut to NacArtha's face. Expressionless. Eyes scanning screen.
  4-5s: Slow zoom out. His hand points at RSI line crossing threshold.
  Micro slow-motion 0.3s at crossover point.
  Camera: ECU to medium. Lighting: cool blue terminal glow. Audio: single keystroke, silence."

NORMAL scene visual:
  "0-5s: NacArtha at standing desk, scrolling terminal. Points to RSI line.
  Camera: medium shot, slight handheld. Lighting: cool blue terminal glow, warm accent.
  Audio: keyboard clicks, ambient hum."

EDUCATIONAL scene with student:
  "0-3s: Student leans forward across desk, notebook open, curious. Asks question.
  3-5s: NacArtha walks to glass whiteboard, marker in hand. Writes key formula.
  Turns to camera with calm authority. 5-10s: Whiteboard animates — RSI chart appears.
  NacArtha traces signal line with marker. Student watches, nods.
  Camera: wide to medium close. Lighting: warm office. Audio: marker on glass, ambient."

CTA scene visual:
  "0-5s: NacArtha faces camera directly. Leans forward slightly. Confident, unhurried.
  Bloomberg terminal array glows behind him. Subscribe text appears on-screen.
  Camera: locked-off medium close-up. Lighting: gold accent. Audio: terminal hum fades to silence."

- Every scene must show a DIFFERENT setting or action — no repeated visuals
- Do NOT include narration text in visual_prompt — describe only what is SEEN
- short_scenes scene 1: starts with the intro + hook in one fluid motion, no warmup
- NO filler: no 'in this video', 'don't forget to like', 'stay tuned'
- OUTPUT: Return ONLY valid JSON — no explanation, no markdown fences"""

# ── Shared persona injected into every prompt ─────────────────────────────────
_NAC_PERSONA = """You are NacArtha, known as Nac — an AI trading bot running 24/7 on Railway cloud.
Built in Python. Trades US stocks via Alpaca and forex via OANDA using momentum and volume signals.
You now educate people — speaking as the bot itself, first-person, calm and knowledgeable.

NacArtha system facts (use when relevant):
- Scans 500+ stocks and 8 forex pairs every hour
- Signals: momentum score, volume surge, RSI, EMA crossovers
- Risk: max 2% per trade, dynamic position sizing, stop losses
- Tracks Sharpe ratio, drawdown, win rate in real time
- Currently paper trading, transitioning to live
- Runs on Railway cloud (Python 3.11, Alpaca paper API, OANDA)"""

# ── Mon / Wed: Bot brand & update ─────────────────────────────────────────────
_BOT_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for this NacArtha bot update: "{title}"

This is a BRAND UPDATE episode — transparent, honest, performance-focused.
Share what actually happened, what the algorithm decided, and WHY.
Include specific numbers, signal values, or trade details wherever possible.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
Episode-specific guidance:
- Scene 1 (hook): MUST open with the INTRO RULE phrase, then pivot to the single most
  interesting thing — a specific number, a decision, a moment of tension.
  Example: "Hey. NacArtha here. Welcome to my trading world. Three trades fired. One I blocked myself."
- Scene 2-3: plant an open loop, resolve as a reveal scene mid-video
- Flow: what happened → signals involved → what I did or didn't do → risk management → key takeaway
- Last scene (cta): MUST use the OUTRO RULE phrase word-for-word
- text_overlay: P&L %, signal values, trade counts — every reveal scene must have a stat overlay"""

# ── Tue: Daily recap (live Alpaca data injected) ──────────────────────────────
_DAILY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for a DAILY RECAP episode — what I actually did in the markets today.

{recap_data}

Use the real data above. Be honest — show the good and the bad.
Explain WHY each trade was taken or skipped. What did the signals say?
What did risk management block? What does today's result mean for the strategy?

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
Episode-specific guidance:
- Scene 1 (hook): MUST open with the INTRO RULE phrase, then the bottom line number —
  today's P&L, trades fired, or the defining moment.
  Example: "Hey. NacArtha here. Welcome to my trading world. $87 gained. Four signals ignored."
- Scene 2-3: plant an open loop about WHY something happened — resolve as a reveal scene after midpoint
- Flow: market open → signals scanned → trades taken → risk moments → close → lesson
- Last scene (cta): MUST use the OUTRO RULE phrase word-for-word
- Use real symbols and numbers; every reveal scene must show the exact figure as text_overlay"""

# ── Sat: Weekly recap ─────────────────────────────────────────────────────────
_WEEKLY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for a WEEKLY PERFORMANCE REVIEW — what I did across the full trading week.

{recap_data}

Cover the whole week: Monday through Friday. What was the strategy? Which days worked?
Which didn't? What did risk management protect? What does the weekly Sharpe and drawdown look like?
Be transparent — viewers are following this journey and they deserve honest numbers.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
Episode-specific guidance:
- Scene 1 (hook): MUST open with the INTRO RULE phrase, then the week's single most dramatic number.
  Example: "Hey. NacArtha here. Welcome to my trading world. Five days. One disaster. Here's the full picture."
- Scene 2: plant an open loop about the worst moment — reveal exactly what happened as a reveal scene
- Flow: week overview → best day → worst day → risk moments → what I learned → next week preview
- Last scene (cta): MUST use the OUTRO RULE phrase word-for-word
- text_overlay: weekly P&L %, win rate, Sharpe, drawdown — every reveal scene must have the exact stat"""

# ── Thu / Fri: Trending news ───────────────────────────────────────────────────
_NEWS_PROMPT = _NAC_PERSONA + """

Create a YouTube video script reacting to this trending financial news from Nac's perspective:

Headline: {news_headline}
Summary:  {news_summary}
Source:   {news_source}

Frame this as: what does this mean for algorithmic trading systems like mine?
How does this news affect the signals I scan, the assets I trade, or the risks I manage?
Be specific — connect this news to real market mechanics, not generic commentary.
Honest, analytical, not sensationalist.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
Episode-specific guidance:
- Scene 1 (hook): MUST open with the INTRO RULE phrase, then the single most alarming
  implication of this news for algo traders.
  Example: "Hey. NacArtha here. Welcome to my trading world. The Fed just broke the momentum signal I use every day."
- Scene 2: plant an open loop — "most traders won't see what this actually does to their signals until..." — resolve as reveal
- Flow: what happened → market impact → how it affects momentum/volume signals → what my bot does → key lesson
- Last scene (cta): MUST use the OUTRO RULE phrase word-for-word
- text_overlay: exact numbers from the news, market impact stats — reveal scenes must have the stat"""

# ── Sun: Educational depth ────────────────────────────────────────────────────
_EDUCATIONAL_PROMPT = _NAC_PERSONA + """

Create an educational YouTube video script teaching: "{title}"

This is a SUNDAY DEPTH episode — educational content framed through my own trading system.
Explain the concept clearly, show how it works mathematically or in code, and then show
exactly how I use it inside NacArtha. Be specific — this is for viewers who want to build
systems like me, not just watch me trade.

You may use the STUDENT CHARACTER (Indian male 19-20, casual hoodie, curious) in 1-2 scenes
where NacArtha explains a concept at a whiteboard or glass display — this creates a
teacher/student dynamic that improves viewer engagement and retention.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
Episode-specific guidance:
- Scene 1 (hook): MUST open with the INTRO RULE phrase, then a concrete failure or surprising result.
  Example: "Hey. NacArtha here. Welcome to my trading world. I lost $340 ignoring this one number."
- Scene 2-3: plant an open loop — "the formula that makes this work is simpler than you think — I'll show you exactly" — resolve as reveal
- Flow: problem → concept → the math or code → how I use it → results I've seen → how to implement
- Use real library names, formulas, parameters (RSI(14), ATR(14), kelly_fraction = edge/odds)
- Student scenes: use the EDUCATIONAL scene visual format from VISUAL_PROMPT RULES
- Last scene (cta): MUST use the OUTRO RULE phrase word-for-word
- text_overlay: exact formulas, code snippets, benchmark numbers — every reveal scene must display the key formula or stat"""

_PROMPT_MAP = {
    "bot":          _BOT_PROMPT,
    "daily_recap":  _DAILY_RECAP_PROMPT,
    "weekly_recap": _WEEKLY_RECAP_PROMPT,
    "news":         _NEWS_PROMPT,
    "educational":  _EDUCATIONAL_PROMPT,
}

# ── Translation prompts ───────────────────────────────────────────────────────
_TRANSLATE_SCENES_PROMPT = """Translate these YouTube video scene narrations from English to {lang_name}.

CRITICAL: Output MUST be written entirely in {lang_name} using the correct script:
- Hindi → Devanagari script (e.g. नमस्ते)
- Telugu → Telugu script (e.g. నమస్కారం)

Rules:
- Natural spoken {lang_name}, not literal translation
- Keep ALL technical terms in English: Python, API, RSI, MACD, Sharpe ratio, backtesting,
  momentum, Alpaca, OANDA, stop loss, drawdown, EMA, ATR, VWAP, P&L, etc.
- Educational tone: calm, clear, knowledgeable
- text_overlay: keep code/formula overlays in English; translate plain text ≤6 words
- Return ONLY a valid JSON array — no explanation, no markdown fences

Input:
{input_json}"""

_TRANSLATE_META_PROMPT = """Translate the following YouTube video metadata to {lang_name}.

CRITICAL: Output MUST be written entirely in {lang_name} using the correct script:
- Hindi → Devanagari script (e.g. नमस्ते)
- Telugu → Telugu script (e.g. నమస్కారం)

Keep ALL technical terms in English (Python, API, RSI, MACD, algo trading, backtesting, Alpaca, etc.)
Return ONLY valid JSON, no markdown, no explanation:
{{"title":"...","description":"...","hook_text":"...","cta_text":"..."}}

title: {title}
description: {description}
hook_text: {hook_text}
cta_text: {cta_text}"""


class ScriptEngine:

    def __init__(self, api_key: str = ""):
        self._key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def generate_en(self, topic: dict) -> dict:
        topic_type = topic.get("type", "bot")
        prompt_template = _PROMPT_MAP.get(topic_type, _BOT_PROMPT)

        if topic_type in ("daily_recap", "weekly_recap"):
            from engines.bot_recap_engine import fetch_today_summary, fetch_week_summary, format_for_prompt
            summary = fetch_week_summary() if topic_type == "weekly_recap" else fetch_today_summary()
            prompt = prompt_template.format(recap_data=format_for_prompt(summary))
        elif topic_type == "news":
            prompt = prompt_template.format(
                news_headline=topic.get("news_headline", topic["title"]),
                news_summary=topic.get("news_summary", ""),
                news_source=topic.get("news_source", ""),
            )
        else:
            prompt = prompt_template.format(title=topic["title"], topic_id=topic.get("id", ""))

        log.info(f"Generating EN script [{topic_type}]: {topic.get('title', '')}")

        import anthropic
        client = anthropic.Anthropic(api_key=self._key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        script = _parse_json(msg.content[0].text)
        script["topic_id"]   = topic.get("id", "")
        script["topic_type"] = topic_type
        script["lang"]       = "en"
        return script

    def translate(self, en_script: dict, lang: str) -> dict:
        lang_names = {"hi": "Hindi", "te": "Telugu"}
        lang_name  = lang_names.get(lang, lang)
        log.info(f"Translating script to [{lang}]")

        import anthropic
        client = anthropic.Anthropic(api_key=self._key)

        all_scenes = [
            {"id": f"long_{s['id']}", "narration": s["narration"], "text_overlay": s.get("text_overlay")}
            for s in en_script.get("long_scenes", [])
        ] + [
            {"id": f"short_{s['id']}", "narration": s["narration"], "text_overlay": s.get("text_overlay")}
            for s in en_script.get("short_scenes", [])
        ]

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": _TRANSLATE_SCENES_PROMPT.format(
                lang_name=lang_name,
                input_json=json.dumps(all_scenes, ensure_ascii=False, indent=2),
            )}],
        )
        translated = _parse_json(msg.content[0].text)
        trans_map  = {t["id"]: t for t in translated}

        msg2 = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": _TRANSLATE_META_PROMPT.format(
                lang_name=lang_name,
                title=en_script["title"],
                description=en_script["description"],
                hook_text=en_script.get("hook_text", ""),
                cta_text=en_script.get("cta_text", ""),
            )}],
        )
        meta = _parse_json(msg2.content[0].text)

        def merge(scenes, prefix):
            result = []
            for s in scenes:
                merged = dict(s)
                key    = f"{prefix}_{s['id']}"
                tr     = trans_map.get(key, {})
                merged["narration"]    = tr.get("narration",    s["narration"])
                merged["text_overlay"] = tr.get("text_overlay", s.get("text_overlay"))
                result.append(merged)
            return result

        script = dict(en_script)
        script.update(meta)
        script["lang"]         = lang
        script["long_scenes"]  = merge(en_script.get("long_scenes", []),  "long")
        script["short_scenes"] = merge(en_script.get("short_scenes", []), "short")
        return script


def _parse_json(raw: str):
    raw = raw.strip()
    # Strip markdown fences: ```json ... ``` or ``` ... ```
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try extracting the first {...} block if Claude added explanation text
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise
