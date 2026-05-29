"""
VoiceEngine — Per-language TTS routing.

EN  → ElevenLabs Brian (eleven_multilingual_v2) — deep authoritative English
HI  → ElevenLabs with Hindi-specific voice ID (ELEVENLABS_VOICE_ID_HI) if set,
       else Edge TTS hi-IN-MadhurNeural (male, natural Hindi)
TE  → ElevenLabs with Telugu-specific voice ID (ELEVENLABS_VOICE_ID_TE) if set,
       else Edge TTS te-IN-MohanNeural (male, natural Telugu)

Why separate voices: English voice Brian speaking Hindi/Telugu sounds unnatural.
Native Neural voices for each language match the NacArtha male character.
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger("voice_engine")

# ElevenLabs voice IDs — per language
ELEVENLABS_VOICE_EN = os.environ.get("ELEVENLABS_VOICE_ID_EN", "nPczCjzI2devNBz1zQrb")  # Brian
ELEVENLABS_VOICE_HI = os.environ.get("ELEVENLABS_VOICE_ID_HI", "")  # set in Railway for Hindi
ELEVENLABS_VOICE_TE = os.environ.get("ELEVENLABS_VOICE_ID_TE", "")  # set in Railway for Telugu

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Edge TTS fallback voices — male, consistent with NacArtha character
EDGE_VOICES = {
    "en": ("en-US-BrianNeural",   "-3%"),
    "hi": ("hi-IN-MadhurNeural",  "0%"),   # male, authoritative Hindi
    "te": ("te-IN-MohanNeural",   "0%"),   # male, natural Telugu
}


class VoiceEngine:

    def __init__(self):
        self._el_key = os.environ.get("ELEVENLABS_API_KEY", "")

    def generate(self, text: str, out_path: Path, lang: str = "en") -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"Voice [{lang}] {len(text)} chars → {out_path.name}")

        if self._el_key:
            voice_id = self._voice_id_for_lang(lang)
            if voice_id:
                if self._elevenlabs_generate(text, out_path, voice_id):
                    return out_path
                log.warning(f"  ElevenLabs failed [{lang}], falling back to Edge TTS")
            else:
                log.info(f"  No ElevenLabs voice ID for [{lang}] — using Edge TTS directly")

        return self._edge_generate(text, out_path, lang)

    def _voice_id_for_lang(self, lang: str) -> str:
        """Return ElevenLabs voice ID for the given language, or empty string to skip ElevenLabs."""
        if lang == "en":
            return ELEVENLABS_VOICE_EN
        if lang == "hi":
            return ELEVENLABS_VOICE_HI   # empty = fall through to Edge TTS
        if lang == "te":
            return ELEVENLABS_VOICE_TE   # empty = fall through to Edge TTS
        return ELEVENLABS_VOICE_EN

    def get_duration(self, mp3_path: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3_path)],
                capture_output=True, text=True, check=True,
            )
            return float(json.loads(r.stdout)["format"]["duration"])
        except Exception:
            return 0.0

    def _elevenlabs_generate(self, text: str, out_path: Path, voice_id: str) -> bool:
        try:
            import requests
            url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)
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
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.status_code != 200:
                log.warning(f"  ElevenLabs HTTP {r.status_code}: {r.text}")
                return False
            content_type = r.headers.get("content-type", "")
            if "application/json" in content_type:
                log.warning(f"  ElevenLabs returned JSON instead of audio: {r.text}")
                return False
            out_path.write_bytes(r.content)
            log.info(f"  ElevenLabs [{voice_id[:8]}…] saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return True
        except Exception as e:
            log.warning(f"  ElevenLabs error: {e}")
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
