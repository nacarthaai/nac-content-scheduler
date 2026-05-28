"""
NacArtha Content Scheduler

Runs 24/7 on Railway. Fires the video pipeline at exactly 4:00 PM EDT daily.
Manual trigger: POST /run  (or GET /run?token=<TRIGGER_TOKEN>)

Resilience:
  - Per-language completion markers in output/.done_LANG_YYYY-MM-DD
  - On startup, auto-resumes any languages not yet done today (handles redeploy mid-run)
  - /run returns 409 if pipeline is already running (prevents double-trigger)
"""
import logging
import os
import sys
import time
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
_OUTPUT    = Path(__file__).parent / "output"
_ALL_LANGS = ["en", "hi", "te"]

_pipeline_lock = threading.Lock()   # prevents concurrent runs


def _today() -> str:
    return datetime.now(NY_TZ).strftime("%Y-%m-%d")


def _done_file(lang: str) -> Path:
    return _OUTPUT / f".done_{lang}_{_today()}"


def _pending_langs() -> list:
    """Return languages that haven't completed successfully today."""
    return [l for l in _ALL_LANGS if not _done_file(l).exists()]


def _mark_lang_done(lang: str):
    try:
        _OUTPUT.mkdir(parents=True, exist_ok=True)
        _done_file(lang).touch()
    except Exception:
        pass


def run_pipeline(langs: list, is_retry: bool = False) -> bool:
    label = "RETRY" if is_retry else "PIPELINE"
    log.info(f"=== Firing NacArtha {label} langs={langs} ===")
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)
        import nac_orchestrator
        nac_orchestrator.main(langs=langs, on_lang_done=_mark_lang_done)
        log.info(f"=== {label} complete ===")
        return True
    except Exception as e:
        log.error(f"{label} failed: {e}", exc_info=True)
        _telegram(f"❌ NacArtha {label} FAILED:\n`{e}`")
        return False


def _run_with_retry(langs: list = None):
    """Run pipeline for pending langs; retry once after 30 min on failure."""
    if langs is None:
        langs = _pending_langs()

    if not langs:
        log.info("All languages already done today — skipping")
        return

    if not _pipeline_lock.acquire(blocking=False):
        log.warning("Pipeline already running — skipping duplicate trigger")
        return

    try:
        success = run_pipeline(langs, is_retry=False)
        if not success:
            log.info("Pipeline failed — scheduling retry in 30 minutes")
            _telegram("⏳ NacArtha pipeline will retry in 30 minutes")

            def _retry():
                time.sleep(30 * 60)
                pending = _pending_langs()
                if pending:
                    run_pipeline(pending, is_retry=True)

            threading.Thread(target=_retry, daemon=True, name="PipelineRetry").start()
    finally:
        _pipeline_lock.release()


def _startup_resume():
    """Resume incomplete languages — but ONLY if it's already past 4 PM EDT today.
    If we deploy before 4 PM, the cron handles it. Only resume after the cron window."""
    time.sleep(60)
    now = datetime.now(NY_TZ)
    if now.hour < 16:
        log.info(f"Startup resume skipped — only {now.hour}:{now.minute:02d} ET, cron fires at 16:00")
        return
    pending = _pending_langs()
    if pending:
        log.info(f"Startup resume — incomplete langs today: {pending}")
        _telegram(f"🔄 NacArtha resuming incomplete langs: {pending}")
        _run_with_retry(langs=pending)


def _telegram(text: str):
    import requests as _req
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        _req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def _start_trigger_server():
    """HTTP server — serves 3D dashboard at / and fires pipeline on /run."""
    token     = os.environ.get("TRIGGER_TOKEN", "")
    _html_tpl = (Path(__file__).parent / "static" / "dashboard.html").read_text()
    _html     = _html_tpl.replace("%%TOKEN%%", token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.info(f"HTTP {fmt % args}")

        def _html_resp(self, html):
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _text(self, code, msg):
            body = msg.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", ""):
                return self._html_resp(_html)
            if path == "/run":
                if token and f"token={token}" not in self.path:
                    return self._text(403, "forbidden")
                self._fire()
            else:
                self._text(404, "not found")

        def do_POST(self):
            if self.path.split("?")[0] != "/run":
                return self._text(404, "not found")
            if token and self.headers.get("X-Trigger-Token") != token:
                return self._text(403, "forbidden")
            self._fire()

        def _fire(self):
            if _pipeline_lock.locked():
                return self._text(409, "Pipeline already running\n")
            log.info("Manual trigger received via HTTP")
            threading.Thread(target=_run_with_retry, daemon=True, name="ManualTrigger").start()
            self._text(200, "Pipeline triggered\n")

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    log.info(f"Dashboard: https://nac-content-scheduler-production.up.railway.app")
    threading.Thread(target=server.serve_forever, daemon=True, name="TriggerServer").start()


scheduler = BlockingScheduler()

scheduler.add_job(
    _run_with_retry,
    CronTrigger(hour=16, minute=0, timezone="America/New_York"),
    max_instances=1,
    misfire_grace_time=3600,
)

_start_trigger_server()

# Auto-resume any incomplete languages from a previous interrupted run
threading.Thread(target=_startup_resume, daemon=True, name="StartupResume").start()

now_ny = datetime.now(NY_TZ)
log.info(f"NacArtha Scheduler running — pipeline fires daily at 4:00 PM EDT | Started at {now_ny.strftime('%H:%M')} ET")

try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    log.info("Scheduler stopped")
