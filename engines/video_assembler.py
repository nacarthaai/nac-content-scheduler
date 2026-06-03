"""
VideoAssembler — Operation Khamoshi style pipeline.

Per scene:
  1. Flux image → FFmpeg Ken Burns animation (zoompan) + audio
  2. Pillow text overlay (watermark + scene text + hook/CTA)
  3. Chart overlay (if scene has chart_path)

Final assembly: concat all scenes → mix background music.
Shorts: cut first 60s of long landscape video → crop to portrait 1080×1920.
"""
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("video_assembler")

ASSETS = Path(__file__).parent.parent / "assets"
FONT_PATH = ASSETS / "font.ttf"
WATERMARK = "NACARTHA.AI"
FADE_DUR = 0.4
SHORT_DURATION = 60  # seconds


class VideoAssembler:

    def assemble(
        self,
        scenes: list,
        out_path: Path,
        format: str = "landscape",
        music_path=None,
        hook_text: str = "",
        cta_text: str = "",
    ) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        w, h = (1920, 1080) if format == "landscape" else (1080, 1920)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            scene_paths = []
            for i, scene in enumerate(scenes):
                scene_out = tmp / f"scene_{i:03d}.mp4"
                overlay   = scene.get("text_overlay") or ""
                extra     = hook_text if i == 0 else (cta_text if i == len(scenes) - 1 else "")
                pace      = scene.get("pace", "normal")
                chart_path = Path(scene["chart_path"]) if scene.get("chart_path") else None

                self._build_scene(
                    image=Path(scene["image_path"]),
                    audio=Path(scene["narration_path"]),
                    out=scene_out,
                    w=w, h=h,
                    overlay=overlay,
                    extra_text=extra,
                    scene_idx=i,
                    pace=pace,
                    chart_path=chart_path,
                )
                scene_paths.append(scene_out)

            raw = tmp / "raw.mp4"
            self._concat(scene_paths, raw)

            if music_path and Path(music_path).exists():
                self._mix_music(raw, Path(music_path), out_path)
            else:
                shutil.copy2(raw, out_path)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        log.info(f"Assembled {format} → {out_path.name} ({size_mb:.1f} MB)")
        return out_path

    def assemble_veo_native(
        self,
        scenes: list,
        out_path: Path,
        music_path=None,
        hook_text: str = "",
        cta_text: str = "",
    ) -> Path:
        """Assemble Veo clips keeping their native audio (English trading videos)."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        w, h = 1920, 1080

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            scene_paths = []
            for i, scene in enumerate(scenes):
                ip = scene.get("image_path")
                if not ip or not Path(ip).exists():
                    continue
                src = Path(ip)
                if src.suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv"):
                    continue  # skip non-video scenes (charts, images)

                scene_out = tmp / f"scene_{i:03d}.mp4"
                overlay   = scene.get("text_overlay") or ""
                extra     = hook_text if i == 0 else (cta_text if i == len(scenes) - 1 else "")
                chart_path = Path(scene["chart_path"]) if scene.get("chart_path") else None

                # Trim/scale clip (video only — audio comes from HeyGen TTS)
                base = tmp / f"scene_{i:03d}_base.mp4"
                narration = scene.get("narration_path")
                _run([
                    "ffmpeg", "-y", "-i", str(src),
                    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-an", str(base),
                ])

                # Text overlay PNG
                png = tmp / f"scene_{i:03d}_ovr.png"
                _make_text_png(overlay, extra, w, h, png)

                if chart_path and chart_path.exists():
                    chart_w, chart_h = int(w * 0.80), int(h * 0.38)
                    chart_x, chart_y = (w - chart_w) // 2, int(h * 0.55)
                    vid_tmp = tmp / f"scene_{i:03d}_vid.mp4"
                    _run([
                        "ffmpeg", "-y",
                        "-i", str(base), "-i", str(png), "-i", str(chart_path),
                        "-filter_complex",
                        f"[0:v][1:v]overlay=0:0[with_text];"
                        f"[2:v]scale={chart_w}:{chart_h}[chart];"
                        f"[with_text][chart]overlay={chart_x}:{chart_y}[v]",
                        "-map", "[v]",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                        str(vid_tmp),
                    ])
                else:
                    vid_tmp = tmp / f"scene_{i:03d}_vid.mp4"
                    _run([
                        "ffmpeg", "-y", "-i", str(base), "-i", str(png),
                        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
                        "-map", "[v]",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                        str(vid_tmp),
                    ])

                # Mix HeyGen TTS narration audio with video
                if narration and Path(narration).exists():
                    _run([
                        "ffmpeg", "-y", "-i", str(vid_tmp), "-i", str(narration),
                        "-filter_complex",
                        "[1:a]apad[nar];[nar]atrim=duration=5[a]",
                        "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                        "-shortest", str(scene_out),
                    ])
                else:
                    # No narration — add silent audio track so concat works
                    _run([
                        "ffmpeg", "-y", "-i", str(vid_tmp),
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                        "-shortest", str(scene_out),
                    ])
                vid_tmp.unlink(missing_ok=True)

                base.unlink(missing_ok=True)
                png.unlink(missing_ok=True)
                scene_paths.append(scene_out)

            if not scene_paths:
                log.warning("assemble_veo_native: no valid Veo scenes found")
                return out_path

            raw = tmp / "raw.mp4"
            self._concat(scene_paths, raw)

            if music_path and Path(music_path).exists():
                self._mix_music(raw, Path(music_path), out_path)
            else:
                import shutil; shutil.copy2(raw, out_path)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        log.info(f"Assembled Veo-native → {out_path.name} ({size_mb:.1f} MB)")
        return out_path

    def cut_short(self, long_path: Path, short_path: Path) -> Path:
        """Cut first 60s of landscape long video → portrait 1080×1920 Short."""
        short_path.parent.mkdir(parents=True, exist_ok=True)
        _run([
            "ffmpeg", "-y",
            "-i", str(long_path),
            "-t", str(SHORT_DURATION),
            "-vf", "scale=1920:1080,crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=720:1280",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(short_path),
        ])
        size_mb = short_path.stat().st_size / (1024 * 1024)
        log.info(f"Short cut → {short_path.name} ({size_mb:.1f} MB)")
        return short_path

    def _build_scene(
        self,
        image: Path,
        audio: Path,
        out: Path,
        w: int,
        h: int,
        overlay: str,
        extra_text: str,
        scene_idx: int,
        pace: str = "normal",
        chart_path: Path = None,
    ):
        duration = _audio_duration(audio)
        if duration <= 0:
            duration = 8.0

        total_frames = int(duration * 30)

        # Ken Burns: slow zoom-in, slight left/right pan alternating per scene
        pan_dir = 1 if scene_idx % 2 == 0 else -1
        zoom_speed = 0.0012  # reaches ~1.08x at 60 frames, ~1.1x at 8s

        if pace == "hook":
            vf = (
                f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
                f"crop={w*2}:{h*2},"
                f"zoompan=z='pzoom+{zoom_speed}':x='iw/2-(iw/zoom/2)+{pan_dir}*(iw/zoom/2-iw/2)*on/{total_frames}':"
                f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps=30,"
                f"fade=t=out:st={max(0.1, duration - 0.2):.3f}:d=0.2"
            )
        elif pace == "reveal":
            vf = (
                f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
                f"crop={w*2}:{h*2},"
                f"zoompan=z='pzoom+{zoom_speed*1.5}':x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps=30,"
                f"fade=t=in:st=0:d={FADE_DUR},"
                f"fade=t=out:st={max(0.1, duration - 0.2):.3f}:d=0.2:color=white"
            )
        else:
            vf = (
                f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
                f"crop={w*2}:{h*2},"
                f"zoompan=z='pzoom+{zoom_speed}':x='iw/2-(iw/zoom/2)+{pan_dir}*(iw/zoom/2-iw/2)*on/{total_frames}':"
                f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={w}x{h}:fps=30,"
                f"fade=t=in:st=0:d={FADE_DUR},"
                f"fade=t=out:st={max(0.1, duration - FADE_DUR):.3f}:d={FADE_DUR}"
            )

        base = out.with_stem(out.stem + "_base")
        png  = out.with_stem(out.stem + "_ovr")

        is_video = image.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv")

        try:
            if is_video:
                # HeyGen clip: loop/trim to audio duration, scale to target resolution
                _run([
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", str(image),
                    "-i", str(audio),
                    "-t", str(duration),
                    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30",
                    "-af", "apad",
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    str(base),
                ])
            else:
                # Flux image: Ken Burns animation
                _run([
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(image),
                    "-i", str(audio),
                    "-t", str(duration),
                    "-vf", vf,
                    "-af", "apad",
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    str(base),
                ])

            # Pass 2 — text overlay + optional chart overlay
            _make_text_png(overlay, extra_text, w, h, png, pace=pace)

            if chart_path and chart_path.exists():
                # Chart occupies bottom 40% of frame, centered, 80% width
                chart_w = int(w * 0.80)
                chart_h = int(h * 0.38)
                chart_x = (w - chart_w) // 2
                chart_y = int(h * 0.55)
                _run([
                    "ffmpeg", "-y",
                    "-i", str(base),
                    "-i", str(png),
                    "-i", str(chart_path),
                    "-filter_complex",
                    f"[0:v][1:v]overlay=0:0[with_text];"
                    f"[2:v]scale={chart_w}:{chart_h}[chart];"
                    f"[with_text][chart]overlay={chart_x}:{chart_y}[v]",
                    "-map", "[v]", "-map", "0:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "copy",
                    str(out),
                ])
            else:
                _run([
                    "ffmpeg", "-y",
                    "-i", str(base),
                    "-i", str(png),
                    "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
                    "-map", "[v]", "-map", "0:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "copy",
                    str(out),
                ])
        finally:
            base.unlink(missing_ok=True)
            png.unlink(missing_ok=True)

    def _concat(self, paths: list, out: Path):
        list_file = out.parent / "_list.txt"
        list_file.write_text("\n".join(f"file '{p}'" for p in paths))
        _run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(out),
        ])
        list_file.unlink(missing_ok=True)

    def _mix_music(self, video: Path, music: Path, out: Path):
        _run([
            "ffmpeg", "-y",
            "-i", str(video),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            "[1:a]volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(out),
        ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_text_png(overlay: str, extra_text: str, w: int, h: int, out_path: Path, pace: str = "normal"):
    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Watermark — top right
    wm_font = _font(28)
    wm_bb   = draw.textbbox((0, 0), WATERMARK, font=wm_font)
    wm_w    = wm_bb[2] - wm_bb[0]
    draw.text((w - wm_w - 24, 24), WATERMARK, fill=(255, 255, 255, 170), font=wm_font)

    # Scene text overlay — bottom center
    if overlay:
        if pace == "reveal":
            ov_font  = _font(62)
            ov_color = (255, 215, 0, 255)
            box_fill = (0, 0, 0, 200)
            padding  = (24, 16)
        else:
            ov_font  = _font(44)
            ov_color = (255, 255, 255, 255)
            box_fill = (0, 0, 0, 170)
            padding  = (18, 12)

        ov_bb = draw.textbbox((0, 0), overlay, font=ov_font)
        ov_w  = ov_bb[2] - ov_bb[0]
        ov_h  = ov_bb[3] - ov_bb[1]
        x = (w - ov_w) // 2
        y = h - ov_h - 90
        draw.rectangle(
            [x - padding[0], y - padding[1], x + ov_w + padding[0], y + ov_h + padding[1]],
            fill=box_fill,
        )
        draw.text((x, y), overlay, fill=ov_color, font=ov_font)

    # Hook / CTA — top edge (above face) to avoid covering NAC
    if extra_text:
        is_hook = pace == "hook"
        ex_size = 60 if is_hook else 52
        ex_font = _font(ex_size)
        lines   = _wrap(extra_text, draw, ex_font, w - 80)
        lh      = draw.textbbox((0, 0), "Ag", font=ex_font)[3] + 8
        total_h = lh * len(lines)
        y = 18  # always pin to very top — never overlaps face
        for line in lines:
            lb  = draw.textbbox((0, 0), line, font=ex_font)
            lw  = lb[2] - lb[0]
            x   = (w - lw) // 2
            pad = (28, 16)
            draw.rectangle(
                [x - pad[0], y - pad[1], x + lw + pad[0], y + lh + pad[1]],
                fill=(0, 0, 0, 220),
            )
            draw.text((x, y), line, fill=(255, 215, 0, 255), font=ex_font)
            y += lh + 4

    img.save(str(out_path), "PNG")


def _font(size: int = 44):
    for p in [str(FONT_PATH),
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap(text: str, draw: ImageDraw.Draw, font, max_w: int) -> list:
    words, lines, current = text.split(), [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def _audio_duration(mp3: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3)],
            capture_output=True, text=True, check=True,
        )
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def _run(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-1000:]}")
