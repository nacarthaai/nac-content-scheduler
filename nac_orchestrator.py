"""
NacArtha Cinematic Pipeline v2

Every clip is purpose-built using Seedance 2.0:
  - reference_images: NacArtha character sheets → consistent photorealistic character
  - reference_audios: ElevenLabs narration audio → automatic lip sync

Flow per language:
  1. Translate script
  2. Generate narration audio (ElevenLabs / Edge TTS fallback)
  3. For each scene: Seedance 2.0 (character ref + audio) → lip-synced clip
  4. FFmpeg assembles final video with HUD overlays + music
  5. Upload to YouTube

No Ken Burns, no stock footage, no generic B-roll.
Every visual matches exactly what Nac is saying.
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

from engines.script_engine   import ScriptEngine
from engines.topic_selector  import TopicSelector
from engines.voice_engine    import VoiceEngine
from engines.seedance_engine import SeedanceEngine
from engines.video_assembler import VideoAssembler
from engines.thumbnail_engine import ThumbnailEngine
from engines.music_engine    import MusicEngine
from engines.upload_engine   import UploadEngine

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
    parser.add_argument("--topic",      default="", help="Topic ID (blank = auto-select)")
    parser.add_argument("--topic-type", default="", help="Force type: bot | news | evergreen")
    parser.add_argument("--lang",       default="all", help="en | hi | te | all")
    args = parser.parse_args()

    if langs is None:
        langs = ["en", "hi", "te"] if args.lang == "all" else [args.lang]

    run_id  = datetime.now().strftime("nac_%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"=== NacArtha Pipeline  run={run_id}  langs={langs}  topic={args.topic or 'auto'} ===")

    topic_selector  = TopicSelector()
    script_engine   = ScriptEngine()
    voice_engine    = VoiceEngine()
    seedance        = SeedanceEngine()
    assembler       = VideoAssembler()
    thumbnail_engine = ThumbnailEngine()
    music_engine    = MusicEngine()
    uploader        = UploadEngine(
        client_id=os.environ.get("YOUTUBE_CLIENT_ID", ""),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
        refresh_tokens={
            "en": os.environ.get("YOUTUBE_REFRESH_TOKEN_EN", ""),
            "hi": os.environ.get("YOUTUBE_REFRESH_TOKEN_HI", ""),
            "te": os.environ.get("YOUTUBE_REFRESH_TOKEN_TE", ""),
        },
    )

    # ── 1. Select topic + generate EN master script ──────────────────────────
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

    # ── 2. Select music ──────────────────────────────────────────────────────
    music_path = music_engine.select(en_script.get("topic_id", ""), en_script.get("topic_type", ""))
    log.info(f"Music: {music_path.name if music_path else 'none'}")

    # ── 3. Per-language pipeline ─────────────────────────────────────────────
    # Each language gets its own clips because lip sync is per audio track.
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

            # ── 3a. Generate narration audio FIRST (needed for lip sync) ────
            log.info(f"  [{lang}] Generating narration audio…")
            long_scenes  = _generate_audio(script["long_scenes"],  lang_dir / "audio" / "long",  voice_engine, lang)
            short_scenes = _generate_audio(script["short_scenes"], lang_dir / "audio" / "short", voice_engine, lang)

            # ── 3b. Generate video clips with Seedance 2.0 (lip synced) ────
            log.info(f"  [{lang}] Generating video clips with Seedance 2.0…")
            clips_long  = _generate_clips(long_scenes,  lang_dir / "clips" / "long",  seedance, "landscape")
            clips_short = _generate_clips(short_scenes, lang_dir / "clips" / "short", seedance, "portrait")

            # Attach clip paths to scenes
            fallback = _black_clip(run_dir)
            for s in long_scenes:
                s["video_path"] = str(clips_long.get(s["id"], fallback))
            for s in short_scenes:
                s["video_path"] = str(clips_short.get(s["id"], fallback))

            # Text overlays always in English (translated glyphs don't render on Railway)
            en_long_overlays  = {s["id"]: s.get("text_overlay") for s in en_script["long_scenes"]}
            en_short_overlays = {s["id"]: s.get("text_overlay") for s in en_script["short_scenes"]}
            for s in long_scenes:
                s["text_overlay"] = en_long_overlays.get(s["id"])
            for s in short_scenes:
                s["text_overlay"] = en_short_overlays.get(s["id"])

            # ── 3c. Assemble ────────────────────────────────────────────────
            long_path  = lang_dir / "long.mp4"
            short_path = lang_dir / "short.mp4"

            log.info(f"  [{lang}] Assembling long video…")
            assembler.assemble(
                long_scenes, long_path, "landscape", music_path,
                hook_text=en_script.get("hook_text", ""),
                cta_text=en_script.get("cta_text", ""),
            )

            log.info(f"  [{lang}] Assembling short video…")
            assembler.assemble(
                short_scenes, short_path, "portrait", music_path,
                hook_text=en_script.get("hook_text", ""),
                cta_text=en_script.get("cta_text", ""),
            )

            # ── 3d. Thumbnail ────────────────────────────────────────────────
            thumb_path = lang_dir / "thumbnail.jpg"
            thumbnail_engine.generate(en_script["title"], lang, thumb_path)

            # ── 3e. Upload ───────────────────────────────────────────────────
            refresh_token = uploader.refresh_tokens.get(lang, "")
            if not refresh_token:
                log.warning(f"  [{lang}] No refresh token — skipping upload")
                results[lang] = {"status": "no_token", "long": str(long_path), "short": str(short_path)}
                if on_lang_done:
                    on_lang_done(lang)
                continue

            description = (
                en_script["description"]
                + "\n\nMusic: Kevin MacLeod (incompetech.com) — Licensed under Creative Commons: By Attribution 3.0"
            )

            log.info(f"  [{lang}] Uploading long video…")
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

    # ── 4. Summary + Telegram ────────────────────────────────────────────────
    summary = {"run_id": run_id, "topic": en_script.get("title"), "results": results}
    (run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    _notify_telegram(summary)

    log.info("\n=== PIPELINE COMPLETE ===")
    for lang, r in results.items():
        status = r.get("status", "?")
        detail = r.get("long_url") or r.get("error", "")
        log.info(f"  [{lang.upper()}] {status}: {detail}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_audio(scenes: list, out_dir: Path, voice_engine: VoiceEngine, lang: str) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = []
    for scene in scenes:
        sid        = scene["id"]
        audio_path = out_dir / f"scene_{sid:03d}.mp3"
        voice_engine.generate(scene["narration"], audio_path, lang)
        s = dict(scene)
        s["narration_path"] = str(audio_path)
        result.append(s)
    return result


def _generate_clips(scenes: list, out_dir: Path, seedance: SeedanceEngine, orientation: str) -> dict:
    """Generate one Seedance 2.0 clip per scene, with lip sync from narration audio."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = {}
    for scene in scenes:
        sid        = scene["id"]
        clip_path  = out_dir / f"scene_{sid:03d}.mp4"
        visual     = scene.get("visual_prompt") or ", ".join(scene.get("visual_keywords", ["NacArtha trading room"]))
        audio_path = Path(scene.get("narration_path", "")) if scene.get("narration_path") else None

        log.info(f"  Scene {sid} [{scene.get('pace','?')}] → Seedance 2.0")
        result = seedance.generate(visual, clip_path, orientation, audio_path=audio_path)
        if result:
            clips[sid] = result
        else:
            log.warning(f"  Scene {sid}: Seedance failed — will use black fallback")
    return clips


def _black_clip(run_dir: Path) -> Path:
    fb = run_dir / "clips" / "fallback_black.mp4"
    if not fb.exists():
        fb.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30",
            "-t", "5", "-c:v", "libx264", "-crf", "23", str(fb),
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
