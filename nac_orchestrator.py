"""
NacArtha Cinematic Pipeline v5

Three video types, each with different asset sources:

  bot_performance → HeyGen Nac clips + yfinance/trading system charts + Veo trading backgrounds
  educational     → HeyGen Nac + student clips + yfinance example charts + Veo classroom backgrounds
  news            → HeyGen Nac clips + real news images (NewsAPI) + yfinance market impact charts

Shorts: cut from first 60s of long video (portrait 1080×1920).
Same clips used across EN/HI/TE — only audio differs per language.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engines.script_engine    import ScriptEngine
from engines.topic_selector   import TopicSelector
from engines.voice_engine     import VoiceEngine
from engines.video_assembler  import VideoAssembler
from engines.thumbnail_engine import ThumbnailEngine
from engines.music_engine     import MusicEngine
from engines.upload_engine    import UploadEngine
from engines.library_engine            import LibraryEngine
from engines.chart_engine              import ChartEngine
from engines.synclabs_engine           import SyncLabsEngine
from engines.visual_intelligence_engine import VisualIntelligenceEngine

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
    parser.add_argument("--topic",      default="")
    parser.add_argument("--topic-type", default="")
    parser.add_argument("--lang",       default="all")
    args = parser.parse_args()

    if langs is None:
        langs = ["en", "hi", "te"] if args.lang == "all" else [args.lang]

    run_id  = datetime.now().strftime("nac_%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"=== NacArtha Pipeline  run={run_id}  langs={langs} ===")

    topic_selector   = TopicSelector()
    script_engine    = ScriptEngine()
    voice_engine     = VoiceEngine()
    assembler        = VideoAssembler()
    thumbnail_engine = ThumbnailEngine()
    music_engine     = MusicEngine()
    library          = LibraryEngine()
    charts           = ChartEngine()
    synclabs         = SyncLabsEngine()
    visual_intel     = VisualIntelligenceEngine()
    uploader         = UploadEngine(
        client_id=os.environ.get("YOUTUBE_CLIENT_ID", ""),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
        refresh_tokens={
            "en": os.environ.get("YOUTUBE_REFRESH_TOKEN_EN", ""),
            "hi": os.environ.get("YOUTUBE_REFRESH_TOKEN_HI", ""),
            "te": os.environ.get("YOUTUBE_REFRESH_TOKEN_TE", ""),
        },
    )

    # ── 1. Topic + script ────────────────────────────────────────────────────
    if args.topic:
        from engines.topic_selector import BOT_BRAND_TOPICS, EDUCATIONAL_TOPICS
        all_topics = BOT_BRAND_TOPICS + EDUCATIONAL_TOPICS
        topic = next((t for t in all_topics if t["id"] == args.topic), None)
        if not topic:
            topic = {"id": args.topic, "title": args.topic, "type": "bot"}
    else:
        topic = topic_selector.select(force_type=getattr(args, "topic_type", ""))

    video_type = topic.get("type", "bot")
    log.info(f"Topic [{video_type}]: {topic.get('title', '')}")

    en_script = script_engine.generate_en(topic=topic)
    (run_dir / "script_en.json").write_text(json.dumps(en_script, ensure_ascii=False, indent=2))

    # ── 2. Music ─────────────────────────────────────────────────────────────
    music_path = music_engine.select(en_script.get("topic_id", ""), video_type)
    log.info(f"Music: {music_path.name if music_path else 'none'}")

    # ── 3. Build scene visuals (shared across all languages) ─────────────────
    log.info(f"Building visuals for type={video_type}…")
    scene_visuals = _build_visuals(
        en_script["long_scenes"], run_dir, video_type,
        library, charts, topic, visual_intel,
    )

    # ── 4. Per-language pipeline ──────────────────────────────────────────────
    results = {}

    for lang in langs:
        log.info(f"\n{'='*55}\n  [{lang.upper()}] Pipeline\n{'='*55}")
        lang_dir = run_dir / lang
        lang_dir.mkdir(exist_ok=True)

        try:
            script = en_script if lang == "en" else script_engine.translate(en_script, lang)
            (lang_dir / f"script_{lang}.json").write_text(
                json.dumps(script, ensure_ascii=False, indent=2)
            )

            is_trading_en = (video_type in ("bot_performance", "bot") and lang == "en")

            long_path  = lang_dir / "long.mp4"
            short_path = lang_dir / "short.mp4"

            if is_trading_en:
                # EN trading: ElevenLabs TTS narration over Veo/Runway visuals
                log.info(f"  [{lang}] Trading EN — generating ElevenLabs TTS narration…")
                audio_scenes = _generate_audio(en_script["long_scenes"], lang_dir / "audio", voice_engine, "en")
                audio_map = {s["id"]: s.get("narration_path") for s in audio_scenes}

                en_overlays = {s["id"]: s.get("text_overlay") for s in en_script["long_scenes"]}
                scenes_vis = []
                for s in en_script["long_scenes"]:
                    v = scene_visuals.get(s["id"], {})
                    scenes_vis.append({
                        **s,
                        "image_path":     v.get("image_path", str(_black_image(run_dir))),
                        "chart_path":     v.get("chart_path"),
                        "extra_visuals":  v.get("extra_visuals", []),
                        "text_overlay":   en_overlays.get(s["id"]),
                        "narration_path": audio_map.get(s["id"]),
                    })
                log.info(f"  [{lang}] Assembling Veo-native video with ElevenLabs audio…")
                assembler.assemble_veo_native(
                    scenes_vis, long_path, music_path,
                    hook_text=en_script.get("hook_text", ""),
                    cta_text=en_script.get("cta_text", ""),
                )
                if not long_path.exists():
                    log.warning(f"  [en] Veo-native failed — falling back to TTS assembly (reusing cached audio)")
                    for s in audio_scenes:
                        v = scene_visuals.get(s["id"], {})
                        s["image_path"] = v.get("image_path", str(_black_image(run_dir)))
                        s["chart_path"] = v.get("chart_path")
                        s["text_overlay"] = None
                    assembler.assemble(audio_scenes, long_path, "landscape", music_path)
            else:
                # All languages (EN non-trading, HI, TE): ElevenLabs multilingual TTS assembly
                log.info(f"  [{lang}] Generating ElevenLabs audio…")
                scenes = _generate_audio(script["long_scenes"], lang_dir / "audio", voice_engine, lang)

                en_overlays = {s["id"]: s.get("text_overlay") for s in en_script["long_scenes"]}
                for s in scenes:
                    v = scene_visuals.get(s["id"], {})
                    s["image_path"]   = v.get("image_path", str(_black_image(run_dir)))
                    s["chart_path"]   = v.get("chart_path")
                    s["extra_visuals"]= v.get("extra_visuals", [])
                    s["text_overlay"] = en_overlays.get(s["id"])

                assembled_path = lang_dir / "assembled.mp4"
                log.info(f"  [{lang}] Assembling…")
                assembler.assemble(
                    scenes, assembled_path, "landscape", music_path,
                    hook_text=en_script.get("hook_text", ""),
                    cta_text=en_script.get("cta_text", ""),
                )
                import shutil; shutil.copy2(assembled_path, long_path)

            # Cut short from long video
            log.info(f"  [{lang}] Cutting Short…")
            assembler.cut_short(long_path, short_path)

            # Thumbnail
            thumb_path = lang_dir / "thumbnail.jpg"
            thumbnail_engine.generate(en_script["title"], lang, thumb_path)

            # Upload
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

            log.info(f"  [{lang}] Uploading…")
            long_urls = uploader.upload_all_languages(
                video_path=long_path,
                thumbnail_path=thumb_path,
                translations={lang: {
                    "title":       script["title"],
                    "description": description,
                    "tags":        script.get("tags", []),
                }},
            )
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
            log.info(f"  [{lang}] ✓ Long: {results[lang]['long_url']} | Short: {results[lang]['short_url']}")

        except Exception as e:
            log.error(f"[{lang.upper()}] FAILED: {e}", exc_info=True)
            results[lang] = {"status": "error", "error": str(e)}

    # ── 5. Summary ────────────────────────────────────────────────────────────
    summary = {"run_id": run_id, "topic": en_script.get("title"), "results": results}
    (run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    _notify_telegram(summary)

    log.info("\n=== PIPELINE COMPLETE ===")
    for lang, r in results.items():
        log.info(f"  [{lang.upper()}] {r.get('status')}: {r.get('long_url') or r.get('error', '')}")


# ── Visual builder (type-specific) ────────────────────────────────────────────

def _build_visuals(
    scenes: list,
    run_dir: Path,
    video_type: str,
    library: LibraryEngine,
    chart_eng: ChartEngine,
    topic: dict,
    visual_intel: "VisualIntelligenceEngine | None" = None,
) -> dict:
    """Returns {scene_id: {image_path, chart_path, extra_visuals}} for all scenes."""
    visuals = {}
    images_dir = run_dir / "images"
    charts_dir = run_dir / "charts"

    # Pre-fetch news images once for news-type videos
    news_images = []
    if video_type in ("news", "trending_news"):
        query = topic.get("news_headline", topic.get("title", "financial markets"))
        news_images = chart_eng.fetch_news_images(query, charts_dir / "news", max_images=6)

    news_img_idx = 0

    for i, scene in enumerate(scenes):
        sid        = scene["id"]
        scene_type = scene.get("scene_type", "illustrated")
        emotion    = scene.get("emotion", "confidence")
        chart_key  = scene.get("chart_key")
        images_dir.mkdir(parents=True, exist_ok=True)

        image_path = None
        chart_path = None

        is_trading = video_type in ("bot_performance", "bot")

        # ── nac_face scene ───────────────────────────────────────────────────
        if scene_type == "nac_face":
            pace = scene.get("pace", "normal")
            if is_trading:
                # Hook + CTA: use Runway clips (camera-facing, highest impact)
                # Reveal + others: use any NAC veo clip by pose
                pose_map = {"hook": "camera_direct", "cta": "camera_point", "reveal": "pointing"}
                pose = pose_map.get(pace)
                if pace in ("hook", "cta"):
                    clip = library.get_runway_nac_clip(pose=pose) or library.get_nac_veo_clip(pose=pose)
                else:
                    clip = library.get_nac_veo_clip(pose=pose) or library.get_nac_veo_clip()
            else:
                clip = None
            if not clip:
                cat  = {"hook": "hook", "cta": "cta", "reveal": "reveal"}.get(pace, "normal")
                clip = library.get_nac_clip(emotion=emotion, category=cat)
            image_path = str(clip) if clip else None

        # ── student scene ────────────────────────────────────────────────────
        elif scene_type == "student":
            clip = library.get_student_clip(emotion="curiosity")
            image_path = str(clip) if clip else None

        # ── chart scene — treat as illustrated (no charts in videos) ────────
        elif scene_type == "chart":
            bg = library.get_nac_veo_clip() or library.get_runway_nac_clip()
            image_path = str(bg) if bg else None
            chart_path = None  # no charts in videos

        # ── news scene ───────────────────────────────────────────────────────
        elif scene_type == "news":
            if news_images and news_img_idx < len(news_images):
                image_path = str(news_images[news_img_idx])
                news_img_idx += 1
            if chart_key:
                chart_path = _generate_chart(chart_key, chart_eng, charts_dir, topic)

        # ── illustrated scene ────────────────────────────────────────────────
        else:
            if is_trading:
                bg = library.get_nac_veo_clip()
            else:
                bg_cat = "classroom" if video_type == "educational" else "trading"
                bg     = library.get_background(bg_cat)
            image_path = str(bg) if bg else None

        # ── NAC Memory Rule: get contextual visuals for every scene ─────────
        extra_visuals = []
        if visual_intel:
            narration = scene.get("narration", "")
            news_headline = topic.get("news_headline", topic.get("title", ""))
            intel_dir = images_dir / f"intel_{sid}"
            try:
                extra_visuals = visual_intel.get_scene_visuals(
                    narration=narration,
                    scene_type=scene_type,
                    out_dir=intel_dir,
                    scene_id=str(sid),
                    news_headline=news_headline,
                    max_images=3,
                    video_type=video_type,
                )
                extra_visuals = [str(p) for p in extra_visuals if p and Path(p).exists()]
            except Exception as e:
                log.warning(f"  Visual intel scene {sid}: {e}")

        visuals[sid] = {
            "image_path":    image_path,
            "chart_path":    chart_path,
            "extra_visuals": extra_visuals,
        }

    return visuals


def _generate_chart(chart_key: str, chart_eng: ChartEngine, charts_dir: Path, topic: dict) -> Path | None:
    charts_dir.mkdir(parents=True, exist_ok=True)
    symbol = topic.get("symbol", "SPY")

    if chart_key == "pnl":
        return _fetch_bot_chart("pnl", charts_dir)
    if chart_key == "equity":
        return _fetch_bot_chart("equity", charts_dir)
    if chart_key == "positions":
        return _fetch_bot_chart("positions", charts_dir)
    if chart_key == "trades":
        return _fetch_bot_chart("trades", charts_dir)
    if chart_key == "candlestick":
        return chart_eng.candlestick(symbol, "1mo", charts_dir / f"candle_{symbol}.png")
    if chart_key == "rsi":
        return chart_eng.rsi_ema(symbol, "3mo", charts_dir / f"rsi_{symbol}.png")
    if chart_key == "news_impact":
        ev_date = topic.get("event_date", datetime.now().strftime("%Y-%m-%d"))
        return chart_eng.news_impact(symbol, ev_date, charts_dir / f"impact_{symbol}.png")
    return None


def _fetch_bot_chart(key: str, charts_dir: Path) -> Path | None:
    """Fetch pre-rendered chart PNG from Railway trading system."""
    railway_url = os.environ.get("RAILWAY_API_URL", "")
    api_key     = os.environ.get("TRADING_API_KEY", "")
    if not railway_url:
        return None
    try:
        import requests
        r = requests.get(
            f"{railway_url}/api/charts/{key}",
            headers={"X-Api-Key": api_key},
            timeout=30,
        )
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            p = charts_dir / f"{key}.png"
            p.write_bytes(r.content)
            return p
    except Exception as e:
        log.warning(f"  Bot chart [{key}] fetch failed: {e}")
    return None


# ── Shared helpers ────────────────────────────────────────────────────────────

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


def _upload_for_translate(video_path: Path) -> str:
    """Upload EN video to HeyGen /v3/assets (multipart). Returns asset_id or empty string."""
    import requests as _r
    api_key = os.environ.get("HEYGEN_API_KEY", "")
    size_mb = video_path.stat().st_size / 1024 / 1024
    if size_mb > 32:
        log.warning(f"  EN video {size_mb:.1f} MB exceeds HeyGen 32 MB limit — translate skipped")
        return ""
    try:
        with open(video_path, "rb") as f:
            r = _r.post(
                "https://api.heygen.com/v3/assets",
                headers={"X-Api-Key": api_key},
                files={"file": ("long.mp4", f, "video/mp4")},
                timeout=300,
            )
        if r.status_code != 200:
            log.warning(f"  HeyGen asset upload failed: {r.status_code} {r.text[:200]}")
            return ""
        data = r.json().get("data", {})
        asset_id = data.get("asset_id", "")
        log.info(f"  HeyGen asset uploaded → asset_id={asset_id[:16]}…")
        return asset_id
    except Exception as e:
        log.warning(f"  HeyGen asset upload error: {e}")
        return ""


def _heygen_video_translate(asset_id: str, output_language: str, out_path: Path, api_key: str) -> Path:
    """Translate EN video (by HeyGen asset_id) to target language using v3 API."""
    import requests as _r, time as _t
    h = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    try:
        payload = {
            "video": {"type": "asset_id", "asset_id": asset_id},
            "output_languages": [output_language],
        }
        r = _r.post("https://api.heygen.com/v3/video-translations", headers=h,
                    json=payload, timeout=30)
        if r.status_code not in (200, 202):
            log.warning(f"  HeyGen translate submit failed: {r.status_code} {r.text[:300]}")
            return None
        resp_data = r.json().get("data", {})
        # v3 returns video_translation_id (singular) for single-language request
        tid = (resp_data.get("video_translation_id")
               or (resp_data.get("video_translation_ids") or [None])[0])
        if not tid:
            log.warning(f"  HeyGen translate: no job ID in response: {resp_data}")
            return None
        log.info(f"  HeyGen translate job={tid}")

        deadline = _t.time() + 1800
        while _t.time() < deadline:
            _t.sleep(20)
            s = _r.get(f"https://api.heygen.com/v3/video-translations/{tid}",
                       headers={"X-Api-Key": api_key}, timeout=15)
            d = s.json().get("data", {})
            status = d.get("status", "")
            log.info(f"  HeyGen translate [{status}]")
            if status == "completed":
                url = d.get("video_url", "")
                resp = _r.get(url, stream=True, timeout=300)
                resp.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_content(1024 * 1024): f.write(chunk)
                log.info(f"  Translate saved → {out_path.name} ({out_path.stat().st_size/1024/1024:.1f} MB)")
                return out_path
            if status == "failed":
                log.warning(f"  HeyGen translate failed: {d.get('failure_message', d)}")
                return None
        log.warning("  HeyGen translate timeout")
        return None
    except Exception as e:
        log.error(f"  _heygen_video_translate error: {e}", exc_info=True)
        return None


def _concat_audio(audio_dir: Path, out_path: Path):
    """Concatenate all scene audio files into one WAV for SyncLabs."""
    import glob, shutil
    files = sorted(audio_dir.glob("scene_*.mp3"))
    if not files:
        return
    list_file = audio_dir / "_concat.txt"
    list_file.write_text("\n".join(f"file '{f}'" for f in files))
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:a", "pcm_s16le", str(out_path),
    ], capture_output=True)
    list_file.unlink(missing_ok=True)


def _black_image(run_dir: Path) -> Path:
    fb = run_dir / "images" / "fallback_black.jpg"
    if not fb.exists():
        fb.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080",
            "-frames:v", "1", str(fb),
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
