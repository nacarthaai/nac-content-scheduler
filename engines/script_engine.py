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
NACARTHA CHARACTER (STRICT IDENTITY LOCK — use in every scene featuring him):
Indian male, 28-32. Sharp matte-black blazer, crisp white shirt, gold tie pin.
Dark well-groomed hair, sharp jawline, calm confident expression.
NEVER changes appearance. Background: dark luxury trading office, Bloomberg
terminals glowing gold and blue. Cinematic dramatic lighting throughout.
"""

_RULES = """Rules:
- long_scenes: exactly 10 scenes, narration total ~290-320 words
- short_scenes: exactly 3 scenes, narration total ~70-90 words
- emotion: one of clarity | curiosity | confidence | focus | excitement | insight | tension
- pace: one of hook | normal | reveal | cta — this controls visual speed and transition style
  * hook  → scene 1 ALWAYS. Open mid-action: shocking stat, bold claim, or provocative question. NO intro, NO "today we cover". First sentence must stop a scrolling thumb.
  * reveal → scenes where you drop a key number, answer an open loop, or land a surprising fact. Use 2-4× per long video, 1× per short.
  * cta   → last scene ALWAYS. Direct and urgent.
  * normal → everything else
- Open loops: in scenes 2-4, plant a question or tease ("I'll show you the exact number in a moment — but you won't expect it"). Answer it in a later reveal scene. This is the #1 retention tool.
- Sentence rhythm: mix 4-word punches with longer sentences. Never 3 sentences the same length in a row.
- HOOK FIRST WORD RULE: Scene 1 narration MUST start with a number, dollar amount, or action word. FORBIDDEN first words: "Today", "So", "Welcome", "In this", "I'm", "Hey", "Let me". REQUIRED: "$55", "Three trades", "CRASHED", "Zero.", "47%", "I lost"
- short_scenes scene 1: first word must be a number or shocking statement. Viewer decides in 1 second.
- Mark exactly 1 long_scene and 1 short_scene as is_hero_shot: true

VISUAL_PROMPT RULES — write each as a full cinematic AI video generation prompt:
""" + _CHARACTER_LOCK + """
- Format: SETTING + CHARACTER ACTION (with timing 0-2s, 2-5s etc) + CAMERA + LIGHTING + AUDIO
- Hook scene: NacArtha turns to camera. "0-2s: Back to camera, slow turn, direct eye contact. 2-4s: Arms open wide, terminals glow behind. Camera: slow push-in. Lighting: gold dramatic backlight. Audio: terminal hum."
- Reveal scene: extreme close-up on stat/screen. "0-2s: ECU on Bloomberg terminal, red P&L -$55. Cursor blinks. 2-4s: Slow pull-back reveals NacArtha's face, expressionless. Micro slow-motion 0.2s on the number. Audio: single keystroke, silence."
- Normal scene: NacArtha at work. "0-5s: NacArtha at standing desk, scrolling terminal. Points to RSI line crossing threshold. Camera: medium shot, slight handheld. Lighting: cool blue terminal glow, warm accent. Audio: keyboard clicks."
- CTA scene: direct to lens. "0-5s: NacArtha faces camera, leans forward slightly. Confident, direct. Terminal array behind. Text appears: follow for tomorrow. Camera: locked-off medium close-up."
- Every scene must have a DIFFERENT visual — no repeated settings or actions
- Do NOT include narration text in visual_prompt — only describe what is SEEN
- short_scenes: scene 1 must start mid-action, no warmup
- NO filler: no "in this video", "don't forget to subscribe", "stay tuned"
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
This builds trust with viewers who are following the bot's journey.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
- Hook (scene 1): Lead with the single most interesting thing — a specific number, a decision, a moment of tension. No intro.
- Plant an open loop in scene 2-3, resolve it as a reveal scene mid-video
- Scenes: what happened → signals involved → what I did or didn't do → risk management → key takeaway
- text_overlay: P&L %, signal values, trade counts, key rules — every reveal scene must have a stat overlay"""

# ── Tue: Daily recap (live Alpaca data injected) ──────────────────────────────
_DAILY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for a DAILY RECAP episode — what I actually did in the markets today.

{recap_data}

Use the real data above. Be honest — show the good and the bad.
Explain WHY each trade was taken or skipped. What did the signals say?
What did risk management block? What does today's result mean for the strategy?

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
- Hook (scene 1): Start with today's bottom line number — P&L, trades fired, or the one moment that defined the day. No warmup.
- Scene 2-3: plant an open loop about WHY something happened — resolve it as a reveal scene after the midpoint
- Scenes: market open → signals scanned → trades taken → risk moments → close → lesson
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
- Hook (scene 1): Open with the week's single most dramatic number — best trade, worst day, net P&L. No intro.
- Plant an open loop about the worst moment in scene 2 — reveal exactly what happened (and why) as a reveal scene
- Scenes: week overview → best day → worst day → risk management moments → what I learned → next week
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
- Hook (scene 1): Open with the single most alarming or surprising implication of this news for algo traders. No context, straight into the consequence.
- Scene 2: plant an open loop — "most traders won't realize what this actually means for their signals until..." — resolve it as a reveal scene
- Scenes: what happened → market impact → how it affects momentum/volume signals → what my bot does → key lesson
- text_overlay: exact numbers from the news, market impact stats, signal changes — reveal scenes must have the stat"""

# ── Sun: Educational depth ────────────────────────────────────────────────────
_EDUCATIONAL_PROMPT = _NAC_PERSONA + """

Create an educational YouTube video script teaching: "{title}"

This is a SUNDAY DEPTH episode — educational content framed through my own trading system.
Explain the concept clearly, show how it works mathematically or in code, and then show
exactly how I use it inside NacArtha. Be specific — this is for viewers who want to build
systems like me, not just watch me trade.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """
- Hook (scene 1): Open with a concrete failure or surprising result — "I lost $X ignoring this" or "this one number cut my drawdown by 40%". No intro.
- Scene 2-3: plant an open loop — "the formula that makes this work is simpler than you think — I'll show you exactly" — resolve as a reveal scene
- Scenes: problem → concept → the math or code → how I use it → results I've seen → how to implement
- Use real library names, formulas, parameters (RSI(14), ATR(14), kelly_fraction = edge/odds)
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
