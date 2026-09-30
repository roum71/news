import streamlit as st
import pandas as pd
import requests

from io import BytesIO
from datetime import date, timedelta, datetime


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Instagram News Extractor",
    page_icon="📸",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("📸 Instagram News Extractor")

st.write(
    "Extract public Instagram posts within a selected date range "
    "and export the results to Excel."
)


# ============================================================
# API CONFIG
# ============================================================

API_URL = "https://api.instagapi.com/api/user/posts"


# ============================================================
# GET API KEY FROM STREAMLIT SECRETS
# ============================================================

def get_api_key():

    try:

        if "instagram" not in st.secrets:

            return None

        api_key = st.secrets["instagram"]["api_key"]

        if not api_key:

            return None

        return api_key

    except Exception:

        return None


# ============================================================
# CLEAN USERNAME
# ============================================================

def clean_username(value):

    value = value.strip()

    # Remove @
    value = value.replace("@", "")

    # Handle Instagram URL
    if "instagram.com/" in value:

        value = value.split("instagram.com/")[1]

        value = value.split("?")[0]

        value = value.split("#")[0]

    # Remove trailing /
    value = value.strip("/")

    # Keep only username
    value = value.split("/")[0]

    return value


# ============================================================
# CONVERT INSTAGRAM DATE
# ============================================================

def parse_post_date(value):

    if not value:
        return None

    try:

        # Example:
        # 2026-07-18T15:42:07Z

        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return dt.date()

    except Exception:

        return None


# ============================================================
# CONVERT POST TYPE
# ============================================================

def get_post_type(media_type):

    if media_type == 1:

        return "Photo"

    elif media_type == 2:

        return "Video"

    elif media_type == 8:

        return "Carousel"

    return "Unknown"


# ============================================================
# CREATE EXCEL
# ============================================================

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

        worksheet = writer.sheets["Instagram Posts"]

        worksheet.column_dimensions["A"].width = 25
        worksheet.column_dimensions["B"].width = 15
        worksheet.column_dimensions["C"].width = 18
        worksheet.column_dimensions["D"].width = 80
        worksheet.column_dimensions["E"].width = 12
        worksheet.column_dimensions["F"].width = 12
        worksheet.column_dimensions["G"].width = 60

    return output.getvalue()


# ============================================================
# API REQUEST
# ============================================================

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

    # --------------------------------------------------------
    # Maximum pages is deliberately limited.
    #
    # Free InstaGapi plan has limited monthly requests.
    # --------------------------------------------------------

    while page_number < max_pages:

        page_number += 1

        params = {
            "username_or_id": username
        }

        if pagination_token:

            params["pagination_token"] = pagination_token


        # ----------------------------------------------------
        # API REQUEST
        # ----------------------------------------------------

        response = requests.get(
            API_URL,
            headers=headers,
            params=params,
            timeout=30
        )


        # ----------------------------------------------------
        # HTTP ERROR
        # ----------------------------------------------------

        if response.status_code != 200:

            try:

                error_data = response.json()

            except Exception:

                error_data = response.text


            raise Exception(
                f"API Error {response.status_code}: "
                f"{error_data}"
            )


        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        data = response.json()


        # ----------------------------------------------------
        # DATA OBJECT
        # ----------------------------------------------------

        result = data.get("data", {})

        items = result.get("items", [])


        # ----------------------------------------------------
        # No more posts
        # ----------------------------------------------------

        if not items:

            break


        # ----------------------------------------------------
        # PROCESS POSTS
        # ----------------------------------------------------

        oldest_date_in_page = None


        for item in items:

            post_date = parse_post_date(
                item.get("taken_at")
            )


            if not post_date:

                continue


            # Track oldest post in current page

            if (
                oldest_date_in_page is None
                or post_date < oldest_date_in_page
            ):

                oldest_date_in_page = post_date


            # ------------------------------------------------
            # Skip posts newer than end date
            # ------------------------------------------------

            if post_date > end_date:

                continue


            # ------------------------------------------------
            # Stop collecting older posts
            # ------------------------------------------------

            if post_date < start_date:

                continue


            # ------------------------------------------------
            # TYPE
            # ------------------------------------------------

            post_type = get_post_type(
                item.get("media_type")
            )


            # ------------------------------------------------
            # CAPTION
            # ------------------------------------------------

            caption = (
                item.get("caption_text")
                or ""
            )


            # ------------------------------------------------
            # LIKES
            # ------------------------------------------------

            likes = (
                item.get("like_count")
                or 0
            )


            # ------------------------------------------------
            # COMMENTS
            # ------------------------------------------------

            comments = (
                item.get("comment_count")
                or 0
            )


            # ------------------------------------------------
            # SHORTCODE
            # ------------------------------------------------

            shortcode = (
                item.get("code")
                or ""
            )


            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            if shortcode:

                url = (
                    "https://www.instagram.com/p/"
                    + shortcode
                    + "/"
                )

            else:

                url = ""


            # ------------------------------------------------
            # ADD POST
            # ------------------------------------------------

            posts.append(
                {
                    "Account": username,
                    "Date": post_date,
                    "Type": post_type,
                    "Caption": caption,
                    "Likes": likes,
                    "Comments": comments,
                    "URL": url,
                }
            )


        # ----------------------------------------------------
        # Pagination
        # ----------------------------------------------------

        pagination_token = (
            result.get("pagination_token")
        )


        # ----------------------------------------------------
        # If there is no next page, stop
        # ----------------------------------------------------

        if not pagination_token:

            break


        # ----------------------------------------------------
        # If the oldest post is already before start date,
        # we have enough history.
        # ----------------------------------------------------

        if (
            oldest_date_in_page is not None
            and oldest_date_in_page < start_date
        ):

            break


    return posts


