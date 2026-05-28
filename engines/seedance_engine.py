"""
SeedanceEngine — AI video clips via Seedance 1 Lite (ByteDance) on Replicate.

Character lock: uses nac_character_ref.png as first_frame_image so NAC's face
and outfit are anchored in every AI-generated clip.

Env vars:
  REPLICATE_API_KEY  — required
  SEEDANCE_MODEL     — optional override (default: bytedance/seedance-1-lite)
                        set to bytedance/seedance-2.0 for higher quality
"""
import base64
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("seedance_engine")

REPLICATE_API   = "https://api.replicate.com/v1"
_DEFAULT_MODEL  = "bytedance/seedance-1-lite"
_CHAR_REF       = Path(__file__).parent.parent / "assets" / "nac_character_ref.png"


def _encode_ref_image() -> str | None:
    """Return base64 data-URL of the character reference image, or None if missing."""
    if not _CHAR_REF.exists():
        return None
    try:
        b64 = base64.b64encode(_CHAR_REF.read_bytes()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        log.warning(f"  Seedance: failed to encode char ref: {e}")
        return None


class SeedanceEngine:

    def __init__(self):
        self._key       = os.environ.get("REPLICATE_API_KEY", "")
        self._model     = os.environ.get("SEEDANCE_MODEL", _DEFAULT_MODEL)
        self._char_ref  = _encode_ref_image()
        if self._char_ref:
            log.info("  Seedance: character reference image loaded (image-to-video mode)")
        else:
            log.info("  Seedance: no character ref found — text-to-video mode")

    def generate(self, visual_description: str, out_path: Path, orientation: str = "landscape", narration: str = "") -> Path:
        if not self._key:
            log.warning("REPLICATE_API_KEY not set — skipping Seedance")
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aspect = "16:9" if orientation == "landscape" else "9:16"
            headers = {
                "Authorization": f"Bearer {self._key}",
                "Content-Type":  "application/json",
            }
            inp = {
                "prompt":       _cinematic_prompt(visual_description, narration),
                "duration":     5,
                "aspect_ratio": aspect,
                "resolution":   "720p",
            }
            # Image-to-video: anchor NAC's character reference as first frame
            if self._char_ref:
                inp["first_frame_image"] = self._char_ref

            payload = {"input": inp}
            r = requests.post(
                f"{REPLICATE_API}/models/{self._model}/predictions",
                headers=headers, json=payload, timeout=60,
            )
            if r.status_code not in (200, 201):
                log.warning(f"  Seedance submit failed: {r.status_code} {r.text[:300]}")
                # If image-to-video rejected, retry without the reference frame
                if self._char_ref and r.status_code == 422:
                    log.info("  Seedance: retrying without first_frame_image")
                    inp.pop("first_frame_image", None)
                    r = requests.post(
                        f"{REPLICATE_API}/models/{self._model}/predictions",
                        headers=headers, json={"input": inp}, timeout=60,
                    )
                    if r.status_code not in (200, 201):
                        return None
                else:
                    return None

            prediction = r.json()
            pid = prediction.get("id")
            mode = "img2vid" if self._char_ref and "first_frame_image" in inp else "txt2vid"
            log.info(f"  Seedance job {pid} queued  model={self._model}  mode={mode}")

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


def _cinematic_prompt(visual: str, narration: str = "") -> str:
    context = f"Scene context: {narration[:120]}. " if narration else ""
    return (
        f"{context}Visual: {visual}. "
        "Cinematic slow motion, 4K quality, dark luxury aesthetic, "
        "shallow depth of field, gold and black color palette, "
        "dramatic lighting, no text, photorealistic."
    )
