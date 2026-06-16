"""
SocialEngine — posts videos to Instagram Reels and TikTok.

Credentials required in Railway env vars:
  INSTAGRAM_USER_ID       — numeric IG Business account ID
  INSTAGRAM_ACCESS_TOKEN  — long-lived Graph API token
  TIKTOK_ACCESS_TOKEN     — TikTok Content Posting API token

Snapchat: no public API for organic content posting. Use Buffer/Later manually.

Video hosting: videos are staged to a GitHub Release (gh CLI) to get a
public URL required by Instagram and TikTok URL-ingest endpoints.
"""
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

log = logging.getLogger("social_engine")

GITHUB_REPO = "nacarthaai/nac-content-scheduler"
RELEASE_TAG = "media-staging"                         # single rolling release for temp hosting

GRAPH_BASE  = "https://graph.facebook.com/v21.0"
TIKTOK_BASE = "https://open.tiktokapis.com/v2"


# ── GitHub staging helper ─────────────────────────────────────────────────────

def _stage_to_github(video_path: Path) -> str:
    """Upload video to a GitHub Release and return the public download URL."""
    name = video_path.name

    # Ensure the rolling release exists
    check = subprocess.run(
        ["gh", "release", "view", RELEASE_TAG, "--repo", GITHUB_REPO],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        subprocess.run(
            ["gh", "release", "create", RELEASE_TAG,
             "--repo", GITHUB_REPO,
             "--title", "Media Staging (auto-managed)",
             "--notes", "Temporary video hosting for social API ingest. Safe to ignore."],
            check=True, capture_output=True,
        )
        log.info(f"  Created GitHub release '{RELEASE_TAG}'")

    # Delete old asset with same name if it exists (replace)
    subprocess.run(
        ["gh", "release", "delete-asset", RELEASE_TAG, name,
         "--repo", GITHUB_REPO, "--yes"],
        capture_output=True,
    )

    # Upload
    subprocess.run(
        ["gh", "release", "upload", RELEASE_TAG, str(video_path),
         "--repo", GITHUB_REPO, "--clobber"],
        check=True, capture_output=True,
    )
    url = (
        f"https://github.com/{GITHUB_REPO}/releases/download/"
        f"{RELEASE_TAG}/{name}"
    )
    log.info(f"  Staged to GitHub: {url}")
    return url


# ── Instagram Reels ───────────────────────────────────────────────────────────

class InstagramEngine:
    """Post Reels to an Instagram Business account via Meta Graph API."""

    def __init__(self):
        self.user_id = os.environ.get("INSTAGRAM_USER_ID", "")
        self.token   = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

    def _ready(self) -> bool:
        if not self.user_id or not self.token:
            log.warning("Instagram: INSTAGRAM_USER_ID or INSTAGRAM_ACCESS_TOKEN not set — skipping")
            return False
        return True

    def post_reel(self, video_path: Path, caption: str) -> str | None:
        if not self._ready():
            return None

        log.info(f"[Instagram] Staging video for API ingest...")
        video_url = _stage_to_github(video_path)

        # Step 1 — create media container
        log.info("[Instagram] Creating Reels container...")
        r = requests.post(
            f"{GRAPH_BASE}/{self.user_id}/media",
            params={
                "media_type":    "REELS",
                "video_url":     video_url,
                "caption":       caption,
                "share_to_feed": "true",
                "access_token":  self.token,
            },
            timeout=30,
        )
        r.raise_for_status()
        creation_id = r.json()["id"]
        log.info(f"  Container created: {creation_id}")

        # Step 2 — wait for video to finish processing (up to 5 min)
        for attempt in range(30):
            time.sleep(10)
            status_r = requests.get(
                f"{GRAPH_BASE}/{creation_id}",
                params={"fields": "status_code", "access_token": self.token},
                timeout=15,
            )
            status = status_r.json().get("status_code", "")
            log.info(f"  Status [{attempt+1}/30]: {status}")
            if status == "FINISHED":
                break
            if status == "ERROR":
                log.error(f"[Instagram] Video processing failed: {status_r.json()}")
                return None
        else:
            log.error("[Instagram] Timed out waiting for video processing")
            return None

        # Step 3 — publish
        log.info("[Instagram] Publishing Reel...")
        pub_r = requests.post(
            f"{GRAPH_BASE}/{self.user_id}/media_publish",
            params={"creation_id": creation_id, "access_token": self.token},
            timeout=30,
        )
        pub_r.raise_for_status()
        media_id = pub_r.json()["id"]
        url = f"https://www.instagram.com/reel/{media_id}/"
        log.info(f"  ✓ Instagram Reel posted: {url}")
        return url


# ── TikTok ────────────────────────────────────────────────────────────────────

class TikTokEngine:
    """Post videos to TikTok via Content Posting API (URL ingest)."""

    def __init__(self):
        self.token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")

    def _ready(self) -> bool:
        if not self.token:
            log.warning("TikTok: TIKTOK_ACCESS_TOKEN not set — skipping")
            return False
        return True

    def post_video(self, video_path: Path, title: str) -> str | None:
        if not self._ready():
            return None

        log.info(f"[TikTok] Staging video for API ingest...")
        video_url = _stage_to_github(video_path)

        # Step 1 — initialize post with URL pull
        log.info("[TikTok] Initializing video post...")
        r = requests.post(
            f"{TIKTOK_BASE}/post/publish/video/init/",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type":  "application/json; charset=UTF-8",
            },
            json={
                "post_info": {
                    "title":          title[:150],
                    "privacy_level":  "PUBLIC_TO_EVERYONE",
                    "disable_duet":   False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": {
                    "source":    "PULL_FROM_URL",
                    "video_url": video_url,
                },
            },
            timeout=30,
        )
        data = r.json()
        if data.get("error", {}).get("code", "ok") != "ok":
            log.error(f"[TikTok] Init failed: {data}")
            return None
        publish_id = data["data"]["publish_id"]
        log.info(f"  publish_id: {publish_id}")

        # Step 2 — poll status
        for attempt in range(30):
            time.sleep(10)
            status_r = requests.post(
                f"{TIKTOK_BASE}/post/publish/status/fetch/",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type":  "application/json; charset=UTF-8",
                },
                json={"publish_id": publish_id},
                timeout=15,
            )
            status_data = status_r.json().get("data", {})
            status = status_data.get("status", "")
            log.info(f"  Status [{attempt+1}/30]: {status}")
            if status == "PUBLISH_COMPLETE":
                tiktok_id = status_data.get("publicaly_available_post_id", [""])[0]
                url = f"https://www.tiktok.com/@nacarthaai/video/{tiktok_id}" if tiktok_id else "https://www.tiktok.com/@nacarthaai"
                log.info(f"  ✓ TikTok posted: {url}")
                return url
            if status in ("FAILED", "SPAM_RISK_TOO_MANY_POSTS"):
                log.error(f"[TikTok] Post failed: {status_data}")
                return None
        else:
            log.error("[TikTok] Timed out waiting for publish")
            return None


