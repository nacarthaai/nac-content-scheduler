"""
HailuoEngine — AI video clips via Hailuo AI (MiniMax Video-01).

Free tier: ~30 clips/month.
Same interface as SeedanceEngine: generate(visual_description, out_path, orientation) → Path | None

Env vars:
  MINIMAX_API_KEY   — required (from platform.minimaxi.com)
  MINIMAX_GROUP_ID  — required (your account group ID)
"""
import json
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("hailuo_engine")

_API_BASE = "https://api.minimaxi.chat/v1"


class HailuoEngine:

    def __init__(self):
        self._key      = os.environ.get("MINIMAX_API_KEY", "")
        self._group_id = os.environ.get("MINIMAX_GROUP_ID", "")

    def generate(self, visual_description: str, out_path: Path, orientation: str = "landscape", narration: str = "") -> Path:
        if not self._key or not self._group_id:
            log.info("MINIMAX_API_KEY / MINIMAX_GROUP_ID not set — skipping Hailuo")
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            headers = {
                "Authorization": f"Bearer {self._key}",
                "Content-Type":  "application/json",
            }
            payload = {
                "model":  "video-01",
                "prompt": _cinematic_prompt(visual_description, narration),
            }
            r = requests.post(
                f"{_API_BASE}/video_generation",
                headers=headers, json=payload, timeout=60,
            )
            if r.status_code not in (200, 201):
                log.warning(f"  Hailuo submit failed: {r.status_code} {r.text[:300]}")
                return None

            data    = r.json()
            task_id = data.get("task_id")
            if not task_id:
                log.warning(f"  Hailuo: no task_id in response: {data}")
                return None

            log.info(f"  Hailuo job {task_id} queued")
            return self._poll(task_id, headers, out_path)

        except Exception as e:
            log.warning(f"  Hailuo error: {e}")
            return None

    def _poll(self, task_id: str, headers: dict, out_path: Path, max_wait: int = 300) -> Path:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(10)
            try:
                r = requests.get(
                    f"{_API_BASE}/query/video_generation",
                    headers=headers,
                    params={"task_id": task_id},
                    timeout=30,
                )
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status", "")
                if status == "Success":
                    video_url = data.get("file_id") or data.get("video_url")
                    if not video_url:
                        log.warning("  Hailuo: succeeded but no video URL")
                        return None
                    if data.get("file_id"):
                        return self._retrieve(data["file_id"], headers, out_path)
                    return _download(video_url, out_path)
                if status in ("Fail", "Failed"):
                    log.warning(f"  Hailuo job failed: {data}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Hailuo [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Hailuo poll error: {e}")
        log.warning("  Hailuo polling timeout (300s)")
        return None

    def _retrieve(self, file_id: str, headers: dict, out_path: Path) -> Path:
        try:
            r = requests.get(
                f"{_API_BASE}/files/retrieve",
                headers=headers,
                params={"GroupId": self._group_id, "file_id": file_id},
                timeout=60,
            )
            r.raise_for_status()
            download_url = r.json().get("file", {}).get("download_url")
            if not download_url:
                log.warning("  Hailuo: no download_url in file retrieve")
                return None
            return _download(download_url, out_path)
        except Exception as e:
            log.warning(f"  Hailuo retrieve error: {e}")
            return None


def _download(url: str, out_path: Path) -> Path:
    if not url:
        log.warning("  Hailuo: no video URL")
        return None
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    log.info(f"  Hailuo clip saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
    return out_path


def _cinematic_prompt(visual: str, narration: str = "") -> str:
    context = f"Scene context: {narration[:120]}. " if narration else ""
    return (
        f"{context}Visual: {visual}. "
        "Cinematic slow motion, 4K quality, dark luxury aesthetic, "
        "shallow depth of field, gold and black color palette, "
        "dramatic lighting, no text, photorealistic."
    )
