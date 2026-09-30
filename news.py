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
# CREATE INSTALOADER
# ============================================================

def create_instaloader():

    loader = instaloader.Instaloader(
        download_comments=False,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        save_metadata=False,
        compress_json=False
    )

    return loader


# ============================================================
# CLEAN INSTAGRAM USERNAME
# ============================================================

def clean_username(value):

    value = value.strip()

    # Remove @
    value = value.replace("@", "")

    # If a full Instagram URL was entered
    if "instagram.com/" in value:

        value = value.split("instagram.com/")[1]

        # Remove query parameters
        value = value.split("?")[0]

        # Remove fragments
        value = value.split("#")[0]

    # Remove trailing slash
    value = value.strip("/")

    # Keep only username
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
        worksheet.column_dimensions["A"].width = 25
        worksheet.column_dimensions["B"].width = 15
        worksheet.column_dimensions["C"].width = 18
        worksheet.column_dimensions["D"].width = 80
        worksheet.column_dimensions["E"].width = 12
        worksheet.column_dimensions["F"].width = 12
        worksheet.column_dimensions["G"].width = 60

    return output.getvalue()


# ============================================================
# USER INPUT
# ============================================================

username_input = st.text_input(
    "Instagram Username or URL",
    placeholder=(
        "rakmediaoffice or "
        "https://www.instagram.com/rakmediaoffice/"
    ),
    help=(
        "Enter either the Instagram username "
        "or the full Instagram profile URL."
    )
)


# ============================================================
# DATE INPUT
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
# EXTRACT BUTTON
# ============================================================

extract_button = st.button(
    "🔎 Extract Posts",
    type="primary",
    use_container_width=True
)


# ============================================================
# MAIN PROCESS
# ============================================================

if extract_button:

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

    st.info(
        f"Instagram account: @{username}"
    )


    # --------------------------------------------------------
    # Create Instaloader
    # --------------------------------------------------------

    loader = create_instaloader()


    try:

        # ----------------------------------------------------
        # Find Instagram profile
        # ----------------------------------------------------

        with st.spinner(
            f"Connecting to Instagram account @{username}..."
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

        checked_posts = 0


        for post in profile.get_posts():

            checked_posts += 1

            post_date = post.date.date()


            status.write(
                f"Checking post {checked_posts}: {post_date}"
            )


            # ------------------------------------------------
            # Stop when posts become older than requested date
            # ------------------------------------------------

            if post_date < start_date:

                break


            # ------------------------------------------------
            # Keep posts inside selected period
            # ------------------------------------------------

            if start_date <= post_date <= end_date:

                # Determine type
                try:

                    post_type = post.typename

                except Exception:

                    post_type = "Unknown"


                # Add post
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
        # Create DataFrame
        # ----------------------------------------------------

        df = pd.DataFrame(posts)


        # ----------------------------------------------------
        # No posts found
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


        # ----------------------------------------------------
        # Success message
        # ----------------------------------------------------

        st.success(
            f"Found {len(df)} posts from @{username}"
        )


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        col1, col2, col3 = st.columns(3)


        with col1:

            st.metric(
                "Posts",
                len(df)
            )


        with col2:

            total_likes = int(
                df["Likes"]
                .fillna(0)
                .sum()
            )

            st.metric(
                "Total Likes",
                total_likes
            )


        with col3:

            total_comments = int(
                df["Comments"]
                .fillna(0)
                .sum()
            )

            st.metric(
                "Total Comments",
                total_comments
            )


        # ----------------------------------------------------
        # Display results
        # ----------------------------------------------------

        st.subheader("Extracted Posts")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # ----------------------------------------------------
        # Create Excel
        # ----------------------------------------------------

        excel_file = convert_to_excel(df)


        filename = (
            f"{username}_instagram_posts_"
            f"{start_date}_{end_date}.xlsx"
        )


        # ----------------------------------------------------
        # Download button
        # ----------------------------------------------------

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
            "Instagram temporarily blocked the request "
            "(HTTP 429 – Too Many Requests)."
        )

        st.warning(
            "Instagram is currently limiting automated access "
            "from this server."
        )

        st.info(
            "Please wait before trying again. "
            "Do not repeatedly press Extract Posts."
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
