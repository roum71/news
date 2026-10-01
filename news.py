import streamlit as st
import pandas as pd
import requests
import json
import re
import random
import time
from datetime import date, timedelta
from io import BytesIO


# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="Instagram News Extractor",
    page_icon="📸",
    layout="wide"
)


# ---------------------------------------------------------
# USER-AGENT POOL & HELPER FUNCTIONS
# ---------------------------------------------------------

USER_AGENTS = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) "
    "Gecko/20100101 Firefox/127.0",
    # Mobile Chrome / Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
]


def build_headers(rotate_per_request):
    """Generate headers with randomized User-Agent and accepted languages."""
    if rotate_per_request:
        ua = random.choice(USER_AGENTS)
    else:
        if "run_user_agent" not in st.session_state:
            st.session_state["run_user_agent"] = random.choice(USER_AGENTS)
        ua = st.session_state["run_user_agent"]

    headers = {
        "User-Agent": ua,
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en;q=0.9",
        ]),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Referer": "https://www.instagram.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    return headers


COOKIE_FILE = "ig_session.txt"


def get_saved_cookie():
    """Load session cookie from secrets or a local file."""
    # Option A: Streamlit Secrets
    try:
        secret_cookie = st.secrets["instagram"]["session_cookie"]
        if secret_cookie:
            return secret_cookie.strip(), "Streamlit Secrets"
    except Exception:
        pass

    # Option B: Plain text file next to the app
    try:
        with open(COOKIE_FILE, "r") as f:
            file_cookie = f.read().strip()
            if file_cookie:
                return file_cookie, COOKIE_FILE
    except Exception:
        pass

    return "", None


def build_instagram_url(value):
    """Clean and standardise Instagram profile URL."""
    value = value.strip()
    if not value:
        return None

    if "instagram.com" in value:
        value = value.split("?")[0].rstrip("/")
        if not value.startswith("http"):
            value = "https://" + value
        return value + "/"

    value = value.lstrip("@").strip("/")
    return f"https://www.instagram.com/{value}/"


def extract_username(value):
    """Extract username string from URL or input."""
    value = value.strip().lstrip("@")
    if "instagram.com" in value:
        parts = [p for p in value.split("/") if p]
        if "instagram.com" in parts[0]:
            if len(parts) > 1:
                return parts[1]
            return None
        return None

    return value.split("/")[0]


# ---------------------------------------------------------
# TITLE & UI INPUTS
# ---------------------------------------------------------

st.title("📸 Instagram News Extractor")

st.write(
    "Extract public Instagram posts directly from an Instagram "
    "profile page — no API key required."
)

st.caption(
    "Note: without logging in or using a session cookie, Instagram only exposes "
    "the most recent ~12 posts of a public profile."
)

col1, col2 = st.columns(2)

with col1:
    username_input = st.text_input(
        "Instagram username or profile URL",
        value="rakmediaoffice",
        placeholder="rakmediaoffice"
    )

with col2:
    days = st.number_input(
        "Number of days",
        min_value=1,
        max_value=3650,
        value=30
    )

end_date = date.today()
start_date = end_date - timedelta(days=int(days))

st.write(
    f"**Date range:** {start_date.strftime('%Y-%m-%d')} "
    f"to {end_date.strftime('%Y-%m-%d')}"
)


# ---------------------------------------------------------
# NETWORK OPTIONS (expandable)
# ---------------------------------------------------------

with st.expander("🌐 Network options (use these if you get HTTP 429)"):

    ua_option = st.selectbox(
        "User-Agent strategy",
        options=[
            "Rotate randomly (recommended)",
            "Randomize every retry",
        ],
        index=0
    )

    proxy_input = st.text_input(
        "Proxy (optional)",
        placeholder="http://user:pass@host:port or socks5://host:port",
        help="Instagram rate-limits by IP. A proxy gives you a different IP."
    )

    _saved_cookie, _saved_source = get_saved_cookie()

    if _saved_cookie:
        st.success(
            f"✅ Session cookie loaded automatically from {_saved_source}"
        )

    cookie_input = st.text_input(
        "Instagram session cookie (optional)",
        value=_saved_cookie,
        placeholder="sessionid=YOUR_SESSION_ID; ds_user_id=...",
        help=(
            "Paste your sessionid cookie from a logged-in browser. "
            "Save it once in Streamlit Secrets "
            "[instagram] session_cookie=... or in a file named "
            "ig_session.txt next to this app."
        )
    )

    max_retries = st.slider(
        "Max retries",
        min_value=1,
        max_value=5,
        value=3
    )


# ---------------------------------------------------------
# DIAGNOSTICS
# ---------------------------------------------------------

with st.expander("🩺 Diagnostics — check which IP Instagram sees"):

    st.write(
        "A hard HTTP 429 means Instagram blocked your server's IP. "
        "User-Agent rotation cannot fix an IP block. "
        "Use the **session cookie** field (most reliable) or a **proxy**."
    )

    st.markdown(
        """
**How to get your session cookie (free):**
1. Open instagram.com in your browser and log in.
2. Press **F12** → **Application** tab → **Cookies** → `instagram.com`.
3. Copy the value of the `sessionid` cookie.

**Save it once — auto-loaded every run:**
- **Secrets (recommended):** create `.streamlit/secrets.toml` with:
  ```toml
  [instagram]
  session_cookie = "sessionid=YOUR_VALUE"
