import streamlit as st
import pandas as pd
import instaloader

from io import BytesIO
from datetime import date, timedelta

from instaloader.exceptions import (
    ProfileNotExistsException,
    TooManyRequestsException,
    ConnectionException,
    LoginRequiredException,
)


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
# CREATE INSTALOADER
# ============================================================

@st.cache_resource
def create_loader():

    loader = instaloader.Instaloader(
        download_comments=False,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=1,
        request_timeout=30,
    )

    # --------------------------------------------------------
    # Load saved Instagram session from Streamlit Secrets
    # --------------------------------------------------------

    try:

        if "instagram_session" in st.secrets:

            session_data = st.secrets["instagram_session"]

            login_username = session_data.get("username")
            session_file = session_data.get("session_file")

            if login_username and session_file:

                loader.load_session(
                    login_username,
                    session_file
                )

                st.session_state["instagram_logged_in"] = True

    except Exception as e:

        st.session_state["instagram_logged_in"] = False

    return loader


# ============================================================
# CLEAN USERNAME
# ============================================================

def clean_username(value):

    value = value.strip()

    value = value.replace("@", "")

    if "instagram.com/" in value:

        value = value.split("instagram.com/")[1]

        value = value.split("?")[0]

        value = value.split("#")[0]

    value = value.strip("/")

    value = value.split("/")[0]

    return value


# ============================================================
# EXCEL
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
# LOGIN STATUS
# ============================================================

loader = create_loader()

if st.session_state.get("instagram_logged_in", False):

    st.success("🟢 Instagram session is loaded.")

else:

    st.warning(
        "🟡 No Instagram session is configured yet."
    )

    st.info(
        "Create an Instagram session first, then add it to "
        "Streamlit Secrets."
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

    if not username_input:

        st.error(
            "Please enter an Instagram username or URL."
        )

        st.stop()


    if start_date > end_date:

        st.error(
            "Start Date cannot be later than End Date."
        )

        st.stop()


    # --------------------------------------------------------
    # Check Session
    # --------------------------------------------------------

    if not st.session_state.get(
        "instagram_logged_in",
        False
    ):

        st.error(
            "Instagram session is not configured."
        )

        st.info(
            "Please configure the Instagram session in "
            "Streamlit Secrets first."
        )

        st.stop()


    # --------------------------------------------------------
    # Username
    # --------------------------------------------------------

    username = clean_username(username_input)

    st.info(
        f"Searching Instagram account: @{username}"
    )


    try:

        # ----------------------------------------------------
        # PROFILE
        # ----------------------------------------------------

        with st.spinner(
            f"Connecting to @{username}..."
        ):

            profile = instaloader.Profile.from_username(
                loader.context,
                username
            )


        st.success(
            f"Account found: @{username}"
        )


        # ----------------------------------------------------
        # POSTS
        # ----------------------------------------------------

        posts = []

        checked = 0

        status = st.empty()


        for post in profile.get_posts():

            checked += 1

            post_date = post.date.date()

            status.write(
                f"Checking post {checked}: {post_date}"
            )


            # Newest → oldest
            if post_date < start_date:

                break


            # ------------------------------------------------
            # Date filter
            # ------------------------------------------------

            if start_date <= post_date <= end_date:

                try:

                    post_type = post.typename

                except Exception:

                    post_type = "Unknown"


                posts.append(
                    {
                        "Account": username,
                        "Date": post_date,
                        "Type": post_type,
                        "Caption": post.caption or "",
                        "Likes": post.likes,
                        "Comments": post.comments,
                        "URL": (
                            "https://www.instagram.com/p/"
                            + post.shortcode
                            + "/"
                        ),
                    }
                )


        status.empty()


        # ----------------------------------------------------
        # DATAFRAME
        # ----------------------------------------------------

        df = pd.DataFrame(posts)


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


        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        st.success(
            f"Found {len(df)} posts."
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


        # ----------------------------------------------------
        # TABLE
        # ----------------------------------------------------

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # ----------------------------------------------------
        # EXCEL
        # ----------------------------------------------------

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
    # ERRORS
    # ========================================================

    except TooManyRequestsException:

        st.error(
            "Instagram returned HTTP 429 — Too Many Requests."
        )

        st.warning(
            "Instagram is temporarily limiting this session. "
            "Wait before retrying."
        )


    except ProfileNotExistsException:

        st.error(
            f"Instagram account @{username} was not found."
        )


    except LoginRequiredException:

        st.error(
            "The Instagram session has expired or is invalid."
        )


    except ConnectionException as e:

        st.error(
            "Could not connect to Instagram."
        )

        st.code(str(e))


    except Exception as e:

        st.error(
            "An unexpected error occurred."
        )

        st.code(str(e))
