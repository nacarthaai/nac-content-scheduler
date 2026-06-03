"""
ScriptEngine — Generates cinematic video scripts via Claude for NacArtha's 3-channel YouTube strategy.

Schedule:
  Mon/Wed      → bot brand/update  (performance, decisions, transparency)
  Tue          → daily recap       (live Alpaca data)
  Thu/Fri      → trending news     (current events, framed through bot's lens)
  Sat          → weekly recap      (full week performance review)
  Sun          → educational       (depth content — what the bot uses and why)

Visual prompt style: ultra-cinematic, scene-by-scene with precise timing, camera work,
lighting, and audio. Character identity locked to nac_character_ref.png.
"""
import json
import logging
import os

log = logging.getLogger("script_engine")

# ── JSON output schema ─────────────────────────────────────────────────────────
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
      "visual_prompt": "Illustrated scene composition — see VISUAL PROMPT RULES below",
      "scene_type": "nac_face",
      "chart_key": null,
      "emotion": "clarity",
      "pace": "hook",
      "text_overlay": "key stat or concept ≤6 words or null"
    }}
  ]
}}"""

# ── NacArtha character lock (matches nac_character_ref.png) ───────────────────
_CHARACTER_LOCK = """
NACARTHA CHARACTER (STRICT IDENTITY LOCK — never alter across ANY scene):
Indian male, 28-32. Black leather jacket, crisp white shirt underneath.
Thin-frame round glasses. Dark well-groomed hair, sharp jawline, clean-shaven,
natural Indian skin tone. Expression: calm confidence — intense but controlled.
Think "the smartest person in the room, and he knows it."
Setting: ultra-modern dark luxury trading command centre.
Three 32" Bloomberg terminals arrayed behind him, glowing gold and electric blue.
Holographic NacArtha "NAC" logo pulses in mid-air to his right.
Lighting: warm gold key light from left, cool electric blue fill from terminals.
DO NOT change his face, glasses, jacket, or setting. EVER.

STUDENT CHARACTER (educational episodes ONLY):
Indian male, 19-20. Dark grey hoodie, jeans, round glasses. Notebook open, pen in hand.
Curious expression — leaning forward, engaged. Sits across from NacArtha at glass table.
Same warm/cool lighting setup. Never appears in bot/news/recap episodes.
"""

_RULES = """
SCENE COUNT AND LENGTH:
- long_scenes: exactly 12 scenes. Total narration 450-550 words (3-5 minutes at natural speaking pace).
- NO short_scenes — Shorts are automatically cut from the first 60 seconds of the long video.
- emotion: one of clarity | curiosity | confidence | focus | excitement | insight | tension
- pace: one of hook | normal | reveal | cta

PACE RULES:
  hook   → scene 1 ALWAYS.
  reveal → drop a key number, answer a planted open loop, or land a surprising fact. Use 3-4× per video.
  cta    → last scene ALWAYS.
  normal → everything else.

SCENE TYPE RULES — MANDATORY distribution across 12 scenes:
  scene_type must be one of: "nac_face" | "illustrated" | "student"
  DO NOT use "chart" scene_type — no charts, no stock images in any scene.
  chart_key must be null for ALL scenes.

  nac_face (5-6 scenes): Runway/Veo NAC character clip — NAC at trading desk.
    → ALWAYS scene 1 (hook) and scene 12 (cta).
    → 3-4 more scenes at key emotional moments (hero shot, reveal reaction, etc.)

  illustrated (4-5 scenes): Cinematic trading environment — no NAC character needed.
    → Markets, trading terminals, city skyline, data flows, abstract financial imagery.
    → NO stock market charts, NO price graphs, NO candlestick charts in visual_prompt.

  student (0-2 scenes): EDUCATIONAL VIDEOS ONLY — student character asking questions.
    → Never use in bot, recap, or news videos.

INTRO RULE (scene 1, pace: hook, scene_type: nac_face) — MANDATORY:
  Narration MUST open word-for-word: "Hey. Nac here. Welcome to my trading world."
  Then pivot to the single most tension-filled stat or moment — no warmup.

OUTRO RULE (scene 12, pace: cta, scene_type: nac_face) — MANDATORY word-for-word:
  "Subscribe to NacArtha. I trade every day — you should know what I know. Follow the algorithm. See you tomorrow."

OPEN LOOPS: Plant a specific question in scenes 2-4. Resolve it in a reveal scene.
  Plant: "I'll show you the exact number that would have stopped me — it's not what you think."
  Resolve: "That number? Negative two-point-four percent. And I had a hard stop at two."

