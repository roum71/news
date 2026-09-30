import streamlit as st
import pandas as pd
import requests
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
    "Extract public Instagram posts from an Instagram profile "
    "and filter them by publication date."
)


# ---------------------------------------------------------
# GET BRIGHT DATA TOKEN
# ---------------------------------------------------------

try:
    API_TOKEN = st.secrets["brightdata"]["api_token"]
except Exception:
    st.error(
        "Bright Data API token is missing. "
        "Please add [brightdata] api_token in Streamlit Secrets."
    )
    st.stop()


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
# CLEAN INSTAGRAM URL
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


# ---------------------------------------------------------
# CALL BRIGHT DATA
# ---------------------------------------------------------

def get_instagram_posts(profile_url):

    endpoint = (
        "https://api.brightdata.com/datasets/v3/trigger"
        "?dataset_id=gd_lk5ns7kz21pck8jpis"
        "&format=json"
        "&uncompressed_webhook=true"
    )

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = [
        {
            "url": profile_url
        }
    ]

    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=180
    )

    if response.status_code != 200:
        raise Exception(
            f"Bright Data returned HTTP {response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ---------------------------------------------------------
# NORMALIZE RESPONSE
# ---------------------------------------------------------

def normalize_posts(data):

    # Bright Data may return a list directly
    if isinstance(data, list):
        return data

    # Some responses may contain data/results
    if isinstance(data, dict):

        for key in ["data", "results", "items", "records"]:

            if key in data and isinstance(data[key], list):
                return data[key]

        # Single record
        if "url" in data:
            return [data]

    return []


# ---------------------------------------------------------
# EXTRACT FIELD SAFELY
# ---------------------------------------------------------

def get_value(item, *keys):

    for key in keys:

        value = item.get(key)

        if value is not None:
            return value

    return None


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

            raw_data = get_instagram_posts(profile_url)

            posts = normalize_posts(raw_data)

        except Exception as e:

            st.error("Unable to retrieve Instagram data.")
            st.code(str(e))
            st.stop()


    if not posts:

        st.warning(
            "No posts were returned by Bright Data."
        )
        st.stop()


    # -----------------------------------------------------
    # PROCESS POSTS
    # -----------------------------------------------------

    records = []

    for post in posts:

        # Date
        raw_date = get_value(
            post,
            "date_posted",
            "timestamp",
            "date",
            "taken_at"
        )

        parsed_date = pd.to_datetime(
            raw_date,
            errors="coerce",
            utc=True
        )

        if pd.isna(parsed_date):
            continue

        post_date = parsed_date.date()

        # Date filtering
        if post_date < start_date or post_date > end_date:
            continue


        # URL
        post_url = get_value(
            post,
            "url",
            "post_url"
        )


        # Caption
        caption = get_value(
            post,
            "description",
            "caption",
            "caption_text"
        )

        if caption is None:
            caption = ""


        # Likes
        likes = get_value(
            post,
            "likes",
            "num_likes",
            "like_count"
        )

        if likes is None:
            likes = 0


        # Comments
        comments = get_value(
            post,
            "num_comments",
            "comments",
            "comment_count"
        )

        if comments is None:
            comments = 0


        # Username
        user_posted = get_value(
            post,
            "user_posted",
            "username",
            "account"
        )

        # Type
        post_type = "Post"

        if post_url and "/reel/" in str(post_url):
            post_type = "Reel"


        records.append({
            "Date": post_date,
            "Type": post_type,
            "Username": user_posted or "",
            "Caption": caption,
            "Likes": likes,
            "Comments": comments,
            "URL": post_url or ""
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
        st.metric(
            "Posts",
            total_posts
        )

    with c2:
        st.metric(
            "Likes",
            f"{int(total_likes):,}"
        )

    with c3:
        st.metric(
            "Comments",
            f"{int(total_comments):,}"
        )


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
            "Date": st.column_config.DateColumn(
                "Date"
            )
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


    st.download_button(
        label="📥 Download Excel",
        data=output,
        file_name=(
            f"instagram_{username_input.replace('@', '')}_"
            f"{start_date}_{end_date}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
