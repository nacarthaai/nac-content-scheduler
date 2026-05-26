"""
StockEngine — Downloads free stock footage from Pexels.

Searches by keyword, downloads HD clips, caches by keyword hash to avoid
re-downloading. Returns a local Path to the clip, or None if unavailable.
"""
import hashlib
import logging
import os
import random
from datetime import date
from pathlib import Path

import requests

log = logging.getLogger("stock_engine")

PEXELS_API = "https://api.pexels.com/videos/search"
CACHE_DIR = Path(__file__).parent.parent / "cache" / "stock"


class StockEngine:

    def __init__(self):
        self._key = os.environ.get("PEXELS_API_KEY", "")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def fetch(self, keywords: list[str], orientation: str = "landscape", min_duration: int = 5, variant: str = "") -> Path:
        # Pexels needs short search terms — extract first 3 words from the visual prompt
        query = " ".join(" ".join(keywords).split()[:3])
        # Include today's date + variant (scene id) so each scene gets its own independent clip,
        # even when multiple scenes share the same visual keywords.
        today = date.today().isoformat()
        cache_key = hashlib.md5(f"{query}:{orientation}:{today}:{variant}".encode()).hexdigest()[:12]
        cached = CACHE_DIR / f"{cache_key}.mp4"
        if cached.exists() and cached.stat().st_size > 10_000:
            log.info(f"  Stock cache hit: {query} [{variant}] ({today})")
            return cached
        return self._download(query, cached, orientation, min_duration)

    def _download(self, query: str, out_path: Path, orientation: str, min_duration: int) -> Path:
        if not self._key:
            log.warning("PEXELS_API_KEY not set — skipping stock fetch")
            return None
        try:
            r = requests.get(
                PEXELS_API,
                headers={"Authorization": self._key},
                params={"query": query, "orientation": orientation, "size": "medium", "per_page": 15},
                timeout=30,
            )
            r.raise_for_status()
            videos = r.json().get("videos", [])
            clip_url = _best_clip_url(videos, min_duration)
            if not clip_url:
                log.warning(f"  No Pexels clip for: {query}")
                return None
            log.info(f"  Downloading: {query}")
            r2 = requests.get(clip_url, timeout=180, stream=True)
            r2.raise_for_status()
            out_path.write_bytes(r2.content)
            log.info(f"  Saved → {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return out_path
        except Exception as e:
            log.warning(f"  Pexels download failed ({query}): {e}")
            return None


def _best_clip_url(videos: list, min_duration: int) -> str:
    candidates = []
    for v in videos:
        if v.get("duration", 0) < min_duration:
            continue
        files = sorted(
            [f for f in v.get("video_files", []) if f.get("width", 0) <= 1920],
            key=lambda x: x.get("height", 0),
            reverse=True,
        )
        hd = [f for f in files if f.get("quality") in ("hd", "sd")]
        if hd:
            candidates.append(hd[0]["link"])
    # Pick randomly so different scenes get different footage, not always the first result
    return random.choice(candidates) if candidates else None
