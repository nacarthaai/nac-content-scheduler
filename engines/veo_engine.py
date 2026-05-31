"""
VeoEngine — video clip generation via Google Veo.

Auth: GOOGLE_API_KEY (from Google AI Studio)
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("veo_engine")

_SDK_AVAILABLE = False
try:
    from google import genai
    from google.genai import types
    _SDK_AVAILABLE = True
except ImportError:
    pass

# Veo 3.1 Fast — $0.10-0.15/sec, balanced quality for background clips
_MODEL = "veo-3.1-fast-generate-001"


class VeoEngine:

    def __init__(self):
        self._key = os.environ.get("GOOGLE_API_KEY", "")
        self._client = None

        if not self._key:
            log.warning("  GOOGLE_API_KEY not set — Veo generation will be skipped")
            return

        if not _SDK_AVAILABLE:
            log.warning("  google-genai SDK not installed — run: pip install google-genai")
            return

        try:
            self._client = genai.Client(api_key=self._key)
            log.info(f"  Veo engine ready (model={_MODEL})")
        except Exception as e:
            log.error(f"  Veo client init failed: {e}")

    def generate(
        self,
        prompt: str,
        out_path: Path,
        orientation: str = "landscape",
        duration: int = 5,
    ) -> Path | None:
        if not self._client:
            return None

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aspect = "16:9" if orientation == "landscape" else "9:16"

            log.info(f"  Veo generating: {prompt[:60]}…")

            operation = self._client.models.generate_videos(
                model=_MODEL,
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio=aspect,
                    duration_seconds=duration,
                    number_of_videos=1,
                    enhance_prompt=True,
                    generate_audio=False,  # silent clips — avoids 33-40% audio surcharge
                ),
            )

            return self._wait_and_download(operation, out_path)

        except Exception as e:
            log.error(f"  Veo generate error: {e}", exc_info=True)
            return None

    def _wait_and_download(self, operation, out_path: Path, max_wait: int = 300) -> Path | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(10)
            try:
                operation = self._client.operations.get(operation)
                if operation.done:
                    if operation.error:
                        log.warning(f"  Veo error: {operation.error}")
                        return None

                    videos = (operation.response or {})
                    generated = getattr(videos, "generated_videos", []) or []
                    if not generated:
                        log.warning("  Veo: no videos in response")
                        return None

                    video_obj = generated[0].video

                    # video_bytes may be populated directly
                    if video_obj.video_bytes:
                        out_path.write_bytes(video_obj.video_bytes)
                    elif video_obj.uri:
                        # Download via files API
                        video_bytes = self._client.files.download(file=video_obj)
                        out_path.write_bytes(video_bytes)
                    else:
                        log.warning("  Veo: no video bytes or URI in response")
                        return None

                    size_mb = out_path.stat().st_size / (1024 * 1024)
                    log.info(f"  Veo saved → {out_path.name} ({size_mb:.1f} MB)")
                    return out_path

                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Veo [processing] {elapsed}s…")

            except Exception as e:
                log.warning(f"  Veo poll error: {e}")

        log.warning(f"  Veo timeout ({max_wait}s)")
        return None

    def is_ready(self) -> bool:
        return self._client is not None
