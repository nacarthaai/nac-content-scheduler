"""
VoiceEngine — ElevenLabs TTS for EN, HeyGen video_translate for HI/TE.

EN  → ElevenLabs (ELEVENLABS_VOICE_ID_EN) — Nac's cloned voice, ~$0.57/month
HI  → HeyGen video_translate (not TTS) — handled in orchestrator
TE  → HeyGen video_translate (not TTS) — handled in orchestrator
"""
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

log = logging.getLogger("voice_engine")

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_ELEVENLABS_MODEL = "eleven_multilingual_v2"


class VoiceEngine:

    def __init__(self):
        self._el_key     = os.environ.get("ELEVENLABS_API_KEY", "")
        self._el_voice   = os.environ.get("ELEVENLABS_VOICE_ID_EN", "")
        if self._el_key and self._el_voice:
            log.info(f"  ElevenLabs TTS ready — voice={self._el_voice[:8]}…")
        else:
            log.warning("  ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID_EN not set")

    def generate(self, text: str, out_path: Path, lang: str = "en") -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists() and out_path.stat().st_size > 1024:
            log.info(f"Voice [{lang}] cached → {out_path.name}")
            return out_path

        log.info(f"Voice [{lang}] {len(text)} chars → {out_path.name}")

        if lang != "en":
            raise RuntimeError(
                f"VoiceEngine.generate() called for [{lang}] — HI/TE audio is handled "
                f"via HeyGen video_translate in the orchestrator, not TTS."
            )

        if not self._el_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set — cannot generate NAC voice audio")
        if not self._el_voice:
            raise RuntimeError("ELEVENLABS_VOICE_ID_EN not set — cannot generate NAC voice audio")

        if self._elevenlabs_generate(text, out_path):
            return out_path

        raise RuntimeError("ElevenLabs TTS failed for [en] — check API key and voice ID")

    def get_duration(self, mp3_path: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3_path)],
                capture_output=True, text=True, check=True,
            )
            return float(json.loads(r.stdout)["format"]["duration"])
        except Exception:
            return 0.0

    def _elevenlabs_generate(self, text: str, out_path: Path) -> bool:
        try:
            r = requests.post(
                _ELEVENLABS_URL.format(voice_id=self._el_voice),
                headers={
                    "xi-api-key": self._el_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": _ELEVENLABS_MODEL,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                        "style": 0.3,
                        "use_speaker_boost": True,
                    },
                },
                timeout=120,
            )
            if r.status_code != 200:
                log.warning(f"  ElevenLabs HTTP {r.status_code}: {r.text[:300]}")
                return False
            out_path.write_bytes(r.content)
            log.info(f"  ElevenLabs saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return True
        except Exception as e:
            log.warning(f"  ElevenLabs TTS error: {e}")
            return False
