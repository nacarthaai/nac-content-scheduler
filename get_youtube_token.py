"""
Run this ONCE locally to get your YouTube OAuth2 refresh token.
Save the token as YOUTUBE_REFRESH_TOKEN in GitHub secrets.

Usage:
    python get_youtube_token.py
    python get_youtube_token.py --secrets client_secret.json
"""
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", default="client_secret.json",
                        help="Path to downloaded client_secret JSON file")
    args = parser.parse_args()

    print("\nOpening browser for Google authorization...")
    print("Select your YouTube channel account.\n")

    flow = InstalledAppFlow.from_client_secrets_file(args.secrets, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "=" * 60)
    print("SUCCESS — Your refresh token:")
    print("=" * 60)
    print(creds.refresh_token)
    print("=" * 60)
    print("\nAdd this as YOUTUBE_REFRESH_TOKEN in GitHub → Settings → Secrets")
