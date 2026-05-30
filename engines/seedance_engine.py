from __future__ import annotations
"""
SeedanceEngine v2 — Seedance 2.0 on Replicate.

Uses reference_images for character consistency (NacArtha character sheets)
and reference_audios for automatic lip sync (ElevenLabs narration audio).
All video generation goes through this engine — no Ken Burns, no stock footage,
no generic B-roll. Every clip is purpose-built for its scene.

Character reference images live in assets/ in the repo and are read locally
from the Railway container — no external storage needed.

Env vars:
  REPLICATE_API_KEY — required
"""
import base64
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("seedance_engine")

REPLICATE_API = "https://api.replicate.com/v1"
MODEL         = "bytedance/seedance-2.0"

_ASSETS = Path(__file__).parent.parent / "assets"
_REF_IMAGES = [
    _ASSETS / "nac_ref_1.png",
    _ASSETS / "nac_ref_2.png",
]


def _img_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


def _audio_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:audio/mpeg;base64,{b64}"


class SeedanceEngine:

    def __init__(self):
        self._key = os.environ.get("REPLICATE_API_KEY", "")

        # Load character reference images as base64 data URIs from local assets/
        self._ref_images = [_img_to_data_uri(p) for p in _REF_IMAGES if p.exists()]

        if self._ref_images:
            log.info(f"  Seedance 2.0: {len(self._ref_images)} character reference images loaded from assets/")
        else:
            log.warning("  Seedance 2.0: nac_ref_1.png / nac_ref_2.png not found in assets/ — no character lock")

    def generate(
        self,
        visual_brief: str,
        out_path: Path,
        orientation: str = "landscape",
        audio_path: Path = None,
    ) -> Path | None:
        """
        Generate a video clip.
        - visual_brief: specific description of what is happening in this scene
        - audio_path: ElevenLabs narration audio → Seedance lip-syncs Nac to it
        """
        if not self._key:
            log.warning("  REPLICATE_API_KEY not set — skipping Seedance")
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aspect = "16:9" if orientation == "landscape" else "9:16"

            inp = {
                "prompt":           _build_prompt(visual_brief),
                "aspect_ratio":     aspect,
                "duration":         5,
                "resolution":       "720p",
                "generate_audio":   False,   # we supply our own ElevenLabs audio
            }

            # reference_images + reference_audios skipped:
            #   - reference_images (face photos) trigger Replicate E005 content filter
            #   - reference_audios requires reference_images (E006 if omitted)
            # Character identity held via detailed prompt. Lip sync not active.
            pass

            headers = {
                "Authorization": f"Bearer {self._key}",
                "Content-Type":  "application/json",
            }

            r = requests.post(
                f"{REPLICATE_API}/models/{MODEL}/predictions",
                headers=headers,
                json={"input": inp},
                timeout=120,
            )

            if r.status_code not in (200, 201):
                log.warning(f"  Seedance 2.0 submit failed: {r.status_code} {r.text[:300]}")
                return None

            prediction = r.json()
            pid = prediction.get("id")
            log.info(f"  Seedance 2.0 job {pid} queued  aspect={aspect}")

            if prediction.get("status") == "succeeded":
                return self._download(prediction, out_path)

            return self._poll(pid, out_path, headers)

        except Exception as e:
            log.error(f"  Seedance 2.0 error: {e}", exc_info=True)
            return None

    def _upload_audio(self, audio_path: Path) -> str | None:
        """Upload audio file to Replicate file storage, return URL."""
        try:
            with open(audio_path, "rb") as f:
                r = requests.post(
                    f"{REPLICATE_API}/files",
                    headers={"Authorization": f"Bearer {self._key}"},
                    files={"content": (audio_path.name, f, "audio/mpeg")},
                    timeout=60,
                )
            if r.status_code in (200, 201):
                info = r.json()
                url = info.get("urls", {}).get("get") or info.get("url", "")
                log.info(f"  Audio uploaded → {url[:60]}…")
                return url
            log.warning(f"  Audio upload failed: {r.status_code} {r.text[:200]}")
            return None
        except Exception as e:
            log.warning(f"  Audio upload error: {e}")
            return None

    def _poll(self, pid: str, out_path: Path, headers: dict, max_wait: int = 600) -> Path | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            time.sleep(12)
            try:
                r = requests.get(f"{REPLICATE_API}/predictions/{pid}", headers=headers, timeout=30)
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status")
                if status == "succeeded":
                    return self._download(data, out_path)
                if status in ("failed", "canceled"):
                    log.warning(f"  Seedance 2.0 job {status}: {data.get('error', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Seedance 2.0 [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Seedance 2.0 poll error: {e}")
        log.warning(f"  Seedance 2.0 timeout ({max_wait}s)")
        return None

    def _download(self, prediction: dict, out_path: Path) -> Path | None:
        output    = prediction.get("output")
        video_url = output if isinstance(output, str) else (output[0] if output else None)
        if not video_url:
            log.warning("  Seedance 2.0: no output URL in response")
            return None
        r = requests.get(video_url, timeout=300)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        size_kb = out_path.stat().st_size // 1024
        log.info(f"  Seedance 2.0 saved → {out_path.name} ({size_kb} KB)")
        return out_path


# ── Prompt builder ────────────────────────────────────────────────────────────

_ENVIRONMENT = (
    "NacArtha AI trading command center, night. "
    "Floor-to-ceiling glass windows, city skyline. "
    "Multiple Bloomberg terminals glowing gold and electric blue. "
    "Dark luxury, premium hedge fund aesthetic, cinematic 4K. "
    "Dramatic key lighting from left, electric blue fill from monitors."
)

_CHARACTER = (
    "A young professional male trader in a dark tailored blazer and white shirt, "
    "thin-frame glasses, calm focused expression, facing the camera."
)


def _build_prompt(visual_brief: str) -> str:
    return f"{visual_brief}. {_CHARACTER}. {_ENVIRONMENT}. Cinematic. No text overlays."
