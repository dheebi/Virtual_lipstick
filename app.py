# pyrefly: ignore [missing-import]
import streamlit as st
# pyrefly: ignore [missing-import]
import streamlit.components.v1 as components
import cv2
import numpy as np
from PIL import Image
import mediapipe as mp
import os
import hashlib
import threading
import pandas as pd
import datetime

def get_image_as_b64(file_path):
    import base64
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            ext = os.path.splitext(file_path)[1].replace(".", "").lower()
            if ext in ["png", "jpg", "jpeg", "webp", "svg"]:
                b64 = base64.b64encode(data).decode()
                mime = "jpeg" if ext == "jpg" else ext
                return f"data:image/{mime};base64,{b64}"
        except Exception:
            pass
    return None

# =========================
# EXCEL BACKEND USER DATABASE
# =========================
DB_FILE = "users.xlsx"
db_lock = threading.Lock()

def init_user_db():
    with db_lock:
        if not os.path.exists(DB_FILE):
            df = pd.DataFrame(columns=["username", "password_hash", "created_at"])
            try:
                df.to_excel(DB_FILE, index=False)
            except PermissionError:
                st.error("Error: The user database file is open in Excel. Please close it to let the app initialize.")
                st.stop()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    try:
        init_user_db()
    except Exception:
        pass
    with db_lock:
        try:
            df = pd.read_excel(DB_FILE)
        except PermissionError:
            return False, "Error: The user database file (users.xlsx) is open in Excel. Please close it and try again."
        except Exception:
            df = pd.DataFrame(columns=["username", "password_hash", "created_at"])
        
        usernames_existing = df["username"].dropna().astype(str).str.lower().values
        if username.lower() in usernames_existing:
            return False, "Username already exists."
        
        new_row = {
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        try:
            df.to_excel(DB_FILE, index=False)
        except PermissionError:
            return False, "Error: The user database file (users.xlsx) is open in Excel. Please close it and try again."
        except Exception as e:
            return False, f"Database error: {str(e)}"
        return True, "Account created successfully!"

def authenticate_user(username, password):
    try:
        init_user_db()
    except Exception:
        pass
    with db_lock:
        try:
            df = pd.read_excel(DB_FILE)
        except PermissionError:
            st.error("Error: The user database file (users.xlsx) is open in Excel. Please close it and try again.")
            st.stop()
        except Exception:
            return False
            
        pwd_hash = hash_password(password)
        df_filtered = df.dropna(subset=["username", "password_hash"])
        match = df_filtered[
            (df_filtered["username"].astype(str).str.lower() == username.lower()) &
            (df_filtered["password_hash"].astype(str) == pwd_hash)
        ]
        return not match.empty

# Initialize DB on startup
init_user_db()

# =========================
# PROFILE-BASED LOOK PERSISTENCE
# =========================
import json
import uuid

PROFILE_BASE_DIR = "user_profiles"

def get_user_profile_dir(username):
    # Sanitize username to make a safe directory name
    clean_username = "".join(c for c in username if c.isalnum() or c in (" ", "_", "-")).strip()
    if not clean_username:
        clean_username = "default_user"
    return os.path.join(PROFILE_BASE_DIR, clean_username)

def load_user_looks(username):
    user_dir = get_user_profile_dir(username)
    looks_file = os.path.join(user_dir, "looks.json")
    images_dir = os.path.join(user_dir, "images")
    
    # Ensure directories exist
    if not os.path.exists(images_dir):
        os.makedirs(images_dir, exist_ok=True)
        
    if not os.path.exists(looks_file):
        return []
        
    try:
        with open(looks_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_user_looks(username, looks_list):
    user_dir = get_user_profile_dir(username)
    looks_file = os.path.join(user_dir, "looks.json")
    
    os.makedirs(user_dir, exist_ok=True)
    
    try:
        with open(looks_file, "w", encoding="utf-8") as f:
            json.dump(looks_list, f, indent=4)
        return True
    except Exception:
        return False

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="✦ AURALITH AI Lipstick Studio ✦", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&family=Outfit:wght@300;400;500;600;700&family=Poppins:wght@300;400;500;600;700&display=swap');

/* Global Font Override */
.main, .sidebar-content, [data-testid="stHeader"], [data-testid="stSidebar"], .stApp {
    font-family: 'Outfit', sans-serif !important;
}

/* Background & Main Panel styling */
.stApp {
    background-color: #f9f9fb !important;
    background-image: none !important;
}

/* Typography styles */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    color: #2b1020 !important;
    text-shadow: none !important;
    letter-spacing: -0.3px;
}

/* AURALITH Hero Banner styling */
.auralith-hero {
    background: linear-gradient(135deg, #2b1020 0%, #fc2779 50%, #d4a373 100%) !important;
    color: #ffffff !important;
    border-radius: 20px !important;
    padding: 60px 40px;
    text-align: center;
    box-shadow: 0 12px 40px rgba(43, 16, 32, 0.15);
    margin-bottom: 30px;
    position: relative;
    overflow: hidden;
}
.auralith-hero::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 80%);
    pointer-events: none;
}

/* Glassmorphism card elements */
.glass-card {
    background: #ffffff !important;
    border-radius: 16px !important;
    border: 1px solid #e8e8f2 !important;
    padding: 24px;
    margin: 15px 0;
    box-shadow: 0 8px 32px rgba(43, 16, 32, 0.03) !important;
    transition: all 0.3s ease;
}
.glass-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 40px rgba(252, 39, 121, 0.06) !important;
    border-color: #d4a373 !important;
}

/* Luxury Login Card */
.login-card {
    background: #ffffff !important;
    border-radius: 24px !important;
    border: 1px solid #e8e8f2 !important;
    padding: 45px;
    box-shadow: 0 20px 50px rgba(43, 16, 32, 0.12) !important;
    margin-top: 40px;
    border-top: 6px solid #d4a373 !important;
}

/* Dashboard Metrics */
.metric-container {
    display: flex;
    justify-content: space-between;
    gap: 15px;
    margin: 20px 0 30px 0;
}

.metric-card {
    flex: 1;
    background: #ffffff !important;
    border: 1px solid #e8e8f2 !important;
    border-radius: 16px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 8px 24px rgba(43,16,32,0.02);
    border-top: 4px solid #d4a373 !important;
}

.metric-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #8b8b9c;
    margin-bottom: 6px;
    font-weight: 600;
}

.metric-value {
    font-size: 24px;
    font-weight: 700;
    color: #2b1020 !important;
}

.skin-badge {
    display: inline-block; 
    padding: 8px 20px; 
    border-radius: 30px;
    font-weight: 700; 
    font-size: 13px; 
    color: white; 
    margin: 8px 0;
    box-shadow: 0 4px 12px rgba(43,16,32,0.08);
    border: 2px solid #d4a373 !important;
}

.shade-pill {
    display: inline-block; 
    padding: 6px 16px; 
    border-radius: 20px;
    font-size: 12px; 
    font-weight: 600; 
    color: white; 
    margin: 4px;
    cursor: pointer; 
    border: 1px solid rgba(255,255,255,0.4);
    transition: all 0.2s ease;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.shade-pill:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(252, 39, 121, 0.25);
    border-color: rgba(255, 255, 255, 0.8);
}

.rec-header { 
    font-size: 14px; 
    font-weight: 700; 
    color: #2b1020 !important; 
    margin: 15px 0 8px 0; 
    text-transform: uppercase;
    letter-spacing: 1px;
    border-left: 3px solid #d4a373;
    padding-left: 10px;
}

/* Sidebar styling overrides */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e8e8f2 !important;
}

.sidebar-avatar {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2b1020 0%, #fc2779 50%, #d4a373 100%);
    margin: 0 auto 15px auto;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    font-weight: bold;
    color: white;
    box-shadow: 0 6px 15px rgba(252, 39, 121, 0.15);
}

.sidebar-header-title {
    text-align: center;
    font-weight: 700;
    color: #2b1020;
    font-size: 18px;
    margin-bottom: 2px;
    letter-spacing: 0.5px;
}

