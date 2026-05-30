from __future__ import annotations
"""
HiggsFieldEngine — character-consistent video via Higgsfield API.

Two-step per clip:
  1. Soul model  → generate a consistent Nac character IMAGE for the scene
  2. DoP model   → animate that image into a 5-second video clip

Auth: HIGGSFIELD_API_KEY + HIGGSFIELD_API_SECRET (or HF_KEY="key:secret")
"""
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("higgsfield_engine")

_BASE  = "https://platform.higgsfield.ai"
_SOUL  = "higgsfield-ai/soul/standard"
_DOP   = "higgsfield-ai/dop/standard"


class HiggsFieldEngine:

    def __init__(self):
        key    = os.environ.get("HIGGSFIELD_API_KEY", "")
        secret = os.environ.get("HIGGSFIELD_API_SECRET", "")
        if not key:
            combined = os.environ.get("HF_KEY", "")
            if ":" in combined:
                key, secret = combined.split(":", 1)
        self._key    = key
        self._secret = secret
        self._auth   = f"Key {key}:{secret}"
        if key:
            log.info("  HiggsField engine ready")
        else:
            log.warning("  HIGGSFIELD_API_KEY not set — video generation will be skipped")

    def generate(
        self,
        visual_brief: str,
        out_path: Path,
        orientation: str = "landscape",
        audio_path: Path = None,
    ) -> Path | None:
        if not self._key:
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aspect = "16:9" if orientation == "landscape" else "9:16"

            image_url = self._soul_image(visual_brief, aspect)
            if not image_url:
                log.warning("  Soul failed — skipping DoP")
                return None

            return self._dop_video(image_url, visual_brief, out_path, aspect)

        except Exception as e:
            log.error(f"  HiggsField error: {e}", exc_info=True)
            return None

    # ── Soul: character image ─────────────────────────────────────────────────

    def _soul_image(self, visual_brief: str, aspect: str) -> str | None:
        body = {
            "prompt":       _soul_prompt(visual_brief),
            "resolution":   "2K",
            "aspect_ratio": aspect,
            "camera_fixed": True,
        }
        r = requests.post(
            f"{_BASE}/{_SOUL}",
            headers={"Authorization": self._auth, "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        if r.status_code not in (200, 201):
            log.warning(f"  Soul submit failed: {r.status_code} {r.text[:300]}")
            return None

        data = r.json()
        rid  = data.get("request_id") or data.get("id")
        log.info(f"  Soul job {rid} queued")

        if data.get("status") == "completed":
            return _extract_image_url(data)
        return self._poll_soul(rid)

    def _poll_soul(self, rid: str, max_wait: int = 300) -> str | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(8)
            try:
                r = requests.get(
                    f"{_BASE}/requests/{rid}/status",
                    headers={"Authorization": self._auth},
                    timeout=30,
                )
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status", "")
                if status == "completed":
                    url = _extract_image_url(data)
                    if url:
                        return url
                    log.warning(f"  Soul completed but no image URL. Full response: {data}")
                    return None
                if status in ("failed", "nsfw"):
                    log.warning(f"  Soul {status}: {data.get('error', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Soul [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Soul poll error: {e}")
        log.warning(f"  Soul timeout ({max_wait}s)")
        return None

    # ── DoP: image → video ────────────────────────────────────────────────────

    def _dop_video(self, image_url: str, visual_brief: str, out_path: Path, aspect: str) -> Path | None:
        body = {
            "image_url": image_url,
            "prompt":    _motion_prompt(visual_brief),
            "duration":  5,
        }
        r = requests.post(
            f"{_BASE}/{_DOP}",
            headers={"Authorization": self._auth, "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        if r.status_code not in (200, 201):
            log.warning(f"  DoP submit failed: {r.status_code} {r.text[:300]}")
            return None

        data = r.json()
        rid  = data.get("request_id") or data.get("id")
        log.info(f"  DoP job {rid} queued")

        if data.get("status") == "completed":
            return self._download(data, out_path)
        return self._poll_dop(rid, out_path)

    def _poll_dop(self, rid: str, out_path: Path, max_wait: int = 600) -> Path | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(12)
            try:
                r = requests.get(
                    f"{_BASE}/requests/{rid}/status",
                    headers={"Authorization": self._auth},
                    timeout=30,
                )
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status", "")
                if status == "completed":
                    return self._download(data, out_path)
                if status in ("failed", "nsfw"):
                    log.warning(f"  DoP {status}: {data.get('error', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  DoP [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  DoP poll error: {e}")
        log.warning(f"  DoP timeout ({max_wait}s)")
        return None

    def _download(self, data: dict, out_path: Path) -> Path | None:
        video_url = _extract_video_url(data)
        if not video_url:
            log.warning(f"  HiggsField: no video URL in response: {data}")
            return None
        r = requests.get(video_url, timeout=300)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        size_kb = out_path.stat().st_size // 1024
        log.info(f"  HiggsField saved → {out_path.name} ({size_kb} KB)")
        return out_path


# ── Response helpers ──────────────────────────────────────────────────────────

def _extract_image_url(data: dict) -> str | None:
    for path in [
        lambda d: d["result"]["images"][0]["url"],
        lambda d: d["result"]["images"][0],
        lambda d: d["images"][0]["url"],
        lambda d: d["images"][0],
        lambda d: d["result"]["url"],
        lambda d: d["url"],
    ]:
        try:
            val = path(data)
            if isinstance(val, str) and val.startswith("http"):
                return val
        except (KeyError, IndexError, TypeError):
            pass
    return None


def _extract_video_url(data: dict) -> str | None:
    for path in [
        lambda d: d["result"]["videos"][0]["url"],
        lambda d: d["result"]["videos"][0],
        lambda d: d["videos"][0]["url"],
        lambda d: d["videos"][0],
        lambda d: d["result"]["url"],
        lambda d: d["url"],
    ]:
        try:
            val = path(data)
            if isinstance(val, str) and val.startswith("http"):
                return val
        except (KeyError, IndexError, TypeError):
            pass
    return None


# ── Prompt builders ───────────────────────────────────────────────────────────

_ENV = (
    "NacArtha AI trading command center, night-time. "
    "Floor-to-ceiling glass, city skyline glowing outside. "
    "Bloomberg terminals with gold and electric-blue data. "
    "Dark luxury hedge-fund aesthetic, cinematic 4K lighting."
)

_CHAR = (
    "Indian male, late 20s, sharp features, thin-frame glasses, "
    "dark tailored blazer, white shirt, calm confident expression."
)


def _soul_prompt(visual_brief: str) -> str:
    return f"{visual_brief}. {_CHAR}. {_ENV}. Photorealistic, no text, no watermarks."


def _motion_prompt(visual_brief: str) -> str:
    return f"Slow cinematic push-in. {visual_brief}. Subtle atmosphere, professional."
