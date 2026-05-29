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
      "visual_prompt": "Full cinematic AI video generation prompt — see VISUAL PROMPT RULES below",
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
- long_scenes: exactly 10 scenes. Total narration 290-320 words.
- short_scenes: exactly 3 scenes. Total narration 70-90 words.
- emotion: one of clarity | curiosity | confidence | focus | excitement | insight | tension
- pace: one of hook | normal | reveal | cta

PACE RULES:
  hook   → scene 1 ALWAYS. Opens with mandatory intro phrase then immediate hook content.
  reveal → drop a key number, answer a planted open loop, or land a surprising fact.
           Use 2-4× per long video, 1× per short.
  cta    → last scene ALWAYS. Subscribe outro — word-for-word (see OUTRO RULE).
  normal → everything else.

INTRO RULE (scene 1, pace: hook) — MANDATORY for every episode:
  Long video narration MUST open word-for-word with:
    "Hey. Nac here. Welcome to my trading world."
  Then pivot immediately to the single most tension-filled stat or moment — no warmup.
  Example: "Hey. Nac here. Welcome to my trading world. Three trades. One I killed myself. Here's why."

  Short video: "Hey. NacArtha." then the hook stat in the same breath.
  Example: "Hey. NacArtha. The bot just refused $1,200 in profit. On purpose."

OUTRO RULE (last scene, pace: cta) — MANDATORY word-for-word:
  Long: "Subscribe to NacArtha. I trade every day — you should know what I know. Follow the algorithm. See you tomorrow."
  Short: "Subscribe to NacArtha. Daily trades, live. Don't miss tomorrow."

OPEN LOOPS: Plant a specific question in scenes 2-4. Resolve it as a reveal scene.
  Plant: "I'll show you the exact number that would have stopped me — it's not what you think."
  Resolve: "That number? Negative two-point-four percent. And I had a hard stop at two."
  This is the #1 retention mechanism. Every episode needs one.

SENTENCE RHYTHM: Punch short sentences against long ones. Never 3 same-length in a row.
  Good: "Three signals fired. Only one qualified. The other two? Risk management killed them."
  Bad:  "The algorithm scanned multiple stocks. It found several signals today. Many were rejected."

Mark exactly 1 long_scene and 1 short_scene as is_hero_shot: true.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VISUAL PROMPT RULES — CINEMATIC FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write every visual_prompt as a full AI video generation brief with precise timing.
Structure EVERY prompt exactly like this:

[Shot type]. [Camera movement]. [Stability/style — e.g. "smooth dolly" or "slight handheld micro-jitter"].
Audio: [ambient only — keyboard, terminal hum, chair, breathing, paper — NO music unless scene specifies].
Lighting: [exact setup — "warm gold key left + cool blue terminal fill" or specific variation].

[NACARTHA CHARACTER or STUDENT CHARACTER block — use _CHARACTER_LOCK exactly]

ACTION:
0-2s: [exact action — what moves, what body part, what object, what micro-detail]
2-5s: [exact action — camera move + character action together]
5-8s: [exact action + optional micro slow-motion: "Micro slow-motion 0.3s at [moment]. Back to real-time."]
[continue until full scene duration]

Camera: [shot size progression, e.g. "ECU → medium close" or "locked-off medium"]

━━ SCENE 1 (pace: hook) VISUAL — MANDATORY TEMPLATE ━━
Use this EXACT intro visual for ALL episode types — do not deviate:

"Single continuous shot, no cuts. Smooth cinematic dolly push-in.
Audio: mechanical keyboard click at 2s, terminal hum throughout, distant fan hum, chair movement. No music.
Lighting: dark trading office. Warm gold key light from left. Cool electric blue from terminals.
Holographic NAC logo pulses gently right of frame.

NACARTHA CHARACTER (STRICT IDENTITY LOCK): [description]

ACTION:
0-1s: NacArtha stands center frame, back to camera. Dark trading office. Three Bloomberg terminals
glow gold and blue behind him. Holographic NAC logo pulses right.
1-2s: Slow turn toward lens. Direct eye contact. Slight confident smirk. Glasses catch terminal glow.
2-3s: Speaks directly to camera. Mouth moves. Narration begins.
3-5s: Turns. Walks to glass desk. Sits in one smooth motion. Opens matte-black laptop.
5-7s: NacArtha logo pulses gold on laptop screen. Blue holographic glow reflects off his glasses.
Leans forward slightly toward screen.
7-10s: Camera begins slow push-in toward laptop screen. Logo dissolves. Live trading dashboard
appears — green/red candles, P&L counter, bot activity feed scrolling.
Micro slow-motion 0.4s as dashboard fills frame. Back to real-time.
Camera: slow push-in throughout. Frame shifts from wide to ECU on laptop screen."

━━ LAST SCENE (pace: cta) VISUAL — MANDATORY TEMPLATE ━━
"Single continuous shot, locked-off. Medium close-up.
Audio: terminal hum fades slowly to near-silence. Single keyboard click at 3s.
Lighting: warm gold accent from left intensifies. Blue terminal glow softens behind him.

