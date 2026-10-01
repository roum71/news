import streamlit as st
import pandas as pd
import requests
import json
import re
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
# SCRAPE INSTAGRAM PROFILE PAGE (NO API KEY)
# ---------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
}


def fetch_profile_html(profile_url):

    response = requests.get(
        profile_url,
        headers=HEADERS,
        timeout=30
    )

    if response.status_code == 404:
        raise Exception("Profile not found (404). Check the username.")

    if response.status_code != 200:
        raise Exception(
            f"Instagram returned HTTP {response.status_code}."
        )

    return response.text


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


def get_instagram_posts(profile_url):

    html = fetch_profile_html(profile_url)

    page_json = extract_profile_json(html)

    if not page_json:
        raise Exception(
            "Could not read Instagram's page data. Instagram may be "
            "serving a login wall to this server. Try again later or "
            "from a different network."
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

    with st.spinner("Collecting Instagram posts..."):

        try:
            posts, found_username = get_instagram_posts(profile_url)

        except Exception as e:
            st.error("Unable to retrieve Instagram data.")
            st.code(str(e))
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
