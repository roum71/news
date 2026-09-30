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
    "Extract public Instagram posts from a selected account "
    "within a specific date range and export the results to Excel."
)


# ============================================================
# CREATE INSTALOADER
# ============================================================

@st.cache_resource
def create_instaloader():

    loader = instaloader.Instaloader(
        download_comments=False,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=1,
        request_timeout=30
    )

    return loader


# ============================================================
# CLEAN INSTAGRAM USERNAME
# ============================================================

def clean_username(value):

    value = value.strip()

    # Remove @
    value = value.replace("@", "")

    # If user entered a full Instagram URL
    if "instagram.com/" in value:

        value = value.split("instagram.com/")[1]

        # Remove everything after username
        value = value.split("?")[0]
        value = value.split("#")[0]

    # Remove trailing slash
    value = value.strip("/")

    # Remove possible path elements
    value = value.split("/")[0]

    return value


# ============================================================
# EXCEL EXPORT
# ============================================================

def convert_to_excel(df):

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

        # Column widths
        widths = {
            "A": 22,
            "B": 15,
            "C": 18,
            "D": 80,
            "E": 12,
            "F": 12,
            "G": 60
        }

        for column, width in widths.items():
            worksheet.column_dimensions[column].width = width

    return output.getvalue()


# ============================================================
# INPUT
# ============================================================

username_input = st.text_input(
    "Instagram Username or URL",
    placeholder="rakmediaoffice or https://www.instagram.com/rakmediaoffice/",
    help="You can enter either the username or the full Instagram profile URL."
)


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
# EXTRACT BUTTON
# ============================================================

if st.button(
    "🔎 Extract Posts",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # Validate input
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
    # Convert URL to username
    # --------------------------------------------------------

    username = clean_username(username_input)

    st.info(
        f"Instagram account: @{username}"
    )


    # --------------------------------------------------------
    # Create loader
    # --------------------------------------------------------

    loader = create_instaloader()


    try:

        # ----------------------------------------------------
        # Get profile
        # ----------------------------------------------------

        with st.spinner(
            f"Connecting to Instagram: @{username}"
        ):

            profile = instaloader.Profile.from_username(
                loader.context,
                username
            )


        st.success(
            f"Account found: @{username}"
        )


        # ----------------------------------------------------
        # Extract posts
        # ----------------------------------------------------

        posts = []

        status = st.empty()

        checked = 0


        for post in profile.get_posts():

            checked += 1

            post_date = post.date.date()

            status.write(
                f"Checking post {checked}: {post_date}"
            )


            # Instagram normally returns newest first.
            # Stop once we reach posts older than the
            # requested start date.
            if post_date < start_date:

                break


            # Only selected date range
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
        # Create dataframe
        # ----------------------------------------------------

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
        # Sort
        # ----------------------------------------------------

        df = df.sort_values(
            by="Date",
            ascending=False
        ).reset_index(drop=True)


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        st.success(
            f"Found {len(df)} posts from @{username}"
        )


        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Posts",
                len(df)
            )

        with col2:

            st.metric(
                "Total Likes",
                int(df["Likes"].fillna(0).sum())
            )

        with col3:

            st.metric(
                "Total Comments",
                int(df["Comments"].fillna(0).sum())
            )


        # ----------------------------------------------------
        # Results table
        # ----------------------------------------------------

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # ----------------------------------------------------
        # Excel
        # ----------------------------------------------------

        excel_file = convert_to_excel(df)


        filename = (
            f"{username}_instagram_posts_"
            f"{start_date}_{end_date}.xlsx"
        )


        st.download_button(
            label="⬇️ Download Excel",
            data=excel_file,
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
            "Instagram temporarily blocked the request "
            "(HTTP 429 – Too Many Requests)."
        )

        st.warning(
            "Please wait before trying again. "
            "This is an Instagram access limitation, "
            "not a problem with your username."
        )


    except ProfileNotExistsException:

        st.error(
            f"The Instagram account @{username} "
            "could not be found."
        )


    except LoginRequiredException:

        st.error(
            "Instagram requires authentication to access "
            "this content."
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