.sidebar-header-subtitle {
    text-align: center;
    color: #d4a373;
    font-size: 10px;
    font-weight: 700;
    margin-bottom: 20px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

/* Look Card styling */
.look-card {
    background: #ffffff !important;
    border-radius: 16px;
    border: 1px solid #e8e8f2 !important;
    padding: 20px;
    margin-bottom: 15px;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(43, 16, 32, 0.02) !important;
}
.look-card:hover {
    transform: translateY(-3px);
    border-color: #d4a373 !important;
    box-shadow: 0 10px 25px rgba(252, 39, 121, 0.08) !important;
}

/* AURALITH Custom Navigation Header Container */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff !important;
    border: 1.5px solid #e8e8f2 !important;
    padding: 8px 24px !important;
    border-radius: 20px !important;
    box-shadow: 0 4px 20px rgba(43, 16, 32, 0.02) !important;
    margin-bottom: 25px !important;
}

/* Search Input Styling */
div[data-testid="stTextInput"] input {
    background-color: #f5f5f7 !important;
    border-radius: 20px !important;
    border: 1.5px solid #e8e8f2 !important;
    color: #2b1020 !important;
    font-size: 13px !important;
    padding: 8px 16px !important;
    transition: all 0.25s ease !important;
}
div[data-testid="stTextInput"] input:focus {
    background-color: #ffffff !important;
    border-color: #fc2779 !important;
    box-shadow: 0 0 0 2px rgba(252, 39, 121, 0.1) !important;
}

/* Header Navigation Buttons Compact Layout & Styling */
div[data-testid="stVerticalBlockBorderWrapper"] button {
    padding: 6px 10px !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    border-radius: 20px !important;
    white-space: nowrap !important;
    letter-spacing: 0.2px !important;
    border: 1px solid #d4a373 !important;
}

.auralith-logo {
    font-family: 'Montserrat', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #2b1020;
    letter-spacing: 2px;
    line-height: 48px;
}
.auralith-logo span {
    color: #fc2779;
}

