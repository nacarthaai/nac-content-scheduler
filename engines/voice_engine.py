"""
VoiceEngine — ElevenLabs multilingual TTS for EN, HI, TE.

All languages use NAC's cloned voice (ELEVENLABS_VOICE_ID_NAC) with eleven_multilingual_v2.
~$0.57/month total (3k chars/day × 3 languages ≈ 9k chars/day, within creator plan).
No HeyGen TTS or video_translate needed for audio.
"""
import json
import logging
import os
import subprocess
from pathlib import Path

import requests

log = logging.getLogger("voice_engine")

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_ELEVENLABS_MODEL = "eleven_multilingual_v2"


class VoiceEngine:

    def __init__(self):
        self._key   = os.environ.get("ELEVENLABS_API_KEY", "")
        self._voice = os.environ.get("ELEVENLABS_VOICE_ID_NAC", "")
        if self._key and self._voice:
            log.info(f"  ElevenLabs TTS ready — voice={self._voice[:8]}… (EN/HI/TE)")
        else:
            log.warning("  ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID_NAC not set")

    def generate(self, text: str, out_path: Path, lang: str = "en") -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists() and out_path.stat().st_size > 1024:
            log.info(f"Voice [{lang}] cached → {out_path.name}")
            return out_path

        log.info(f"Voice [{lang}] {len(text)} chars → {out_path.name}")

        if not self._key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")
        if not self._voice:
            raise RuntimeError("ELEVENLABS_VOICE_ID_NAC not set")

        if self._generate(text, out_path, lang):
            return out_path

        raise RuntimeError(f"ElevenLabs TTS failed for [{lang}]")

    def get_duration(self, mp3_path: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3_path)],
                capture_output=True, text=True, check=True,
            )
            return float(json.loads(r.stdout)["format"]["duration"])
        except Exception:
            return 0.0

    def _generate(self, text: str, out_path: Path, lang: str) -> bool:
        try:
            r = requests.post(
                _ELEVENLABS_URL.format(voice_id=self._voice),
                headers={"xi-api-key": self._key, "Content-Type": "application/json"},
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
                log.warning(f"  ElevenLabs [{lang}] HTTP {r.status_code}: {r.text[:300]}")
                return False
            out_path.write_bytes(r.content)
            log.info(f"  ElevenLabs [{lang}] saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return True
        except Exception as e:
            log.warning(f"  ElevenLabs [{lang}] error: {e}")
            return False
