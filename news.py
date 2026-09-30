import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import date, timedelta, datetime


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Instagram News Extractor",
    page_icon="📸",
    layout="wide"
)

st.title("📸 Instagram News Extractor")

st.write(
    "Extract public Instagram posts within a selected date range "
    "and export the results to Excel."
)


# =========================================================
# API SETTINGS
# =========================================================

PROFILE_URL = "https://api.instagapi.com/api/user/info"
POSTS_URL = "https://api.instagapi.com/api/user/posts"


# =========================================================
# GET API KEY
# =========================================================

def get_api_key():

    try:

        if "instagram" not in st.secrets:
            return None

        api_key = st.secrets["instagram"]["api_key"]

        if not api_key:
            return None

        return str(api_key).strip()

    except Exception:

        return None


api_key = get_api_key()


# =========================================================
# API KEY STATUS
# =========================================================

if api_key:

    st.success("🟢 InstaGapi API key loaded.")

    st.caption(
        f"Detected key: {api_key[:8]}..."
    )

else:

    st.error(
        "🔴 InstaGapi API key was not found."
    )

    st.info(
        """
Use this exact format in Streamlit Cloud → Settings → Secrets:

[instagram]
api_key = "sk_live_xxxxxxxxx"
"""
    )


# =========================================================
# TEST PROFILE API
# =========================================================

st.divider()

st.subheader("🔧 API Diagnostics")

if st.button(
    "🧪 1. Test Profile API",
    use_container_width=True
):

    if not api_key:

        st.error(
            "API key is not being read from Streamlit Secrets."
        )

        st.stop()

    headers = {
        "X-Api-Key": api_key
    }

    try:

        with st.spinner("Testing Profile API..."):

            response = requests.get(
                PROFILE_URL,
                headers=headers,
                params={
                    "username_or_id": "rakmediaoffice"
                },
                timeout=30
            )

        st.write(
            "**Profile API HTTP Status:**",
            response.status_code
        )

        if response.status_code == 200:

            st.success(
                "✅ Profile API works. The API key is valid."
            )

            try:

                profile_data = response.json()

                # Show response for diagnosis
                st.json(profile_data)

            except Exception:

                st.code(response.text)

        else:

            st.error(
                "❌ Profile API request failed."
            )

            try:

                st.json(response.json())

            except Exception:

                st.code(response.text)

    except Exception as e:

        st.error(
            "Could not connect to InstaGapi."
        )

        st.code(str(e))


# =========================================================
# TEST POSTS API
# =========================================================

if st.button(
    "🧪 2. Test Instagram Posts API",
    use_container_width=True
):

    if not api_key:

        st.error(
            "API key is not being read from Streamlit Secrets."
        )

        st.stop()

    headers = {
        "X-Api-Key": api_key
    }

    try:

        with st.spinner("Testing Instagram Posts API..."):

            response = requests.get(
                POSTS_URL,
                headers=headers,
                params={
                    "username_or_id": "rakmediaoffice"
                },
                timeout=30
            )

        st.write(
            "**Posts API HTTP Status:**",
            response.status_code
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        if response.status_code == 200:

            st.success(
                "✅ Posts API works."
            )

            try:

                posts_test = response.json()

                st.json(posts_test)

            except Exception:

                st.code(response.text)

        # -------------------------------------------------
        # AUTH ERROR
        # -------------------------------------------------

        elif response.status_code in [401, 403]:

            st.error(
                "❌ Posts API rejected the request."
            )

            st.warning(
                """
The Profile API already returned HTTP 200, so your API key
is being accepted by InstaGapi.

This error is specifically coming from the Posts API.
"""
            )

            try:

                error_data = response.json()

                st.json(error_data)

            except Exception:

                st.code(response.text)

        # -------------------------------------------------
        # RATE LIMIT
        # -------------------------------------------------

        elif response.status_code == 429:

            st.warning(
                "⚠️ InstaGapi rate limit reached."
            )

            try:

                st.json(response.json())

            except Exception:

                st.code(response.text)

        # -------------------------------------------------
        # OTHER
        # -------------------------------------------------

        else:

            st.error(
                f"Unexpected Posts API response: "
                f"{response.status_code}"
            )

            try:

                st.json(response.json())

            except Exception:

                st.code(response.text)

    except Exception as e:

        st.error(
            "Could not connect to the Posts API."
        )

        st.code(str(e))


# =========================================================
# CLEAN USERNAME
# =========================================================

def clean_username(value):

    if not value:
        return ""

    value = value.strip()

    value = value.replace("@", "")

    if "instagram.com/" in value:

        value = value.split("instagram.com/")[1]

        value = value.split("?")[0]

        value = value.split("#")[0]

    value = value.strip("/")

    value = value.split("/")[0]

    return value


# =========================================================
# PARSE DATE
# =========================================================

def parse_post_date(value):

    if not value:
        return None

    try:

        # ISO format
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        return dt.date()

    except Exception:

        pass

    # Sometimes APIs may return Unix timestamp
    try:

        timestamp = int(value)

        return datetime.fromtimestamp(
            timestamp
        ).date()

    except Exception:

        return None


# =========================================================
# POST TYPE
# =========================================================

def get_post_type(media_type):

    if media_type == 1:
        return "Photo"

    if media_type == 2:
        return "Video"

    if media_type == 8:
        return "Carousel"

    return "Unknown"


# =========================================================
# GET POSTS
# =========================================================

def get_posts(
    username,
    start_date,
    end_date,
    api_key
):

    headers = {
        "X-Api-Key": api_key
    }

    posts = []

    pagination_token = None

    page_number = 0

    max_pages = 20

    while page_number < max_pages:

        page_number += 1

        params = {
            "username_or_id": username
        }

        if pagination_token:

            params["pagination_token"] = pagination_token

        response = requests.get(
            POSTS_URL,
            headers=headers,
            params=params,
            timeout=30
        )

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            try:

                error_data = response.json()

            except Exception:

                error_data = response.text

            raise Exception(
                f"HTTP {response.status_code}\n"
                f"{error_data}"
            )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        data = response.json()

        result = data.get(
            "data",
            {}
        )

        items = result.get(
            "items",
            []
        )

        if not items:

            break

        oldest_date_in_page = None

        # -------------------------------------------------
        # POSTS
        # -------------------------------------------------

        for item in items:

            post_date = parse_post_date(
                item.get("taken_at")
            )

            if not post_date:

                continue

            if (
                oldest_date_in_page is None
                or post_date < oldest_date_in_page
            ):

                oldest_date_in_page = post_date

            # Outside date range

            if post_date > end_date:

                continue

            if post_date < start_date:

                continue

            # -------------------------------------------------
            # DATA
            # -------------------------------------------------

            media_type = item.get(
                "media_type"
            )

            post_type = get_post_type(
                media_type
            )

            caption = (
                item.get("caption_text")
                or ""
            )

            likes = (
                item.get("like_count")
                or 0
            )

            comments = (
                item.get("comment_count")
                or 0
            )

            shortcode = (
                item.get("code")
                or ""
            )

            if shortcode:

                url = (
                    "https://www.instagram.com/p/"
                    + shortcode
                    + "/"
                )

            else:

                url = ""

            posts.append(
                {
                    "Account": username,
                    "Date": post_date,
                    "Type": post_type,
                    "Caption": caption,
                    "Likes": likes,
                    "Comments": comments,
                    "URL": url
                }
            )

        # -------------------------------------------------
        # PAGINATION
        # -------------------------------------------------

        pagination_token = result.get(
            "pagination_token"
        )

        if not pagination_token:

            break

        # Stop when posts become older
        # than requested period

        if (
            oldest_date_in_page is not None
            and oldest_date_in_page < start_date
        ):

            break

    return posts


# =========================================================
# EXCEL
# =========================================================

def create_excel(df):

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

        worksheet = writer.sheets[
            "Instagram Posts"
        ]

        worksheet.column_dimensions[
            "A"
        ].width = 25

        worksheet.column_dimensions[
            "B"
        ].width = 15

        worksheet.column_dimensions[
            "C"
        ].width = 18

        worksheet.column_dimensions[
            "D"
        ].width = 80

        worksheet.column_dimensions[
            "E"
        ].width = 12

        worksheet.column_dimensions[
            "F"
        ].width = 12

        worksheet.column_dimensions[
            "G"
        ].width = 60

    return output.getvalue()


# =========================================================
# EXTRACTION SECTION
# =========================================================

st.divider()

st.subheader("📸 Extract Instagram Posts")

username_input = st.text_input(
    "Instagram Username or URL",
    value="rakmediaoffice",
    placeholder="rakmediaoffice"
)


# =========================================================
# DATES
# =========================================================

today = date.today()

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "Start Date",
        value=today - timedelta(days=30)
    )

