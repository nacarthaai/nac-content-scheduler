"""
OpenArtEngine — AI-generated backgrounds via FLUX on Replicate, converted to video.

Drops in alongside StockEngine as the primary clip source for non-hero scenes.
Same interface as StockEngine: fetch(keywords, orientation, variant="") → Path | None

Pipeline per scene:
  1. Generate a finance-themed image with FLUX Schnell (via Replicate)
  2. Convert to a 10-second looping mp4 via ffmpeg
  3. VideoAssembler applies its Ken Burns zoom+pan on top → fully cinematic clip
  4. Result cached per (keyword, orientation, date, scene) — same pattern as StockEngine

Fallback: if REPLICATE_API_KEY is unset or generation fails, returns None
and the orchestrator falls back to StockEngine (Pexels).

Env vars:
  REPLICATE_API_KEY  — required (shared with SeedanceEngine)
  FLUX_MODEL         — optional override (default: black-forest-labs/flux-schnell)
                        set to black-forest-labs/flux-dev for higher quality (~$0.025/image)
"""
import hashlib
import logging
import os
import subprocess
import time
from datetime import date
from pathlib import Path

import requests

log = logging.getLogger("openart_engine")

REPLICATE_API = "https://api.replicate.com/v1"
_DEFAULT_FLUX = "black-forest-labs/flux-schnell"
CACHE_DIR     = Path(__file__).parent.parent / "cache" / "openart"


class OpenArtEngine:

    def __init__(self):
        self._key   = os.environ.get("REPLICATE_API_KEY", "")
        self._model = os.environ.get("FLUX_MODEL", _DEFAULT_FLUX)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def fetch(self, prompt, orientation: str = "landscape", variant: str = "") -> Path:
        if not self._key:
            log.info("  REPLICATE_API_KEY not set — skipping OpenArt (Pexels fallback will be used)")
            return None

        query     = prompt if isinstance(prompt, str) else ", ".join(prompt)
        today     = date.today().isoformat()
        cache_key = hashlib.md5(f"{query}:{orientation}:{today}:{variant}".encode()).hexdigest()[:12]
        cached    = CACHE_DIR / f"{cache_key}.mp4"

        if cached.exists() and cached.stat().st_size > 10_000:
            log.info(f"  OpenArt cache hit: {query} [{variant}]")
            return cached

        img_path = CACHE_DIR / f"{cache_key}.jpg"
        if not self._generate_image(query, orientation, img_path):
            return None
        return self._image_to_video(img_path, cached, orientation)

    # ── Private ───────────────────────────────────────────────────────────────

    def _generate_image(self, query: str, orientation: str, out_path: Path) -> bool:
        aspect = "16:9" if orientation == "landscape" else "9:16"
        try:
            headers = {
                "Authorization": f"Bearer {self._key}",
                "Content-Type":  "application/json",
                "Prefer":        "wait",          # block up to 60s for fast models like Schnell
            }
            payload = {
                "input": {
                    "prompt":         _finance_prompt(query),
                    "aspect_ratio":   aspect,
                    "output_format":  "jpg",
                    "output_quality": 90,
                    "num_outputs":    1,
                }
            }
            r = requests.post(
                f"{REPLICATE_API}/models/{self._model}/predictions",
                headers=headers, json=payload, timeout=120,
            )
            if r.status_code not in (200, 201):
                log.warning(f"  FLUX HTTP {r.status_code}: {r.text}")
                return False

            data = r.json()
            if data.get("status") != "succeeded":
                # Prefer:wait timed out — poll the rest of the way
                data = self._poll(data.get("id"), headers)
            if not data:
                return False

            output  = data.get("output")
            img_url = output[0] if isinstance(output, list) else output
            if not img_url:
                log.warning("  FLUX: no output URL in response")
                return False

            r2 = requests.get(img_url, timeout=60)
            r2.raise_for_status()
            out_path.write_bytes(r2.content)
            log.info(f"  FLUX image → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return True

        except Exception as e:
            log.warning(f"  FLUX error: {e}")
            return False

    def _poll(self, pid: str, headers: dict, max_wait: int = 120) -> dict:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(5)
            try:
                r = requests.get(f"{REPLICATE_API}/predictions/{pid}", headers=headers, timeout=30)
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status")
                if status == "succeeded":
                    return data
                if status in ("failed", "canceled"):
                    log.warning(f"  FLUX job {status}: {data.get('error', '')}")
                    return None
            except Exception as e:
                log.warning(f"  FLUX poll error: {e}")
        log.warning("  FLUX polling timeout (120s)")
        return None

    def _image_to_video(self, img_path: Path, out_path: Path, orientation: str) -> Path:
        w, h = (1920, 1080) if orientation == "landscape" else (1080, 1920)
        try:
            result = subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(img_path),
                "-t", "10",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-r", "30", "-pix_fmt", "yuv420p",
                str(out_path),
            ], capture_output=True, text=True)
            if result.returncode != 0:
                log.warning(f"  ffmpeg image→video failed: {result.stderr[-500:]}")
                return None
            log.info(f"  OpenArt video → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return out_path
        except Exception as e:
            log.warning(f"  image_to_video error: {e}")
            return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _finance_prompt(prompt: str) -> str:
    # If the prompt is already a full cinematic visual_prompt (contains timing cues or camera directions),
    # use it directly with just a no-text suffix for FLUX image generation.
    if any(kw in prompt for kw in ("0-2s:", "0-5s:", "Camera:", "Lighting:", "Audio:", "cinematic")):
        return prompt + " Photorealistic 4K still frame. No text, no watermarks, no subtitles."
    return (
        f"Professional finance and trading scene: {prompt}. "
        "Dark luxury aesthetic, gold and black color palette, "
        "cinematic dramatic lighting, ultra-realistic 4K quality. "
        "No people, no text, no logos, no watermarks. "
        "Bloomberg terminal style, sophisticated financial environment."
    )
