import streamlit as st
import pandas as pd
import instaloader
from io import BytesIO
from datetime import date, timedelta

# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Instagram News Extractor",
    page_icon="📸",
    layout="wide"
)

st.title("📸 Instagram News Extractor")

st.write(
    "Extract public Instagram posts from a selected account "
    "within a specific date range and export the results to Excel."
)

# --------------------------------------------------
# Inputs
# --------------------------------------------------

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

# --------------------------------------------------
# Excel function
# --------------------------------------------------

def convert_df_to_excel(df):
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

        # Format the Excel sheet
        worksheet = writer.sheets["Instagram Posts"]

        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:
                try:
                    cell_length = len(str(cell.value))
                    if cell_length > max_length:
                        max_length = cell_length
                except Exception:
                    pass

            worksheet.column_dimensions[column_letter].width = min(
                max_length + 2,
                60
            )

    return output.getvalue()


# --------------------------------------------------
# Extract posts
# --------------------------------------------------

if st.button("🔎 Extract Instagram Posts", type="primary"):

    if not username:
        st.error("Please enter an Instagram username.")
        st.stop()

    username = username.strip().replace("@", "")

    if start_date > end_date:
        st.error("Start Date cannot be later than End Date.")
        st.stop()

    try:

        # Create Instaloader
        loader = instaloader.Instaloader(
            download_comments=False,
            download_pictures=False,
            download_videos=False,
            download_geotags=False,
            save_metadata=False,
            compress_json=False
        )

        with st.spinner(
            f"Connecting to Instagram account: @{username}"
        ):

            profile = instaloader.Profile.from_username(
                loader.context,
                username
            )

        st.info(
            f"Reading public posts from Instagram account: @{username}"
        )

        posts = []

        progress = st.progress(0)
        status = st.empty()

        # Get posts one by one instead of loading everything into memory
        post_iterator = profile.get_posts()

        checked_posts = 0

        for post in post_iterator:

            checked_posts += 1

            post_date = post.date.date()

            status.write(
                f"Checking post {checked_posts} — {post_date}"
            )

            # Instagram posts are normally returned newest first.
            # Once we reach posts older than the start date,
            # we can stop searching.
            if post_date < start_date:
                break

            if start_date <= post_date <= end_date:

                # Determine post type
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
                            f"https://www.instagram.com/p/"
                            f"{post.shortcode}/"
                        )
                    }
                )

            # Progress is approximate because Instagram does not
            # provide the total number of posts in advance.
            progress.progress(
                min((checked_posts % 100) / 100, 1.0)
            )

        progress.empty()
        status.empty()

        # --------------------------------------------------
        # Results
        # --------------------------------------------------

        df = pd.DataFrame(posts)

        if df.empty:

            st.warning(
                "No public posts were found for the selected date range."
            )

        else:

            # Sort newest first
            df = df.sort_values(
                by="Date",
                ascending=False
            ).reset_index(drop=True)

            st.success(
                f"Found {len(df)} posts from @{username}"
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            # --------------------------------------------------
            # Download Excel
            # --------------------------------------------------

            excel_data = convert_df_to_excel(df)

            filename = (
                f"{username}_instagram_posts_"
                f"{start_date}_{end_date}.xlsx"
            )

            st.download_button(
                label="⬇️ Download Excel",
                data=excel_data,
                file_name=filename,
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )

    except instaloader.exceptions.ProfileNotExistsException:

        st.error(
            f"The Instagram account '@{username}' does not exist "
            "or could not be found."
        )

    except Exception as e:

        st.error(
            "Instagram could not be accessed. "
            "This can happen if Instagram temporarily blocks "
            "automated requests or changes its website structure."
        )

        st.code(str(e))