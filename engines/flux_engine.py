"""
FluxEngine — scene image generation via Replicate (Flux Schnell).

scene_type modes:
  illustrated → cinematic environment/action scene
  nac_face    → illustrated portrait of Nac character in trading room
  chart       → dark trading room background (real chart overlaid by assembler)
"""
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("flux_engine")

_POLL_URL = "https://api.replicate.com/v1/predictions/{id}"
_SUBMIT_URL = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"

_STYLE = (
    "cinematic illustration, semi-realistic, dramatic lighting, "
    "highly detailed, dark luxury aesthetic, 4K, no text, no watermarks"
)

_NAC_CHAR = (
    "Indian male late 20s, thin-frame round glasses, dark tailored blazer, "
    "crisp white shirt, sharp jawline, clean-shaven, natural Indian skin tone, "
    "calm confident expression, cinematic illustrated portrait"
)

_ENV = (
    "NacArtha AI trading command center at night, floor-to-ceiling glass walls, "
    "city skyline glowing outside, Bloomberg terminals with gold and electric-blue data streams, "
    "dark luxury hedge-fund aesthetic, warm gold key light from left, cool electric-blue terminal fill"
)


class FluxEngine:

    def __init__(self):
        self._key = os.environ.get("REPLICATE_API_TOKEN", "")
        if self._key:
            log.info("  Flux engine ready (Replicate flux-schnell)")
        else:
            log.warning("  REPLICATE_API_TOKEN not set — image generation skipped")

    def generate(
        self,
        visual_prompt: str,
        out_path: Path,
        orientation: str = "landscape",
        scene_type: str = "illustrated",
    ) -> Path | None:
        if not self._key:
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            prompt = _build_prompt(visual_prompt, scene_type)
            aspect = "16:9" if orientation == "landscape" else "9:16"

            r = requests.post(
                _SUBMIT_URL,
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json={"input": {
                    "prompt": prompt,
                    "aspect_ratio": aspect,
                    "output_format": "jpg",
                    "output_quality": 90,
                    "num_inference_steps": 4,
                }},
                timeout=30,
            )
            if r.status_code not in (200, 201):
                log.warning(f"  Flux submit failed: {r.status_code} {r.text[:200]}")
                return None

            data = r.json()
            pred_id = data.get("id")
            log.info(f"  Flux job {pred_id} [{scene_type}]")

            if data.get("status") == "succeeded":
                return self._save(data, out_path)
            return self._poll(pred_id, out_path)

        except Exception as e:
            log.error(f"  Flux error: {e}", exc_info=True)
            return None

    def _poll(self, pred_id: str, out_path: Path, max_wait: int = 120) -> Path | None:
        deadline = time.time() + max_wait
        url = _POLL_URL.format(id=pred_id)
        while time.time() < deadline:
            time.sleep(4)
            try:
                r = requests.get(url, headers={"Authorization": f"Bearer {self._key}"}, timeout=15)
                if r.status_code != 200:
                    continue
                data = r.json()
                status = data.get("status", "")
                if status == "succeeded":
                    return self._save(data, out_path)
                if status == "failed":
                    log.warning(f"  Flux failed: {data.get('error', '')}")
                    return None
                elapsed = int(time.time() - (deadline - max_wait))
                log.info(f"  Flux [{status}] {elapsed}s…")
            except Exception as e:
                log.warning(f"  Flux poll error: {e}")
        log.warning(f"  Flux timeout ({max_wait}s)")
        return None

    def _save(self, data: dict, out_path: Path) -> Path | None:
        output = data.get("output")
        url = output[0] if isinstance(output, list) else output
        if not url or not isinstance(url, str):
            log.warning("  Flux: no image URL in response")
            return None
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        log.info(f"  Flux saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
        return out_path


def _build_prompt(visual_prompt: str, scene_type: str) -> str:
    if scene_type == "nac_face":
        return f"{_NAC_CHAR}. {visual_prompt}. {_ENV}. {_STYLE}."
    if scene_type == "chart":
        return f"Empty dark trading command center background, {_ENV}, clean empty screens ready for data display. {_STYLE}."
    # illustrated
    return f"{visual_prompt}. {_ENV}. {_STYLE}."