# ── Snapchat ──────────────────────────────────────────────────────────────────

class SnapchatEngine:
    """Snapchat does not offer a public API for organic Spotlight/Story posting.
    Use Buffer, Later, or Hootsuite for scheduled Snapchat posts."""

    def post_video(self, video_path: Path, caption: str) -> None:
        log.warning(
            "[Snapchat] No public API for organic content posting. "
            "Use a scheduling tool (Buffer/Later) or post manually."
        )
        return None


# ── Unified poster ────────────────────────────────────────────────────────────

class SocialEngine:
    """Post a video to Instagram, TikTok, and log Snapchat limitation."""

    def __init__(self):
        self.instagram = InstagramEngine()
        self.tiktok    = TikTokEngine()
        self.snapchat  = SnapchatEngine()

    def post_all(self, video_path: Path, caption: str, title: str) -> dict:
        """
        Post to all social platforms. Returns {platform: url_or_None}.
        Continues on failure so one platform never blocks the others.
        """
        results = {}

        log.info("--- Instagram ---")
        try:
            results["instagram"] = self.instagram.post_reel(video_path, caption)
        except Exception as e:
            log.error(f"[Instagram] Error: {e}")
            results["instagram"] = None

        log.info("--- TikTok ---")
        try:
            results["tiktok"] = self.tiktok.post_video(video_path, title)
        except Exception as e:
            log.error(f"[TikTok] Error: {e}")
            results["tiktok"] = None

        log.info("--- Snapchat ---")
        results["snapchat"] = self.snapchat.post_video(video_path, caption)

        return results
