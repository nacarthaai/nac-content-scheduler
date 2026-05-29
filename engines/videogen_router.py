"""
VideoGenRouter — rotates AI video generation across free-tier platforms.

Monthly free clip budgets (5-second clips):
  Kling AI   →  66 clips  (170 credits ÷ 2.6/clip)
  Hailuo     →  30 clips
  Seedance   →  30 clips  (via seedance.io direct, separate from Replicate paid)

Priority order: Kling → Hailuo → Seedance (paid Replicate fallback)

Set FORCE_ENGINE=seedance to skip free tiers and use Seedance directly.
Useful for high-quality test runs or when free credits are exhausted.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("videogen_router")

_OUTPUT  = Path(__file__).parent.parent / "output"
_NY_TZ   = ZoneInfo("America/New_York")

_MONTHLY_LIMITS = {
    "kling":          66,
    "hailuo":         30,
    "seedance_free":  30,
}


def _usage_file() -> Path:
    month = datetime.now(_NY_TZ).strftime("%Y-%m")
    return _OUTPUT / f".videogen_usage_{month}.json"


def _load_usage() -> dict:
    f = _usage_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {k: 0 for k in _MONTHLY_LIMITS}


def _save_usage(usage: dict):
    try:
        _OUTPUT.mkdir(parents=True, exist_ok=True)
        _usage_file().write_text(json.dumps(usage))
    except Exception as e:
        log.warning(f"  Router: failed to save usage: {e}")


def _under_limit(usage: dict, engine: str) -> bool:
    return usage.get(engine, 0) < _MONTHLY_LIMITS.get(engine, 0)


class VideoGenRouter:

    def __init__(self):
        from engines.kling_engine    import KlingEngine
        from engines.hailuo_engine   import HailuoEngine
        from engines.seedance_engine import SeedanceEngine

        self._kling    = KlingEngine()
        self._hailuo   = HailuoEngine()
        self._seedance = SeedanceEngine()
        self._force    = os.environ.get("FORCE_ENGINE", "").lower()  # "seedance" to skip free tiers

    def generate(self, visual_description: str, out_path: Path, orientation: str = "landscape", narration: str = "") -> Path:

        # ── Force Seedance mode (set FORCE_ENGINE=seedance in Railway env) ────
        if self._force == "seedance":
            log.info("  Router → Seedance (FORCE_ENGINE=seedance)")
            return self._seedance.generate(visual_description, out_path, orientation, narration)

        usage = _load_usage()

        # ── 1. Kling (66/month free) ──────────────────────────────────────────
        if _under_limit(usage, "kling") and self._kling._access:
            log.info(f"  Router → Kling [{usage['kling']}/{_MONTHLY_LIMITS['kling']} used]")
            result = self._kling.generate(visual_description, out_path, orientation, narration)
            if result:
                usage["kling"] += 1
                _save_usage(usage)
                return result
            log.warning("  Router: Kling failed — trying Hailuo")

        # ── 2. Hailuo (30/month free) ─────────────────────────────────────────
        if _under_limit(usage, "hailuo") and self._hailuo._key:
            log.info(f"  Router → Hailuo [{usage['hailuo']}/{_MONTHLY_LIMITS['hailuo']} used]")
            result = self._hailuo.generate(visual_description, out_path, orientation, narration)
            if result:
                usage["hailuo"] += 1
                _save_usage(usage)
                return result
            log.warning("  Router: Hailuo failed — trying Seedance paid")

        # ── 3. Seedance paid (Replicate) ──────────────────────────────────────
        log.info("  Router → Seedance (paid Replicate)")
        return self._seedance.generate(visual_description, out_path, orientation, narration)

    def monthly_usage_report(self) -> str:
        usage  = _load_usage()
        month  = datetime.now(_NY_TZ).strftime("%B %Y")
        lines  = [f"VideoGen usage — {month}"]
        total  = 0
        for engine, limit in _MONTHLY_LIMITS.items():
            used  = usage.get(engine, 0)
            total += used
            lines.append(f"  {engine:<16} {used:>3}/{limit} clips")
        lines.append(f"  {'TOTAL FREE':<16} {total:>3}/{sum(_MONTHLY_LIMITS.values())}")
        if self._force:
            lines.append(f"  FORCE_ENGINE={self._force}")
        return "\n".join(lines)
