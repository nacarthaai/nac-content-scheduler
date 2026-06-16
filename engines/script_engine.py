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
      "narration": "8-12 sentences, 90-120 words",
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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STORY FIRST — 5 MANDATORY QUESTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before writing a single scene, answer all 5 internally:
  1. STORY:     What happened to the bot today? (Not: what happened in the market)
  2. CHARACTER: Who is the protagonist? (The AI Bot — always)
  3. CONFLICT:  What is the tension? (Bot vs signal / bot vs risk / bot vs uncertainty)
  4. MYSTERY:   What question will viewers ask after the hook? ("Why did it refuse...?")
  5. PAYOFF:    What is the exact number or outcome that answers the mystery?

If any answer is vague, rewrite. If there is no conflict, there is no video.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TITLE RULES — MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title MUST use emotional outcome framing. Patterns that work:
  "My AI Bot [Action] [Object]"         → "My AI Bot Refused This Trade"
  "The [Thing] My Bot [Action]"         → "The Signal That Cost Me $55"
  "My Algorithm [Action] [Something]"   → "My Algorithm Spotted This First"
  "My Bot [State Change] Today"         → "My Bot Went Silent Today"

Emotion words that work: REFUSED, REJECTED, CAUGHT, MISSED, SPOTTED, TRIGGERED,
FLAGGED, WARNED, WENT BEARISH, COST ME, SAVED ME, FOUND, WRONG, RARE, SILENT