with col2:

    end_date = st.date_input(
        "End Date",
        value=today
    )


# =========================================================
# EXTRACT
# =========================================================

if st.button(
    "🔎 Extract Instagram Posts",
    type="primary",
    use_container_width=True
):

    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not api_key:

        st.error(
            "API key is missing."
        )

        st.stop()

    # -------------------------------------------------
    # USERNAME
    # -------------------------------------------------

    username = clean_username(
        username_input
    )

    if not username:

        st.error(
            "Please enter an Instagram username."
        )

        st.stop()

    # -------------------------------------------------
    # DATES
    # -------------------------------------------------

    if start_date > end_date:

        st.error(
            "Start Date cannot be later than End Date."
        )

        st.stop()

    st.info(
        f"Searching public Instagram posts for "
        f"@{username}"
    )

    # -------------------------------------------------
    # GET POSTS
    # -------------------------------------------------

    try:

        with st.spinner(
            f"Getting posts from @{username}..."
        ):

            posts = get_posts(
                username=username,
                start_date=start_date,
                end_date=end_date,
                api_key=api_key
            )

        # -------------------------------------------------
        # DATAFRAME
        # -------------------------------------------------

        df = pd.DataFrame(
            posts
        )

        if df.empty:

            st.warning(
                "No public posts were found within "
                "the selected date range."
            )

            st.stop()

        # -------------------------------------------------
        # SORT
        # -------------------------------------------------

        df = df.sort_values(
            by="Date",
            ascending=False
        ).reset_index(
            drop=True
        )

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        st.success(
            f"✅ Found {len(df)} posts."
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Posts",
                len(df)
            )

        with c2:

            st.metric(
                "Likes",
                int(
                    df["Likes"]
                    .fillna(0)
                    .sum()
                )
            )

        with c3:

            st.metric(
                "Comments",
                int(
                    df["Comments"]
                    .fillna(0)
                    .sum()
                )
            )

        # -------------------------------------------------
        # TABLE
        # -------------------------------------------------

        st.subheader(
            "Instagram Posts"
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # EXCEL
        # -------------------------------------------------

        excel_data = create_excel(
            df
        )

        filename = (
            f"{username}_instagram_news_"
            f"{start_date}_"
            f"{end_date}.xlsx"
        )

        st.download_button(
            label="⬇️ Download Excel",
            data=excel_data,
            file_name=filename,
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )

    # =====================================================
    # ERROR HANDLING
    # =====================================================

    except Exception as e:

        st.error(
            "❌ Could not retrieve Instagram posts."
        )

        st.warning(
            "Detailed API response:"
        )

        st.code(
            str(e)
        )
