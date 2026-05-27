"""
SeedanceEngine — AI video clips via Seedance 1 Lite (ByteDance) on Replicate.

Direct drop-in replacement for RunwayEngine.
Same interface: generate(visual_description, out_path, orientation) → Path | None

Cost: ~$0.05–0.10/clip.  Budget cap: 1 hero shot per format = 2 clips/day.

Env vars:
  REPLICATE_API_KEY  — required
  SEEDANCE_MODEL     — optional override (default: bytedance/seedance-1-lite)
                        set to bytedance/seedance-2.0 for higher quality
"""
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("seedance_engine")

REPLICATE_API  = "https://api.replicate.com/v1"
_DEFAULT_MODEL = "bytedance/seedance-1-lite"


class SeedanceEngine:

    def __init__(self):
        self._key   = os.environ.get("REPLICATE_API_KEY", "")
        self._model = os.environ.get("SEEDANCE_MODEL", _DEFAULT_MODEL)

    def generate(self, visual_description: str, out_path: Path, orientation: str = "landscape") -> Path:
        if not self._key:
            log.warning("REPLICATE_API_KEY not set — skipping AI hero shot")
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aspect  = "16:9" if orientation == "landscape" else "9:16"
            headers = {
                "Authorization": f"Bearer {self._key}",
                "Content-Type":  "application/json",
            }
            payload = {
                "input": {
                    "prompt":       _cinematic_prompt(visual_description),
                    "duration":     5,
                    "aspect_ratio": aspect,
                    "resolution":   "720p",
                }
            }
            r = requests.post(
                f"{REPLICATE_API}/models/{self._model}/predictions",
                headers=headers, json=payload, timeout=60,
            )
            if r.status_code not in (200, 201):
                log.warning(f"  Seedance submit failed: {r.status_code} {r.text}")
                return None

            prediction = r.json()
            pid = prediction.get("id")
            log.info(f"  Seedance job {pid} queued  model={self._model}")

            # Replicate may resolve synchronously if the job finished fast
            if prediction.get("status") == "succeeded":
                return _download(prediction, out_path)

            return self._poll(pid, out_path, headers)

        except Exception as e:
            log.warning(f"  Seedance error: {e}")
            return None

    def _poll(self, pid: str, out_path: Path, headers: dict, max_wait: int = 300) -> Path:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(10)
            try:
                r = requests.get(f"{REPLICATE_API}/predictions/{pid}", headers=headers, timeout=30)
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status")
                if status == "succeeded":
                    return _download(data, out_path)
                if status in ("failed", "canceled"):
                    log.warning(f"  Seedance job {status}: {data.get('error', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Seedance [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Seedance poll error: {e}")
        log.warning("  Seedance polling timeout (300s)")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _download(prediction: dict, out_path: Path) -> Path:
    output    = prediction.get("output")
    video_url = output if isinstance(output, str) else (output[0] if output else None)
    if not video_url:
        log.warning("  Seedance: no output URL in response")
        return None
    r = requests.get(video_url, timeout=180)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    log.info(f"  Seedance clip saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
    return out_path


def _cinematic_prompt(base: str) -> str:
    return (
        f"{base}. Cinematic slow motion, 4K quality, dark luxury aesthetic, "
        "shallow depth of field, gold and black color palette, "
        "dramatic lighting, no text, photorealistic."
    )
