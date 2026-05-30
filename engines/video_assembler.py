"""
VideoAssembler — Ken Burns + fade transitions + Pillow text overlays.

No ffmpeg drawtext/freetype dependency — text rendered via Pillow PNG overlay.
Ken Burns: scale 1.12x + alternating pan per scene.
Transitions: fade-to-black between scenes (professional documentary style).
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
                self._build_scene(
                    video=Path(scene["video_path"]),
                    audio=Path(scene["narration_path"]),
                    out=scene_out,
                    w=w, h=h,
                    overlay=overlay,
                    extra_text=extra,
                    scene_idx=i,
                    pace=pace,
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

    def _build_scene(self, video: Path, audio: Path, out: Path,
                     w: int, h: int, overlay: str, extra_text: str, scene_idx: int,
                     pace: str = "normal"):
        duration = _audio_duration(audio)
        if duration <= 0:
            duration = 8.0

        if pace == "hook":
            # No fade-in — first frame must be full brightness (Shorts feed shows frame 0)
            vf = (
                f"fps=30,"
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
                f"fade=t=out:st={max(0.1, duration - 0.2):.3f}:d=0.2"
            )
        elif pace == "reveal":
            # White flash out — signals a key moment
            vf = (
                f"fps=30,"
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
                f"fade=t=in:st=0:d={FADE_DUR},"
                f"fade=t=out:st={max(0.1, duration - 0.2):.3f}:d=0.2:color=white"
            )
        else:
            # normal / cta — simple scale to fit, fade in/out
            vf = (
                f"fps=30,"
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
                f"fade=t=in:st=0:d={FADE_DUR},"
                f"fade=t=out:st={max(0.1, duration - FADE_DUR):.3f}:d={FADE_DUR}"
            )

        base = out.with_stem(out.stem + "_base")
        png  = out.with_stem(out.stem + "_ovr")

        try:
            # Pass 1 — Ken Burns + fades + audio
            _run([
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", str(video),
                "-i", str(audio),
                "-t", str(duration),
                "-vf", vf,
                "-af", "apad",
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(base),
            ])

            # Pass 2 — Pillow text overlay (watermark + scene text + hook/CTA)
            _make_text_png(overlay, extra_text, w, h, png, pace=pace)
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

    # Watermark — top right, always present
    wm_font = _font(28)
    wm_bb   = draw.textbbox((0, 0), WATERMARK, font=wm_font)
    wm_w    = wm_bb[2] - wm_bb[0]
    draw.text((w - wm_w - 24, 24), WATERMARK, fill=(255, 255, 255, 170), font=wm_font)

    # Scene text overlay — bottom center
    # reveal: larger gold text to make the stat pop; others: white normal size
    if overlay:
        if pace == "reveal":
            ov_font  = _font(62)
            ov_color = (255, 215, 0, 255)    # gold — signals importance
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

    # Hook / CTA — large, high contrast, upper-center (thumb-zone safe on Shorts)
    if extra_text:
        is_hook = pace == "hook"
        ex_size = 72 if is_hook else 56          # bigger on hook
        ex_font = _font(ex_size)
        lines   = _wrap(extra_text, draw, ex_font, w - 80)
        lh      = draw.textbbox((0, 0), "Ag", font=ex_font)[3] + 10
        total_h = lh * len(lines)
        # Hook: place in upper third (more visible in Shorts feed preview)
        # CTA: center screen
        y = int(h * 0.18) if is_hook else (h - total_h) // 2
        for line in lines:
            lb  = draw.textbbox((0, 0), line, font=ex_font)
            lw  = lb[2] - lb[0]
            x   = (w - lw) // 2
            pad = (28, 16)
            # Solid black box — no transparency, maximum contrast
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
