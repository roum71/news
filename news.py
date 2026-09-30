import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import date, timedelta, datetime


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Instagram News Extractor",
    page_icon="📸",
    layout="wide"
)

st.title("📸 Instagram News Extractor")

st.write(
    "Extract public Instagram posts within a selected date range "
    "and export them to Excel."
)


# =========================================================
# INSTAGAPI ENDPOINTS
# =========================================================

PROFILE_URL = "https://api.instagapi.com/api/user/info"
POSTS_URL = "https://api.instagapi.com/api/user/posts"


# =========================================================
# GET API KEY FROM STREAMLIT SECRETS
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

    st.success("🟢 InstaGapi API key loaded successfully.")

    st.caption(
        f"Key detected: {api_key[:8]}..."
    )

else:

    st.error(
        "🔴 InstaGapi API key was not found."
    )

    st.info(
        """
Go to:

Streamlit Cloud → Settings → Secrets

Use exactly:

[instagram]
api_key = "sk_live_xxxxxxxxx"
"""
    )


# =========================================================
# CLEAN USERNAME
# =========================================================

def clean_username(value):

    if not value:
        return ""

    value = value.strip()

    value = value.replace("@", "")

    if "instagram.com/" in value:

        value = value.split(
            "instagram.com/"
        )[1]

        value = value.split("?")[0]

        value = value.split("#")[0]

    value = value.strip("/")

    value = value.split("/")[0]

    return value


# =========================================================
# GET PROFILE
# =========================================================

def get_profile(username, api_key):

    headers = {
        "X-Api-Key": api_key
    }

    response = requests.get(
        PROFILE_URL,
        headers=headers,
        params={
            "username_or_id": username
        },
        timeout=30
    )

    return response


# =========================================================
# GET POSTS
# =========================================================