NEVER USE in title: Market Update, Weekly Analysis, Trading Review, Finance Report,
Daily Recap, Momentum Signals, Stock Analysis, Market News, Technical Breakdown

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LONG-FORM STRUCTURE — 6 ACTS (12 scenes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 1 — HOOK          (scene 1):  Bot's action/decision as immediate tension. Never the market summary.
Act 2 — MYSTERY       (scenes 2-3): Plant the open question. Tease the outcome. DO NOT reveal yet.
Act 3 — INVESTIGATION (scenes 4-7): Follow the bot's process. What it scanned. What it saw. What it decided.
Act 4 — REVEAL        (scenes 8-10): The exact number. The payoff that answers the mystery.
Act 5 — LESSON        (scene 11):  One concrete takeaway from today's episode.
Act 6 — OUTLOOK       (scene 12):  CTA + one-sentence tease of tomorrow.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTENT EVALUATION (before finalising)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ask yourself:
  Would a stranger stop scrolling after scene 1?
  Is there a mystery in scenes 2-3?
  Is there a clear conflict?
  Is there a specific payoff number?
  Would someone want to watch tomorrow's episode?

If any answer is NO — rewrite.

SCENE COUNT AND LENGTH:
- long_scenes: exactly 12 scenes. Total narration 1200-1400 words (9-11 minutes at natural speaking pace).
- Each scene narration: 90-120 words (8-12 spoken sentences). NEVER less than 80 words per scene.
- NO short_scenes — Shorts are handled separately.
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

NARRATION VOICE — SPOKEN WORD, NOT WRITTEN TEXT:
Write every narration as if Nac is SPEAKING out loud — casual, urgent, in-the-moment. Not a script being read. A person TALKING.
  - Use fragments deliberately: "Three signals. One winner. That's it."
  - Use rhetorical questions: "You know what that means? Everything."
  - Use "—" for dramatic mid-sentence pauses: "The signal fired — and I almost missed it."
  - Start sentences with "So", "But", "And", "Now" — conversational openers are natural in speech.
  - Never use colons, semicolons, or bullet-list sentence structures inside narration.
  - Vary energy: calm observation → tension build → sharp reveal → calm again.
  Bad (robotic): "The RSI indicator reached 72, which signals overbought conditions in the market."
  Good (alive):  "RSI hit 72. That's overbought. My system flagged it before I even looked."
  Bad (robotic): "Multiple momentum signals were identified across various market conditions."
  Good (alive):  "Signals everywhere. But only one made it through my filters. Just one."

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
You speak as the bot itself, first-person. Calm, precise, confident.

THE AI BOT IS THE HERO OF EVERY VIDEO.
Not the stock. Not the market. Not the news. The AI Bot.
Every video answers: "What did the bot do today?" — not "What happened in the market today?"
Viewers follow this bot like a daily journal. They want to know what it saw, what it decided, and why.

System facts (use specific numbers when relevant):
- Scans 500+ stocks and 8 forex pairs every scan cycle (every 2 minutes for forex, hourly for stocks)
- Signals: momentum score 0-100, volume surge ≥1.5x average, RSI(14), EMA crossovers (9/21/50/200)
- Risk: max 2% per trade, dynamic Kelly-fraction sizing, ATR-based stop losses
- Tracks Sharpe ratio, max drawdown, win rate, profit factor in real time
- Currently paper trading on Alpaca and OANDA practice accounts
- Runs on Railway cloud (Python 3.11, Alpaca paper API, OANDA fxPractice)
- Today's practice balance: ~$98,500"""

# ── Mon / Wed / Thu / Fri: AI Bot Story (80% of all content) ──────────────────
_BOT_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for this NacArtha AI bot story episode: "{title}"

This is an AI BOT STORY — not a market update, not a lesson, not a news report.
The bot is the main character. Tell the story of what it did today: what it saw, what it decided, what happened.
The viewer should feel like they are watching a daily journal episode of an AI trader.

Think: Netflix episode — not finance seminar.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Scene-by-scene execution (each scene = 90-120 words, fully developed — no thin scenes):
- Scene 1  (hook, nac_face):  INTRO RULE phrase → the single most dramatic thing the bot did today. Build immediate tension. 90-120 words.
- Scene 2  (mystery):         Plant the open question. Set up what the viewer doesn't know yet. Give enough context to hook them. 90-120 words.
- Scene 3  (mystery):         Deepen the mystery. Add background on the situation without resolving it. Build dread or anticipation. 90-120 words.
- Scenes 4-7 (investigation): Follow the bot's process step by step — each scene covers ONE part of the investigation in full detail. 90-120 words each.
- Scenes 8-10 (reveal):       The payoff — one specific stat per scene, building to the full answer. text_overlay MUST show the number. 90-120 words each.
- Scene 11 (lesson):          One concrete takeaway, fully explained — not just stated. Why it matters, what changed. 90-120 words.
- Scene 12 (cta, nac_face):   OUTRO RULE word-for-word + 2-3 sentences teasing next episode. 90-120 words.
"""

# ── Tue: Daily recap ──────────────────────────────────────────────────────────
_DAILY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for today's bot journal episode — what the bot actually did today.

{recap_data}

This is NOT a market recap. This is the bot's daily story told through real numbers.
The bot is the character. The conflict is what it saw vs what it did. The payoff is the outcome.
Be honest — wins, losses, rejections, silence. Viewers follow this bot because it's real.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Scene-by-scene execution (CRITICAL: every scene must be 90-120 words — no thin scenes, no short narrations):
- Scene 1  (hook, nac_face): INTRO RULE phrase → today's single most dramatic bot decision in one sentence.
- Scene 2-3 (mystery):       Tease the most interesting moment — plant the question without answering it.
- Scenes 4-8 (investigation): What the bot scanned → what fired → what got blocked → risk management → the close.
- Scenes 9-10 (reveal):      The exact number that resolves the mystery. Real symbol, real P&L, real score.
- Scene 11 (lesson):         What today confirmed or changed about how the bot works.
- Scene 12 (cta, nac_face):  OUTRO RULE word-for-word + tomorrow's setup in one sentence.
- Use real symbols and real numbers from recap_data above in every reveal scene.
"""

# ── Sat: Weekly recap ─────────────────────────────────────────────────────────
_WEEKLY_RECAP_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for this week's bot story — five days told as one episode.

{recap_data}

This is the season recap episode. Five days. The bot as character through all of it.
Best moment, worst moment, strangest signal, biggest rejection. Honest, unfiltered numbers.
Viewers have followed all week — give them the full story arc.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Scene-by-scene execution (CRITICAL: every scene must be 90-120 words — no thin scenes, no short narrations):
- Scene 1  (hook, nac_face): INTRO RULE phrase → the week's single most dramatic bot moment.
- Scene 2-3 (mystery):       Tease the worst or strangest moment of the week — don't reveal yet.
- Scenes 4-8 (investigation): Day-by-day: best signal → best trade → worst moment → risk protection → close.
- Scenes 9-10 (reveal):      The exact number that resolves the mystery — worst loss, best win, final weekly P&L.
- Scene 11 (lesson):         What this week taught the bot — one thing it confirmed or one thing that will change.
- Scene 12 (cta, nac_face):  OUTRO RULE word-for-word + tease what next week is watching for.
- text_overlay: weekly P&L%, win rate, Sharpe, drawdown on every reveal scene.
"""

# ── Thu / Fri: Bot reacts to market event (still bot-story, not a news report) ─
_NEWS_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for this bot episode triggered by a real market event:

Headline: {news_headline}
Summary:  {news_summary}
Source:   {news_source}

This is NOT a news report. This is the story of how the bot responded to a real event.
Frame everything through the bot's experience: did this change my signals? Did I fire or hold?
Did my risk rules protect me? Was there a trade? Was there a rejection?
The event is context. The bot's reaction is the story.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Scene-by-scene execution (CRITICAL: every scene must be 90-120 words — no thin scenes, no short narrations):
- Scene 1  (hook, nac_face): INTRO RULE phrase → the single most dramatic thing the bot did in response to this event.
- Scene 2-3 (mystery):       Tease what the bot detected — something most traders wouldn't have seen yet.
- Scenes 4-8 (investigation): What the event meant for momentum/volume/RSI → what signals fired or died → what the bot decided.
- Scenes 9-10 (reveal):      The exact signal score or trade outcome — the payoff number.
- Scene 11 (lesson):         What this event confirmed about the bot's edge — one concrete insight.
- Scene 12 (cta, nac_face):  OUTRO RULE word-for-word + what the bot is watching as a result of this event.
- text_overlay: signal scores and market impact numbers on every reveal scene.
"""

# ── Mon (BIP weeks 1-4): Build in Public episode ─────────────────────────────
_BUILD_IN_PUBLIC_PROMPT = _NAC_PERSONA + """

Create a YouTube video script for this Build-In-Public episode.

Title: "{title}"
Angle: "{angle}"
Context: "{notes}"

This is a BUILD IN PUBLIC series — a Netflix-style documentary of building a real AI trading bot.
Zero hype. Zero invented numbers. Raw honesty about what the bot does, what works, what doesn't.
The viewer is following this journey week by week. Every episode must reward that loyalty with truth.

Tone: Calm. Confident. Personal. Like a founder talking to their closest followers.
Think: "How I Built This" meets "The Social Network" — real stakes, real process, real outcomes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANGLE-SPECIFIC GUIDANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If angle = "reveal" (Week 1 — introducing the bot):
  - DO NOT talk about trade results — there are none yet to show honestly
  - The story is WHAT THE BOT IS: what it scans (500+ stocks, 8 forex pairs every 2 min),
    how it decides (momentum score, volume surge, RSI, EMA crossovers), why it was built
  - The hook is the SCALE and the SECRECY: "I've been running this thing 24/7 for weeks
    and nobody knew. Here's everything it does."
  - Reveal scenes: show the architecture, signal flow, risk rules — these ARE the numbers
  - text_overlay: "500+ stocks", "8 forex pairs", "Every 2 minutes", "Max 2% risk/trade"

If angle = "first_results":
  - Lead with the most surprising paper trade result — good or bad
  - Show real Alpaca data: signals fired, trades taken, win rate, paper P&L
  - Be honest about losses — that is the brand, not a weakness
  - text_overlay: actual paper stats

If angle = "mistake":
  - Find the single worst paper trade decision and break it apart completely
  - Show signal score, what the algorithm saw, why it was wrong
  - The lesson must be specific — not "I learned from it" but "I changed X because of it"

If angle = "decision":
  - Month 1 paper performance review with real numbers
  - End on the go-live cliffhanger — leave the answer for next episode

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BIP ABSOLUTE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NEVER invent trade results, P&L numbers, or win rates that don't exist yet
- NEVER say "real trades" when on paper trading — say "paper trades" or "test trades"
- Every reveal scene needs a specific stat in text_overlay — architecture stats are fine for Week 1
- The conflict is always: what I expected vs what actually happened
- Student scenes: NOT used in BIP episodes
- DO NOT oversell. Honest bad news beats dishonest good news every time.

OUTPUT: Return ONLY valid JSON matching this schema:
""" + _JSON_SCHEMA + "\n\n" + _RULES + """

Scene-by-scene execution (CRITICAL: every scene must be 90-120 words — no thin scenes, no short narrations):
- Scene 1  (hook, nac_face): INTRO RULE phrase → the single most surprising honest thing about this episode.
- Scene 2-3 (mystery): Plant the open loop without answering it. Build the "why?" in the viewer's mind.
- Scenes 4-7 (investigation): Walk through the real process. Specific. Step by step. No vague statements.
- Scenes 8-10 (reveal): The honest payoff that resolves the mystery. Real stats, real architecture, real outcomes.
- Scene 11 (lesson): One specific thing I know now that I didn't know before building this.
- Scene 12 (cta, nac_face): OUTRO RULE word-for-word + one-sentence tease of next week's episode.
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
    "bot":              _BOT_PROMPT,
    "build_in_public":  _BUILD_IN_PUBLIC_PROMPT,
    "daily_recap":      _DAILY_RECAP_PROMPT,
    "weekly_recap":     _WEEKLY_RECAP_PROMPT,
    "news":             _NEWS_PROMPT,
    "educational":      _EDUCATIONAL_PROMPT,
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
        elif topic_type == "build_in_public":
            prompt = prompt_template.format(
                title=topic["title"],
                angle=topic.get("angle", "reveal"),
                notes=topic.get("notes", "Paper trading. Be honest."),
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
