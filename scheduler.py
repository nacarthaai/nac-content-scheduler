"""
NacArtha Content Scheduler

Runs 24/7 on Railway. Fires the video pipeline at exactly 4:00 PM EDT daily.
Manual trigger: POST /run  (or GET /run?token=<TRIGGER_TOKEN>)
No external cron services needed — self-contained.
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

NY_TZ = ZoneInfo("America/New_York")

# Tracks today's successful run. Written to output/ which persists within a
# Railway deployment. Wiped on redeploy — but redeploys after 4pm are rare and
# a duplicate upload is harmless compared to missing a day entirely.
_LAST_RUN_FILE = Path(__file__).parent / "output" / ".last_run_date"

# Secondary check: scan output/ for a run_summary.json from today, which
# means the pipeline finished (even if _LAST_RUN_FILE was lost).
_OUTPUT_DIR = Path(__file__).parent / "output"


def _already_ran_today() -> bool:
    today = datetime.now(NY_TZ).strftime("%Y-%m-%d")
    try:
        if _LAST_RUN_FILE.exists() and _LAST_RUN_FILE.read_text().strip() == today:
            return True
    except Exception:
        pass
    # Fallback: check for a today-dated run directory in output/
    try:
        prefix = f"nac_{today.replace('-', '')}"
        for d in _OUTPUT_DIR.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                summary = d / "run_summary.json"
                if summary.exists():
                    return True
    except Exception:
        pass
    return False


def _mark_ran_today():
    try:
        _LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_RUN_FILE.write_text(datetime.now(NY_TZ).strftime("%Y-%m-%d"))
    except Exception:
        pass


def run_pipeline(is_retry: bool = False):
    label = "RETRY" if is_retry else "PIPELINE"
    log.info(f"=== Firing NacArtha {label} ===")
    try:
        import sys as _sys
        _sys.modules.pop("nac_orchestrator", None)  # fresh import each run
        import nac_orchestrator
        nac_orchestrator.main()
        _mark_ran_today()
        log.info(f"=== {label} complete ===")
        return True
    except Exception as e:
        log.error(f"{label} failed: {e}", exc_info=True)
        _telegram(f"❌ NacArtha {label} FAILED:\n`{e}`")
        return False


def _run_with_retry():
    """Run pipeline; if it fails, retry once after 30 minutes."""
    success = run_pipeline(is_retry=False)
    if not success:
        log.info("Pipeline failed — scheduling retry in 30 minutes")
        _telegram("⏳ NacArtha pipeline will retry in 30 minutes")

        def _retry():
            time.sleep(30 * 60)
            if not _already_ran_today():
                run_pipeline(is_retry=True)

        threading.Thread(target=_retry, daemon=True, name="PipelineRetry").start()


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

now_ny = datetime.now(NY_TZ)
log.info(f"NacArtha Scheduler running — pipeline fires daily at 4:00 PM EDT | Started at {now_ny.strftime('%H:%M')} ET")

try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    log.info("Scheduler stopped")