def get_posts(
    user_id,
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
            "username_or_id": str(user_id)
        }

        if pagination_token:

            params["pagination_token"] = (
                pagination_token
            )

        response = requests.get(
            POSTS_URL,
            headers=headers,
            params=params,
            timeout=30
        )

        # -------------------------------------------------
        # CHECK RESPONSE
        # -------------------------------------------------

        if response.status_code != 200:

            try:

                error_data = response.json()

            except Exception:

                error_data = response.text

            raise Exception(
                f"HTTP Status: {response.status_code}\n\n"
                f"InstaGapi response:\n"
                f"{error_data}"
            )

        # -------------------------------------------------
        # READ JSON
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
        # PROCESS POSTS
        # -------------------------------------------------

        for item in items:

            post_date = parse_post_date(
                item.get("taken_at")
            )

            if not post_date:

                continue

            # Track oldest post
            if (
                oldest_date_in_page is None
                or post_date < oldest_date_in_page
            ):

                oldest_date_in_page = post_date

            # Outside selected range
            if post_date > end_date:

                continue

            if post_date < start_date:

                continue

            # -------------------------------------------------
            # POST INFORMATION
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

                post_url = (
                    "https://www.instagram.com/p/"
                    + shortcode
                    + "/"
                )

            else:

                post_url = ""

            posts.append(
                {
                    "Date": post_date,
                    "Type": post_type,
                    "Caption": caption,
                    "Likes": likes,
                    "Comments": comments,
                    "URL": post_url
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

        # Stop when posts are older than
        # selected period

        if (
            oldest_date_in_page is not None
            and oldest_date_in_page < start_date
        ):

            break

    return posts


# =========================================================
# PARSE DATE
# =========================================================

def parse_post_date(value):

    if not value:
        return None

    # Try ISO date
    try:

        dt = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

        return dt.date()

    except Exception:

        pass

    # Try Unix timestamp
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
# CREATE EXCEL
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
        ].width = 15

        worksheet.column_dimensions[
            "B"
        ].width = 18

        worksheet.column_dimensions[
            "C"
        ].width = 80

        worksheet.column_dimensions[
            "D"
        ].width = 12

        worksheet.column_dimensions[
            "E"
        ].width = 12

        worksheet.column_dimensions[
            "F"
        ].width = 60

    return output.getvalue()


# =========================================================
# DIAGNOSTIC TEST
# =========================================================

st.divider()

st.subheader("🔧 API Diagnostic")

test_username = st.text_input(
    "Instagram Account",
    value="rakmediaoffice",
    key="test_username"
)

if st.button(
    "🧪 Test Profile + Posts API",
    use_container_width=True
):

    if not api_key:

        st.error(
            "API key is missing."
        )

        st.stop()

    username = clean_username(
        test_username
    )

    if not username:

        st.error(
            "Please enter an Instagram username."
        )

        st.stop()

    # -----------------------------------------------------
    # PROFILE
    # -----------------------------------------------------

    st.write("### 1️⃣ Profile API")

    try:

        profile_response = get_profile(
            username,
            api_key
        )

        st.write(
            "Profile HTTP Status:",
            profile_response.status_code
        )

        if profile_response.status_code != 200:

            st.error(
                "Profile API failed."
            )

            st.code(
                profile_response.text
            )

            st.stop()

        profile_json = (
            profile_response.json()
        )

        profile_data = profile_json.get(
            "data",
            {}
        )

        # -------------------------------------------------
        # FIND USERNAME
        # -------------------------------------------------

        returned_username = (
            profile_data.get(
                "username"
            )
            or username
        )

        # -------------------------------------------------
        # FIND USER ID
        # -------------------------------------------------

        user_id = (
            profile_data.get("pk")
            or profile_data.get("id")
        )

        st.success(
            "✅ Profile API works."
        )

        st.write(
            "Username:",
            returned_username
        )

        st.write(
            "User ID:",
            user_id
        )

        if not user_id:

            st.error(
                "Profile API did not return a User ID."
            )

            st.json(
                profile_json
            )

            st.stop()

        # -----------------------------------------------------
        # POSTS
        # -----------------------------------------------------

        st.write("### 2️⃣ Posts API")

        st.write(
            "Testing Posts API using User ID:"
        )

        st.code(
            str(user_id)
        )

        headers = {
            "X-Api-Key": api_key
        }

        posts_response = requests.get(
            POSTS_URL,
            headers=headers,
            params={
                "username_or_id": str(user_id)
            },
            timeout=30
        )

        st.write(
            "Posts HTTP Status:",
            posts_response.status_code
        )

        # -------------------------------------------------
        # POSTS SUCCESS
        # -------------------------------------------------

        if posts_response.status_code == 200:

            st.success(
                "✅ Posts API works using User ID."
            )

            try:

                posts_json = (
                    posts_response.json()
                )

                result = posts_json.get(
                    "data",
                    {}
                )

                items = result.get(
                    "items",
                    []
                )

                st.write(
                    f"Posts returned: {len(items)}"
                )

                # Show only first item for diagnosis
                if items:

                    st.write(
                        "First post returned:"
                    )

                    st.json(
                        items[0]
                    )

                else:

                    st.warning(
                        "API worked, but returned no posts."
                    )

            except Exception:

                st.code(
                    posts_response.text
                )

        # -------------------------------------------------
        # POSTS ERROR
        # -------------------------------------------------

        else:

            st.error(
                "❌ Posts API rejected the request."
            )

            st.write(
                "### Actual InstaGapi response:"
            )

            # This is the important part
            st.code(
                posts_response.text
            )

    except Exception as e:

        st.error(
            "Diagnostic request failed."
        )

        st.code(
            str(e)
        )


# =========================================================
# MAIN EXTRACTION
# =========================================================

st.divider()

st.subheader("📊 Extract Posts")

username_input = st.text_input(
    "Instagram Username or URL",
    value="rakmediaoffice",
    placeholder="rakmediaoffice",
    key="main_username"
)


# =========================================================
# DATE RANGE
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
# EXTRACT BUTTON
# =========================================================

if st.button(
    "🔎 Extract Instagram Posts",
    type="primary",
    use_container_width=True
):

    if not api_key:

        st.error(
            "API key is missing."
        )

        st.stop()

    username = clean_username(
        username_input
    )

    if not username:

        st.error(
            "Please enter an Instagram username."
        )

        st.stop()

    if start_date > end_date:

        st.error(
            "Start Date cannot be later than End Date."
        )

        st.stop()

    # -----------------------------------------------------
    # GET PROFILE FIRST
    # -----------------------------------------------------

    with st.spinner(
        f"Getting Instagram profile @{username}..."
    ):

        profile_response = get_profile(
            username,
            api_key
        )

    if profile_response.status_code != 200:

        st.error(
            "Could not retrieve the Instagram profile."
        )

        st.code(
            profile_response.text
        )

        st.stop()

    profile_json = (
        profile_response.json()
    )

    profile_data = profile_json.get(
        "data",
        {}
    )

    # -----------------------------------------------------
    # USER ID
    # -----------------------------------------------------

    user_id = (
        profile_data.get("pk")
        or profile_data.get("id")
    )

    returned_username = (
        profile_data.get("username")
        or username
    )

    if not user_id:

        st.error(
            "Instagram User ID was not returned."
        )

        st.json(
            profile_json
        )

        st.stop()

    st.info(
        f"Found Instagram account: "
        f"@{returned_username}"
    )

    # -----------------------------------------------------
    # GET POSTS
    # -----------------------------------------------------

    try:

        with st.spinner(
            f"Getting posts from @{returned_username}..."
        ):

            posts = get_posts(
                user_id=user_id,
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
                "No posts were found within "
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
        # METRICS
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
            f"{returned_username}_instagram_news_"
            f"{start_date}_{end_date}.xlsx"
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

    # -----------------------------------------------------
    # ERROR
    # -----------------------------------------------------

    except Exception as e:

        st.error(
            "❌ Could not retrieve Instagram posts."
        )

        st.write(
            "### Detailed API error"
        )

        st.code(
            str(e)
        )
