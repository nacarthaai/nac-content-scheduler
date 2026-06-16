"""
VoiceEngine — TTS for EN, HI, TE.

EN  → ElevenLabs NAC cloned voice (eleven_multilingual_v2) — character voice
HI  → edge-tts hi-IN-MadhurNeural   — free, native Hindi Neural voice
TE  → edge-tts te-IN-MohanNeural    — free, native Telugu Neural voice

ElevenLabs multilingual_v2 is trained primarily on English; it mangles Dravidian
and Hindi phonemes when used with an English-cloned voice. edge-tts Neural voices
are purpose-built for each language and are completely intelligible.
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

# edge-tts Neural voices — native speakers, clear pronunciation
_EDGE_VOICES = {
    "hi": "hi-IN-MadhurNeural",
    "te": "te-IN-MohanNeural",
}


class VoiceEngine:

    def __init__(self):
        self._key   = os.environ.get("ELEVENLABS_API_KEY", "")
        self._voice = os.environ.get("ELEVENLABS_VOICE_ID_NAC", "")
        if self._key and self._voice:
            log.info(f"  ElevenLabs TTS ready — voice={self._voice[:8]}… (EN only)")
        else:
            log.warning("  ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID_NAC not set — EN TTS will fail")
        log.info("  edge-tts ready — HI=hi-IN-MadhurNeural  TE=te-IN-MohanNeural")

    def generate(self, text: str, out_path: Path, lang: str = "en") -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists() and out_path.stat().st_size > 1024:
            log.info(f"Voice [{lang}] cached → {out_path.name}")
            return out_path

        log.info(f"Voice [{lang}] {len(text)} chars → {out_path.name}")

        if lang in _EDGE_VOICES:
            self._generate_edge(text, out_path, lang)
            return out_path

        # EN: ElevenLabs NAC cloned voice
        if not self._key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")
        if not self._voice:
            raise RuntimeError("ELEVENLABS_VOICE_ID_NAC not set")

        if self._generate_elevenlabs(text, out_path, lang):
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

    def _generate_edge(self, text: str, out_path: Path, lang: str) -> None:
        voice = _EDGE_VOICES[lang]
        result = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text, "--write-media", str(out_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"edge-tts [{lang}] failed: {result.stderr[:300]}")
        log.info(f"  edge-tts [{lang}] {voice} → {out_path.name} ({out_path.stat().st_size // 1024} KB)")

    def _generate_elevenlabs(self, text: str, out_path: Path, lang: str) -> bool:
        import time
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
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
                if r.status_code == 429:
                    wait = 30 * attempt
                    log.warning(f"  ElevenLabs [{lang}] rate-limited — waiting {wait}s (attempt {attempt}/{max_attempts})")
                    time.sleep(wait)
                    continue
                if r.status_code != 200:
                    log.warning(f"  ElevenLabs [{lang}] HTTP {r.status_code}: {r.text[:300]}")
                    if attempt < max_attempts:
                        time.sleep(10 * attempt)
                    continue
                out_path.write_bytes(r.content)
                log.info(f"  ElevenLabs [{lang}] saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
                return True
            except Exception as e:
                log.warning(f"  ElevenLabs [{lang}] error (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    time.sleep(10 * attempt)
        return False
