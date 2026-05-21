"""
Generate YouTube OAuth2 refresh tokens for all 3 NacArtha channels.

Run this ONCE locally. A browser window opens for each channel — sign in
with the correct Google account for that channel.

Usage:
    cd trading-system/content-engine
    python get_youtube_tokens.py

Outputs the 3 tokens to paste into Railway env vars:
    YOUTUBE_REFRESH_TOKEN_EN
    YOUTUBE_REFRESH_TOKEN_HI
    YOUTUBE_REFRESH_TOKEN_TE
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

CHANNELS = [
    ("EN", "NacArtha English channel"),
    ("HI", "NacArtha Hindi channel"),
    ("TE", "NacArtha Telugu channel"),
]

CLIENT_SECRETS = "client_secret.json"

tokens = {}

print("\n" + "=" * 60)
print("NacArtha YouTube Token Generator — 3 channels")
print("=" * 60)
print("A browser window will open for each channel.")
print("Sign in with the CORRECT Google account each time.\n")

for lang, label in CHANNELS:
    input(f"Press ENTER to authorize {label} [{lang}]...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    creds = flow.run_local_server(port=0)
    tokens[lang] = creds.refresh_token
    print(f"  Got token for [{lang}]: {creds.refresh_token[:20]}...\n")

print("\n" + "=" * 60)
print("ALL TOKENS — paste these into Railway environment variables:")
print("=" * 60)
for lang, token in tokens.items():
    print(f"\nYOUTUBE_REFRESH_TOKEN_{lang}=")
    print(token)
print("\n" + "=" * 60)
