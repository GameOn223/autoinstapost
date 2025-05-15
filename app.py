import streamlit as st
from instagrapi import Client
import os
import json
import tempfile
import random
import google.generativeai as genai
from PIL import Image

# --- Secrets ---
USERNAME = st.secrets["insta"]["username"]
PASSWORD = st.secrets["insta"]["password"]
SESSION_FILE = st.secrets["insta"]["session_file"]
GEMINI_API_KEY = st.secrets["gemini"]["api_key"]
APP_PASSWORD = st.secrets["app"]["password"]

# --- Static Lists ---
FACULTY_IDS = ["@faculty1", "@faculty2", "@faculty3"]
STUDENT_IDS = ["@student1", "@student2", "@student3"]

# --- Gemini Config ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="📸 Auto Instagram Poster", layout="centered")

# --- Password Protection ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Login Required")
    password = st.text_input("Enter Access Password", type="password")
    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Incorrect Password")
    st.stop()

# --- Login to Instagram ---
@st.cache_resource
def login():
    cl = Client()
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            settings = json.load(f)
            cl.set_settings(settings)
        try:
            cl.login(USERNAME, PASSWORD)
        except Exception:
            cl = Client()
            cl.login(USERNAME, PASSWORD)
            with open(SESSION_FILE, "w") as f:
                json.dump(cl.get_settings(), f)
    else:
        cl.login(USERNAME, PASSWORD)
        with open(SESSION_FILE, "w") as f:
            json.dump(cl.get_settings(), f)
    return cl

# --- Caption Generator ---
def generate_caption(pil_image, extra_prompt=None):
    try:
        prompt = "Write a short, aesthetic Instagram caption for this image.Directly give me Caption Dont Give me here is caption and all that shit"
        if extra_prompt:
            prompt += f" Extra detail: {extra_prompt}"
        response = model.generate_content([pil_image, prompt])
        return response.text.strip()
    except Exception as e:
        return f"Error generating caption: {e}"

# --- UI Start ---
st.title("🤖 Instagram Auto Poster")

uploaded_files = st.file_uploader("📤 Upload image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    images = []
    image_paths = []

    st.subheader("🖼 Preview & Reorder")
    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)
        st.image(img, caption=f"Image {i+1}", use_column_width=True)

    order_input = st.text_input("✏️ Enter custom order (e.g. 1,2,3):", value=",".join(str(i+1) for i in range(len(images))))
    try:
        order = [int(i.strip()) - 1 for i in order_input.split(",")]
        images = [images[i] for i in order]
    except:
        st.warning("⚠️ Invalid order format. Using default.")

    for img in images:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            img.save(tmp.name)
            image_paths.append(tmp.name)

    # Ask user where to post: Story or Feed
    post_type = st.radio("📤 Where do you want to post this?", ["Feed Post", "Story"], index=0)

    # --- Caption Generation ---
    if st.button("✨ Generate Caption"):
        st.subheader("📝 Caption Section")
        extra_prompt = ""
        if len(images) > 1:
            extra_prompt = st.text_input("Optional Extra Prompt for Caption (Multi-image):")

        with st.spinner("Generating caption..."):
            caption = generate_caption(images[0], extra_prompt)

        if caption.startswith("Error"):
            st.error(caption)
        else:
            st.session_state.caption = caption
            st.success("✅ Caption Generated")
            st.write(f"> {caption}")

# --- Honorable Mentions Section ---
if "caption" in st.session_state:
    st.subheader("👥 Honorable Mentions")
    selected_tags = st.multiselect("Select ID groups:", ["Faculty", "Students", "Custom"])

    tag_usernames = []
    if "Faculty" in selected_tags:
        tag_usernames.extend(FACULTY_IDS)
    if "Students" in selected_tags:
        tag_usernames.extend(STUDENT_IDS)
    if "Custom" in selected_tags:
        custom_input = st.text_input("Enter Custom IDs (@user1, @user2):")
        if custom_input:
            tag_usernames.extend([u.strip() for u in custom_input.split(",")])

    # Prepare the "Honorable Mentions" string
    mentions_text = " ".join(tag_usernames)
    full_caption = f"{st.session_state.caption}\n\nHonorable Mentions: {mentions_text}"

    st.markdown("### 🖊 Final Caption:")
    st.text_area("Edit if needed:", value=full_caption, key="final_caption", height=150)

    # --- POST TO INSTAGRAM ---
    if st.button("📲 Post to Instagram"):
        with st.spinner("Uploading to Instagram..."):
            client = login()

            try:
                # Upload the photo first
                if post_type == "Story":
                    if len(image_paths) > 1:
                        st.error("❌ Instagram stories support only one image.")
                    else:
                        result = client.photo_upload_to_story(
                            path=image_paths[0],
                            caption=st.session_state.final_caption
                        )
                        st.success("✅ Story posted!")
                else:
                    if len(image_paths) == 1:
                        # Upload the single photo
                        result = client.photo_upload(
                            path=image_paths[0],
                            caption=st.session_state.final_caption
                        )
                        st.success("✅ Feed post uploaded!")
                    else:
                        # Upload the album
                        result = client.album_upload(
                            paths=image_paths,
                            caption=st.session_state.final_caption
                        )
                        st.success("✅ Album post uploaded!")

            except Exception as e:
                st.error(f"❌ Upload failed: {e}")
