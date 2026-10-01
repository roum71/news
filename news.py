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
# TITLE
# ---------------------------------------------------------

st.title("📸 Instagram News Extractor")

st.write(
    "Extract public Instagram posts directly from an Instagram "
    "profile page — no API key required."
)

st.caption(
    "Note: without logging in, Instagram only exposes the most "
    "recent ~12 posts of a public profile."
)


# ---------------------------------------------------------
# INPUTS
# ---------------------------------------------------------

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
# SAVED SESSION COOKIE (loaded automatically)
# ---------------------------------------------------------
# Priority: 1) Streamlit Secrets  2) ig_session.txt file
# The cookie expires when you log out of Instagram or after
# some weeks — then just update it once, not every run.
# ---------------------------------------------------------

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

    # Option B: plain text file next to the app
    try:
        with open(COOKIE_FILE, "r") as f:
            file_cookie = f.read().strip()
            if file_cookie:
                return file_cookie, COOKIE_FILE
    except Exception:
        pass

    return "", None


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
        placeholder="http://user:pass@host:port  or  socks5://host:port",
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
            "ig_session.txt next to this app, and it will be "
            "loaded automatically every run."
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

**Save it once — auto-loaded every run (pick one):**
- **Secrets (recommended):** in your app folder, create
  `.streamlit/secrets.toml` with:
  `[instagram]`
  `session_cookie = "sessionid=YOUR_VALUE"`
- **File:** create `ig_session.txt` next to the app and put
  `sessionid=YOUR_VALUE` in it.

