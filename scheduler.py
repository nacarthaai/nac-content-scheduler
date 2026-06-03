"""
NacArtha Content Scheduler

Runs 24/7 on Railway. Fires the video pipeline at exactly 4:00 PM EDT/EST daily.

One trigger only — the 4 PM cron. No startup resume, no manual /run, no retries.
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


def run_pipeline():
    # Deploy guard: if the container just started (deploy), skip this cron fire
    uptime_secs = (datetime.now() - _startup_time).total_seconds()
    if uptime_secs < _STARTUP_GUARD:
        log.warning(
            f"Cron fired {uptime_secs:.0f}s after container start — "
            f"likely a deploy restart. SKIPPING to protect 4pm-only rule. "
            f"Next run: tomorrow 4:00 PM ET."
        )
        return

    log.info("=== Firing NacArtha pipeline (4 PM cron) ===")
    if not _pipeline_lock.acquire(blocking=False):
        log.warning("Pipeline already running — skipping")
        return
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)
        import nac_orchestrator
        nac_orchestrator.main(langs=_ALL_LANGS, on_lang_done=_mark_lang_done)
        log.info("=== Pipeline complete ===")
    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        _telegram(f"❌ NacArtha pipeline FAILED:\n`{e}`")
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


def _fire_pipeline(langs: list):
    if not _pipeline_lock.acquire(blocking=False):
        log.warning("Pipeline already running — skipping manual fire")
        return
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)
        import nac_orchestrator
        log.info(f"=== Manual fire: langs={langs} ===")
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
                langs = [l.strip() for l in langs_param.split(",") if l.strip()]
                if _pipeline_lock.locked():
                    body = b"pipeline already running"
                    self.send_response(409)
                else:
                    threading.Thread(
                        target=_fire_pipeline, args=(langs,), daemon=True
                    ).start()
                    body = f"pipeline fired for langs={langs}".encode()
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

scheduler.add_job(
    run_pipeline,
    CronTrigger(hour=16, minute=0, timezone="America/New_York"),
    max_instances=1,
    misfire_grace_time=None,  # never fire a missed job — deploy at 4pm = skip, wait tomorrow
)

_start_dashboard_server()

now_ny = datetime.now(NY_TZ)
log.info(f"NacArtha Scheduler — pipeline fires ONLY at 4:00 PM ET daily | Started at {now_ny.strftime('%H:%M')} ET")
log.info("Trigger rule: 4PM cron + manual /fire only. Missed jobs are SKIPPED — no catch-up.")

try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    log.info("Scheduler stopped")
