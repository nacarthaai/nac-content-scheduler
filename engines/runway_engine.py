"""
RunwayEngine — AI hero shots via Runway Gen-3 Alpha Turbo.

Budget cap: 1 clip per format (long + short) = 2 clips per day.
Each clip: 5 seconds × 5 credits = 25 credits. Standard plan: ~625 credits/month.
"""
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("runway_engine")

RUNWAY_API = "https://api.dev.runwayml.com/v1"
CLIP_DURATION = 5


class RunwayEngine:

    def __init__(self):
        self._key = os.environ.get("RUNWAY_API_KEY", "")

    def generate(self, visual_description: str, out_path: Path, orientation: str = "landscape") -> Path:
        if not self._key:
            log.warning("RUNWAY_API_KEY not set — skipping AI hero shot")
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            w, h = (1280, 720) if orientation == "landscape" else (768, 1280)
            headers = {
                "Authorization": f"Bearer {self._key}",
                "X-Runway-Version": "2024-11-06",
                "Content-Type": "application/json",
            }
            payload = {
                "promptText": _cinematic_prompt(visual_description),
                "model": "gen3a_turbo",
                "duration": CLIP_DURATION,
                "ratio": f"{w}:{h}",
                "watermark": False,
            }
            r = requests.post(f"{RUNWAY_API}/text_to_video", headers=headers, json=payload, timeout=60)
            if r.status_code not in (200, 201):
                log.warning(f"  Runway job failed: {r.status_code} {r.text[:200]}")
                return None
            task_id = r.json().get("id")
            log.info(f"  Runway job {task_id} queued")
            return self._poll(task_id, out_path, headers)
        except Exception as e:
            log.warning(f"  Runway error: {e}")
            return None

    def _poll(self, task_id: str, out_path: Path, headers: dict, max_wait: int = 300) -> Path:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(10)
            try:
                r = requests.get(f"{RUNWAY_API}/tasks/{task_id}", headers=headers, timeout=30)
                if r.status_code != 200:
                    continue
                data = r.json()
                status = data.get("status")
                if status == "SUCCEEDED":
                    video_url = (data.get("output") or [None])[0]
                    if not video_url:
                        return None
                    r2 = requests.get(video_url, timeout=180)
                    out_path.write_bytes(r2.content)
                    log.info(f"  Runway clip saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
                    return out_path
                if status in ("FAILED", "CANCELLED"):
                    log.warning(f"  Runway job {status}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Runway [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Runway poll error: {e}")
        log.warning("  Runway polling timeout")
        return None


def _cinematic_prompt(base: str) -> str:
    return (
        f"{base}. Cinematic slow motion, 4K quality, dark luxury aesthetic, "
        "shallow depth of field, gold and black color palette, "
        "dramatic lighting, no text, photorealistic."
    )
