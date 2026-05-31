"""
LibraryEngine — manages the pre-built HeyGen + Veo clip library.

Library structure:
  assets/library/heygen/nac/        → Nac Digital Twin clips (.mp4)
  assets/library/heygen/student/    → Student preset avatar clips (.mp4)
  assets/library/veo/trading/       → Trading room background clips (.mp4)
  assets/library/veo/classroom/     → Classroom background clips (.mp4)
  assets/library/veo/news/          → News aesthetic background clips (.mp4)
  assets/library/library_index.json → Master clip index

Selection: given emotion + character + category, returns best matching clip.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path

log = logging.getLogger("library_engine")

LIBRARY_DIR = Path(__file__).parent.parent / "assets" / "library"
INDEX_PATH  = LIBRARY_DIR / "library_index.json"

# emotion → ranked list of compatible categories for fallback matching
_EMOTION_CATEGORY_MAP = {
    "confidence": ["hook", "confident", "cta"],
    "clarity":    ["explain", "confident", "normal"],
    "curiosity":  ["explain", "normal"],
    "focus":      ["explain", "normal", "confident"],
    "excitement": ["hook", "confident", "reveal"],
    "insight":    ["reveal", "explain", "confident"],
    "tension":    ["reveal", "normal"],
}


class LibraryEngine:

    def __init__(self):
        self._index = _load_index()
        log.info(f"  Library loaded: {len(self._index)} clips")

    def get_nac_clip(self, emotion: str = "confidence", category: str = None) -> Path | None:
        return self._get_clip("nac", emotion, category)

    def get_student_clip(self, emotion: str = "curiosity", category: str = None) -> Path | None:
        return self._get_clip("student", emotion, category)

    def get_background(self, scene_category: str = "trading") -> Path | None:
        """scene_category: trading | classroom | news"""
        clips = [
            c for c in self._index
            if c.get("type") == "veo" and c.get("category") == scene_category
        ]
        if not clips:
            log.warning(f"  No flux backgrounds for category={scene_category}")
            return None
        chosen = random.choice(clips)
        p = LIBRARY_DIR / chosen["path"]
        return p if p.exists() else None

    def _get_clip(self, character: str, emotion: str, category: str = None) -> Path | None:
        # Build candidate list: exact category match first, then emotion-matched categories
        categories = [category] if category else _EMOTION_CATEGORY_MAP.get(emotion, ["normal"])

        for cat in categories:
            candidates = [
                c for c in self._index
                if c.get("type") == "heygen"
                and c.get("character") == character
                and c.get("category") == cat
            ]
            if candidates:
                chosen = random.choice(candidates)
                p = LIBRARY_DIR / chosen["path"]
                if p.exists():
                    log.info(f"  Library [{character}] emotion={emotion} → {chosen['id']}")
                    return p

        # Final fallback: any clip for this character
        fallbacks = [c for c in self._index if c.get("character") == character and c.get("type") == "heygen"]
        if fallbacks:
            chosen = random.choice(fallbacks)
            p = LIBRARY_DIR / chosen["path"]
            if p.exists():
                log.warning(f"  Library fallback [{character}] → {chosen['id']}")
                return p

        log.warning(f"  No library clip found for character={character} emotion={emotion}")
        return None

    def reload(self):
        self._index = _load_index()
        log.info(f"  Library reloaded: {len(self._index)} clips")


def _load_index() -> list:
    if not INDEX_PATH.exists():
        return []
    try:
        return json.loads(INDEX_PATH.read_text())
    except Exception as e:
        log.error(f"  Library index load failed: {e}")
        return []


def save_index(clips: list):
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(clips, indent=2, ensure_ascii=False))
    log.info(f"  Library index saved: {len(clips)} clips → {INDEX_PATH}")
