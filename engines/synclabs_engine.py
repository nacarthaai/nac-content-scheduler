"""
SyncLabsEngine — lip sync via sync.so API.

Takes a video file + audio file, returns a lip-synced MP4.
Used for Hindi and Telugu trading videos where NAC's mouth
movements need to match the TTS narration.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("synclabs_engine")

_API_BASE = "https://api.sync.so"
_MODEL    = "sync-1.9.0-beta"


class SyncLabsEngine:

    def __init__(self):
        self._key = os.environ.get("SYNCLABS_API_KEY", "")
        if not self._key:
            log.warning("  SYNCLABS_API_KEY not set — lip sync will be skipped")

    def is_ready(self) -> bool:
        return bool(self._key)

    def lipsync(self, video_path: Path, audio_path: Path, out_path: Path) -> Path | None:
        if not self.is_ready():
            log.warning("  SyncLabs not ready — returning un-synced video")
            return None

        try:
            log.info(f"  SyncLabs submitting: {video_path.name} + {audio_path.name}")
            with open(video_path, "rb") as vf, open(audio_path, "rb") as af:
                r = requests.post(
                    f"{_API_BASE}/v2/generate",
                    headers={"x-api-key": self._key},
                    files={
                        "video": (video_path.name, vf, "video/mp4"),
                        "audio": (audio_path.name, af, "audio/wav"),
                    },
                    data={"model": _MODEL},
                    timeout=60,
                )
            r.raise_for_status()
            job_id = r.json()["id"]
            log.info(f"  SyncLabs job={job_id} — polling…")

            return self._poll(job_id, out_path)

        except Exception as e:
            log.error(f"  SyncLabs submit error: {e}", exc_info=True)
            return None

    def _poll(self, job_id: str, out_path: Path, max_wait: int = 600) -> Path | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(15)
            try:
                r = requests.get(
                    f"{_API_BASE}/v2/generate/{job_id}",
                    headers={"x-api-key": self._key},
                    timeout=15,
                )
                d      = r.json()
                status = d.get("status")
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  SyncLabs [{status}] {elapsed}s…")

                if status == "COMPLETED":
                    url = d.get("outputUrl")
                    if not url:
                        log.warning("  SyncLabs: no outputUrl in completed response")
                        return None
                    resp = requests.get(url, stream=True, timeout=120)
                    resp.raise_for_status()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(out_path, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                    size_mb = out_path.stat().st_size / (1024 * 1024)
                    log.info(f"  SyncLabs saved → {out_path.name} ({size_mb:.1f} MB)")
                    return out_path

                if status in ("FAILED", "ERROR"):
                    log.error(f"  SyncLabs failed: {d}")
                    return None

            except Exception as e:
                log.warning(f"  SyncLabs poll error: {e}")

        log.warning(f"  SyncLabs timeout ({max_wait}s)")
        return None