NACARTHA CHARACTER (STRICT IDENTITY LOCK): [description]

ACTION:
0-2s: NacArtha faces camera directly. Sits back slightly. Unhurried expression.
2-3s: Leans forward slowly. Points one finger toward camera. Glasses catch gold light.
3-6s: Direct eye contact. Speaks the outro. Micro slow-motion 0.2s on the word 'algorithm'.
6-8s: Sits back. Slight nod. Confident close.
8-10s: Bloomberg terminals pulse once brighter behind him. NAC logo glows. Subscribe text appears.
Camera: locked-off medium close-up. Never moves."

━━ NORMAL SCENE (pace: normal) VISUAL FORMAT ━━
"Single continuous shot, [one cut / no cuts]. [Smooth cinematic / slight handheld].
Audio: [specific ambient sounds — keyboard, terminal hum, chair movement, paper flip, breathing].
Lighting: warm gold key left + cool blue terminal fill. [Any variation].

NACARTHA CHARACTER (STRICT IDENTITY LOCK): [description]

ACTION:
0-2s: [precise action]
2-5s: [precise action + camera movement]
5-8s: [precise action. Optional: Micro slow-motion 0.3s at [specific moment]. Back to real-time.]
[continue]
Camera: [exact shot progression]"

━━ REVEAL SCENE (pace: reveal) VISUAL FORMAT ━━
"Single continuous shot, no cuts. Smooth push-in to ECU.
Audio: single keyboard click at impact moment. Terminal hum. Near-silence.
Lighting: cool blue dominant from terminal. Warm gold fades to near-black.

NACARTHA CHARACTER (STRICT IDENTITY LOCK): [description]

ACTION:
0-2s: Extreme close-up. Bloomberg terminal screen. Cursor blinks on [specific number/text].
Micro slow-motion 0.5s on the number. Back to real-time.
2-4s: Cut to NacArtha's face. Expressionless. Eyes scanning screen. Terminal glow on glasses.
4-5s: Slow zoom out. His index finger touches screen at the key data point.
Camera: ECU → medium close. Dolly out."

━━ EDUCATIONAL SCENE with STUDENT (educational episodes only) ━━
"Single continuous shot, one smooth cut. Cinematic.
Audio: marker on glass whiteboard, notebook pen, A/C hum, ambient classroom. No music.
Lighting: warm focused overhead on table. Cool blue accent from wall-mounted screen.
NacArtha lit gold from left. Student lit softer from above.

NACARTHA CHARACTER (STRICT IDENTITY LOCK): [description]
STUDENT CHARACTER (STRICT IDENTITY LOCK): [description]

ACTION:
0-2s: Student leans forward across glass table. Notebook open. Pen tapping paper.
Asks question — mouth visible, slight frown of concentration.
2-3s: Cut to NacArtha. Slight pause. Nods once. Stands. Moves to glass whiteboard.
3-7s: Writes formula/concept with marker. Speaks while writing. Letters appear clearly.
7-9s: NacArtha turns to camera — not to student. Addresses viewer directly.
Whiteboard formula visible in background. Student visible in foreground, taking notes.
Micro slow-motion 0.2s as NacArtha turns to camera.
9-10s: Pull back to wide — both characters visible. Whiteboard fills right side of frame.
Camera: medium on student → medium on NacArtha → wide establishing."

ADDITIONAL VISUAL RULES:
- Every scene must show a DIFFERENT angle, action, or setting than the previous
- Do NOT put narration text in visual_prompt — describe only what is SEEN
- Every reveal scene MUST show a specific number on a terminal (use a plausible value)
- Micro slow-motion is allowed only at high-tension moments — max 0.5s, then back to real-time
- short_scenes use the same scene 1 intro template (condensed) and CTA template
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
- Scenes 4-8: What happened → signals → what the bot did/refused → why → risk moment
- Scene 9 (reveal): Resolve the open loop with the exact number
- Scene 10 (cta): OUTRO RULE word-for-word
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
- Scene 10 (cta): OUTRO RULE word-for-word
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
- Scenes 4-8: Day-by-day highlights → best trade → worst trade → risk protection → lesson
- Scene 9 (reveal): Resolve the open loop — the exact worst moment number
- Scene 10 (cta): OUTRO RULE word-for-word
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
- Scenes 4-8: What happened → exact market impact → signal effects → what my bot does/did → lesson
- Scene 9 (reveal): The exact signal or stat that resolves the open loop
- Scene 10 (cta): OUTRO RULE word-for-word
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
- Scenes 4-8: Problem → concept → math/formula → how I use it → student asks a question → NacArtha explains at whiteboard
- Scene 9 (reveal): The exact formula/result that resolves the open loop — shown on whiteboard
- Scene 10 (cta): OUTRO RULE word-for-word
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
