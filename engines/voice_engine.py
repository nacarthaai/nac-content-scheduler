"""
VoiceEngine — ElevenLabs multilingual primary, Edge TTS fallback.

ElevenLabs eleven_multilingual_v2 handles EN, HI, and TE natively.
Edge TTS is the fallback when ElevenLabs key is unavailable or fails.
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger("voice_engine")

ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Brian — deep authoritative male
ELEVENLABS_TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

# Edge TTS voices — used only when ElevenLabs is unavailable
# Swara (female) and Shruti (female) sound more natural than the male variants for educational content
EDGE_VOICES = {
    "en": ("en-US-BrianNeural",   "-3%"),
    "hi": ("hi-IN-SwaraNeural",   "0%"),   # female, clearer enunciation than Madhur
    "te": ("te-IN-ShrutiNeural",  "0%"),   # female, clearer than Mohan
}


class VoiceEngine:

    def __init__(self):
        self._el_key = os.environ.get("ELEVENLABS_API_KEY", "")

    def generate(self, text: str, out_path: Path, lang: str = "en") -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"Voice [{lang}] {len(text)} chars → {out_path.name}")

        # ElevenLabs eleven_multilingual_v2 handles EN, HI, and TE natively
        if self._el_key:
            if self._elevenlabs_generate(text, out_path):
                return out_path
            log.warning(f"  ElevenLabs failed [{lang}], falling back to Edge TTS")

        return self._edge_generate(text, out_path, lang)

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
            import requests
            headers = {"xi-api-key": self._el_key, "Content-Type": "application/json"}
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                    "style": 0.3,
                    "use_speaker_boost": True,
                },
            }
            r = requests.post(ELEVENLABS_TTS_URL, headers=headers, json=payload, timeout=120)
            if r.status_code != 200:
                log.warning(f"  ElevenLabs HTTP {r.status_code}: {r.text}")
                return False
            # Guard against ElevenLabs returning JSON error with 200 status
            content_type = r.headers.get("content-type", "")
            if "application/json" in content_type:
                log.warning(f"  ElevenLabs returned JSON instead of audio: {r.text}")
                return False
            out_path.write_bytes(r.content)
            log.info(f"  ElevenLabs saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return True
        except Exception as e:
            log.warning(f"  ElevenLabs error: {e}")
            return False

    def _edge_generate(self, text: str, out_path: Path, lang: str, retries: int = 3) -> Path:
        import edge_tts
        voice, rate = EDGE_VOICES.get(lang, ("en-US-BrianNeural", "-3%"))
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
