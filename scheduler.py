"""
NacArtha Content Scheduler

Runs 24/7 on Railway.

  Monday    4 PM ET → run_long_pipeline()  — generate 10-min long video + cut all 7 weekly shorts
  Tue-Sun   4 PM ET → run_short_upload()   — upload today's pre-cut short from weekly_plan.json
  POST /fire?mode=long|short               — manual trigger (token-gated)
"""
import logging
import os
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")

NY_TZ      = ZoneInfo("America/New_York")
_ALL_LANGS = ["en", "hi", "te"]

_pipeline_lock  = threading.Lock()
_startup_time   = datetime.now()   # recorded at module load = container start time
_STARTUP_GUARD  = 300              # 5 minutes — never fire within this window of a deploy


def _mark_lang_done(lang: str):
    pass  # no-op — YouTube is source of truth, not local markers


def _deploy_guard() -> bool:
    """Returns True if we should skip (container just deployed)."""
    uptime_secs = (datetime.now() - _startup_time).total_seconds()
    if uptime_secs < _STARTUP_GUARD:
        log.warning(
            f"Cron fired {uptime_secs:.0f}s after container start — "
            f"deploy restart detected. SKIPPING. Next run at 4:00 PM ET."
        )
        return True
    return False


def run_long_pipeline():
    """Monday 4 PM ET — generate long video + cut all 7 weekly shorts."""
    if _deploy_guard():
        return
    log.info("=== Monday: Long video pipeline (4 PM ET) ===")
    if not _pipeline_lock.acquire(blocking=False):
        log.warning("Pipeline already running — skipping")
        return
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)
        import nac_orchestrator
        nac_orchestrator.main(langs=_ALL_LANGS, on_lang_done=_mark_lang_done)
        log.info("=== Long pipeline complete ===")
        _telegram("✅ NacArtha long video + weekly shorts ready")
    except Exception as e:
        log.error(f"Long pipeline failed: {e}", exc_info=True)
        _telegram(f"❌ NacArtha long pipeline FAILED:\n`{e}`")
    finally:
        _pipeline_lock.release()


def run_short_upload():
    """Tue-Sun 4 PM ET — upload today's pre-cut short from weekly_plan.json."""
    if _deploy_guard():
        return
    log.info("=== Daily short upload (4 PM ET) ===")
    if not _pipeline_lock.acquire(blocking=False):
        log.warning("Pipeline already running — skipping")
        return
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)
        import nac_orchestrator
        nac_orchestrator.main_short(langs=_ALL_LANGS, on_lang_done=_mark_lang_done)
        log.info("=== Short upload complete ===")
    except Exception as e:
        log.error(f"Short upload failed: {e}", exc_info=True)
        _telegram(f"❌ NacArtha short upload FAILED:\n`{e}`")
    finally:
        _pipeline_lock.release()


def _telegram(text: str):
    import requests
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def _fire_pipeline(langs: list, mode: str = "long"):
    if not _pipeline_lock.acquire(blocking=False):
        log.warning("Pipeline already running — skipping manual fire")
        return
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)
        import nac_orchestrator
        log.info(f"=== Manual fire: mode={mode} langs={langs} ===")
        if mode == "short":
            nac_orchestrator.main_short(langs=langs, on_lang_done=_mark_lang_done)
        else:
            nac_orchestrator.main(langs=langs, on_lang_done=_mark_lang_done)
        log.info("=== Manual fire complete ===")
    except Exception as e:
        log.error(f"Manual fire failed: {e}", exc_info=True)
        _telegram(f"❌ NacArtha manual fire FAILED:\n`{e}`")
    finally:
        _pipeline_lock.release()


def _start_dashboard_server():
    """Status dashboard only — no trigger endpoint."""
    token     = os.environ.get("TRIGGER_TOKEN", "")
    html_path = Path(__file__).parent / "static" / "dashboard.html"
    _html     = html_path.read_text().replace("%%TOKEN%%", token) if html_path.exists() else "<h1>NacArtha Scheduler Running</h1>"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.info(f"HTTP {fmt % args}")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", ""):
                body = _html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path in ("/health", "/healthz", "/ping"):
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = b"not found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            if parsed.path == "/fire":
                qs    = parse_qs(parsed.query)
                tok   = qs.get("token", [""])[0]
                if token and tok != token:
                    body = b"unauthorized"
                    self.send_response(403)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                langs_param = qs.get("langs", ["en,hi,te"])[0]
                mode        = qs.get("mode",  ["long"])[0]
                langs = [l.strip() for l in langs_param.split(",") if l.strip()]
                if _pipeline_lock.locked():
                    body = b"pipeline already running"
                    self.send_response(409)
                else:
                    threading.Thread(
                        target=_fire_pipeline, args=(langs, mode), daemon=True
                    ).start()
                    body = f"pipeline fired: mode={mode} langs={langs}".encode()
                    self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = b"not found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="Dashboard").start()
    log.info(f"Dashboard running on port {port} (read-only, no trigger)")


scheduler = BlockingScheduler()

# Monday 4 PM ET — full long video + cut 7 weekly shorts
scheduler.add_job(
    run_long_pipeline,
    CronTrigger(day_of_week="mon", hour=16, minute=0, timezone="America/New_York"),
    max_instances=1,
    misfire_grace_time=None,
)

# Tue-Sun 4 PM ET — upload today's pre-cut short
scheduler.add_job(
    run_short_upload,
    CronTrigger(day_of_week="tue,wed,thu,fri,sat,sun", hour=16, minute=0, timezone="America/New_York"),
    max_instances=1,
    misfire_grace_time=None,
)

_start_dashboard_server()

now_ny = datetime.now(NY_TZ)
log.info(f"NacArtha Scheduler — Mon 4PM=long video | Tue-Sun 4PM=daily short | Started {now_ny.strftime('%H:%M')} ET")
log.info("Manual: POST /fire?mode=long|short&token=... Missed jobs SKIPPED — no catch-up.")

try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    log.info("Scheduler stopped")