⚠️ The cookie stops working if you log out of Instagram or
it expires — then just replace it once.
"""
    )

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("🔎 Show my current IP"):
            try:
                ip = requests.get(
                    "https://api.ipify.org",
                    timeout=10
                ).text
                st.code(f"Current server IP: {ip}")
            except Exception as e:
                st.error(f"Could not determine IP: {e}")

    with col_b:
        if st.button("🧪 Test Instagram connection"):
            with st.spinner("Testing..."):
                _cookie, _src = get_saved_cookie()
                _test_headers = build_headers(False)
                if _cookie:
                    _test_headers["Cookie"] = _cookie
                try:
                    _r = requests.get(
                        "https://www.instagram.com/",
                        headers=_test_headers,
                        timeout=30
                    )
                    st.write(f"HTTP status: **{_r.status_code}**")
                    st.write(
                        f"Cookie loaded: "
                        f"**{'YES (from ' + _src + ')' if _cookie else 'NO'}**"
                    )
                    if _r.status_code == 200:
                        if '"ProfilePage"' in _r.text or "_sharedData" in _r.text:
                            st.success(
                                "Instagram is serving real page data — "
                                "extraction should work."
                            )
                        elif "login" in _r.text.lower():
                            st.warning(
                                "HTTP 200 but Instagram sent a LOGIN "
                                "PAGE. Your cookie is missing, expired, "
                                "or formatted wrong. It must be exactly: "
                                "sessionid=THE_VALUE"
                            )
                        else:
                            st.warning(
                                "HTTP 200 but no page data recognized. "
                                "Instagram may have changed its layout."
                            )
                    elif _r.status_code == 429:
                        st.error(
                            "Still 429 — this IP is blocked. The cookie "
                            "must be set (see above) or use a proxy."
                        )
                    elif _r.status_code == 403:
                        st.error(
                            "403 Forbidden — Instagram rejected the "
                            "request headers/cookie. Check cookie format."
                        )
                except Exception as e:
                    st.error(f"Test failed: {e}")


# ---------------------------------------------------------
# CLEAN INSTAGRAM URL / USERNAME
# ---------------------------------------------------------

def build_instagram_url(value):

    value = value.strip()

    if not value:
        return None

    # Full URL
    if "instagram.com" in value:

        value = value.split("?")[0].rstrip("/")

        if not value.startswith("http"):
            value = "https://" + value

        return value + "/"

    # Username
    value = value.lstrip("@").strip("/")

    return f"https://www.instagram.com/{value}/"


def extract_username(value):

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
# USER-AGENT POOL (randomly selected, not a single hardcoded one)
# ---------------------------------------------------------

USER_AGENTS = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) "
    "Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "Edg/126.0.0.0",
    # Mobile Chrome / Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    # Mobile Safari / iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
    "Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
    "Mobile/15E148 Safari/604.1",
]


def build_headers(rotate_per_request):

    if rotate_per_request:
        ua = random.choice(USER_AGENTS)
    else:
        # One UA per extraction run, chosen at random
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
    }

    return headers


# ---------------------------------------------------------
# SCRAPE INSTAGRAM PROFILE PAGE (NO API KEY)
# ---------------------------------------------------------

def fetch_profile_html(profile_url, proxy, cookie,
                       rotate_per_request, max_retries):

    proxies = None

    if proxy.strip():
        proxies = {
            "http": proxy.strip(),
            "https": proxy.strip(),
        }

    last_error = None

    for attempt in range(1, max_retries + 1):

        headers = build_headers(rotate_per_request)

        if cookie.strip():
            headers["Cookie"] = cookie.strip()

        try:

            response = requests.get(
                profile_url,
                headers=headers,
                proxies=proxies,
                timeout=30
            )

            if response.status_code == 200:
                return response.text

            last_error = (
                f"Instagram returned HTTP {response.status_code} "
                f"(attempt {attempt}/{max_retries})"
            )

            # 404 will never succeed — don't retry it
            if response.status_code == 404:
                raise Exception("Profile not found (404). Check the username.")

            # 429 / 403 — wait with backoff and try again
            wait_seconds = attempt * random.uniform(2, 5)
            time.sleep(wait_seconds)

        except requests.RequestException as e:
            last_error = f"Network error (attempt {attempt}): {e}"
            time.sleep(attempt * random.uniform(2, 5))

    raise Exception(
        f"{last_error}. Instagram is rate-limiting this IP. "
        f"Options: wait a few minutes, use a proxy, or paste a "
        f"session cookie in Network options."
    )


def _decode_json_object(text, start_index):
    """Decode the first balanced JSON object starting at or after
    start_index. Returns (obj, end_index) or (None, -1)."""

    decoder = json.JSONDecoder()

    while True:

        brace = text.find("{", start_index)

        if brace == -1:
            return None, -1

        try:
            obj, end = decoder.raw_decode(text[brace:])
            return obj, brace + end
        except json.JSONDecodeError:
            start_index = brace + 1


def extract_profile_json(html):
    """Pull the embedded ProfilePage JSON out of Instagram's HTML."""

    # ---- Method 1: window._sharedData (older layout) ----
    match = re.search(
        r"window\._sharedData\s*=\s*(\{.*?\});",
        html,
        re.DOTALL
    )

    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # ---- Method 2: JSON blobs inside script tags ----
    for script in re.findall(
        r"<script[^>]*>(.*?)</script>",
        html,
        re.DOTALL
    ):

        if '"ProfilePage"' not in script:
            continue

        # window.__additionalDataLoaded('/user/', { ... })
        m = re.search(
            r"__additionalDataLoaded\([^,]+,",
            script
        )
        if m:
            obj, _ = _decode_json_object(script, m.end())
            if obj:
                return obj

        # Plain JSON script
        obj, _ = _decode_json_object(script, 0)
        if obj:
            return obj

    return None


def get_instagram_posts(profile_url, proxy, cookie,
                        rotate_per_request, max_retries):

    html = fetch_profile_html(
        profile_url,
        proxy,
        cookie,
        rotate_per_request,
        max_retries
    )

    page_json = extract_profile_json(html)

    if not page_json:
        raise Exception(
            "Could not read Instagram's page data. Instagram is likely "
            "serving a login wall to this IP (HTTP 429). Try: waiting "
            "a few minutes, using a proxy, or pasting a session cookie."
        )

    # Navigate to the user node (works for both _sharedData and
    # __additionalDataLoaded structures)
    try:
        profile_page = page_json["entry_data"]["ProfilePage"][0]
        user = profile_page["graphql"]["user"]
    except (KeyError, IndexError, TypeError):
        raise Exception(
            "Profile data not found on the page. The account may be "
            "private, suspended, or Instagram changed its layout."
        )

    if not user:
        raise Exception("The profile appears to be private or empty.")

    username = user.get("username") or extract_username(profile_url)

    media = (
        user.get("edge_owner_to_timeline_media") or {}
    )
    edges = media.get("edges") or []

    posts = []

    for edge in edges:

        node = edge.get("node") or {}

        posts.append({
            "shortcode": node.get("shortcode"),
            "timestamp": node.get("taken_at_timestamp"),
            "caption": _extract_caption(node),
            "likes": (
                (node.get("edge_media_preview_like") or {}).get("count")
            ),
            "comments": (
                (node.get("edge_media_to_comment") or {}).get("count")
            ),
            "is_video": node.get("is_video", False),
            "is_reel": node.get("__typename") == "XDTGraphVideo"
                and "/reel/" in (node.get("url") or ""),
            "username": username,
        })

    return posts, username


