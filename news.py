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
# INSTALOADER
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
        max_connection_attempts=1
    )

    # --------------------------------------------------------
    # Optional Instagram session
    # --------------------------------------------------------

    try:

        if "instagram_session" in st.secrets:

            session_data = st.secrets["instagram_session"]

            if session_data.get("username") and session_data.get("session_file"):

                username = session_data["username"]
                session_file = session_data["session_file"]

                loader.load_session(
                    username,
                    session_file
                )

    except Exception:
        pass

    return loader


# ============================================================
# CLEAN USERNAME
# ============================================================

def clean_username(value):

    value = value.strip()

    # Remove @
    value = value.replace("@", "")

    # Convert full URL to username
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
# BUTTON
# ============================================================

if st.button(
    "🔎 Extract Posts",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

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
    # Username
    # --------------------------------------------------------

    username = clean_username(username_input)

    st.info(
        f"Searching Instagram account: @{username}"
    )


    # --------------------------------------------------------
    # Loader
    # --------------------------------------------------------

    loader = create_loader()


    try:

        # ----------------------------------------------------
        # Profile
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
        # Posts
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


            # Instagram normally returns newest first.
            # Stop when posts become older than start date.
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
                        )
                    }
                )


        status.empty()


        # ----------------------------------------------------
        # DataFrame
        # ----------------------------------------------------

        df = pd.DataFrame(posts)


        if df.empty:

            st.warning(
                "No public posts were found "
                "within the selected date range."
            )

            st.stop()


        # ----------------------------------------------------
        # Sort
        # ----------------------------------------------------

        df = df.sort_values(
            by="Date",
            ascending=False
        ).reset_index(drop=True)


        # ----------------------------------------------------
        # Results
        # ----------------------------------------------------

        st.success(
            f"Found {len(df)} posts."
        )


        # Summary

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Posts",
                len(df)
            )

        with c2:

            st.metric(
                "Likes",
                int(df["Likes"].fillna(0).sum())
            )

        with c3:

            st.metric(
                "Comments",
                int(df["Comments"].fillna(0).sum())
            )


        # Table

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # ----------------------------------------------------
        # Excel
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
            "Instagram returned HTTP 429 "
            "(Too Many Requests)."
        )

        st.warning(
            "Instagram is temporarily limiting automated access. "
            "Please wait before trying again."
        )


    except ProfileNotExistsException:

        st.error(
            f"Instagram account @{username} was not found."
        )


    except LoginRequiredException:

        st.error(
            "Instagram requires authentication "
            "for this request."
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