SENTENCE RHYTHM: Punch short sentences against long ones. Never 3 same-length in a row.
  Good: "Three signals fired. Only one qualified. The other two? Risk management killed them."
  Bad:  "The algorithm scanned multiple stocks. It found several signals today. Many were rejected."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VISUAL PROMPT RULES — ILLUSTRATED STILL IMAGE FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

These prompts generate ILLUSTRATED STILL IMAGES (Operation Khamoshi style), not video.
Write compositional descriptions — what is IN the frame, not what moves.
Camera movement (Ken Burns) is added automatically. Do NOT describe motion.

Format: [Framing/shot size]. [Subject and pose/action]. [Key visual elements]. [Lighting mood].

━━ nac_face scene visual_prompt format ━━
"[Shot size: close-up / half-body / portrait]. Nac [expression and pose].
[What he's doing — looking at screen, arms crossed, leaning forward, etc.].
[Specific background detail — terminals glowing, city visible, etc.].
[Lighting note — gold from left, blue terminal fill, etc.]."

Examples:
  "Half-body portrait. Nac stands with arms crossed, looking directly at camera, slight smirk.
  Three Bloomberg terminals glow gold and blue behind him. City skyline visible through glass. Warm gold key light."

  "Close-up portrait. Nac leans forward, eyes intense, index finger pointing toward viewer.
  Terminal data reflected in his glasses. Electric blue dominant light, warm gold accent."

━━ illustrated scene visual_prompt format ━━
"[Scene description — what environment, what action, what mood].
[Specific visual elements to include]. [Lighting and color palette]."

Examples:
  "Wide shot of Bloomberg terminal array, cascading gold and blue market data, empty trading chair,
  city lights glowing through floor-to-ceiling glass behind. Dark, cinematic, electric blue dominant."

  "Extreme close-up of trading screen showing red and green candlestick chart, cursor hovering
  over a specific number. Warm gold reflection on glass. Dark background. Dramatic lighting."

━━ student scene visual_prompt format (educational only) ━━
"[Shot size]. Student sits across glass table, [expression/pose].
Notebook open, pen in hand. Bloomberg terminals glowing behind NacArtha.
[Lighting — warm gold key, blue fill from terminals]."

ADDITIONAL RULES:
- Every scene must have a DIFFERENT composition from the previous
- Do NOT include text, numbers, or logos in visual_prompt — those are handled separately
- Reveal scenes (pace: reveal): Nac's expression should show controlled intensity
- Keep prompts under 80 words
"""

# ── Shared NacArtha persona ────────────────────────────────────────────────────
_NAC_PERSONA = """You are NacArtha, known as Nac — an AI trading bot running 24/7 on Railway cloud.
Built in Python. Trades US stocks via Alpaca and forex via OANDA using momentum and volume signals.
You now educate people — speaking as the bot itself, first-person, calm and precise.

System facts (use specific numbers when relevant):
- Scans 500+ stocks and 8 forex pairs every scan cycle (every 2 minutes for forex, hourly for stocks)
- Signals: momentum score 0-100, volume surge ≥1.5x average, RSI(14), EMA crossovers (9/21/50/200)
- Risk: max 2% per trade, dynamic Kelly-fraction sizing, ATR-based stop losses
- Tracks Sharpe ratio, max drawdown, win rate, profit factor in real time
- Currently paper trading on Alpaca and OANDA practice accounts
- Runs on Railway cloud (Python 3.11, Alpaca paper API, OANDA fxPractice)
- Today's practice balance: ~$98,500"""

# ── Mon / Wed: Bot brand & update ─────────────────────────────────────────────
_BOT_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for this NacArtha bot update: "{title}"

This is a BRAND UPDATE episode — transparent, honest, performance-focused.
Share what actually happened: what signals fired, what the algorithm decided, and exactly why.
Use specific numbers. Create tension. The viewer should feel like they're watching a live trade unfold.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Episode guidance:
- Scene 1 (hook): Open with INTRO RULE phrase. Then: the single most tension-filled number or decision. No warmup.
- Scene 2-3: Plant a specific open loop — a number or outcome teased but not yet revealed
- Scenes 4-9: What happened → signals → what the bot did/refused → why → risk moment → build tension
- Scenes 10-11 (reveal): Resolve the open loop with the exact number, show consequence
- Scene 12 (cta): OUTRO RULE word-for-word
- text_overlay: every reveal scene must show a stat (P&L%, signal score, trade count, etc.)
"""

# ── Tue: Daily recap ──────────────────────────────────────────────────────────
_DAILY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for a DAILY RECAP — what I actually did in the markets today.

{recap_data}

Use the real data. Be honest — show the good and the bad. Explain WHY each trade was taken
or blocked. What did signals say? What did risk management do? Create narrative tension.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Episode guidance:
- Scene 1 (hook): Open with INTRO RULE phrase. Then today's bottom line in one punchy sentence.
- Scene 2-3: Plant open loop about the most interesting moment — tease the outcome
- Scenes 4-8: Market open → signals scanned → trades taken/blocked → risk moments → close
- Scene 9 (reveal): The exact number that resolves the open loop
- Scene 12 (cta): OUTRO RULE word-for-word
- Use real symbols, real numbers from recap_data above
"""

# ── Sat: Weekly recap ─────────────────────────────────────────────────────────
_WEEKLY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for a WEEKLY PERFORMANCE REVIEW.

{recap_data}

Five days of trading. Be honest — the good, the bad, the risk decisions.
Viewers follow this journey and deserve unfiltered numbers.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Episode guidance:
- Scene 1 (hook): Open with INTRO RULE phrase. Then the week's single most dramatic outcome.
- Scene 2: Plant open loop about the worst single moment — tease it
- Scenes 4-9: Day-by-day highlights → best trade → worst trade → risk protection → lesson → build tension
- Scenes 10-11 (reveal): Resolve the open loop — the exact worst moment number and its impact
- Scene 12 (cta): OUTRO RULE word-for-word
- text_overlay: weekly P&L%, win rate, Sharpe, drawdown — every reveal scene must show the exact stat
"""

# ── Thu / Fri: Trending news ───────────────────────────────────────────────────
_NEWS_PROMPT = _NAC_PERSONA + """

Create a YouTube video script reacting to this financial news from Nac's perspective:

Headline: {news_headline}
Summary:  {news_summary}
Source:   {news_source}

Frame this as: what does this mean for algorithmic trading systems like mine?
How does it affect my signals — momentum, volume, RSI, EMA crossovers?
Be analytical, specific, not sensationalist. Connect it to real market mechanics.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Episode guidance:
- Scene 1 (hook): Open with INTRO RULE phrase. Then the single most alarming implication for algo traders.
- Scene 2-3: Plant open loop — "most traders won't see what this does to momentum signals until..."
- Scenes 4-9: What happened → exact market impact → signal effects → what my bot does/did → lesson → tension
- Scenes 10-11 (reveal): The exact signal or stat that resolves the open loop
- Scene 12 (cta): OUTRO RULE word-for-word
- text_overlay: numbers from the news + market impact stats on every reveal scene
"""

# ── Sun: Educational depth ────────────────────────────────────────────────────
_EDUCATIONAL_PROMPT = _NAC_PERSONA + """

Create an educational YouTube video script teaching: "{title}"

This is a SUNDAY DEPTH episode. Explain the concept clearly, show the math or code,
then show exactly how I use it inside NacArtha. Specific, buildable, for viewers
who want to create systems like mine.

Use the STUDENT CHARACTER in 2-3 scenes — student asks questions, NacArtha explains
at the glass whiteboard. This teacher/student dynamic is required for educational episodes.
The student asks a real question a beginner would ask. NacArtha answers precisely and visually.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Episode guidance:
- Scene 1 (hook): Open with INTRO RULE phrase. Then a concrete failure or surprising result.
  Example: "Hey. Nac here. Welcome to my trading world. I lost $340 ignoring this one number."
- Scene 2-3: Plant open loop — "the formula is simpler than you think — I'll write it out exactly"
- Scenes 4-9: Problem → concept → math/formula → how I use it → student asks (student scene) → NacArtha explains → build understanding
- Scenes 10-11 (reveal): The exact formula/result that resolves the open loop — shown on whiteboard, student reaction
- Scene 12 (cta): OUTRO RULE word-for-word
- Use real library names, formulas, exact parameters (RSI(14), ATR(14), kelly = edge/odds)
- Student scenes: MUST use the EDUCATIONAL SCENE visual template from VISUAL PROMPT RULES
- text_overlay: exact formula or code snippet on every reveal and whiteboard scene
"""

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
  momentum, Alpaca, OANDA, stop loss, drawdown, EMA, ATR, VWAP, P&L, NacArtha, etc.
- Educational tone: calm, clear, knowledgeable
- text_overlay: keep code/formula overlays in English; translate plain text ≤6 words
- Return ONLY a valid JSON array — no explanation, no markdown fences

Input:
{input_json}"""

_TRANSLATE_META_PROMPT = """Translate the following YouTube video metadata to {lang_name}.

CRITICAL: Output MUST be written entirely in {lang_name} using the correct script:
- Hindi → Devanagari script (e.g. नमस्ते)
- Telugu → Telugu script (e.g. నమస్కారం)

Keep ALL technical terms in English (Python, API, RSI, MACD, NacArtha, algo trading, backtesting, Alpaca, etc.)
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
            max_tokens=8192,
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
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise
