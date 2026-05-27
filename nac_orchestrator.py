"""
NacArtha Cinematic Pipeline

1 master long video (4 min) + 1 short (50 sec) in English
→ Translated to Hindi + Telugu (same visuals, different ElevenLabs audio)
→ Uploaded to 3 separate YouTube channels

Hero shots:      Seedance 1.0 on Replicate (1 per format = 2 clips/day)
Scene footage:   OpenArtEngine — FLUX image → Ken Burns video (Replicate)
                 Falls back to StockEngine (Pexels) if REPLICATE_API_KEY unset or FLUX fails
Voices:          ElevenLabs multilingual_v2 → Edge TTS fallback
"""
import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engines.script_engine import ScriptEngine
from engines.topic_selector import TopicSelector
from engines.voice_engine import VoiceEngine
from engines.stock_engine import StockEngine
from engines.openart_engine import OpenArtEngine
from engines.seedance_engine import SeedanceEngine
from engines.video_assembler import VideoAssembler
from engines.thumbnail_engine import ThumbnailEngine
from engines.music_engine import MusicEngine
from engines.upload_engine import UploadEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nac_orchestrator")

OUTPUT_DIR = Path(__file__).parent / "output"


def main(langs: list = None, on_lang_done=None):
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except ImportError:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="", help="Topic ID (blank = auto-select)")
    parser.add_argument("--topic-type", default="", help="Force type: bot | news | evergreen")
    parser.add_argument("--lang", default="all", help="en | hi | te | all")
    args = parser.parse_args()

    if langs is None:
        langs = ["en", "hi", "te"] if args.lang == "all" else [args.lang]
    run_id = datetime.now().strftime("nac_%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"=== NacArtha Pipeline  run={run_id}  langs={langs}  topic={args.topic or 'auto'} ===")

    topic_selector   = TopicSelector()
    script_engine    = ScriptEngine()
    voice_engine     = VoiceEngine()
    stock_engine     = StockEngine()      # free Pexels fallback
    openart_engine   = OpenArtEngine()    # primary: FLUX image → video (Replicate)
    seedance_engine  = SeedanceEngine()   # hero shots: AI video (Replicate)
    assembler        = VideoAssembler()
    thumbnail_engine = ThumbnailEngine()
    music_engine     = MusicEngine()
    uploader         = UploadEngine(
        client_id=os.environ.get("YOUTUBE_CLIENT_ID", ""),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
        refresh_tokens={
            "en": os.environ.get("YOUTUBE_REFRESH_TOKEN_EN", ""),
            "hi": os.environ.get("YOUTUBE_REFRESH_TOKEN_HI", ""),
            "te": os.environ.get("YOUTUBE_REFRESH_TOKEN_TE", ""),
        },
    )

    # ── 1. Select topic + generate EN master script ─────────────────────────────
    if args.topic:
        from engines.topic_selector import BOT_BRAND_TOPICS, EDUCATIONAL_TOPICS
        all_topics = BOT_BRAND_TOPICS + EDUCATIONAL_TOPICS
        topic = next((t for t in all_topics if t["id"] == args.topic), None)
        if not topic:
            topic = {"id": args.topic, "title": args.topic, "type": "bot"}
    else:
        topic = topic_selector.select(force_type=getattr(args, "topic_type", ""))

    log.info(f"Generating EN master script [{topic.get('type','?')}]: {topic.get('title','')}")
    en_script = script_engine.generate_en(topic=topic)
    (run_dir / "script_en.json").write_text(json.dumps(en_script, ensure_ascii=False, indent=2))
    log.info(f"Topic: {en_script['title']}")

    # ── 2. Select music for this topic ──────────────────────────────────────────
    music_path = music_engine.select(en_script.get("topic_id", ""), en_script.get("topic_type", ""))
    log.info(f"Music: {music_path.name if music_path else 'none'}")

    # ── 3. Fetch video clips (shared — same visuals for all 3 channels) ─────────
    # Short clips are mapped from long clips (center-cropped landscape→portrait by assembler).
    # No separate portrait Seedance/FLUX calls — saves ~$0.22/day.
    log.info("Fetching video clips…")
    clips_long  = _fetch_clips(en_script["long_scenes"], run_dir, "long", stock_engine, openart_engine, seedance_engine)
    clips_short = _map_short_clips(en_script["short_scenes"], en_script["long_scenes"], clips_long)

    # ── 4. Per-channel pipeline ─────────────────────────────────────────────────
    results = {}

    for lang in langs:
        log.info(f"\n{'='*55}\n  [{lang.upper()}] Channel Pipeline\n{'='*55}")
        lang_dir = run_dir / lang
        lang_dir.mkdir(exist_ok=True)

        try:
            script = en_script if lang == "en" else script_engine.translate(en_script, lang)
            (lang_dir / f"script_{lang}.json").write_text(
                json.dumps(script, ensure_ascii=False, indent=2)
            )

            # Generate narration audio per scene (translated audio, English visuals)
            long_scenes  = _generate_audio(script["long_scenes"],  lang_dir / "audio" / "long",  voice_engine, lang)
            short_scenes = _generate_audio(script["short_scenes"], lang_dir / "audio" / "short", voice_engine, lang)

            # Overwrite text_overlay on every scene with the English version —
            # translated overlays render as boxes since Railway only has DejaVu Sans.
            en_long_overlays  = {s["id"]: s.get("text_overlay") for s in en_script["long_scenes"]}
            en_short_overlays = {s["id"]: s.get("text_overlay") for s in en_script["short_scenes"]}
            for s in long_scenes:
                s["text_overlay"] = en_long_overlays.get(s["id"])
            for s in short_scenes:
                s["text_overlay"] = en_short_overlays.get(s["id"])

            # Attach clip paths
            fallback = _black_clip(run_dir)
            for s in long_scenes:
                s["video_path"] = str(clips_long.get(s["id"], fallback))
            for s in short_scenes:
                s["video_path"] = str(clips_short.get(s["id"], fallback))

            # Assemble videos — all burned-in text always in English
            long_path  = lang_dir / "long.mp4"
            short_path = lang_dir / "short.mp4"

            log.info(f"  [{lang}] Assembling long video…")
            assembler.assemble(long_scenes,  long_path,  "landscape", music_path,
                               hook_text=en_script.get("hook_text", ""),
                               cta_text=en_script.get("cta_text", ""))

            log.info(f"  [{lang}] Assembling short video…")
            assembler.assemble(short_scenes, short_path, "portrait",  music_path,
                               hook_text=en_script.get("hook_text", ""),
                               cta_text=en_script.get("cta_text", ""))

            # Thumbnail — always English title (font has no Devanagari/Telugu glyphs)
            thumb_path = lang_dir / "thumbnail.jpg"
            thumbnail_engine.generate(en_script["title"], lang, thumb_path)

            # Upload to YouTube
            refresh_token = uploader.refresh_tokens.get(lang, "")
            if not refresh_token:
                log.warning(f"  [{lang}] No refresh token — skipping upload")
                results[lang] = {"status": "no_token", "long": str(long_path), "short": str(short_path)}
                continue

            log.info(f"  [{lang}] Uploading long video…")
            # Always use English description — translated descriptions render as boxes in video thumbnails/overlays
            description = en_script["description"] + "\n\nMusic: Kevin MacLeod (incompetech.com) — Licensed under Creative Commons: By Attribution 3.0"

            long_urls = uploader.upload_all_languages(
                video_path=long_path,
                thumbnail_path=thumb_path,
                translations={lang: {
                    "title":       script["title"],
                    "description": description,
                    "tags":        script.get("tags", []),
                }},
            )

            log.info(f"  [{lang}] Uploading short video…")
            short_urls = uploader.upload_all_languages(
                video_path=short_path,
                thumbnail_path=None,
                translations={lang: {
                    "title":       f"#Shorts {script['title']}",
                    "description": description,
                    "tags":        script.get("tags", []) + ["Shorts"],
                }},
            )

            results[lang] = {
                "status":    "success",
                "title":     script["title"],
                "long_url":  long_urls.get(lang),
                "short_url": short_urls.get(lang),
            }
            if on_lang_done:
                on_lang_done(lang)
            log.info(f"  [{lang}] Done. Long: {results[lang]['long_url']} | Short: {results[lang]['short_url']}")

        except Exception as ch_err:
            log.error(f"[{lang.upper()}] CHANNEL FAILED: {ch_err}", exc_info=True)
            results[lang] = {"status": "error", "error": str(ch_err)}

    # ── 4. Summary + Telegram ────────────────────────────────────────────────────
    summary = {"run_id": run_id, "topic": en_script.get("title"), "results": results}
    (run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    _notify_telegram(summary)

    log.info("\n=== PIPELINE COMPLETE ===")
    for lang, r in results.items():
        status = r.get("status", "?")
        detail = r.get("long_url") or r.get("error", "")
        log.info(f"  [{lang.upper()}] {status}: {detail}")


# ── Helpers ───────────────────────────────────────────────────────────────────

_SEEDANCE_PACES = {"hook", "reveal", "cta"}


def _fetch_clips(
    scenes: list[dict],
    run_dir: Path,
    label: str,
    stock_engine: StockEngine,
    openart_engine: OpenArtEngine,
    seedance_engine: SeedanceEngine,
) -> dict:
    clips: dict[int, Path] = {}
    clip_dir = run_dir / "clips" / label
    clip_dir.mkdir(parents=True, exist_ok=True)
    orientation = "portrait" if label == "short" else "landscape"

    for scene in scenes:
        sid       = scene["id"]
        clip_path = clip_dir / f"scene_{sid:03d}.mp4"
        pace      = scene.get("pace", "normal")
        visual    = ", ".join(scene.get("visual_keywords", ["finance", "trading", "market"]))
        narration = scene.get("narration", "")
        result    = None

        # ── hook / reveal / cta → Seedance AI video ──────────────────────────
        if pace in _SEEDANCE_PACES:
            log.info(f"  Scene {sid} [{pace}] → Seedance")
            result = seedance_engine.generate(visual, clip_path, orientation, narration=narration)
            if result:
                clips[sid] = result
                continue
            log.warning(f"  Seedance failed for scene {sid} [{pace}] — falling through to OpenArt")

        # ── normal → FLUX image → Pexels fallback ────────────────────────────
        variant = f"{label}_{sid}"
        result  = openart_engine.fetch(scene.get("visual_keywords", []), orientation, variant=variant)
        if not result:
            result = stock_engine.fetch(scene.get("visual_keywords", []), orientation, variant=variant)

        if result:
            clips[sid] = result
        else:
            log.warning(f"  No clip for scene {sid} — will use black fallback")

    return clips


def _map_short_clips(short_scenes: list, long_scenes: list, clips_long: dict) -> dict:
    """Map short scenes to existing long clips — short[0]→hook, short[1]→hero, short[2]→cta."""
    long_ids = [s["id"] for s in long_scenes]
    hero_id  = next((s["id"] for s in long_scenes if s.get("is_hero_shot")), long_ids[len(long_ids) // 2])
    sources  = [long_ids[0], hero_id, long_ids[-1]]
    clips    = {}
    for i, scene in enumerate(short_scenes):
        src_id = sources[i] if i < len(sources) else long_ids[0]
        clip   = clips_long.get(src_id)
        if clip:
            clips[scene["id"]] = clip
    return clips


def _generate_audio(
    scenes: list[dict],
    out_dir: Path,
    voice_engine: VoiceEngine,
    lang: str,
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = []
    for scene in scenes:
        sid = scene["id"]
        audio_path = out_dir / f"scene_{sid:03d}.mp3"
        voice_engine.generate(scene["narration"], audio_path, lang)
        s = dict(scene)
        s["narration_path"] = str(audio_path)
        result.append(s)
    return result


def _black_clip(run_dir: Path) -> Path:
    fb = run_dir / "clips" / "fallback_black.mp4"
    if not fb.exists():
        fb.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30",
            "-t", "10", "-c:v", "libx264", "-crf", "23", str(fb),
        ], capture_output=True)
    return fb


def _notify_telegram(summary: dict):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        import requests
        lines = [f"*NacArtha Pipeline*\n{summary.get('topic', '?')}\n"]
        for lang, r in summary.get("results", {}).items():
            if r.get("status") == "success":
                lines.append(f"✅ {lang.upper()}: {r.get('long_url', '')}")
            else:
                lines.append(f"❌ {lang.upper()}: {r.get('error', r.get('status', '?'))}")
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "Markdown"},
            timeout=30,
        )
    except Exception as e:
        log.warning(f"Telegram notify failed: {e}")


if __name__ == "__main__":
    main()