def _extract_caption(node):

    caption_data = node.get("edge_media_to_caption") or {}
    edges = caption_data.get("edges") or []

    if edges:
        return (edges[0].get("node") or {}).get("text") or ""

    return ""


# ---------------------------------------------------------
# MAIN BUTTON
# ---------------------------------------------------------

if st.button("🔍 Extract Instagram Posts", type="primary"):

    profile_url = build_instagram_url(username_input)

    if not profile_url:
        st.error("Please enter an Instagram username.")
        st.stop()

    st.info(f"Searching: {profile_url}")

    rotate_per_request = (ua_option == "Randomize every retry")

    with st.spinner("Collecting Instagram posts..."):

        try:
            posts, found_username = get_instagram_posts(
                profile_url,
                proxy_input,
                cookie_input,
                rotate_per_request,
                max_retries
            )

        except Exception as e:
            st.error("Unable to retrieve Instagram data.")
            st.code(str(e))
            _ck, _ck_src = get_saved_cookie()
            if not _ck and not cookie_input.strip():
                st.warning(
                    "No session cookie was loaded. If you saved it to "
                    "Secrets or ig_session.txt, check the format — it "
                    "must look like: sessionid=YOUR_VALUE and on "
                    "Streamlit Cloud it must be set in the app's "
                    "Settings → Secrets page, not a local file."
                )
            elif not _ck and cookie_input.strip():
                st.caption("Cookie was taken from the text field.")
            st.stop()


    if not posts:
        st.warning(
            "No posts were found on the profile page. "
            "The account may be private."
        )
        st.stop()


    # -----------------------------------------------------
    # PROCESS POSTS
    # -----------------------------------------------------

    records = []

    for post in posts:

        raw_date = post.get("timestamp")

        if not raw_date:
            continue

        post_date = date.fromtimestamp(raw_date)

        # Date filtering
        if post_date < start_date or post_date > end_date:
            continue

        shortcode = post.get("shortcode") or ""

        if post.get("is_video") or post.get("is_reel"):
            post_url = f"https://www.instagram.com/reel/{shortcode}/"
            post_type = "Reel"
        else:
            post_url = f"https://www.instagram.com/p/{shortcode}/"
            post_type = "Post"

        records.append({
            "Date": post_date,
            "Type": post_type,
            "Username": post.get("username") or "",
            "Caption": post.get("caption") or "",
            "Likes": post.get("likes") or 0,
            "Comments": post.get("comments") or 0,
            "URL": post_url,
        })


    # -----------------------------------------------------
    # DATAFRAME
    # -----------------------------------------------------

    df = pd.DataFrame(records)

    if df.empty:
        st.warning(
            "Posts were retrieved, but none were within "
            "the selected date range."
        )
        st.stop()


    # Sort newest first
    df = df.sort_values(
        by="Date",
        ascending=False
    ).reset_index(drop=True)


    # -----------------------------------------------------
    # METRICS
    # -----------------------------------------------------

    total_posts = len(df)

    total_likes = pd.to_numeric(
        df["Likes"],
        errors="coerce"
    ).fillna(0).sum()

    total_comments = pd.to_numeric(
        df["Comments"],
        errors="coerce"
    ).fillna(0).sum()


    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Posts", total_posts)

    with c2:
        st.metric("Likes", f"{int(total_likes):,}")

    with c3:
        st.metric("Comments", f"{int(total_comments):,}")


    # -----------------------------------------------------
    # RESULTS
    # -----------------------------------------------------

    st.subheader("Instagram Posts")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn(
                "Post URL",
                display_text="Open Post"
            ),
            "Date": st.column_config.DateColumn("Date")
        }
    )


    # -----------------------------------------------------
    # EXCEL EXPORT
    # -----------------------------------------------------

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Instagram Posts"
        )

    output.seek(0)

    safe_name = (found_username or "profile").replace("@", "")

    st.download_button(
        label="📥 Download Excel",
        data=output,
        file_name=(
            f"instagram_{safe_name}_"
            f"{start_date}_{end_date}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
