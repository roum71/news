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

    return loader


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
# CREATE LOADER
# ============================================================

loader = create_loader()

st.success(
    "🟢 Ready to search public Instagram posts."
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
    # Validate username
    # --------------------------------------------------------

    if not username_input:

        st.error(
            "Please enter an Instagram username or URL."
        )

        st.stop()


    # --------------------------------------------------------
    # Validate dates
    # --------------------------------------------------------

    if start_date > end_date:

        st.error(
            "Start Date cannot be later than End Date."
        )

        st.stop()


    # --------------------------------------------------------
    # Clean username
    # --------------------------------------------------------

    username = clean_username(username_input)

    if not username:

        st.error(
            "Invalid Instagram username."
        )

        st.stop()


    st.info(
        f"Searching Instagram account: @{username}"
    )


    # ========================================================
    # INSTAGRAM
    # ========================================================

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
        # ACCOUNT INFORMATION
        # ----------------------------------------------------

        account_col1, account_col2, account_col3 = st.columns(3)

        with account_col1:

            st.metric(
                "Followers",
                f"{profile.followers:,}"
            )

        with account_col2:

            st.metric(
                "Following",
                f"{profile.followees:,}"
            )

        with account_col3:

            st.metric(
                "Posts",
                f"{profile.mediacount:,}"
            )


        # ====================================================
        # POSTS
        # ====================================================

        posts = []

        checked = 0

        status = st.empty()


        for post in profile.get_posts():

            checked += 1

            post_date = post.date.date()


            status.write(
                f"Checking post {checked}: {post_date}"
            )


            # ------------------------------------------------
            # Instagram returns newest → oldest
            #
            # Once we go before the requested start date,
            # there is no reason to continue.
            # ------------------------------------------------

            if post_date < start_date:

                break


            # ------------------------------------------------
            # DATE FILTER
            # ------------------------------------------------

            if start_date <= post_date <= end_date:

                # --------------------------------------------
                # Post type
                # --------------------------------------------

                try:

                    post_type = post.typename

                except Exception:

                    post_type = "Unknown"


                # --------------------------------------------
                # Caption
                # --------------------------------------------

                try:

                    caption = post.caption or ""

                except Exception:

                    caption = ""


                # --------------------------------------------
                # Likes
                # --------------------------------------------

                try:

                    likes = post.likes

                except Exception:

                    likes = 0


                # --------------------------------------------
                # Comments
                # --------------------------------------------

                try:

                    comments = post.comments

                except Exception:

                    comments = 0


                # --------------------------------------------
                # URL
                # --------------------------------------------

                url = (
                    "https://www.instagram.com/p/"
                    + post.shortcode
                    + "/"
                )


                # --------------------------------------------
                # Add post
                # --------------------------------------------

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


        status.empty()


        # ====================================================
        # DATAFRAME
        # ====================================================

        df = pd.DataFrame(posts)


        # ----------------------------------------------------
        # No results
        # ----------------------------------------------------

        if df.empty:

            st.warning(
                "No public posts were found "
                "within the selected date range."
            )

            st.stop()


        # ----------------------------------------------------
        # Sort newest first
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


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

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

        st.subheader("Instagram Posts")

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
    # ERRORS
    # ========================================================

    except TooManyRequestsException:

        st.error(
            "Instagram returned HTTP 429 — Too Many Requests."
        )

        st.warning(
            "Instagram is temporarily limiting automated "
            "requests from this application."
        )

        st.info(
            "No Instagram password or session is required "
            "by this version of the app."
        )


    except ProfileNotExistsException:

        st.error(
            f"Instagram account @{username} was not found."
        )


    except LoginRequiredException:

        st.error(
            "Instagram requires login to access this account "
            "or its posts."
        )


    except ConnectionException as e:

        st.error(
            "Could not connect to Instagram."
        )

        st.code(
            str(e)
        )


    except Exception as e:

        st.error(
            "An unexpected error occurred."
        )

        st.code(
            str(e)
        )