# ============================================================
# API KEY STATUS
# ============================================================

api_key = get_api_key()


if api_key:

    st.success(
        "🟢 InstaGapi API is configured."
    )

else:

    st.error(
        "🔴 InstaGapi API key is not configured."
    )

    st.info(
        "Go to Streamlit Cloud → Settings → Secrets "
        "and add your API key."
    )


# ============================================================
# INPUT
# ============================================================

username_input = st.text_input(
    "Instagram Username or URL",
    placeholder=(
        "rakmediaoffice or "
        "https://www.instagram.com/rakmediaoffice/"
    )
)


# ============================================================
# DATES
# ============================================================

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


# ============================================================
# EXTRACT
# ============================================================

if st.button(
    "🔎 Extract Posts",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # API KEY
    # --------------------------------------------------------

    if not api_key:

        st.error(
            "InstaGapi API key is missing."
        )

        st.stop()


    # --------------------------------------------------------
    # USERNAME
    # --------------------------------------------------------

    if not username_input:

        st.error(
            "Please enter an Instagram username or URL."
        )

        st.stop()


    # --------------------------------------------------------
    # DATES
    # --------------------------------------------------------

    if start_date > end_date:

        st.error(
            "Start Date cannot be later than End Date."
        )

        st.stop()


    # --------------------------------------------------------
    # CLEAN USERNAME
    # --------------------------------------------------------

    username = clean_username(
        username_input
    )


    if not username:

        st.error(
            "Invalid Instagram username."
        )

        st.stop()


    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    st.info(
        f"Searching public Instagram posts for @{username}"
    )


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


        # ====================================================
        # DATAFRAME
        # ====================================================

        df = pd.DataFrame(posts)


        # ----------------------------------------------------
        # NO RESULTS
        # ----------------------------------------------------

        if df.empty:

            st.warning(
                "No public posts were found "
                "within the selected date range."
            )

            st.stop()


        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        df = df.sort_values(
            by="Date",
            ascending=False
        ).reset_index(drop=True)


        # ====================================================
        # RESULTS
        # ====================================================

        st.success(
            f"Found {len(df)} posts."
        )


        # ====================================================
        # SUMMARY
        # ====================================================

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


        # ====================================================
        # TABLE
        # ====================================================

        st.subheader(
            "Instagram Posts"
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # ====================================================
        # EXCEL
        # ====================================================

        excel_data = create_excel(df)


        filename = (
            f"{username}_instagram_news_"
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


    # ========================================================
    # API ERRORS
    # ========================================================

    except Exception as e:

        error_text = str(e)


        # ----------------------------------------------------
        # 401 / 403
        # ----------------------------------------------------

        if (
            "401" in error_text
            or "403" in error_text
        ):

            st.error(
                "The InstaGapi API key was rejected."
            )

            st.info(
                "Check that the API key in Streamlit "
                "Secrets is correct and active."
            )


        # ----------------------------------------------------
        # 404
        # ----------------------------------------------------

        elif "404" in error_text:

            st.error(
                f"Instagram account @{username} "
                "could not be found."
            )


        # ----------------------------------------------------
        # 429
        # ----------------------------------------------------

        elif "429" in error_text:

            st.error(
                "The InstaGapi request limit has been reached."
            )

            st.warning(
                "The free InstaGapi plan has a limited "
                "number of requests per month."
            )


        # ----------------------------------------------------
        # OTHER
        # ----------------------------------------------------

        else:

            st.error(
                "Could not retrieve Instagram data."
            )

            st.code(
                error_text
            )
