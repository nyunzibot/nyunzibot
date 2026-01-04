#!/usr/bin/env python
"""
Pixiv OAuth helper script.
Gets a refresh token for use with pixivpy-async.

Based on: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362

Usage:
    python pixiv_auth.py login
    
This will open a browser where you log in to Pixiv, then paste the callback URL
to get your refresh token.
"""

import re
import sys
import json
import webbrowser
from urllib.parse import urlencode
from base64 import urlsafe_b64encode
from hashlib import sha256
from secrets import token_urlsafe
from pprint import pprint

import requests

# Pixiv OAuth constants
USER_AGENT = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"


def s256(data: bytes) -> str:
    """S256 transformation method."""
    return urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")


def oauth_pkce():
    """Generate PKCE code verifier and challenge."""
    code_verifier = token_urlsafe(32)
    code_challenge = s256(code_verifier.encode("ascii"))
    return code_verifier, code_challenge


def login():
    """Interactive login flow."""
    code_verifier, code_challenge = oauth_pkce()

    login_params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }

    login_url = f"{LOGIN_URL}?{urlencode(login_params)}"
    
    print("=" * 60)
    print("PIXIV LOGIN")
    print("=" * 60)
    print()
    print("Opening browser to Pixiv login page...")
    print()
    print("If the browser doesn't open, manually go to:")
    print(login_url)
    print()
    
    try:
        webbrowser.open(login_url)
    except Exception:
        pass
    
    print("After logging in, you'll be redirected to a page that may show an error.")
    print("That's expected! Copy the ENTIRE URL from your browser's address bar")
    print("and paste it here.")
    print()
    
    try:
        callback_url = input("Paste the callback URL here: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return
    
    # Extract the code from the callback URL
    # URL format: https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback?state=...&code=...
    match = re.search(r"code=([^&]+)", callback_url)
    if not match:
        print("ERROR: Could not find 'code' parameter in the URL!")
        print("Make sure you copied the entire URL including 'code=...'")
        return
    
    code = match.group(1)
    print()
    print(f"Extracted code: {code[:20]}...")
    print()
    print("Exchanging code for tokens...")
    
    # Exchange code for tokens
    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "include_policy": "true",
            "redirect_uri": REDIRECT_URI,
        },
        headers={
            "User-Agent": USER_AGENT,
            "App-OS": "android",
            "App-OS-Version": "11",
            "App-Version": "5.0.234",
        },
    )
    
    data = response.json()
    
    if "error" in data:
        print("ERROR from Pixiv:")
        pprint(data)
        return
    
    print()
    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print()
    print("Add this to your config.py:")
    print()
    print(f'PIXIV_REFRESH_TOKEN = "{data["refresh_token"]}"')
    print()
    print("Full response (for reference):")
    pprint(data)


def refresh(refresh_token: str):
    """Get new access token using refresh token."""
    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "include_policy": "true",
            "refresh_token": refresh_token,
        },
        headers={
            "User-Agent": USER_AGENT,
            "App-OS": "android",
            "App-OS-Version": "11",
            "App-Version": "5.0.234",
        },
    )
    
    data = response.json()
    pprint(data)
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python pixiv_auth.py login              - Get initial refresh token")
        print("  python pixiv_auth.py refresh <token>    - Test refresh token")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "login":
        login()
    elif command == "refresh" and len(sys.argv) >= 3:
        refresh(sys.argv[2])
    else:
        print("Unknown command. Use 'login' or 'refresh <token>'")
