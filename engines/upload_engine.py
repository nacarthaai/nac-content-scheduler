"""
UploadEngine — uploads video to YouTube in 5 languages using YouTube Data API v3.

Auth: OAuth2 with refresh token stored as GitHub secret.
      Run `python -m engines.upload_engine --auth` once locally to get the refresh token.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

log = logging.getLogger("upload_engine")

YOUTUBE_SCOPES  = ["https://www.googleapis.com/auth/youtube.upload",
                   "https://www.googleapis.com/auth/youtube"]
TOKEN_URI       = "https://oauth2.googleapis.com/token"

# Language → YouTube language code
YT_LANG = {
    "en": "en",
    "hi": "hi",
    "te": "te",
    "ta": "ta",
    "es": "es",
}

# Category: 27 = Education
CATEGORY_ID = "27"


class UploadEngine:

    def __init__(self, client_id: str, client_secret: str,
                 refresh_tokens: dict):
        """
        refresh_tokens: {lang_code: refresh_token_string}
        e.g. {"en": "1//...", "hi": "1//...", "te": "1//..."}
        """
        self.client_id      = client_id
        self.client_secret  = client_secret
        self.refresh_tokens = refresh_tokens   # per-channel tokens
        self._clients       = {}               # lang_code → youtube client

    # ── Public ────────────────────────────────────────────────

    def upload_all_languages(
        self,
        video_path:   Path,
        thumbnail_path: Path,
        translations: dict,   # {lang_code: {title, description, tags}}
        topic_type:   str = "educational",
    ) -> dict:
        """
        Upload video to each language's dedicated channel.
        Returns {lang_code: youtube_url}.
        """
        results = {}

        for lang_code, meta in translations.items():
            token = self.refresh_tokens.get(lang_code)
            if not token:
                log.warning(f"  No refresh token for [{lang_code}] — skipping")
                results[lang_code] = None
                continue

            log.info(f"Uploading [{lang_code}] '{meta['title']}'...")
            try:
                yt = self._get_client(lang_code, token)
                video_id = self._upload_video(yt, video_path, meta, lang_code, topic_type)
                if thumbnail_path and thumbnail_path.exists():
                    self._set_thumbnail(yt, video_id, thumbnail_path)
                url = f"https://youtu.be/{video_id}"
                results[lang_code] = url
                log.info(f"  ✓ [{lang_code}] {url}")
                time.sleep(5)
            except Exception as e:
                log.error(f"  ✗ [{lang_code}] Upload failed: {e}")
                results[lang_code] = None

        return results

    # ── Single upload ─────────────────────────────────────────

    def _upload_video(self, yt, video_path: Path, meta: dict,
                      lang_code: str, topic_type: str) -> str:
        tags = meta.get("tags", []) + [
            "trading", "stockmarket", "algotrading", "AItrading", "NacArtha",
        ]

        body = {
            "snippet": {
                "title":       meta["title"][:100],
                "description": meta["description"],
                "tags":        tags[:500],  # YouTube tag limit
                "categoryId":  CATEGORY_ID,
                "defaultLanguage":      YT_LANG.get(lang_code, "en"),
                "defaultAudioLanguage": YT_LANG.get(lang_code, "en"),
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        request = yt.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info(f"    Upload progress [{lang_code}]: {pct}%")

        return response["id"]

    # ── Thumbnail ─────────────────────────────────────────────

    def _set_thumbnail(self, yt, video_id: str, thumb_path: Path):
        try:
            yt.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg"),
            ).execute()
            log.info(f"    Thumbnail set for {video_id}")
        except Exception as e:
            log.warning(f"    Thumbnail set failed: {e}")

    # ── OAuth2 client ─────────────────────────────────────────

    def _get_client(self, lang_code: str, refresh_token: str):
        if lang_code in self._clients:
            return self._clients[lang_code]

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri=TOKEN_URI,
            scopes=YOUTUBE_SCOPES,
        )
        creds.refresh(Request())
        client = build("youtube", "v3", credentials=creds)
        self._clients[lang_code] = client
        return client


# ── One-time local auth helper ────────────────────────────────

def get_refresh_token(client_id: str, client_secret: str) -> str:
    """
    Run this once locally to get your refresh token.
    Save it as YOUTUBE_REFRESH_TOKEN in GitHub secrets.

    Usage:  python -c "from engines.upload_engine import get_refresh_token; print(get_refresh_token('CLIENT_ID', 'CLIENT_SECRET'))"
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     TOKEN_URI,
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, YOUTUBE_SCOPES)
    creds = flow.run_local_server(port=0)
    return creds.refresh_token


if __name__ == "__main__":
    import argparse, os
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow to get refresh token")
    parser.add_argument("--channel", default="en", help="Channel label (en/hi/te) — for your reference only")
    args = parser.parse_args()

    if args.auth:
        client_id     = os.environ.get("YOUTUBE_CLIENT_ID", "")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            print("ERROR: Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET env vars first")
            raise SystemExit(1)
        print(f"\nOpening browser for [{args.channel}] channel OAuth…")
        token = get_refresh_token(client_id, client_secret)
        print(f"\n{'='*60}")
        print(f"YOUTUBE_REFRESH_TOKEN_{args.channel.upper()}:")
        print(token)
        print(f"{'='*60}")
        print("Paste this into Railway Variables and save.")