/* Marketing Promo Banner */
.auralith-promo-banner {
    background: linear-gradient(90deg, #2b1020 0%, #fc2779 50%, #d4a373 100%);
    color: #ffffff;
    border-radius: 10px;
    padding: 14px 24px;
    margin-bottom: 25px;
    font-weight: 600;
    font-size: 13px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 6px 18px rgba(252, 39, 121, 0.1);
    font-family: 'Montserrat', sans-serif;
    letter-spacing: 0.5px;
}

/* Global button restyling for retail theme */
div.stButton > button {
    background-color: #ffffff !important;
    color: #2b1020 !important;
    border: 1px solid #d4a373 !important;
    border-radius: 24px !important;
    font-weight: 600 !important;
    padding: 8px 20px !important;
    letter-spacing: 0.5px;
    transition: all 0.2s ease !important;
}
div.stButton > button:hover {
    background-color: #fc2779 !important;
    color: #ffffff !important;
    border-color: #fc2779 !important;
    box-shadow: 0 6px 15px rgba(252, 39, 121, 0.15) !important;
    transform: translateY(-1px);
}

/* Active select box and input stylings focus to signature pink */
.stTextInput input:focus, .stSelectbox [data-baseweb="select"] > div:focus {
    border-color: #fc2779 !important;
    box-shadow: 0 0 0 1px #fc2779 !important;
}
</style>
""", unsafe_allow_html=True)

components.html("""
<script>
(function() {
  var _orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = function(constraints) {
    if (constraints && constraints.video) {
      var base = typeof constraints.video === 'object' ? constraints.video : {};
      constraints.video = Object.assign({}, base, {
        width:  { ideal: 1920 }, height: { ideal: 1080 }, facingMode: 'user'
      });
    }
    return _orig(constraints);
  };
})();
</script>
""", height=0)

# =========================
# MEDIAPIPE
# =========================
@st.cache_resource
def load_mediapipe():
    return mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.4,
    )

face_mesh = load_mediapipe()

# -------------------------------------------------------
# MediaPipe lip landmark indices (verified FaceMesh 468-pt)
# -------------------------------------------------------
# Outer lip contours
UPPER_LIP_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
LOWER_LIP_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
# Inner lip contours (vermillion)
UPPER_LIP_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
LOWER_LIP_INNER = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]

# Closed loop: upper L→R (61..291), lower R→L (375..146), back to 61
# NOTE: slice [-2:0:-1] picks indices [9..1] of LOWER, skipping shared corners 291 and 61
OUTER_LIP_LOOP = UPPER_LIP_OUTER + LOWER_LIP_OUTER[-2:0:-1]
INNER_LIP_LOOP = UPPER_LIP_INNER + LOWER_LIP_INNER[-2:0:-1]

# Skin tone sampling zones
SKIN_SAMPLE_LM = {
    "left_cheek":  [116, 117, 118, 119, 120],
    "right_cheek": [345, 346, 347, 348, 349],
    "forehead":    [10, 151, 9, 8, 107],
    "nose_bridge": [6, 197, 195, 5],
    "chin":        [175, 172, 136, 150],
}

# =========================
# PALETTE  — stored as BGR tuples (OpenCV convention)
# Verified: each tuple is (Blue, Green, Red)
# =========================
lipstick_palettes = {
    "💋 Aura Rouge Collection": {
        "Ruby Aura":      ( 30,  30, 200),   # pure bright red
        "Crimson Lith":   ( 15,  10, 140),   # deep crimson
        "Velvet Wine":    ( 20,  20, 170),   # velvet dark wine
    },
    "🌿 Quartz Nude Series": {
        "Silk Caramel":   ( 45,  75, 155),   # warm caramel
        "Satin Taupe":    (160, 180, 205),   # cool beige-taupe
        "Peach Cashmere": (150, 175, 220),   # soft peach-nude
    },
    "🌸 Pink Aura Collection": {
        "Blush Quartz":   (195, 170, 240),   # delicate blush pink
        "Rose Opal":      (120,  80, 210),   # medium rose pink
        "Fuchsia Neon":   (130,  20, 230),   # vivid fuchsia
    },
    "🍇 Berry Luxe Collection": {
        "Plum Crystal":   ( 75,  15, 120),   # rich medium plum
        "Mulberry Silk":  ( 95,  20, 155),   # mulberry berry-pink
        "Royal Berry":    ( 60,   8, 108),   # royal dark berry
    },
    "🌊 Coral Glow Collection": {
        "Sunset Coral":   ( 95, 135, 250),   # bright coral-pink
        "Amber Nude":     ( 60, 110, 240),   # warm amber-orange
        "Sienna Glow":    ( 35,  65, 175),   # earthy terracotta
    },
    "🔮 Velvet Plum Edition": {
        "Deep Amethyst":  ( 50,  10,  90),   # deep intense plum
        "Velvet Orchid":  ( 80,  20, 110),   # magenta orchid
        "Dark Dahlia":    ( 30,   5,  60),   # dramatic near-black plum
    }
}

SKIN_TONE_RECOMMENDATIONS = {
    "Fair":   ["Blush Quartz", "Rose Opal", "Plum Crystal", "Mulberry Silk", "Peach Cashmere"],
    "Light":  ["Rose Opal", "Peach Cashmere", "Sunset Coral", "Blush Quartz", "Silk Caramel"],
    "Medium": ["Satin Taupe", "Sunset Coral", "Amber Nude", "Ruby Aura", "Silk Caramel"],
    "Olive":  ["Sienna Glow", "Silk Caramel", "Crimson Lith", "Amber Nude", "Velvet Wine"],
    "Tan":    ["Velvet Wine", "Royal Berry", "Sienna Glow", "Velvet Orchid", "Deep Amethyst"],
    "Deep":   ["Deep Amethyst", "Dark Dahlia", "Royal Berry", "Fuchsia Neon", "Velvet Orchid"],
}
SKIN_TONE_COLORS = {
    "Fair": "#f5deb3", "Light": "#deb887", "Medium": "#c8a37a",
    "Olive": "#a0785a", "Tan": "#7a4f35", "Deep": "#3b1f0e",
}

ALL_SHADES = {}
for pal, shades in lipstick_palettes.items():
    for shade_name, bgr in shades.items():
        ALL_SHADES[shade_name] = {"palette": pal, "bgr": bgr}


# =========================
# SKIN TONE DETECTION
# =========================
def detect_skin_tone(image_bgr, landmarks, h, w):
    samples = []
    for zone, indices in SKIN_SAMPLE_LM.items():
        for idx in indices:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            patch = image_bgr[max(0, y-3):min(h, y+4), max(0, x-3):min(w, x+4)]
            if patch.size > 0:
                samples.append(patch.reshape(-1, 3))
    if not samples:
        return None, None
    all_pixels = np.vstack(samples).astype(np.float32)
    avg_bgr = all_pixels.mean(axis=0)
    avg_bgr_u8 = np.array([[avg_bgr]], dtype=np.uint8)
    avg_lab = cv2.cvtColor(avg_bgr_u8, cv2.COLOR_BGR2LAB)[0][0]
    L_norm = avg_lab[0] / 255.0 * 100.0
    if   L_norm >= 72: tone = "Fair"
    elif L_norm >= 62: tone = "Light"
    elif L_norm >= 52: tone = "Medium"
    elif L_norm >= 42: tone = "Olive"
    elif L_norm >= 32: tone = "Tan"
    else:              tone = "Deep"
    return tone, tuple(int(c) for c in avg_bgr)

# =========================
# LIP MASK
# =========================
def get_lip_mask_and_landmarks(image_bgr):
    h, w = image_bgr.shape[:2]
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    result = face_mesh.process(rgb)
    if not result.multi_face_landmarks:
        return None, None, None, h, w

    lm = result.multi_face_landmarks[0].landmark

    def pts(idx_list):
        return np.array(
            [(int(lm[i].x * w), int(lm[i].y * h)) for i in idx_list],
            dtype=np.int32,
        )

    outer_pts = pts(OUTER_LIP_LOOP)
    inner_pts = pts(INNER_LIP_LOOP)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [outer_pts], 255)   # outer lip boundary
    cv2.fillPoly(mask, [inner_pts], 255)   # inner area (fills any gap)

    # ── Exclude the mouth opening (dark gap between lips when mouth is open)
    # Use the four inner corners: left inner corner = 78, right = 308, top = 13, bottom = 14
    # Build a mouth-opening mask only if the mouth gap is significant
    mouth_top = int(lm[13].y * h)
    mouth_bot = int(lm[14].y * h)
    mouth_gap = mouth_bot - mouth_top
    if mouth_gap > 4:
        # The visible gap between upper and lower lip (inside the mouth)
        # defined by inner lower top edge and inner upper bottom edge
        gap_pts = pts([78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
                        308, 324, 318, 402, 317, 14, 87, 178, 88, 95])
        # Fill the inner mouth area black to exclude it, but only if it's
        # significantly below the upper inner and above the lower inner
        # (we keep the lips themselves, just remove the open gap)
        pass  # keep both polygons filled — they don't usually include open mouth

    # Upper lip sub-mask for gloss
    upper_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(upper_mask, [pts(UPPER_LIP_OUTER)], 255)
    upper_mask = cv2.bitwise_and(upper_mask, mask)

    return mask, upper_mask, lm, h, w

# =========================
# APPLY LIPSTICK — LAB color transfer (no hue wrap-around issue)
# =========================
def apply_lipstick(image_bgr: np.ndarray,
                   lip_mask: np.ndarray,
                   upper_lip_mask,
                   color_bgr: tuple,
                   alpha: float,
                   finish: str = "Glossy 💋") -> np.ndarray:
    """
    LAB-space 'Color' blend mode  (same as Photoshop Color layer):
      - a* and b* channels carry the hue + saturation → replaced by target color
      - L* (lightness) kept from original → preserves lip texture, wrinkles, sheen
    This works correctly for ALL colors (reds, pinks, nudes, dark berries).
    No HSV hue wrap-around problem.
    """
    h, w = image_bgr.shape[:2]
    img_f = image_bgr.astype(np.float32)

    # ── 1. Hard binary guard — nothing leaks outside ──────────────────
    hard_mask = (lip_mask > 0).astype(np.float32)
    hard_3d   = np.dstack([hard_mask] * 3)

    # ── 2. Feathered alpha weight (clamped inside hard mask) ──────────
    blur_k = 7
    mblur  = cv2.GaussianBlur(lip_mask, (blur_k, blur_k), 3)
    mblur  = cv2.bitwise_and(mblur, lip_mask)          # clamp — no bleed
    mask_f = mblur.astype(np.float32) / 255.0

    # weight per pixel (never exceeds alpha, never goes outside mask)
    w_map  = mask_f * alpha                            # shape (H,W)

    # ── 3. Convert image to LAB ───────────────────────────────────────
    img_lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    # ── 4. Target color in LAB ────────────────────────────────────────
    c_px  = np.array([[[color_bgr[0], color_bgr[1], color_bgr[2]]]], dtype=np.uint8)
    c_lab = cv2.cvtColor(c_px, cv2.COLOR_BGR2LAB)[0][0].astype(np.float32)
    tgt_L, tgt_a, tgt_b = c_lab[0], c_lab[1], c_lab[2]

    # ── 5. LAB "Color" blend ──────────────────────────────────────────
    result_lab = img_lab.copy()

    # a* channel (green↔red axis) — fully replaced by target
    result_lab[..., 1] = img_lab[..., 1] * (1 - w_map) + tgt_a * w_map
    # b* channel (blue↔yellow axis) — fully replaced by target
    result_lab[..., 2] = img_lab[..., 2] * (1 - w_map) + tgt_b * w_map
    # L* (lightness/texture) — keep ~75% original; nudge toward target for dark shades
    l_shift = w_map * 0.28
    result_lab[..., 0] = np.clip(
        img_lab[..., 0] * (1 - l_shift) + tgt_L * l_shift,
        0, 255,
    )

    # ── 6. Back to BGR ────────────────────────────────────────────────
    result_lab_u8 = np.clip(result_lab, 0, 255).astype(np.uint8)
    blended       = cv2.cvtColor(result_lab_u8, cv2.COLOR_LAB2BGR).astype(np.float32)

    # ── 7. Hard clamp — restore skin outside lip boundary ─────────────
    blended = img_f * (1 - hard_3d) + blended * hard_3d
    blended = np.clip(blended, 0, 255)

    # ── 8. Gloss highlight on upper lip (skip for Matte) ──────────────
    if finish != "Matte 💄" and upper_lip_mask is not None and upper_lip_mask.any():
        up_hard    = (upper_lip_mask > 0).astype(np.float32)
        up_hard_3d = np.dstack([up_hard] * 3)

        rows = np.where(upper_lip_mask.any(axis=1))[0]
        if len(rows) >= 2:
            y_top    = rows[0]
            y_bot    = rows[-1]
            centre_y = y_top + (y_bot - y_top) * 0.28
            sigma    = max(1.0, (y_bot - y_top) * 0.13)
            y_idx    = np.arange(h, dtype=np.float32)
            hs_1d    = np.clip(np.exp(-0.5 * ((y_idx - centre_y) / sigma) ** 2), 0, 1)
            hs_3d    = np.dstack([np.outer(hs_1d, np.ones(w, np.float32))] * 3)
        else:
            hs_3d = np.ones_like(blended, dtype=np.float32)

        gloss_strength = 0.45 if finish == "Glossy 💋" else 0.25
        A_n         = blended / 255.0
        screened    = np.clip((1 - (1 - A_n) * (1 - 0.30)) * 255.0, 0, 255)
        gloss_w     = up_hard_3d * hs_3d * alpha * gloss_strength

        # Save the fully-colored result (both lips) before adding gloss
        colored_both_lips = blended.copy()
        blended_with_gloss = np.clip(blended * (1 - gloss_w) + screened * gloss_w, 0, 255)

        # ✅ FIX: blend gloss ONLY onto upper lip pixels;
        #    lower lip keeps its colored result (not reset to img_f)
        blended = colored_both_lips * (1 - up_hard_3d) + blended_with_gloss * up_hard_3d

        # Restore pixels that are truly OUTSIDE the full lip boundary to original
        blended = img_f * (1 - hard_3d) + blended * hard_3d
        blended = np.clip(blended, 0, 255)

    return blended.astype(np.uint8)


# =========================
# SESSION STATE & INITIALIZATION
# =========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = "✨ AURALITH Home"
if "saved_looks" not in st.session_state:
    st.session_state.saved_looks = []
if "try_on_history" not in st.session_state:
    st.session_state.try_on_history = []
if "skin_tone_history" not in st.session_state:
    st.session_state.skin_tone_history = []
if "selected_shade" not in st.session_state:
    st.session_state.selected_shade = None
if "selected_palette" not in st.session_state:
    st.session_state.selected_palette = list(lipstick_palettes.keys())[0]
if "selected_opacity" not in st.session_state:
    st.session_state.selected_opacity = 0.65
if "selected_finish" not in st.session_state:
    st.session_state.selected_finish = "Glossy 💋"
if "login_mode" not in st.session_state:
    st.session_state.login_mode = "login"
if "show_locator" not in st.session_state:
    st.session_state.show_locator = False

# Helper to base64 encode PIL images
def pil_to_b64(img):
    import io
    import base64
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

# Responsive Swipe Slider HTML generator
def render_before_after_slider(before_bgr, after_bgr, split_pos):
    before_rgb = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2RGB)
    after_rgb = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2RGB)
    before_pil = Image.fromarray(before_rgb)
    after_pil = Image.fromarray(after_rgb)
    
    before_b64 = pil_to_b64(before_pil)
    after_b64 = pil_to_b64(after_pil)
    
    html_code = f"""
    <div style="position: relative; width: 100%; max-width: 480px; margin: 0 auto; aspect-ratio: 4/5; overflow: hidden; border-radius: 16px; border: 2px solid #d4a373; box-shadow: 0 10px 30px rgba(43, 16, 32, 0.15);">
        <!-- AFTER Image -->
        <img src="data:image/jpeg;base64,{after_b64}" style="position: absolute; left:0; top:0; width: 100%; height: 100%; object-fit: cover;" />
        
        <!-- BEFORE Image (clipped from right using pure responsive CSS clip-path) -->
        <img src="data:image/jpeg;base64,{before_b64}" style="position: absolute; left:0; top:0; width: 100%; height: 100%; object-fit: cover; clip-path: inset(0 {100 - split_pos}% 0 0);" />
        
        <!-- Split line indicator -->
        <div style="position: absolute; left: {split_pos}%; top: 0; bottom: 0; width: 2px; background-color: #fc2779; box-shadow: 0 0 10px #fc2779; pointer-events: none; z-index: 10;">
            <!-- Slider Handle knob -->
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 24px; height: 24px; border-radius: 50%; background: #ffffff; border: 2px solid #fc2779; box-shadow: 0 2px 6px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
                <span style="font-size: 8px; color: #fc2779; font-weight: bold;">↔</span>
            </div>
        </div>
        
        <!-- Labels -->
        <span style="position: absolute; left: 15px; top: 15px; background: rgba(43, 16, 32, 0.75); color: #ffffff; padding: 4px 10px; border-radius: 20px; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #d4a373; z-index: 11; pointer-events: none;">BEFORE</span>
        <span style="position: absolute; right: 15px; top: 15px; background: rgba(252, 39, 121, 0.85); color: #ffffff; padding: 4px 10px; border-radius: 20px; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #ffffff; z-index: 11; pointer-events: none;">AURALITH ART</span>
    </div>
    """
    return html_code

# Deterministic shade match confidence score based on skin tone
def get_match_confidence(shade_name, skin_tone):
    if not skin_tone:
        return 85
    recs = SKIN_TONE_RECOMMENDATIONS.get(skin_tone, [])
    val = int(hashlib.md5(f"{shade_name}_{skin_tone}".encode()).hexdigest(), 16)
    if shade_name in recs:
        return 90 + (val % 9)
    else:
        return 65 + (val % 25)

# Naming explanations & descriptions
SHADE_DESCRIPTIONS = {
    "Ruby Aura": "A deep, classic ruby red that leaves a powerful, timeless impression.",
    "Crimson Lith": "A velvet-textured royal crimson for glamorous, confident evenings.",
    "Velvet Wine": "A rich, full-bodied dark wine red for bold, futuristic styling.",
    "Silk Caramel": "A warm, buttery nude caramel that melts seamlessly into the lips.",
    "Satin Taupe": "A sophisticated, neutral cool-toned beige with a satin glow.",
    "Peach Cashmere": "A soft, pastel peach-nude that feels like luxurious cashmere.",
    "Blush Quartz": "A delicate, crystal-pink blush tone for a subtle daily radiance.",
    "Rose Opal": "A medium-rose pink with luminous crystalline highlights.",
    "Fuchsia Neon": "A high-intensity, electric fuchsia statement shade.",
    "Plum Crystal": "A rich, crystal-infused medium plum for an elegant, elevated pop.",
    "Mulberry Silk": "A soft berry-toned silk finish with deep warm undertones.",
    "Royal Berry": "A majestic, dark berry hue that complements all skin tones.",
    "Sunset Coral": "A bright, sun-kissed coral pink that radiates pure warmth.",
    "Amber Nude": "A glowing, warm amber-nude with a subtle golden aura.",
    "Sienna Glow": "A deep, earthy terracotta red with sunset reflections.",
    "Deep Amethyst": "A dark, intense purple-plum with amethyst crystal undertones.",
    "Velvet Orchid": "A vibrant, luxury magenta orchid that commands attention.",
    "Dark Dahlia": "A mysterious, near-black velvet plum for dramatic appeal."
}

# =========================
# NAVIGATION & ROUTING VIEWS
# =========================
import datetime
import pandas as pd

def render_login_page():
    st.write("")
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        logo_b64 = get_image_as_b64("auralith_logo.jpg")
        if logo_b64:
            st.markdown(f"""
            <div style="text-align: center; margin-top: 30px; margin-bottom: 35px;">
                <img src="{logo_b64}" style="height: 280px; width: 280px; object-fit: contain; border-radius: 30px; box-shadow: 0 15px 40px rgba(252, 39, 121, 0.1); border: 1.5px solid #e8e8f2; background-color: #ffffff; padding: 20px;">
            </div>
            """, unsafe_allow_html=True)
            
        if st.session_state.login_mode == "login":
            st.markdown("<h2 style='text-align: center; margin-top: 0; color: #2b1020; font-family: \"Montserrat\", sans-serif; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;'>✦ Welcome to AURALITH ✦</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #8b8b9c; font-size: 13px; margin-bottom: 25px;'>Sign in to access virtual try-on, automated skin-tone recommendations, and your Lookbook.</p>", unsafe_allow_html=True)
            
            username_input = st.text_input("Username", placeholder="Enter your identity", key="user_field")
            password_input = st.text_input("Password", type="password", placeholder="••••••••", key="pass_field")
            
            st.write("")
            if st.button("Log In ✦", use_container_width=True):
                if username_input.strip() == "":
                    st.error("Please enter a username.")
                elif password_input.strip() == "":
                    st.error("Please enter a password.")
                else:
                    if authenticate_user(username_input.strip(), password_input.strip()):
                        st.session_state.logged_in = True
                        st.session_state.username = username_input.strip()
                        st.session_state.saved_looks = load_user_looks(username_input.strip())
                        st.success("Successfully logged in!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password. Please try again.")
            
            st.markdown("<p style='text-align: center; font-size: 13px; margin-top: 15px; color: #8b8b9c;'>Don't have an account?</p>", unsafe_allow_html=True)
            if st.button("Create Account ✦", use_container_width=True):
                st.session_state.login_mode = "signup"
                st.rerun()
                
        else: # "signup"
            st.markdown("<h2 style='text-align: center; margin-top: 0; color: #2b1020; font-family: \"Montserrat\", sans-serif; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;'>✦ Join AURALITH ✦</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #8b8b9c; font-size: 13px; margin-bottom: 25px;'>Create a profile to save your beauty preferences and access try-on recommendations.</p>", unsafe_allow_html=True)
            
            new_user = st.text_input("Choose Username", placeholder="Enter a username", key="new_user_field")
            new_pass = st.text_input("Choose Password", type="password", placeholder="••••••••", key="new_pass_field")
            confirm_pass = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="confirm_pass_field")
            
            st.write("")
            if st.button("Register & Get Started ✦", use_container_width=True):
                if new_user.strip() == "":
                    st.error("Please choose a username.")
                elif new_pass.strip() == "":
                    st.error("Please enter a password.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                else:
                    success, msg = register_user(new_user.strip(), new_pass)
                    if success:
                        st.success(msg)
                        st.session_state.login_mode = "login"
                        st.rerun()
                    else:
                        st.error(msg)
            
            st.markdown("<p style='text-align: center; font-size: 13px; margin-top: 15px; color: #8b8b9c;'>Already have an account?</p>", unsafe_allow_html=True)
            if st.button("Back to Log In 🚪", use_container_width=True):
                st.session_state.login_mode = "login"
                st.rerun()

def render_sidebar():
    with st.sidebar:
        avatar_char = st.session_state.username[0].upper() if st.session_state.username else "A"
        st.markdown(f'<div class="sidebar-avatar">{avatar_char}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-header-title">{st.session_state.username}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-header-subtitle">AURALITH Member ✦</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigate", 
            ["✨ AURALITH Home", "💄 Virtual Try-On", "📸 Lookbook Dashboard"], 
            index=["✨ AURALITH Home", "💄 Virtual Try-On", "📸 Lookbook Dashboard"].index(st.session_state.current_page), 
            label_visibility="collapsed"
        )
        st.session_state.current_page = page
        
        st.divider()
        
        # Mini metrics
        total_looks = len(st.session_state.saved_looks)
        st.markdown(
            f'<div style="background: rgba(43,16,32,0.03); border-radius: 12px; padding: 12px; border: 1px solid rgba(212,163,115,0.2); text-align:center;">'
            f'<span style="font-size:10px; color:#8b8b9c; display:block; text-transform:uppercase; letter-spacing:1px;">Lookbook Canvas Count</span>'
            f'<span style="font-size:24px; font-weight:700; color:#fc2779;">{total_looks} Saved</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        st.write("")
        st.write("")
        if st.button("Logout 🚪", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.saved_looks = []
            st.session_state.current_page = "✨ AURALITH Home"
            st.rerun()

def render_home_page():
    # Hero Section
    st.markdown("""
    <div class="auralith-hero">
        <h1 style="color: #ffffff !important; font-size: 3.2rem; font-weight: 800; letter-spacing: 4px; margin: 0 0 10px 0; text-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;">A U R A L I T H</h1>
        <p style="font-size: 1.25rem; font-weight: 500; color: #f9f9fb; letter-spacing: 1.5px; margin-bottom: 25px;">Where Futuristic AI Meets Luxury Beauty</p>
        <p style="font-size: 0.95rem; line-height: 1.7; max-width: 750px; margin: 0 auto 30px auto; color: rgba(255,255,255,0.9); font-weight: 300;">
            AURALITH was created to redefine digital beauty experiences through artificial intelligence, personalized shade discovery, and luxury cosmetic innovation. 
            Upload your beauty canvas and experience your perfect shade.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # CTA
    _, col_cta_center, _ = st.columns([1, 2, 1])
    with col_cta_center:
        if st.button("Experience AI-Powered Lipstick Try-On ✦", use_container_width=True):
            st.session_state.current_page = "💄 Virtual Try-On"
            st.rerun()
            
    st.divider()
    
    # Feature Cards Showcase
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px; color:#2b1020;'>✦ The AURALITH Experience</h2>", unsafe_allow_html=True)
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 4px solid #fc2779 !important;">
            <h4 style="margin-top:0; color:#fc2779 !important;">🔮 Virtual Try-On Studio</h4>
            <p style="font-size: 13px; color:#555; line-height: 1.6; margin-bottom:0;">
                Experience hyper-realistic lipstick rendering in real-time. Seamlessly toggle between Matte 💄, Satin ✨, and Glossy 💋 finishes with adaptive transparency overlays.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with f_col2:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 4px solid #d4a373 !important;">
            <h4 style="margin-top:0; color:#d4a373 !important;">📐 Intelligent Shade Discovery</h4>
            <p style="font-size: 13px; color:#555; line-height: 1.6; margin-bottom:0;">
                Our advanced computer vision models sample multi-zone complexion landmarks to detect your skin tone and match you with optimized luxury shades.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with f_col3:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 4px solid #2b1020 !important;">
            <h4 style="margin-top:0; color:#2b1020 !important;">📸 Personalized Lookbook</h4>
            <p style="font-size: 13px; color:#555; line-height: 1.6; margin-bottom:0;">
                Curate your custom digital lookbook portfolio. Revisit previous beauty transformations, compare colors side-by-side, and manage your beauty collection.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # Signature Collections Catalog Showcase
    st.markdown("<h2 style='text-align: center; margin-bottom: 5px; color:#2b1020;'>✦ Luxury Signature Collections</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#8b8b9c; font-size:13px; margin-bottom:30px;'>Interactive catalog. Click 'Try ✦' on any shade to load it instantly in the Studio.</p>", unsafe_allow_html=True)
    
    # Grid of Collections
    collections_data = [
        {"name": "💋 Aura Rouge Collection", "key": "💋 Aura Rouge Collection", "desc": "Powerful, timeless classic reds designed to make an impact."},
        {"name": "🌿 Quartz Nude Series", "key": "🌿 Quartz Nude Series", "desc": "Velvety butter-nude tones that blend seamlessly into the lips."},
        {"name": "🌸 Pink Aura Collection", "key": "🌸 Pink Aura Collection", "desc": "Luminous crystalline pink shades reflecting fresh quartz energy."},
        {"name": "🍇 Berry Luxe Collection", "key": "🍇 Berry Luxe Collection", "desc": "Deep, majestic, berry-infused silk pigments for absolute luxury."},
        {"name": "🌊 Coral Glow Collection", "key": "🌊 Coral Glow Collection", "desc": "Sun-kissed, glowing orange-sienna pigments for a warm radiance."},
        {"name": "🔮 Velvet Plum Edition", "key": "🔮 Velvet Plum Edition", "desc": "Mysterious, intense violet and amethyst tones for dramatic elegance."}
    ]
    
    for i in range(0, 6, 2):
        col_left, col_right = st.columns(2)
        for idx, col_box in enumerate([col_left, col_right]):
            col_info = collections_data[i + idx]
            palette_name = col_info["key"]
            with col_box:
                st.markdown(f"""
                <div style="background: #ffffff; border-radius: 16px; border: 1.5px solid #e8e8f2; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.01);">
                    <h3 style="margin-top:0; color:#2b1020 !important; font-size:16px; border-bottom: 2px solid #fc2779; display:inline-block; padding-bottom:4px;">{col_info["name"]}</h3>
                    <p style="font-size:12px; color:#8b8b9c; margin: 10px 0 20px 0; height:32px; overflow:hidden;">{col_info["desc"]}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Show swatches and Try buttons
                shades = lipstick_palettes[palette_name]
                s_cols = st.columns(len(shades))
                for s_idx, (shade_name, bgr) in enumerate(shades.items()):
                    r, g, b = bgr[2], bgr[1], bgr[0]
                    with s_cols[s_idx]:
                        # Draw circle swatch
                        st.markdown(f"""
                        <div style="text-align: center; margin-bottom: 10px;">
                            <div title="{SHADE_DESCRIPTIONS.get(shade_name, '')}" style="width:28px; height:28px; border-radius:50%; background:rgb({r},{g},{b}); margin:0 auto 6px auto; border:2px solid #ffffff; box-shadow: 0 3px 8px rgba(43,16,32,0.18);"></div>
                            <span style="font-size:10px; font-weight:600; display:block; color:#2b1020; height:24px; overflow:hidden; line-height:1.2;">{shade_name}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("Try ✦", key=f"home_try_{shade_name}", use_container_width=True):
                            st.session_state.selected_shade = shade_name
                            st.session_state.selected_palette = palette_name
                            st.session_state.current_page = "💄 Virtual Try-On"
                            st.rerun()
        st.write("")

    st.divider()
    
    # Future Vision Roadmap
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px; color:#2b1020;'>✦ Future Vision of AURALITH</h2>", unsafe_allow_html=True)
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 3px solid #d4a373 !important;">
            <h5 style="margin-top:0; color:#2b1020 !important;">Real-Time AR Engine</h5>
            <p style="font-size: 11px; color:#666; line-height: 1.6; margin-bottom:0;">
                Integrating live browser camera feeds using WebGL shader matrices for low-latency facial landmark mapping and real-time color overlays.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with r_col2:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 3px solid #fc2779 !important;">
            <h5 style="margin-top:0; color:#2b1020 !important;">AI Beauty Assistant</h5>
            <p style="font-size: 11px; color:#666; line-height: 1.6; margin-bottom:0;">
                An intelligent conversational LLM chat companion that recommends lipstick textures and shades matching your clothes, event type, or mood.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with r_col3:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 3px solid #2b1020 !important;">
            <h5 style="margin-top:0; color:#2b1020 !important;">Luxury Shopping & Blending</h5>
            <p style="font-size: 11px; color:#666; line-height: 1.6; margin-bottom:0;">
                Enabling home delivery checkout and bespoke laboratory lipstick blending where pigment ratios are custom-mixed according to your skin analysis.
            </p>
        </div>
        """, unsafe_allow_html=True)

def render_try_on_page():
    # Brand Promo Banner
    st.markdown("""
    <div class="auralith-promo-banner">
        <span>✨ AURALITH ARTISTRY: Try on virtual shades, unlock complexion-based match recommendation profiles.</span>
        <span style="border: 1.5px solid white; padding: 4px 12px; border-radius: 20px; cursor: pointer; font-size:11px; font-weight:700;">EXPLORE MORE</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.title("💄 Virtual Try-On Studio")
    st.markdown("### ✨ Experience Your Perfect Shade")
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.markdown("#### 📷 Input Canvas")
        source = st.radio("Source", ["Upload Your Beauty Canvas 🎨", "Capture Your Silhouette 📷"], horizontal=True, label_visibility="collapsed")
        img_file = (
            st.camera_input("Capture Silhouette")
            if source == "Capture Your Silhouette 📷"
            else st.file_uploader("Upload Your Beauty Canvas", type=["jpg", "jpeg", "png"])
        )
    
    with col_right:
        st.markdown("#### 🎨 Color Selection")
        
        # Palette drop down
        default_palette = st.session_state.selected_palette
        if default_palette not in lipstick_palettes:
            default_palette = list(lipstick_palettes.keys())[0]
            
        palette = st.selectbox(
            "Collection", list(lipstick_palettes.keys()),
            index=list(lipstick_palettes.keys()).index(default_palette),
        )
        
        # Shade drop down
        shade_list = list(lipstick_palettes[palette].keys())
        default_shade = st.session_state.selected_shade
        default_shade_idx = 0
        if default_shade in shade_list:
            default_shade_idx = shade_list.index(default_shade)
            
        shade = st.selectbox("Shade Profile", shade_list, index=default_shade_idx)
        
        # Sync values back to state
        st.session_state.selected_shade = shade
        st.session_state.selected_palette = palette
        
        # Color preview swatches — BGR→RGB for CSS
        circles_html = ""
        for name, c in lipstick_palettes[palette].items():
            border = "4px solid #d4a373" if name == shade else "2px solid rgba(255,255,255,0.4)"
            r, g, b = c[2], c[1], c[0]
            circles_html += (
                f'<div title="{name}: {SHADE_DESCRIPTIONS.get(name, "")}" style="display:inline-block;width:30px;height:30px;'
                f'border-radius:50%;background:rgb({r},{g},{b});'
                f'margin:4px;border:{border};box-shadow:0 3px 6px rgba(0,0,0,0.15);"></div>'
            )
        st.markdown(circles_html, unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:11px; color:#8b8b9c; font-style:italic; margin-top:5px;'>\"{SHADE_DESCRIPTIONS.get(shade, '')}\"</p>", unsafe_allow_html=True)
        
        # Control parameters
        opacity = st.slider("Texture Coverage (Opacity)", 0.20, 1.00, st.session_state.selected_opacity, step=0.05)
        st.session_state.selected_opacity = opacity
        
        finishes = ["Glossy 💋", "Satin ✨", "Matte 💄"]
        default_finish = st.session_state.selected_finish
        default_finish_idx = finishes.index(default_finish) if default_finish in finishes else 0
        
        finish  = st.selectbox("Cosmetic Finish", finishes, index=default_finish_idx)
        st.session_state.selected_finish = finish

    # Try-On rendering execution
    if img_file:
        image_pil = Image.open(img_file).convert("RGB")
        image_rgb = np.array(image_pil)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        # Sequenced luxury loaders
        loading_placeholder = st.empty()
        steps = [
            "✦ Mapping facial geometry landmarks...",
            "✦ Segmenting vermillion lip contours...",
            "✦ Calibrating mouth posture values...",
            "✦ Inspecting complexion lightness profile..."
        ]
        import time
        for step in steps:
            loading_placeholder.markdown(f"<p style='font-size:13px; color:#fc2779; font-weight:600; font-style:italic; margin:10px 0;'>{step}</p>", unsafe_allow_html=True)
            time.sleep(0.15)
        loading_placeholder.empty()
        
        mask, upper_mask, landmarks, h, w = get_lip_mask_and_landmarks(image_bgr)
            
        if mask is None:
            st.error("❌ AURALITH AI could not locate a face in this canvas. Ensure adequate lighting and front alignment.")
            st.stop()
            
        if mask.sum() == 0:
            st.error("❌ Lip contours not isolated correctly. Try capturing with a neutral facial expression.")
            st.stop()
            
        # Detect Skin Tone
        skin_tone, _ = detect_skin_tone(image_bgr, landmarks, h, w)
        recommended_shades = SKIN_TONE_RECOMMENDATIONS.get(skin_tone, [])
        
        # Tone Badge
        tone_css = SKIN_TONE_COLORS.get(skin_tone, "#888")
        txt_col  = "#fff" if skin_tone in ("Olive", "Tan", "Deep", "Medium") else "#1a1a1a"
        st.markdown(
            f'<div class="skin-badge" style="background:{tone_css};color:{txt_col};">'
            f'🎨 Complexion Detected: <b>{skin_tone}</b></div>',
            unsafe_allow_html=True,
        )
        
        # Display AI Undertone Insights Panel
        undertones_map = {
            "Fair": "cool pink, berry rose, and soft mauve undertones. They neutralize pale complexions and add a healthy flush.",
            "Light": "peach, warm coral, and pastel pink undertones. These enhance light complexions with a fresh, youthful glow.",
            "Medium": "warm honey, terracotta, and soft beige-brown. These balance medium skin values and add natural elegance.",
            "Olive": "earthy brick, deep coral, and bronzed terracotta. These complement warm olive complexions with a sun-kissed finish.",
            "Tan": "warm caramel, rich burgundy, and vibrant burnt orange. These amplify tan skin tones with maximum contrast.",
            "Deep": "deep plum, dark burgundy, fuchsia magenta, and near-black wine. These define deep complexions with rich, dramatic pigments."
        }
        undertones = undertones_map.get(skin_tone, "harmonious pigments matching your complexion profile.")
        st.markdown(f"""
        <div class="glass-card" style="background: rgba(212, 163, 115, 0.05) !important; border: 1px solid #d4a373 !important; padding:15px; margin-top:5px; margin-bottom:15px;">
            <span style="font-size:10px; text-transform:uppercase; letter-spacing:1px; color:#8b8b9c; font-weight:700; display:block; margin-bottom:5px;">✦ AI Beauty Insights</span>
            <p style="font-size:12px; color:#2b1020; margin-bottom: 0; line-height:1.6;">
                Your detected complexion profile is <b>{skin_tone}</b>. 
                Our AI beauty engine recommends shades containing <b>{undertones}</b>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Recommendations Pills & Quick Select buttons
        if recommended_shades:
            st.markdown('<div class="rec-header">✨ RECOMMENDED SHADES FOR YOUR PROFILE</div>', unsafe_allow_html=True)
            pills = ""
            for rs in recommended_shades:
                if rs in ALL_SHADES:
                    bgr = ALL_SHADES[rs]["bgr"]
                    r, g, b = bgr[2], bgr[1], bgr[0]
                    pills += f'<span class="shade-pill" style="background:rgb({r},{g},{b});">{rs}</span>'
            st.markdown(pills, unsafe_allow_html=True)
            
            rec_cols = st.columns(len(recommended_shades))
            for i, rs in enumerate(recommended_shades):
                if rs in ALL_SHADES:
                    with rec_cols[i]:
                        # Deterministic confidence for this recommendation
                        conf_rec = get_match_confidence(rs, skin_tone)
                        if st.button(f"👄 {rs}\n({conf_rec}%)", key=f"rec_{rs}"):
                            st.session_state.selected_shade = rs
                            st.session_state.selected_palette = ALL_SHADES[rs]["palette"]
                            st.rerun()
                            
        st.divider()
        
        # Resolve active color BGR
        active_shade = st.session_state.selected_shade or shade
        if active_shade in ALL_SHADES:
            final_color = ALL_SHADES[active_shade]["bgr"]
            palette = ALL_SHADES[active_shade]["palette"]
        else:
            final_color = lipstick_palettes[palette][shade]
            
        # Apply lipstick rendering
        with st.spinner("Rendering realistic pigments..."):
            result_bgr = apply_lipstick(
                image_bgr, mask, upper_mask, final_color, opacity, finish
            )
            # Log try-on to history
            if not st.session_state.try_on_history or st.session_state.try_on_history[-1]["shade"] != active_shade:
                st.session_state.try_on_history.append({
                    "shade": active_shade,
                    "palette": palette,
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
        
        # Calculate match confidence score
        confidence = get_match_confidence(active_shade, skin_tone)
        
        # Match Confidence progress bar UI
        st.markdown(f"""
        <div style="margin: 15px 0 25px 0;">
            <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:700; color:#2b1020; text-transform:uppercase; letter-spacing:0.5px;">
                <span>AI Complexion Match Score</span>
                <span style="color:#fc2779;">{confidence}% Match Score</span>
            </div>
            <div style="background-color:#e8e8f2; border-radius:10px; height:8px; width:100%; margin-top:6px; overflow:hidden;">
                <div style="background: linear-gradient(90deg, #fc2779 0%, #d4a373 100%); width:{confidence}%; height:100%; border-radius:10px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Before / After Comparison slider
        st.markdown("<h4 style='color:#2b1020;'>Transformation Preview ✨</h4>", unsafe_allow_html=True)
        split_pos = st.slider("Before vs After Slider", 0, 100, 50, label_visibility="collapsed")
        
        slider_html = render_before_after_slider(image_bgr, result_bgr, split_pos)
        components.html(slider_html, height=520)
        
        st.write("")
        
        # Side by side fallback
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.image(image_rgb, caption="Original Silhouette Canvas", use_container_width=True)
        with col_s2:
            st.image(result_rgb, caption=f"AURALITH Finish: {active_shade} ({finish})", use_container_width=True)
            
        st.success(f"✅ Applied **{active_shade}** ({finish}) | Opacity: {opacity:.0%} | Match: **{confidence}%**")
        
        # Save Look Button
        st.write("")
        col_save, _ = st.columns([1, 1])
        with col_save:
            if st.button("Save To Lookbook ✦", use_container_width=True):
                # Avoid duplicate looks
                already_saved = any(
                    look["shade"] == active_shade and
                    look["finish"] == finish and
                    look["opacity"] == opacity
                    for look in st.session_state.saved_looks
                )
                if already_saved:
                    st.info("This look is already saved in your Lookbook.")
                else:
                    look_id = str(uuid.uuid4())
                    user_dir = get_user_profile_dir(st.session_state.username)
                    user_images_dir = os.path.join(user_dir, "images")
                    os.makedirs(user_images_dir, exist_ok=True)
                    
                    img_filename = f"{look_id}.png"
                    img_path = os.path.join(user_images_dir, img_filename)
                    
                    # Save the tried-on result image
                    try:
                        cv2.imwrite(img_path, result_bgr)
                        image_saved = True
                    except Exception as e:
                        image_saved = False
                        st.error(f"Failed to save preview image: {str(e)}")
                        
                    look_data = {
                        "id": look_id,
                        "shade": active_shade,
                        "palette": palette,
                        "finish": finish,
                        "opacity": opacity,
                        "skin_tone": skin_tone or "Not Detected",
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "bgr": tuple(int(c) for c in final_color),
                        "image_path": img_path if image_saved else ""
                    }
                    st.session_state.saved_looks.append(look_data)
                    save_user_looks(st.session_state.username, st.session_state.saved_looks)
                    
                    if skin_tone and skin_tone not in st.session_state.skin_tone_history:
                        st.session_state.skin_tone_history.append(skin_tone)
                    st.success("Beauty canvas saved to your Lookbook! View it in your Lookbook tab. ✦")

def render_dashboard_page():
    st.title("📸 AURALITH Lookbook ✦")
    st.markdown("### ✨ Your Personalized Digital Beauty Portfolio")
    
    # Calculate Metrics
    total_saved = len(st.session_state.saved_looks)
    
    # Get last skin tone
    last_skin_tone = "Not Detected"
    for look in reversed(st.session_state.saved_looks):
        if look["skin_tone"] != "Not Detected":
            last_skin_tone = look["skin_tone"]
            break
            
    # Favorite collection
    fav_palette = "None"
    if st.session_state.saved_looks:
        p_list = [l["palette"] for l in st.session_state.saved_looks]
        fav_palette = max(set(p_list), key=p_list.count)
    elif st.session_state.try_on_history:
        p_list = [l["palette"] for l in st.session_state.try_on_history]
        fav_palette = max(set(p_list), key=p_list.count)
        
    # Favorite finish
    fav_finish = "None"
    if st.session_state.saved_looks:
        f_list = [l["finish"] for l in st.session_state.saved_looks]
        fav_finish = max(set(f_list), key=f_list.count)
        
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card">
            <div class="metric-title">Bespoke Canvas Saved</div>
            <div class="metric-value">💖 {total_saved}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Complexion Profile</div>
            <div class="metric-value">🎨 {last_skin_tone}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Preferred Collection</div>
            <div class="metric-value">💄 {fav_palette.replace("💋 ", "").replace("🌸 ", "").replace("🌿 ", "").replace("🔥 ", "").replace("🍇 ", "").replace("🔮 ", "").replace("🌊 ", "")}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Preferred Finish</div>
            <div class="metric-value">✨ {fav_finish.replace(" 💋", "").replace(" ✨", "").replace(" 💄", "")}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Saved Looks Gallery Manager
    st.markdown("### 📸 Your Saved Try-On Gallery")
    if not st.session_state.saved_looks:
        st.info("No saved looks found yet. Try on different lipstick shades in the Virtual Try-On tab, and click 'Save To Lookbook ✦' to create your lookbook!")
    else:
        # Checkboxes for Compare Looks
        st.markdown("<p style='color:#8b8b9c; font-size:12px;'>Select multiple looks below to trigger the Comparison Studio overlay.</p>", unsafe_allow_html=True)
        
        # Grid layout for looks
        cols = st.columns(3)
        for idx, look in enumerate(st.session_state.saved_looks):
            col_idx = idx % 3
            with cols[col_idx]:
                # Render the image preview at the top of the column
                if "image_path" in look and os.path.exists(look["image_path"]):
                    st.image(look["image_path"], use_container_width=True)
                else:
                    st.markdown('<div style="width:100%; height:200px; border-radius:12px; background:rgba(255,255,255,0.02); display:flex; align-items:center; justify-content:center; color:#555; font-size:12px; border: 1px solid rgba(255,255,255,0.05); margin-bottom:10px;">No Image Preview</div>', unsafe_allow_html=True)
                
                # Metadata card
                r, g, b = look["bgr"][2], look["bgr"][1], look["bgr"][0]
                st.markdown(f"""
                <div class="look-card" style="margin-top: -10px; background: rgba(255,255,255,0.85); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                        <div style="width: 14px; height: 14px; border-radius: 50%; background: rgb({r},{g},{b}); border: 1px solid rgba(0,0,0,0.15);"></div>
                        <h4 style="margin: 0; font-size: 14px; color:#2b1020 !important;">{look["shade"]}</h4>
                    </div>
                    <div style="font-size: 11px; color: #555; line-height: 1.5; margin-bottom: 5px;">
                        <strong>Collection:</strong> {look["palette"]}<br>
                        <strong>Finish:</strong> {look["finish"]}<br>
                        <strong>Opacity:</strong> {look["opacity"]:.0%}<br>
                        <strong>Skin Tone:</strong> {look["skin_tone"]}<br>
                        <span style="font-size: 9px; color: #888;">Saved: {look["timestamp"]}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Checkbox for comparison
                st.checkbox("Select to Compare ✨", key=f"comp_{look['id']}")
                
                btn1, btn2 = st.columns(2)
                with btn1:
                    if st.button("Apply Again 💄", key=f"apply_{idx}", use_container_width=True):
                        st.session_state.selected_shade = look["shade"]
                        st.session_state.selected_palette = look["palette"]
                        st.session_state.selected_finish = look["finish"]
                        st.session_state.selected_opacity = look["opacity"]
                        st.session_state.current_page = "💄 Virtual Try-On"
                        st.rerun()
                with btn2:
                    if st.button("Delete Look 🗑️", key=f"delete_{idx}", use_container_width=True):
                        look_to_delete = st.session_state.saved_looks.pop(idx)
                        if "image_path" in look_to_delete and os.path.exists(look_to_delete["image_path"]):
                            try:
                                os.remove(look_to_delete["image_path"])
                            except Exception:
                                pass
                        save_user_looks(st.session_state.username, st.session_state.saved_looks)
                        st.rerun()
        
        # Renders the Comparison Studio if multiple items are checked
        selected_compare_looks = []
        for look in st.session_state.saved_looks:
            if st.session_state.get(f"comp_{look['id']}"):
                selected_compare_looks.append(look)
                
        if len(selected_compare_looks) > 1:
            st.divider()
            st.markdown("### ✨ Comparison Studio Overlay")
            st.markdown("Comparing your selected beauty canvases side-by-side:")
            comp_cols = st.columns(len(selected_compare_looks))
            for c_idx, cl in enumerate(selected_compare_looks):
                with comp_cols[c_idx]:
                    if "image_path" in cl and os.path.exists(cl["image_path"]):
                        st.image(cl["image_path"], use_container_width=True)
                    st.markdown(f"""
                    <div style="background: rgba(212, 163, 115, 0.1); border-radius: 12px; padding: 12px; border: 1.5px solid #d4a373; text-align: center; margin-top:5px;">
                        <h4 style="margin: 0 0 5px 0; font-size:14px; color:#2b1020 !important;">{cl["shade"]}</h4>
                        <span style="font-size:11px; color:#555;">Finish: {cl["finish"]}<br>Match: {get_match_confidence(cl["shade"], cl["skin_tone"])}%</span>
                    </div>
                    """, unsafe_allow_html=True)
            st.divider()
                        
    # Recommendations based on profile
    st.markdown("---")
    st.markdown("### ✨ Personalized Complexion Suggestions")
    last_detected_skin = "Medium"
    for look in reversed(st.session_state.saved_looks):
        if look["skin_tone"] != "Not Detected":
            last_detected_skin = look["skin_tone"]
            break
            
    st.markdown(f"Based on your profile, your detected skin tone is **{last_detected_skin}**. Here are recommended shades for your complexion:")
    
    rec_shades = SKIN_TONE_RECOMMENDATIONS.get(last_detected_skin, [])
    if rec_shades:
        rec_cols = st.columns(len(rec_shades))
        for idx, shade_name in enumerate(rec_shades):
            if shade_name in ALL_SHADES:
                shade_info = ALL_SHADES[shade_name]
                bgr = shade_info["bgr"]
                r, g, b = bgr[2], bgr[1], bgr[0]
                with rec_cols[idx]:
                    conf = get_match_confidence(shade_name, last_detected_skin)
                    st.markdown(f"""
                    <div style="background: rgba(255,255,255,0.6); padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #e8e8f2; box-shadow: 0 4px 10px rgba(0,0,0,0.01);">
                        <div style="width: 24px; height: 24px; border-radius: 50%; background: rgb({r},{g},{b}); margin: 0 auto 6px auto; border: 1px solid rgba(0,0,0,0.1);"></div>
                        <span style="font-size:11px; font-weight:600; display:block; color:#2b1020; height:32px; overflow:hidden; line-height:1.2;">{shade_name}</span>
                        <span style="font-size:10px; color:#fc2779; font-weight:700;">{conf}% Match</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Experience ✦", key=f"rec_dash_{shade_name}", use_container_width=True):
                        st.session_state.selected_shade = shade_name
                        st.session_state.selected_palette = shade_info["palette"]
                        st.session_state.current_page = "💄 Virtual Try-On"
                        st.rerun()

# -----------------
# CONTROL FLOW & ROUTING
# -----------------
def render_nykaa_header():
    # Render header inside a bordered container card using st.container(border=True)
    with st.container(border=True):
        col_logo, col_search, col_nav = st.columns([0.5, 1.8, 2.7], vertical_alignment="center")
        
        with col_logo:
            logo_b64 = get_image_as_b64("auralith_logo.jpg")
            if logo_b64:
                st.markdown(f'<div style="display:flex; align-items:center;"><img src="{logo_b64}" alt="AURALITH" style="height: 58px; object-fit: contain;"></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="auralith-logo">AURALITH<span>✦</span></div>', unsafe_allow_html=True)
                
        with col_search:
            search_query = st.text_input(
                "Search",
                placeholder="🔍 Search for luxury shades (e.g. Ruby, Rose)...",
                label_visibility="collapsed",
                key="header_search_input"
            )
            if search_query:
                matched_shade = None
                for s_name in ALL_SHADES.keys():
                    if search_query.lower() in s_name.lower():
                        matched_shade = s_name
                        break
                if matched_shade:
                    st.session_state.selected_shade = matched_shade
                    st.session_state.selected_palette = ALL_SHADES[matched_shade]["palette"]
                    st.session_state.current_page = "💄 Virtual Try-On"
                    st.toast(f"Found and loaded shade: {matched_shade} 💋")
                    st.rerun()
                else:
                    st.toast(f"No shades found matching '{search_query}' 🔍", icon="❌")
                    
        with col_nav:
            nav_cols = st.columns(3)
            bag_count = len(st.session_state.saved_looks)
            
            with nav_cols[0]:
                if st.button("✦ Studio", key="nav_studio_btn", use_container_width=True):
                    st.session_state.current_page = "💄 Virtual Try-On"
                    st.rerun()
            with nav_cols[1]:
                if st.button("✦ Locator", key="nav_locator_btn", use_container_width=True):
                    st.session_state.current_page = "✨ AURALITH Home"
                    st.session_state.show_locator = True
                    st.rerun()
            with nav_cols[2]:
                if st.button(f"✦ Bag ({bag_count})", key="nav_bag_btn", use_container_width=True):
                    st.session_state.current_page = "📸 Lookbook Dashboard"
                    st.rerun()

if not st.session_state.logged_in:
    render_login_page()
else:
    render_nykaa_header()
    render_sidebar()
    
    # Store locator display helper
    if st.session_state.get("show_locator"):
        st.markdown("""
        <div class="glass-card" style="background: rgba(212, 163, 115, 0.08) !important; border: 2px solid #d4a373 !important; padding: 25px; margin-bottom: 25px; border-radius: 16px;">
            <h3 style="margin-top:0; color:#2b1020 !important;">📍 AURALITH Store Locator</h3>
            <p style="font-size: 14px; color:#555; line-height: 1.6; margin-bottom: 15px;">
                Visit our signature boutiques to experience bespoke personalized color analysis and laboratory shade blending in person:
            </p>
            <ul style="font-size: 13px; color:#2b1020; line-height: 1.8; margin-left: 20px;">
                <li><strong>📍 Paris Flagship:</strong> 18 Rue de la Paix, 75002 Paris</li>
                <li><strong>📍 New York Fifth Avenue:</strong> 740 Fifth Avenue, New York, NY 10019</li>
                <li><strong>📍 Mumbai Palladium:</strong> The Palladium Mall, Lower Parel, Mumbai 400013</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Close Locator ✖", key="close_loc_btn"):
            st.session_state.show_locator = False
            st.rerun()
            
    if st.session_state.current_page == "✨ AURALITH Home":
        render_home_page()
    elif st.session_state.current_page == "💄 Virtual Try-On":
        render_try_on_page()
    elif st.session_state.current_page == "📸 Lookbook Dashboard":
        render_dashboard_page()