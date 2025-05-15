import streamlit as st
from instagrapi import Client
import os
import json
import tempfile
import google.generativeai as genai
from PIL import Image

# --- Load secrets ---
USERNAME = st.secrets["insta"]["username"]
PASSWORD = st.secrets["insta"]["password"]
SESSION_FILE = st.secrets["insta"]["session_file"]
GEMINI_API_KEY = st.secrets["gemini"]["api_key"]

# --- Configure Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="📸 Auto Instagram Poster", layout="centered")
st.title("🤖 Instagram Auto Poster")
st.caption("Upload an image, generate a caption, and post it directly to Instagram.")

# --- Instagram Login ---
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

# --- Generate Caption ---
def generate_caption(pil_image):
    try:
        response = model.generate_content(
            [pil_image, "Generate a short, creative, and engaging Instagram caption for this image."],
            stream=False,
        )
        return response.text.strip()
    except Exception as e:
        return f"Error generating caption: {e}"

# --- UI ---
uploaded_file = st.file_uploader("📤 Upload an image", type=["jpg", "jpeg", "png"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, use_column_width=True)

    # 👉 Convert RGBA/other to RGB (JPEG-safe)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Save image to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        image.save(tmp.name)
        image_path = tmp.name

    # --- Generate Caption ---
    if st.button("✨ Generate Caption"):
        with st.spinner("Generating caption using Gemini..."):
            caption = generate_caption(image)

        if caption.startswith("Error"):
            st.error(caption)
        else:
            st.session_state.caption = caption
            st.success("✅ Caption generated!")
            st.write(f"📝 Generated Caption:\n> {caption}")

    # --- Post Options ---
    if "caption" in st.session_state:
        st.write("### Choose how to post:")
        option = st.radio("Use generated caption or write your own?", ("Generated", "Custom"))

        if option == "Custom":
            custom_caption = st.text_area("✏️ Write your custom caption:")
        else:
            custom_caption = st.session_state.caption

        # --- Post to Instagram ---
        if st.button("📲 Post to Instagram"):
            with st.spinner("Posting to Instagram..."):
                client = login()
                try:
                    result = client.photo_upload(image_path, custom_caption)
                    st.success(f"✅ Posted successfully! Post ID: {result.dict().get('pk')}")
                except Exception as e:
                    st.error(f"❌ Failed to post: {e}")
