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
# PAGE CONFIGURATION
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
# INSTALOADER SESSION
# ============================================================

@st.cache_resource
def create_instaloader():

    loader = instaloader.Instaloader(
        download_comments=False,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_captions=True,
        save_metadata=False,
        compress_json=False,
    )

    # Do not keep retrying for many minutes if Instagram
    # returns HTTP 429.
    loader.context.max_connection_attempts = 1

    return loader


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

        # Set reasonable column widths
        widths = {
            "A": 20,
            "B": 15,
            "C": 18,
            "D": 70,
            "E": 12,
            "F": 12,
            "G": 55
        }

        for column, width in widths.items():
            worksheet.column_dimensions[column].width = width

    return output.getvalue()


# ============================================================
# USER INPUT
# ============================================================

username = st.text_input(
    "Instagram Username",
    placeholder="example_account",
    help="Enter the Instagram username without @"
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

extract = st.button(
    "🔎 Extract Posts",
    type="primary",
    use_container_width=True
)


# ============================================================
# MAIN EXTRACTION
# ============================================================

if extract:

    # --------------------------------------------------------
    # Validate username
    # --------------------------------------------------------

    if not username:

        st.error(
            "Please enter an Instagram username."
        )

        st.stop()

    username = username.strip().replace("@", "")

    # --------------------------------------------------------
    # Validate dates
    # --------------------------------------------------------

    if start_date > end_date:

        st.error(
            "Start Date cannot be later than End Date."
        )

        st.stop()

    # --------------------------------------------------------
    # Create / reuse loader
    # --------------------------------------------------------

    loader = create_instaloader()

    try:

        # ----------------------------------------------------
        # Get profile
        # ----------------------------------------------------

        with st.spinner(
            f"Connecting to Instagram account @{username}..."
        ):

            profile = instaloader.Profile.from_username(
                loader.context,
                username
            )

        st.success(
            f"Connected to @{username}"
        )

        # ----------------------------------------------------
        # Extract posts
        # ----------------------------------------------------

        posts = []

        progress = st.progress(0)

        status = st.empty()

        checked = 0

        for post in profile.get_posts():

            checked += 1

            post_date = post.date.date()

            status.write(
                f"Checking post {checked}: {post_date}"
            )

            # Instagram normally returns newest posts first.
            # Stop once we are older than the requested period.
            if post_date < start_date:
                break

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

            # Visual progress only
            progress.progress(
                min(checked / 100, 1.0)
            )

        progress.empty()
        status.empty()

        # ----------------------------------------------------
        # Results
        # ----------------------------------------------------

        df = pd.DataFrame(posts)

        if df.empty:

            st.warning(
                "No public posts were found "
                "within the selected date range."
            )

        else:

            df = df.sort_values(
                "Date",
                ascending=False
            ).reset_index(drop=True)

            st.success(
                f"Found {len(df)} posts."
            )

            # ----------------------------------------------
            # Summary
            # ----------------------------------------------

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

            # ----------------------------------------------
            # Display results
            # ----------------------------------------------

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            # ----------------------------------------------
            # Excel
            # ----------------------------------------------

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
    # ERROR HANDLING
    # ========================================================

    except TooManyRequestsException:

        st.error(
            "Instagram temporarily rejected the request "
            "(HTTP 429 – Too Many Requests)."
        )

        st.warning(
            "This is an Instagram access/rate-limit restriction. "
            "The application has stopped instead of waiting "
            "for several minutes."
        )

        st.info(
            "Please wait before trying again. "
            "Repeated attempts can increase the restriction."
        )


    except ProfileNotExistsException:

        st.error(
            f"The Instagram account @{username} "
            "could not be found."
        )


    except LoginRequiredException:

        st.error(
            "Instagram requires authentication to access "
            "this account or request."
        )


    except ConnectionException as e:

        st.error(
            "Instagram could not be reached."
        )

        st.code(str(e))


    except Exception as e:

        st.error(
            "An unexpected error occurred."
        )

        st.code(str(e))
