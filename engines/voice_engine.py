"""
VoiceEngine — HeyGen TTS primary, Edge TTS fallback.

EN  → HeyGen voice (HEYGEN_VOICE_ID_EN) — Nac's cloned voice
HI  → HeyGen voice (HEYGEN_VOICE_ID_HI) — Nac's Hindi voice
TE  → HeyGen voice (HEYGEN_VOICE_ID_TE) — Nac's Telugu voice

Fallback: Edge TTS (free, no API key needed)
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

log = logging.getLogger("voice_engine")

_HEYGEN_URL = "https://api.heygen.com/v3/voices/speech"

EDGE_VOICES = {
    "en": ("en-US-BrianNeural",  "-3%"),
    "hi": ("hi-IN-MadhurNeural", "+0%"),
    "te": ("te-IN-MohanNeural",  "+0%"),
}


class VoiceEngine:

    def __init__(self):
        self._api_key = os.environ.get("HEYGEN_API_KEY", "")
        self._voice_ids = {
            "en": os.environ.get("HEYGEN_VOICE_ID_EN", ""),
            "hi": os.environ.get("HEYGEN_VOICE_ID_HI", ""),
            "te": os.environ.get("HEYGEN_VOICE_ID_TE", ""),
        }
        if self._api_key:
            log.info("  HeyGen TTS engine ready")
        else:
            log.warning("  HEYGEN_API_KEY not set — will use Edge TTS fallback")

    def generate(self, text: str, out_path: Path, lang: str = "en") -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip API call if audio already exists (idempotent re-runs)
        if out_path.exists() and out_path.stat().st_size > 1024:
            log.info(f"Voice [{lang}] cached → {out_path.name}")
            return out_path

        log.info(f"Voice [{lang}] {len(text)} chars → {out_path.name}")

        if not self._api_key:
            raise RuntimeError("HEYGEN_API_KEY not set — cannot generate NAC voice audio")

        voice_id = self._voice_ids.get(lang, "")
        if not voice_id:
            raise RuntimeError(
                f"HEYGEN_VOICE_ID_{lang.upper()} not set — cannot generate NAC voice audio"
            )

        if self._heygen_generate(text, out_path, voice_id, lang):
            return out_path

        raise RuntimeError(
            f"HeyGen TTS failed for [{lang}] — refusing Edge TTS fallback to protect NAC voice. "
            f"Check HeyGen API status and voice ID {voice_id[:8]}…"
        )

    def get_duration(self, mp3_path: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3_path)],
                capture_output=True, text=True, check=True,
            )
            return float(json.loads(r.stdout)["format"]["duration"])
        except Exception:
            return 0.0

    def _heygen_generate(self, text: str, out_path: Path, voice_id: str, lang: str) -> bool:
        try:
            r = requests.post(
                _HEYGEN_URL,
                headers={"X-Api-Key": self._api_key, "Content-Type": "application/json"},
                json={"voice_id": voice_id, "text": text, "speed": 1.0},
                timeout=120,
            )
            if r.status_code != 200:
                log.warning(f"  HeyGen HTTP {r.status_code}: {r.text[:300]}")
                return False

            content_type = r.headers.get("content-type", "")

            # Direct binary audio response
            if "audio" in content_type:
                out_path.write_bytes(r.content)
                log.info(f"  HeyGen saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
                return True

            # JSON response with audio URL
            data = r.json()
            audio_url = (
                data.get("data", {}).get("audio_url")
                or data.get("audio_url")
                or data.get("url")
            )
            if audio_url:
                audio_r = requests.get(audio_url, timeout=120)
                audio_r.raise_for_status()
                out_path.write_bytes(audio_r.content)
                log.info(f"  HeyGen saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
                return True

            log.warning(f"  HeyGen: no audio in response: {data}")
            return False

        except Exception as e:
            log.warning(f"  HeyGen TTS error: {e}")
            return False

    def _edge_generate(self, text: str, out_path: Path, lang: str, retries: int = 3) -> Path:
        import edge_tts
        voice, rate = EDGE_VOICES.get(lang, EDGE_VOICES["en"])
        log.info(f"  Edge TTS [{lang}] voice={voice}")
        mp3_raw = out_path.with_stem(out_path.stem + "_raw")

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(mp3_raw))

        for attempt in range(1, retries + 1):
            try:
                asyncio.run(_run())
                mp3_raw.rename(out_path)
                log.info(f"  Edge TTS saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
                return out_path
            except Exception as e:
                mp3_raw.unlink(missing_ok=True)
                log.warning(f"  Edge TTS attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(5 * attempt)
        return None
