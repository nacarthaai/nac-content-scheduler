"""
KlingEngine — AI video clips via Kling AI API (Kuaishou).

Free tier: ~66 clips/month (170 credits; 2.6 credits per 5-sec clip).
Same interface as SeedanceEngine: generate(visual_description, out_path, orientation) → Path | None

Env vars:
  KLING_ACCESS_KEY   — required (from kling.kuaishou.com developer console)
  KLING_SECRET_KEY   — required
  KLING_MODEL        — optional override (default: kling-v1)
                        options: kling-v1 | kling-v1-5 | kling-v2
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("kling_engine")

_API_BASE    = "https://api.klingai.com"
_DEFAULT_MDL = "kling-v1"
_CHAR_REF    = Path(__file__).parent.parent / "assets" / "nac_character_ref.png"


def _encode_ref_image() -> str | None:
    if not _CHAR_REF.exists():
        return None
    try:
        return base64.b64encode(_CHAR_REF.read_bytes()).decode()
    except Exception:
        return None


def _jwt(access_key: str, secret_key: str) -> str:
    """Build a minimal HS256 JWT for Kling's auth scheme."""
    header      = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    now         = int(time.time())
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps({"iss": access_key, "exp": now + 1800, "nbf": now - 5}, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    msg     = f"{header}.{payload_b64}".encode()
    sig     = hmac.new(secret_key.encode(), msg, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header}.{payload_b64}.{sig_b64}"


class KlingEngine:

    def __init__(self):
        self._access   = os.environ.get("KLING_ACCESS_KEY", "")
        self._secret   = os.environ.get("KLING_SECRET_KEY", "")
        self._model    = os.environ.get("KLING_MODEL", _DEFAULT_MDL)
        self._char_ref = _encode_ref_image()

    def generate(self, visual_description: str, out_path: Path, orientation: str = "landscape", narration: str = "") -> Path:
        if not self._access or not self._secret:
            log.info("KLING_ACCESS_KEY / KLING_SECRET_KEY not set — skipping Kling")
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aspect  = "16:9" if orientation == "landscape" else "9:16"
            token   = _jwt(self._access, self._secret)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            }

            # Use image-to-video to lock NAC's character reference as first frame
            if self._char_ref:
                payload = {
                    "model":         self._model,
                    "prompt":        _cinematic_prompt(visual_description, narration),
                    "duration":      "5",
                    "aspect_ratio":  aspect,
                    "cfg_scale":     0.5,
                    "mode":          "std",
                    "image":         f"data:image/png;base64,{self._char_ref}",
                    "image_tail":    None,
                }
                endpoint = f"{_API_BASE}/v1/videos/image2video"
            else:
                payload = {
                    "model":        self._model,
                    "prompt":       _cinematic_prompt(visual_description, narration),
                    "duration":     "5",
                    "aspect_ratio": aspect,
                    "cfg_scale":    0.5,
                    "mode":         "std",
                }
                endpoint = f"{_API_BASE}/v1/videos/text2video"

            r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            if r.status_code not in (200, 201):
                log.warning(f"  Kling submit failed: {r.status_code} {r.text[:300]}")
                return None

            data = r.json()
            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                log.warning(f"  Kling: no task_id in response: {data}")
                return None

            mode = "image2video" if self._char_ref else "text2video"
            log.info(f"  Kling job {task_id} queued  model={self._model}  mode={mode}")
            return self._poll(task_id, headers, out_path, mode=mode)

        except Exception as e:
            log.warning(f"  Kling error: {e}")
            return None

    def _poll(self, task_id: str, headers: dict, out_path: Path, max_wait: int = 300, mode: str = "text2video") -> Path:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(10)
            try:
                r = requests.get(
                    f"{_API_BASE}/v1/videos/{mode}/{task_id}",
                    headers=headers, timeout=30,
                )
                if r.status_code != 200:
                    continue
                data   = r.json().get("data", {})
                status = data.get("task_status", "")
                if status == "succeed":
                    works = data.get("task_result", {}).get("videos", [])
                    if not works:
                        log.warning("  Kling: succeeded but no videos in result")
                        return None
                    return _download(works[0].get("url"), out_path)
                if status in ("failed",):
                    log.warning(f"  Kling job failed: {data.get('task_status_msg', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Kling [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Kling poll error: {e}")
        log.warning("  Kling polling timeout (300s)")
        return None


def _download(url: str, out_path: Path) -> Path:
    if not url:
        log.warning("  Kling: no video URL")
        return None
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    log.info(f"  Kling clip saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
    return out_path


def _cinematic_prompt(visual: str, narration: str = "") -> str:
    context = f"Scene context: {narration[:120]}. " if narration else ""
    return (
        f"{context}Visual: {visual}. "
        "Cinematic slow motion, 4K quality, dark luxury aesthetic, "
        "shallow depth of field, gold and black color palette, "
        "dramatic lighting, no text, photorealistic."
    )
