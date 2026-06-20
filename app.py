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
# LIVE BEAUTY STUDIO CUSTOM COMPONENT
# =========================
live_beauty_studio = components.declare_component(
    "live_beauty_studio",
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_beauty_component")
)

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

def calculate_beauty_analytics(looks_list):
    if not looks_list:
        return {
            "preferred_finish": "None",
            "favorite_collection": "None",
            "most_used_shade": "None",
            "average_match_score": 0,
            "average_beauty_score": 0,
            "last_detected_complexion": "Not Detected",
            "last_detected_undertone": "Not Detected",
            "personality_summary": "Start saving looks to discover and define your signature beauty style."
        }
        
    finishes = [l["finish"] for l in looks_list]
    pref_finish = max(set(finishes), key=finishes.count) if finishes else "None"
    
    palettes = [l["palette"] for l in looks_list]
    fav_palette = max(set(palettes), key=palettes.count) if palettes else "None"
    
    shades = [l["shade"] for l in looks_list]
    most_used_shade = max(set(shades), key=shades.count) if shades else "None"
    
    total_score = 0
    total_b_score = 0
    count = 0
    last_complexion = "Not Detected"
    last_undertone = "Not Detected"
    
    for l in looks_list:
        tone = l.get("skin_tone", "Not Detected")
        undertone = l.get("undertone", "Not Detected")
        
        if tone != "Not Detected" and tone != "None":
            last_complexion = tone
        if undertone != "Not Detected" and undertone != "None":
            last_undertone = undertone
            
        score, _ = get_match_score(l["shade"], tone if tone != "Not Detected" else None, l["finish"])
        b_score, _, _ = get_beauty_score_and_harmony(score, l["shade"], undertone if undertone != "Not Detected" else None)
        
        total_score += score
        total_b_score += b_score
        count += 1
        
    avg_score = int(total_score / count) if count > 0 else 0
    avg_b_score = int(total_b_score / count) if count > 0 else 0
    
    # Generate dynamic personality summary
    clean_finish = pref_finish.replace(" 💋", "").replace(" ✨", "").replace(" 💄", "").replace(" 🪄", "").replace(" 💎", "").lower()
    clean_collection = fav_palette.replace("💋 ", "").replace("🌸 ", "").replace("🌿 ", "").replace("🍇 ", "").replace("🌊 ", "").replace("🔮 ", "").lower()
    
    if "rouge" in clean_collection or "plum" in clean_collection or "berry" in clean_collection:
        vibe = "sophisticated evening-inspired looks"
    else:
        vibe = "effortless daily-wear radiance"
        
    personality_summary = f"Your beauty profile reflects a preference for {clean_finish} {most_used_shade.lower()} tones, luxury {clean_collection} collections, and {vibe}."
    
    return {
        "preferred_finish": pref_finish,
        "favorite_collection": fav_palette,
        "most_used_shade": most_used_shade,
        "average_match_score": avg_score,
        "average_beauty_score": avg_b_score,
        "last_detected_complexion": last_complexion,
        "last_detected_undertone": last_undertone,
        "personality_summary": personality_summary
    }

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
            data = json.load(f)
            if isinstance(data, dict) and "looks" in data:
                return data["looks"]
            return data
    except Exception:
        return []

def save_user_looks(username, looks_list):
    user_dir = get_user_profile_dir(username)
    looks_file = os.path.join(user_dir, "looks.json")
    
    os.makedirs(user_dir, exist_ok=True)
    
    try:
        analytics = calculate_beauty_analytics(looks_list)
        data = {
            "looks": looks_list,
            "analytics": analytics
        }
        with open(looks_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
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

st.html("""
<script>
(function() {
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
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
  }
})();
</script>
""", unsafe_allow_javascript=True)

# =========================
# MEDIAPIPE
# =========================
@st.cache_resource
def load_mediapipe():
    import sys
    try:
        import mediapipe.python.solutions as solutions
        return solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.4,
        )
    except Exception as e1:
        try:
            class FaceMeshWrapper:
                def __init__(self, model_path='model/face_landmarker.task'):
                    from mediapipe.tasks import python
                    from mediapipe.tasks.python import vision
                    
                    base_options = python.BaseOptions(model_asset_path=model_path)
                    options = vision.FaceLandmarkerOptions(
                        base_options=base_options,
                        output_face_blendshapes=False,
                        output_facial_transformation_matrixes=False,
                        num_faces=1
                    )
                    self.detector = vision.FaceLandmarker.create_from_options(options)

                def process(self, rgb_image):
                    import mediapipe as mp
                    # Wrap raw numpy rgb image in mp.Image
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                    detection_result = self.detector.detect(mp_image)
                    
                    class LegacyFaceLandmarks:
                        def __init__(self, landmark_list):
                            self.landmark = landmark_list
                            
                    class LegacyResult:
                        def __init__(self, face_landmarks):
                            if face_landmarks:
                                self.multi_face_landmarks = [LegacyFaceLandmarks(face_landmarks[0])]
                            else:
                                self.multi_face_landmarks = None
                                
                    return LegacyResult(detection_result.face_landmarks)
            
            return FaceMeshWrapper('model/face_landmarker.task')
        except Exception as e2:
            import traceback
            st.error("### 🔍 MediaPipe Diagnostic Report")
            st.write(f"**Python Version**: {sys.version}")
            
            mp_loaded = "Not Loaded"
            mp_path = "N/A"
            mp_contents = []
            try:
                import mediapipe as mp
                mp_loaded = getattr(mp, "__version__", "unknown")
                mp_path = getattr(mp, "__file__", "unknown")
                if mp_path and mp_path != "unknown":
                    mp_dir = os.path.dirname(mp_path)
                    mp_contents = os.listdir(mp_dir)
            except Exception as mpe:
                mp_loaded = f"Error: {mpe}"
                
            st.write(f"**MediaPipe Version**: {mp_loaded}")
            st.write(f"**MediaPipe Path**: {mp_path}")
            st.write(f"**MediaPipe Dir Contents**: {mp_contents}")
            
            try:
                import google.protobuf as pb
                st.write(f"**Protobuf Version**: {pb.__version__}")
            except Exception as pbe:
                st.write(f"**Protobuf Error**: {pbe}")
            
            st.write("**Detailed Import Traceback (Legacy Solutions Error)**:")
            st.code(traceback.format_exc())
            st.write(f"**Modern Tasks API Error**: {e2}")
            
            st.stop()

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
        "Scarlet Ember":  ( 20,  40, 230),   # bright scarlet red
        "Rose Garnet":    ( 50,  20, 160),   # deep rose-garnet red
    },
    "🌿 Quartz Nude Series": {
        "Silk Caramel":   ( 45,  75, 155),   # warm caramel
        "Satin Taupe":    (160, 180, 205),   # cool beige-taupe
        "Peach Cashmere": (150, 175, 220),   # soft peach-nude
        "Nude Quartz":    (170, 185, 215),   # delicate soft nude-rose
        "Almond Silk":    (110, 135, 190),   # warm toasted almond
    },
    "🌸 Pink Aura Collection": {
        "Blush Quartz":   (195, 170, 240),   # delicate blush pink
        "Rose Opal":      (120,  80, 210),   # medium rose pink
        "Fuchsia Neon":   (130,  20, 230),   # vivid fuchsia
        "Petal Glow":     (180, 150, 235),   # soft warm petal pink
        "Pink Sapphire":  (160,  60, 235),   # luminous vibrant pink
    },
    "🍇 Berry Luxe Collection": {
        "Plum Crystal":   ( 75,  15, 120),   # rich medium plum
        "Mulberry Silk":  ( 95,  20, 155),   # mulberry berry-pink
        "Royal Berry":    ( 60,   8, 108),   # royal dark berry
        "Blackberry Muse": ( 55,  10,  95),   # deep dark blackberry
        "Velvet Mulberry": ( 80,  25, 135),   # rich warm mulberry
    },
    "🌊 Coral Glow Collection": {
        "Sunset Coral":   ( 95, 135, 250),   # bright coral-pink
        "Amber Nude":     ( 60, 110, 240),   # warm amber-orange
        "Sienna Glow":    ( 35,  65, 175),   # earthy terracotta
        "Coral Bloom":    ( 90, 120, 245),   # soft radiant coral
        "Peach Sunrise":  (110, 150, 255),   # peachy orange-pink
    },
    "🔮 Velvet Plum Edition": {
        "Deep Amethyst":  ( 50,  10,  90),   # deep intense plum
        "Velvet Orchid":  ( 80,  20, 110),   # magenta orchid
        "Dark Dahlia":    ( 30,   5,  60),   # dramatic near-black plum
        "Midnight Plum":  ( 40,   5,  70),   # very dark midnight plum
        "Violet Eclipse": (100,  15,  95),   # deep royal violet-plum
    }
}

SKIN_TONE_RECOMMENDATIONS = {
    "Fair":   ["Blush Quartz", "Rose Opal", "Plum Crystal", "Mulberry Silk", "Peach Cashmere", "Petal Glow", "Nude Quartz", "Pink Sapphire"],
    "Light":  ["Rose Opal", "Peach Cashmere", "Sunset Coral", "Blush Quartz", "Silk Caramel", "Almond Silk", "Coral Bloom", "Petal Glow"],
    "Medium": ["Satin Taupe", "Sunset Coral", "Amber Nude", "Ruby Aura", "Silk Caramel", "Peach Sunrise", "Almond Silk", "Scarlet Ember"],
    "Olive":  ["Sienna Glow", "Silk Caramel", "Crimson Lith", "Amber Nude", "Velvet Wine", "Rose Garnet", "Velvet Mulberry", "Coral Bloom"],
    "Tan":    ["Velvet Wine", "Royal Berry", "Sienna Glow", "Velvet Orchid", "Deep Amethyst", "Velvet Mulberry", "Violet Eclipse", "Scarlet Ember"],
    "Deep":   ["Deep Amethyst", "Dark Dahlia", "Royal Berry", "Fuchsia Neon", "Velvet Orchid", "Midnight Plum", "Blackberry Muse", "Violet Eclipse"],
}
SKIN_TONE_COLORS = {
    "Fair": "#f5deb3", "Light": "#deb887", "Medium": "#c8a37a",
    "Olive": "#a0785a", "Tan": "#7a4f35", "Deep": "#3b1f0e",
}

ALL_SHADES = {}

SHADE_METADATA = {
    # Reds
    "Ruby Aura": {"mood": "Bold & Confident", "occasion": "Evening Event"},
    "Crimson Lith": {"mood": "Seductive & Regal", "occasion": "Gala & Red Carpet"},
    "Velvet Wine": {"mood": "Mysterious & Intense", "occasion": "Night Out"},
    "Scarlet Ember": {"mood": "Fiery & Passionate", "occasion": "Cocktail Party"},
    "Rose Garnet": {"mood": "Romantic & Sophisticated", "occasion": "Anniversary Dinner"},
    
    # Nudes
    "Silk Caramel": {"mood": "Warm & Effortless", "occasion": "Brunch & Daytime"},
    "Satin Taupe": {"mood": "Professional & Calming", "occasion": "Office Wear"},
    "Peach Cashmere": {"mood": "Soft & Cozy", "occasion": "Casual Outing"},
    "Nude Quartz": {"mood": "Minimalist & Pure", "occasion": "Daily Wear"},
    "Almond Silk": {"mood": "Toasted & Modern", "occasion": "Business Meeting"},
    
    # Pinks
    "Blush Quartz": {"mood": "Romantic & Elegant", "occasion": "Date Night"},
    "Rose Opal": {"mood": "Playful & Vibrant", "occasion": "Weekend Getaway"},
    "Fuchsia Neon": {"mood": "Electric & Eccentric", "occasion": "Music Festival"},
    "Petal Glow": {"mood": "Fresh & Radiant", "occasion": "Spring Wedding"},
    "Pink Sapphire": {"mood": "Luminous & Glamorous", "occasion": "Birthday Celebration"},
    
    # Berries
    "Plum Crystal": {"mood": "Chic & Intellectual", "occasion": "Art Gallery Opening"},
    "Mulberry Silk": {"mood": "Graceful & Warm", "occasion": "Afternoon Tea"},
    "Royal Berry": {"mood": "Majestic & Powerful", "occasion": "VIP Reception"},
    "Blackberry Muse": {"mood": "Vampy & Artistic", "occasion": "Fashion Show"},
    "Velvet Mulberry": {"mood": "Smooth & Rich", "occasion": "Theatre & Opera"},
    
    # Corals
    "Sunset Coral": {"mood": "Sun-kissed & Energetic", "occasion": "Beach Party"},
    "Amber Nude": {"mood": "Earthy & Centered", "occasion": "Sunset Cruise"},
    "Sienna Glow": {"mood": "Terracotta & Warm", "occasion": "Autumn Festival"},
    "Coral Bloom": {"mood": "Bright & Cheerful", "occasion": "Summer Picnic"},
    "Peach Sunrise": {"mood": "Vibrant & Hopeful", "occasion": "Morning Brunch"},
    
    # Plums
    "Deep Amethyst": {"mood": "Glamorous", "occasion": "Party & Fashion Events"},
    "Velvet Orchid": {"mood": "Sensual & Bold", "occasion": "Late Night Lounge"},
    "Dark Dahlia": {"mood": "Dramatic & Dark", "occasion": "Gothic Event"},
    "Midnight Plum": {"mood": "Mysterious & Sleek", "occasion": "VIP Afterparty"},
    "Violet Eclipse": {"mood": "Cosmic & Avant-garde", "occasion": "Creative Showcase"}
}

LIP_LINER_MAPPING = {
    # Reds
    "Ruby Aura": {"color": ( 15,  10, 140), "name": "Crimson Define"},
    "Crimson Lith": {"color": ( 10,   5,  90), "name": "Midnight Crimson"},
    "Velvet Wine": {"color": ( 10,   5,  90), "name": "Midnight Crimson"},
    "Scarlet Ember": {"color": ( 15,  10, 140), "name": "Crimson Define"},
    "Rose Garnet": {"color": ( 20,  20, 170), "name": "Garnet Rim"},
    
    # Nudes
    "Silk Caramel": {"color": ( 30,  50, 120), "name": "Toasted Caramel"},
    "Satin Taupe": {"color": (110, 135, 190), "name": "Taupe Border"},
    "Peach Cashmere": {"color": (110, 135, 190), "name": "Taupe Border"},
    "Nude Quartz": {"color": (110, 135, 190), "name": "Taupe Border"},
    "Almond Silk": {"color": ( 30,  50, 120), "name": "Toasted Caramel"},
    
    # Pinks
    "Blush Quartz": {"color": (120,  80, 210), "name": "Rose Edge"},
    "Rose Opal": {"color": (120,  80, 210), "name": "Rose Edge"},
    "Fuchsia Neon": {"color": (160,  60, 235), "name": "Fuchsia Contour"},
    "Petal Glow": {"color": (120,  80, 210), "name": "Rose Edge"},
    "Pink Sapphire": {"color": (160,  60, 235), "name": "Fuchsia Contour"},
    
    # Berries
    "Plum Crystal": {"color": ( 60,   8, 108), "name": "Berry Contour"},
    "Mulberry Silk": {"color": ( 60,   8, 108), "name": "Berry Contour"},
    "Royal Berry": {"color": ( 55,  10,  95), "name": "Blackberry Contour"},
    "Blackberry Muse": {"color": ( 30,   5,  60), "name": "Dark Dahlia Rim"},
    "Velvet Mulberry": {"color": ( 60,   8, 108), "name": "Berry Contour"},
    
    # Corals
    "Sunset Coral": {"color": ( 35,  65, 175), "name": "Terracotta Line"},
    "Amber Nude": {"color": ( 35,  65, 175), "name": "Terracotta Line"},
    "Sienna Glow": {"color": ( 30,   5,  60), "name": "Dark Sienna"},
    "Coral Bloom": {"color": ( 35,  65, 175), "name": "Terracotta Line"},
    "Peach Sunrise": {"color": ( 35,  65, 175), "name": "Terracotta Line"},
    
    # Plums
    "Deep Amethyst": {"color": ( 30,   5,  60), "name": "Amethyst Rim"},
    "Velvet Orchid": {"color": ( 50,  10,  90), "name": "Orchid Border"},
    "Dark Dahlia": {"color": ( 20,   0,  40), "name": "Midnight Dahlia"},
    "Midnight Plum": {"color": ( 20,   0,  40), "name": "Midnight Dahlia"},
    "Violet Eclipse": {"color": ( 50,  10,  90), "name": "Orchid Border"}
}

for pal, shades in lipstick_palettes.items():
    for shade_name, bgr in shades.items():
        meta = SHADE_METADATA.get(shade_name, {"mood": "Mysterious", "occasion": "Special Occasion"})
        ALL_SHADES[shade_name] = {
            "palette": pal,
            "bgr": bgr,
            "mood": meta["mood"],
            "occasion": meta["occasion"]
        }

def get_match_score(shade_name, skin_tone, finish):
    h_val = int(hashlib.md5(f"{shade_name}_{skin_tone or 'Medium'}_{finish}".encode()).hexdigest(), 16)
    
    # 1. Skin Tone Compatibility (60%)
    if not skin_tone:
        skin_comp = 85
    else:
        recs = SKIN_TONE_RECOMMENDATIONS.get(skin_tone, [])
        if shade_name in recs:
            skin_comp = 90 + (h_val % 10)
        else:
            skin_comp = 60 + (h_val % 25)
            
    # 2. Collection Compatibility (20%)
    palette = ALL_SHADES.get(shade_name, {}).get("palette", "")
    coll_mapping = {
        "💋 Aura Rouge Collection": ["Medium", "Olive", "Tan", "Deep"],
        "🌿 Quartz Nude Series": ["Fair", "Light", "Medium", "Olive"],
        "🌸 Pink Aura Collection": ["Fair", "Light", "Medium"],
        "🍇 Berry Luxe Collection": ["Olive", "Tan", "Deep", "Medium"],
        "🌊 Coral Glow Collection": ["Light", "Medium", "Olive", "Tan"],
        "🔮 Velvet Plum Edition": ["Tan", "Deep", "Olive"]
    }
    
    if not skin_tone:
        coll_comp = 85
    else:
        compatible_tones = coll_mapping.get(palette, [])
        if skin_tone in compatible_tones:
            coll_comp = 90 + (h_val % 11)
        else:
            coll_comp = 70 + (h_val % 11)
            
    # 3. Finish Compatibility (20%)
    is_red_berry_plum = palette in ["💋 Aura Rouge Collection", "🍇 Berry Luxe Collection", "🔮 Velvet Plum Edition"]
    is_pink_coral_nude = palette in ["🌿 Quartz Nude Series", "🌸 Pink Aura Collection", "🌊 Coral Glow Collection"]
    
    if "Velvet" in finish:
        finish_comp = 95 if is_red_berry_plum else 65
    elif "Glass" in finish:
        finish_comp = 95 if is_pink_coral_nude else 65
    elif "Glossy" in finish:
        finish_comp = 88
    elif "Satin" in finish:
        finish_comp = 86
    else:
        finish_comp = 84
        
    total_score = int(skin_comp * 0.60 + coll_comp * 0.20 + finish_comp * 0.20)
    total_score = max(50, min(100, total_score))
    
    if total_score >= 90:
        cat = "Exceptional Harmony"
    elif total_score >= 80:
        cat = "Luxury Harmony"
    elif total_score >= 70:
        cat = "Beautiful Harmony"
    elif total_score >= 60:
        cat = "Good Harmony"
    else:
        cat = "Experimental Harmony"
        
    return total_score, cat

def get_beauty_score_and_harmony(match_score, shade_name, undertone):
    if not undertone:
        b_score = match_score
    else:
        palette = ALL_SHADES.get(shade_name, {}).get("palette", "")
        is_cool = palette in ["🌸 Pink Aura Collection", "🍇 Berry Luxe Collection", "🔮 Velvet Plum Edition"]
        is_warm = palette in ["🌿 Quartz Nude Series", "🌊 Coral Glow Collection"]
        
        if undertone == "Cool":
            modifier = 4 if is_cool else (-3 if is_warm else 0)
        elif undertone == "Warm":
            modifier = 4 if is_warm else (-3 if is_cool else 0)
        else:  # Neutral
            modifier = 2
            
        b_score = int(match_score + modifier)
        
    b_score = max(50, min(100, b_score))
    
    if b_score >= 90:
        harmony = "Exceptional Harmony"
        rec_level = "Exceptional Match"
    elif b_score >= 80:
        harmony = "Luxury Harmony"
        rec_level = "Luxury Match"
    elif b_score >= 70:
        harmony = "Beautiful Harmony"
        rec_level = "Beautiful Fit"
    elif b_score >= 60:
        harmony = "Good Harmony"
        rec_level = "Good Match"
    else:
        harmony = "Experimental Harmony"
        rec_level = "Experimental Style"
        
    return b_score, harmony, rec_level

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
        return None, None, None
    all_pixels = np.vstack(samples).astype(np.float32)
    avg_bgr = all_pixels.mean(axis=0)
    avg_bgr_u8 = np.array([[avg_bgr]], dtype=np.uint8)
    avg_lab = cv2.cvtColor(avg_bgr_u8, cv2.COLOR_BGR2LAB)[0][0]
    L_norm = avg_lab[0] / 255.0 * 100.0
    a_val = avg_lab[1]
    b_val = avg_lab[2]
    
    if   L_norm >= 72: tone = "Fair"
    elif L_norm >= 62: tone = "Light"
    elif L_norm >= 52: tone = "Medium"
    elif L_norm >= 42: tone = "Olive"
    elif L_norm >= 32: tone = "Tan"
    else:              tone = "Deep"
    
    ratio = (b_val / a_val) if a_val > 0 else 1.0
    if ratio > 1.22:
        undertone = "Warm"
    elif ratio < 0.95:
        undertone = "Cool"
    else:
        undertone = "Neutral"
        
    return tone, tuple(int(c) for c in avg_bgr), undertone

# =========================
# LIP MASK
# =========================
def get_lip_mask_and_landmarks(image_bgr):
    h, w = image_bgr.shape[:2]
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    result = face_mesh.process(rgb)
    if not result.multi_face_landmarks:
        return None, None, None, None, h, w

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
    cv2.fillPoly(mask, [inner_pts], 0)     # subtract inner mouth opening/cavity so lipstick is not applied inside the mouth

    # Upper lip sub-mask for gloss
    upper_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(upper_mask, [pts(UPPER_LIP_OUTER)], 255)
    upper_mask = cv2.bitwise_and(upper_mask, mask)

    # Lower lip sub-mask for gloss
    lower_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(lower_mask, [pts(LOWER_LIP_OUTER)], 255)
    lower_mask = cv2.bitwise_and(lower_mask, mask)

    return mask, upper_mask, lower_mask, lm, h, w

# =========================
# APPLY LIPSTICK — LAB color transfer (no hue wrap-around issue)
# =========================
def apply_lipstick(image_bgr: np.ndarray,
                   lip_mask: np.ndarray,
                   upper_lip_mask,
                   lower_lip_mask,
                   color_bgr: tuple,
                   alpha: float,
                   finish: str = "Glossy 💋",
                   volume_enhancement: str = "Natural",
                   liner_mode: str = "None",
                   liner_color_bgr: tuple = None) -> np.ndarray:
    """
    LAB-space 'Color' blend mode + Lip Shape Enhancement + Lip Liner.
    """
    h, w = image_bgr.shape[:2]
    img_f = image_bgr.astype(np.float32)

    # ── 0. Optional Lip Shape Volume Enhancement ──────────────────────
    if volume_enhancement == "Soft Volume":
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        lip_mask = cv2.dilate(lip_mask, kernel)
        if upper_lip_mask is not None:
            upper_lip_mask = cv2.dilate(upper_lip_mask, kernel)
        if lower_lip_mask is not None:
            lower_lip_mask = cv2.dilate(lower_lip_mask, kernel)
    elif volume_enhancement == "Editorial Volume":
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        lip_mask = cv2.dilate(lip_mask, kernel)
        if upper_lip_mask is not None:
            upper_lip_mask = cv2.dilate(upper_lip_mask, kernel)
        if lower_lip_mask is not None:
            lower_lip_mask = cv2.dilate(lower_lip_mask, kernel)

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

    # L* (lightness/texture)
    if "Velvet" in finish:
        # Soften texture on the L channel for soft-focus velvet look
        blurred_L = cv2.GaussianBlur(img_lab[..., 0], (5, 5), 1.5)
        smooth_L = img_lab[..., 0] * 0.40 + blurred_L * 0.60
        # Mute reflections slightly
        l_shift = w_map * 0.24
        result_lab[..., 0] = np.clip(
            smooth_L * (1 - l_shift) + tgt_L * l_shift,
            0, 255,
        )
    else:
        # Standard texture preservation with standard shift
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

    # ── 8. Gloss highlight on lips (skip for Matte and Velvet) ──────────
    if finish not in ["Matte 💄", "Velvet Finish 🪄"] and (upper_lip_mask is not None and upper_lip_mask.any()):
        # Gloss intensity and spread parameters
        if finish == "Glass Finish 💎":
            gloss_strength = 0.20
            screen_factor = 0.25
            size_multiplier = 2.5  # wide reflection
            apply_lower = True
        elif finish == "Glossy 💋":
            gloss_strength = 0.12
            screen_factor = 0.15
            size_multiplier = 3.5  # very wide reflection
            apply_lower = True
        else:  # Satin ✨
            gloss_strength = 0.06
            screen_factor = 0.10
            size_multiplier = 5.0  # extremely wide and soft reflection
            apply_lower = False

        # Highlight map for upper lip
        hs_upper = np.zeros_like(blended, dtype=np.float32)
        if upper_lip_mask is not None and upper_lip_mask.any():
            up_hard = (upper_lip_mask > 0).astype(np.float32)
            up_hard_3d = np.dstack([up_hard] * 3)
            
            # Find center using moments
            M = cv2.moments(upper_lip_mask)
            if M["m00"] != 0:
                cX = M["m10"] / M["m00"]
                cY = M["m01"] / M["m00"]
                x_box, y_box, w_box, h_box = cv2.boundingRect(upper_lip_mask)
                
                # Offset slightly upwards for Cupid's bow highlight
                cY = cY - h_box * 0.1
                
                # Determine standard deviations for soft 2D gradient
                sigma_x = max(1.0, w_box * 0.12 * size_multiplier)
                sigma_y = max(1.0, h_box * 0.25 * size_multiplier)
                
                y_idx = np.arange(h, dtype=np.float32).reshape(-1, 1)
                x_idx = np.arange(w, dtype=np.float32).reshape(1, -1)
                
                hs_2d = np.exp(-0.5 * (((y_idx - cY) / sigma_y) ** 2 + ((x_idx - cX) / sigma_x) ** 2))
                hs_3d = np.dstack([hs_2d] * 3)
                hs_upper = up_hard_3d * hs_3d

        # Highlight map for lower lip (if applicable)
        hs_lower = np.zeros_like(blended, dtype=np.float32)
        if apply_lower and lower_lip_mask is not None and lower_lip_mask.any():
            lo_hard = (lower_lip_mask > 0).astype(np.float32)
            lo_hard_3d = np.dstack([lo_hard] * 3)
            
            # Find center using moments
            M = cv2.moments(lower_lip_mask)
            if M["m00"] != 0:
                cX = M["m10"] / M["m00"]
                cY = M["m01"] / M["m00"]
                x_box, y_box, w_box, h_box = cv2.boundingRect(lower_lip_mask)
                
                # Offset slightly downwards for center-lower lip highlight
                cY = cY + h_box * 0.05
                
                # Determine standard deviations for soft 2D gradient
                sigma_x = max(1.0, w_box * 0.10 * size_multiplier)
                sigma_y = max(1.0, h_box * 0.30 * size_multiplier)
                
                y_idx = np.arange(h, dtype=np.float32).reshape(-1, 1)
                x_idx = np.arange(w, dtype=np.float32).reshape(1, -1)
                
                hs_2d = np.exp(-0.5 * (((y_idx - cY) / sigma_y) ** 2 + ((x_idx - cX) / sigma_x) ** 2))
                hs_3d = np.dstack([hs_2d] * 3)
                hs_lower = lo_hard_3d * hs_3d

        # Combined highlight map
        hs_combined = np.clip(hs_upper + hs_lower, 0, 1)

        # Screen blend mode
        A_n = blended / 255.0
        screened = np.clip((1 - (1 - A_n) * (1 - screen_factor)) * 255.0, 0, 255)
        gloss_w = hs_combined * alpha * gloss_strength

        # Apply gloss blend specifically to the lip area
        blended_with_gloss = np.clip(blended * (1 - gloss_w) + screened * gloss_w, 0, 255)

        # Blend gloss ONLY onto lip pixels (using the hard mask of the lips)
        blended = blended * (1 - hard_3d) + blended_with_gloss * hard_3d
        blended = np.clip(blended, 0, 255)

    # ── 9. Smart Lip Liner Simulation ───────────────────────────────
    if liner_mode != "None" and liner_color_bgr is not None:
        contours, _ = cv2.findContours(lip_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) > 0:
            if liner_mode == "Natural Define":
                thickness = 2
                blur_k = 3
                liner_alpha = 0.65
            elif liner_mode == "Soft Volume":
                thickness = 3
                blur_k = 5
                liner_alpha = 0.75
            elif liner_mode == "Precision Luxe":
                thickness = 2
                blur_k = 1
                liner_alpha = 0.85
            elif liner_mode == "Dramatic Glam":
                thickness = 4
                blur_k = 5
                liner_alpha = 0.90
            else:
                thickness = 0
                blur_k = 0
                liner_alpha = 0.0

            if thickness > 0:
                liner_overlay = np.zeros((h, w, 3), dtype=np.uint8)
                cv2.drawContours(liner_overlay, contours, -1, liner_color_bgr, thickness)
                if blur_k > 1:
                    liner_overlay = cv2.GaussianBlur(liner_overlay, (blur_k, blur_k), 0)
                
                liner_gray = cv2.cvtColor(liner_overlay, cv2.COLOR_BGR2GRAY)
                _, l_mask = cv2.threshold(liner_gray, 1, 255, cv2.THRESH_BINARY)
                
                liner_mask_f = (l_mask / 255.0) * liner_alpha
                liner_mask_3d = np.dstack([liner_mask_f] * 3)
                
                blended = (blended * (1 - liner_mask_3d) + liner_overlay * liner_mask_3d)
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
if "processed_captures" not in st.session_state:
    st.session_state.processed_captures = set()
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
def render_transformation_studio(before_bgr, after_bgr):
    before_rgb = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2RGB)
    after_rgb = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2RGB)
    before_pil = Image.fromarray(before_rgb)
    after_pil = Image.fromarray(after_rgb)
    
    before_b64 = pil_to_b64(before_pil)
    after_b64 = pil_to_b64(after_pil)
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body {{
        margin: 0;
        padding: 0;
        overflow: hidden;
        background-color: transparent;
        font-family: 'Montserrat', sans-serif;
    }}
    #studio-wrapper {{
        position: relative;
        width: 100%;
        max-width: 480px;
        margin: 0 auto;
        aspect-ratio: 4/5;
        border-radius: 16px;
        border: 2px solid #d4a373;
        box-shadow: 0 10px 30px rgba(43, 16, 32, 0.15);
        overflow: hidden;
        background-color: #0b060c;
    }}
    .viewport {{
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        cursor: grab;
    }}
    .viewport:active {{
        cursor: grabbing;
    }}
    .zoom-container {{
        width: 100%;
        height: 100%;
        position: absolute;
        left: 0;
        top: 0;
        transform-origin: center center;
        transition: transform 0.05s ease-out;
    }}
    .image-wrapper {{
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
    }}
    .after-img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        pointer-events: none;
    }}
    .before-img-wrapper {{
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        clip-path: inset(0 50% 0 0);
    }}
    .before-img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        pointer-events: none;
    }}
    .slider-bar {{
        position: absolute;
        left: 50%;
        top: 0;
        bottom: 0;
        width: 2px;
        background-color: #fc2779;
        box-shadow: 0 0 10px #fc2779;
        cursor: col-resize;
        z-index: 10;
    }}
    .slider-handle {{
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #ffffff;
        border: 2px solid #fc2779;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: col-resize;
        transition: transform 0.2s;
    }}
    .slider-handle:hover {{
        transform: translate(-50%, -50%) scale(1.1);
    }}
    .handle-arrow {{
        font-size: 12px;
        color: #fc2779;
        font-weight: bold;
        user-select: none;
    }}
    .badge {{
        position: absolute;
        top: 15px;
        background: rgba(43, 16, 32, 0.75);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
        border: 1px solid #d4a373;
        z-index: 11;
        pointer-events: none;
    }}
    .badge-before {{
        left: 15px;
    }}
    .badge-after {{
        right: 15px;
        background: rgba(252, 39, 121, 0.85);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
        border: 1px solid #ffffff;
        z-index: 11;
        pointer-events: none;
    }}
    .toolbar {{
        position: absolute;
        bottom: 15px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(18, 9, 16, 0.88);
        border: 1.5px solid #d4a373;
        border-radius: 20px;
        padding: 8px 14px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        z-index: 12;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        align-items: center;
        width: 250px;
    }}
    .view-mode-bar {{
        display: flex;
        justify-content: center;
        gap: 5px;
        width: 100%;
        border-bottom: 1px solid rgba(212, 163, 115, 0.2);
        padding-bottom: 6px;
    }}
    .mode-btn {{
        background: transparent;
        border: 1px solid rgba(212, 163, 115, 0.25);
        color: #8b8b9c;
        font-size: 9px;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 10px;
        cursor: pointer;
        text-transform: uppercase;
        transition: all 0.2s;
    }}
    .mode-btn.active {{
        background: #fc2779;
        color: #ffffff;
        border-color: #fc2779;
    }}
    .tool-btn {{
        background: transparent;
        border: none;
        color: #ffffff;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }}
    .tool-btn:hover {{
        color: #fc2779;
        background: rgba(255, 255, 255, 0.1);
    }}
    .zoom-text {{
        color: #d4a373;
        font-size: 11px;
        font-weight: 700;
        min-width: 32px;
        text-align: center;
    }}
    .sbs-view {{
        display: none;
        width: 100%;
        height: 100%;
        position: absolute;
        top: 0;
        left: 0;
    }}
    .sbs-pane {{
        flex: 1;
        height: 100%;
        position: relative;
        overflow: hidden;
    }}
    .sbs-pane img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
    }}
    </style>
    </head>
    <body>
    <div id="studio-wrapper">
        <div class="viewport" id="viewport">
            <!-- Side by Side View container -->
            <div class="sbs-view" id="sbs-view">
                <div class="sbs-pane" style="border-right: 1.5px solid #d4a373;">
                    <img src="data:image/jpeg;base64,{before_b64}" />
                    <span class="badge badge-before">BEFORE</span>
                </div>
                <div class="sbs-pane">
                    <img src="data:image/jpeg;base64,{after_b64}" />
                    <span class="badge badge-after">AURALITH</span>
                </div>
            </div>

            <!-- Single Zoom / Pan / Split View container -->
            <div class="zoom-container" id="zoom-container">
                <div class="image-wrapper">
                    <img class="after-img" src="data:image/jpeg;base64,{after_b64}" />
                </div>
                <div class="before-img-wrapper" id="before-wrapper">
                    <img class="before-img" src="data:image/jpeg;base64,{before_b64}" />
                </div>
            </div>
            
            <div class="slider-bar" id="slider-bar">
                <div class="slider-handle">
                    <span class="handle-arrow">↔</span>
                </div>
            </div>
            
            <span class="badge badge-before" id="badge-before-label">BEFORE</span>
            <span class="badge badge-after" id="badge-after-label">AURALITH ART</span>
            
            <div class="toolbar">
                <div class="view-mode-bar">
                    <button class="mode-btn active" id="btn-mode-split" onclick="setMode('split')">Split</button>
                    <button class="mode-btn" id="btn-mode-orig" onclick="setMode('orig')">Original</button>
                    <button class="mode-btn" id="btn-mode-enh" onclick="setMode('enh')">Enhanced</button>
                    <button class="mode-btn" id="btn-mode-sbs" onclick="setMode('sbs')">Side-by-Side</button>
                </div>
                <div style="display: flex; gap: 10px; align-items: center; justify-content: center; width: 100%;">
                    <button class="tool-btn" id="btn-zoom-out" title="Zoom Out">-</button>
                    <span class="zoom-text" id="zoom-val">1.0x</span>
                    <button class="tool-btn" id="btn-zoom-in" title="Zoom In">+</button>
                    <button class="tool-btn" id="btn-reset" title="Reset View">↺</button>
                    <button class="tool-btn" id="btn-fullscreen" title="Fullscreen">⛶</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    const viewport = document.getElementById('viewport');
    const zoomContainer = document.getElementById('zoom-container');
    const beforeWrapper = document.getElementById('before-wrapper');
    const sliderBar = document.getElementById('slider-bar');
    const zoomVal = document.getElementById('zoom-val');
    const sbsView = document.getElementById('sbs-view');
    const badgeBefore = document.getElementById('badge-before-label');
    const badgeAfter = document.getElementById('badge-after-label');
    
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnReset = document.getElementById('btn-reset');
    const btnFullscreen = document.getElementById('btn-fullscreen');
    
    let zoom = 1.0;
    let panX = 0;
    let panY = 0;
    let splitPercent = 50;
    let activeMode = 'split'; // split, orig, enh, sbs
    
    let isDraggingSplit = false;
    let isPanning = false;
    
    let startX = 0;
    let startY = 0;
    let startPanX = 0;
    let startPanY = 0;
    
    function updateTransforms() {{
        // Update Zoom & Pan
        zoomContainer.style.transform = `scale(${{zoom}}) translate(${{panX}}px, ${{panY}}px)`;
        zoomVal.innerText = zoom.toFixed(1) + 'x';
        
        // Update Split Position
        sliderBar.style.left = splitPercent + '%';
        beforeWrapper.style.clipPath = `inset(0 ${{100 - splitPercent}}% 0 0)`;
    }}
    
    function setMode(mode) {{
        activeMode = mode;
        
        document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
        document.getElementById('btn-mode-' + mode).classList.add('active');
        
        if (mode === 'sbs') {{
            zoomContainer.style.display = 'none';
            sliderBar.style.display = 'none';
            badgeBefore.style.display = 'none';
            badgeAfter.style.display = 'none';
            sbsView.style.display = 'flex';
        }} else {{
            zoomContainer.style.display = 'block';
            sbsView.style.display = 'none';
            
            if (mode === 'orig') {{
                sliderBar.style.display = 'none';
                badgeBefore.style.display = 'block';
                badgeAfter.style.display = 'none';
                beforeWrapper.style.clipPath = 'inset(0 0 0 0)';
            }} else if (mode === 'enh') {{
                sliderBar.style.display = 'none';
                badgeBefore.style.display = 'none';
                badgeAfter.style.display = 'block';
                beforeWrapper.style.clipPath = 'inset(0 100% 0 0)';
            }} else {{ // split
                sliderBar.style.display = 'block';
                badgeBefore.style.display = 'block';
                badgeAfter.style.display = 'block';
                beforeWrapper.style.clipPath = `inset(0 ${{100 - splitPercent}}% 0 0)`;
            }}
        }}
    }}
    
    // Split dragging
    function handleSplitMove(clientX) {{
        if (activeMode !== 'split') return;
        const rect = viewport.getBoundingClientRect();
        const posX = clientX - rect.left;
        let percent = (posX / rect.width) * 100;
        percent = Math.max(0, Math.min(100, percent));
        splitPercent = percent;
        updateTransforms();
    }}
    
    sliderBar.addEventListener('mousedown', (e) => {{
        isDraggingSplit = true;
        e.stopPropagation();
        e.preventDefault();
    }});
    
    // Panning
    viewport.addEventListener('mousedown', (e) => {{
        if (activeMode !== 'sbs' && zoom > 1.0) {{
            isPanning = true;
            startX = e.clientX;
            startY = e.clientY;
            startPanX = panX;
            startPanY = panY;
            e.preventDefault();
        }}
    }});
    
    window.addEventListener('mousemove', (e) => {{
        if (isDraggingSplit) {{
            handleSplitMove(e.clientX);
        }} else if (isPanning) {{
            const dx = (e.clientX - startX) / zoom;
            const dy = (e.clientY - startY) / zoom;
            panX = startPanX + dx;
            panY = startPanY + dy;
            
            // Limit panning
            const maxPan = 150 * (zoom - 1);
            panX = Math.max(-maxPan, Math.min(maxPan, panX));
            panY = Math.max(-maxPan, Math.min(maxPan, panY));
            
            updateTransforms();
        }}
    }});
    
    window.addEventListener('mouseup', () => {{
        isDraggingSplit = false;
        isPanning = false;
    }});
    
    // Touch support
    sliderBar.addEventListener('touchstart', (e) => {{
        isDraggingSplit = true;
        e.stopPropagation();
    }});
    
    viewport.addEventListener('touchstart', (e) => {{
        if (activeMode !== 'sbs' && zoom > 1.0 && e.touches.length === 1) {{
            isPanning = true;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            startPanX = panX;
            startPanY = panY;
        }}
    }});
    
    window.addEventListener('touchmove', (e) => {{
        if (isDraggingSplit && e.touches.length > 0) {{
            handleSplitMove(e.touches[0].clientX);
        }} else if (isPanning && e.touches.length === 1) {{
            const dx = (e.touches[0].clientX - startX) / zoom;
            const dy = (e.touches[0].clientY - startY) / zoom;
            panX = startPanX + dx;
            panY = startPanY + dy;
            
            const maxPan = 150 * (zoom - 1);
            panX = Math.max(-maxPan, Math.min(maxPan, panX));
            panY = Math.max(-maxPan, Math.min(maxPan, panY));
            
            updateTransforms();
        }}
    }});
    
    window.addEventListener('touchend', () => {{
        isDraggingSplit = false;
        isPanning = false;
    }});
    
    // Wheel Zoom
    viewport.addEventListener('wheel', (e) => {{
        if (activeMode === 'sbs') return;
        e.preventDefault();
        const zoomDelta = e.deltaY < 0 ? 0.25 : -0.25;
        zoom = Math.max(1.0, Math.min(4.0, zoom + zoomDelta));
        if (zoom === 1.0) {{
            panX = 0;
            panY = 0;
        }}
        updateTransforms();
    }}, {{ passive: false }});
    
    // Toolbar buttons
    btnZoomIn.addEventListener('click', (e) => {{
        if (activeMode === 'sbs') return;
        zoom = Math.min(4.0, zoom + 0.5);
        updateTransforms();
    }});
    
    btnZoomOut.addEventListener('click', (e) => {{
        if (activeMode === 'sbs') return;
        zoom = Math.max(1.0, zoom - 0.5);
        if (zoom === 1.0) {{
            panX = 0;
            panY = 0;
        }}
        updateTransforms();
    }});
    
    btnReset.addEventListener('click', (e) => {{
        zoom = 1.0;
        panX = 0;
        panY = 0;
        splitPercent = 50;
        setMode('split');
        updateTransforms();
    }});
    
    btnFullscreen.addEventListener('click', (e) => {{
        const elem = document.getElementById('studio-wrapper');
        if (!document.fullscreenElement) {{
            elem.requestFullscreen().catch(err => {{
                console.log("Error attempting fullscreen: " + err.message);
            }});
        }} else {{
            document.exitFullscreen();
        }}
    }});
    
    document.addEventListener('fullscreenchange', () => {{
        const wrapper = document.getElementById('studio-wrapper');
        if (document.fullscreenElement) {{
            wrapper.style.maxWidth = 'none';
            wrapper.style.aspectRatio = 'none';
            wrapper.style.width = '100vw';
            wrapper.style.height = '100vh';
        }} else {{
            wrapper.style.maxWidth = '480px';
            wrapper.style.aspectRatio = '4/5';
            wrapper.style.width = '100%';
            wrapper.style.height = 'auto';
        }}
    }});
    
    updateTransforms();
    </script>
    </body>
    </html>
    """
    return html_code


# Deterministic shade match confidence score based on skin tone
def get_match_confidence(shade_name, skin_tone):
    return get_match_score(shade_name, skin_tone, "Glossy 💋")[0]

# Naming explanations & descriptions
SHADE_DESCRIPTIONS = {
    "Ruby Aura": "A deep, classic ruby red that leaves a powerful, timeless impression.",
    "Crimson Lith": "A velvet-textured royal crimson for glamorous, confident evenings.",
    "Velvet Wine": "A rich, full-bodied dark wine red for bold, futuristic styling.",
    "Scarlet Ember": "A fierce, glowing scarlet red that radiates warmth and modern luxury.",
    "Rose Garnet": "A deep, rich garnet red with romantic rose undertones for evening elegance.",
    "Silk Caramel": "A warm, buttery nude caramel that melts seamlessly into the lips.",
    "Satin Taupe": "A sophisticated, neutral cool-toned beige with a satin glow.",
    "Peach Cashmere": "A soft, pastel peach-nude that feels like luxurious cashmere.",
    "Nude Quartz": "A delicate, crystal-clear beige-nude with a whisper of soft rose quartz.",
    "Almond Silk": "A warm, toasted almond nude that adds a natural velvet dimension.",
    "Blush Quartz": "A delicate, crystal-pink blush tone for a subtle daily radiance.",
    "Rose Opal": "A medium-rose pink with luminous crystalline highlights.",
    "Fuchsia Neon": "A high-intensity, electric fuchsia statement shade.",
    "Petal Glow": "A soft, fresh-cut petal pink with luminous light-reflecting pigment.",
    "Pink Sapphire": "A rich, precious pink sapphire gemstone shade that makes a striking impact.",
    "Plum Crystal": "A rich, crystal-infused medium plum for an elegant, elevated pop.",
    "Mulberry Silk": "A soft berry-toned silk finish with deep warm undertones.",
    "Royal Berry": "A majestic, dark berry hue that complements all skin tones.",
    "Blackberry Muse": "A deep, dark blackberry pigment for an ultra-luxurious vampy look.",
    "Velvet Mulberry": "A warm, luscious mulberry berry-pink designed for smooth sophistication.",
    "Sunset Coral": "A bright, sun-kissed coral pink that radiates pure warmth.",
    "Amber Nude": "A glowing, warm amber-nude with a subtle golden aura.",
    "Sienna Glow": "A deep, earthy terracotta red with sunset reflections.",
    "Coral Bloom": "A fresh, radiant coral red that captures the energy of spring blossoms.",
    "Peach Sunrise": "A bright, warm peachy pink that mimics the golden glow of a new dawn.",
    "Deep Amethyst": "A dark, intense purple-plum with amethyst crystal undertones.",
    "Velvet Orchid": "A vibrant, luxury magenta orchid that commands attention.",
    "Dark Dahlia": "A mysterious, near-black velvet plum for dramatic appeal.",
    "Midnight Plum": "A mysterious, near-black plum that commands attention with dark depth.",
    "Violet Eclipse": "A deep, royal violet plum inspired by cosmic shades and velvet textures."
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
        
        # Navigation (5 Experiences V3.1)
        page = st.radio(
            "Navigate", 
            ["✨ AURALITH Home", "💄 Virtual Try-On Studio", "🎥 Live AI Beauty Studio", "📸 AURALITH Lookbook", "📱 Mobile Beauty Experience"], 
            index=["✨ AURALITH Home", "💄 Virtual Try-On Studio", "🎥 Live AI Beauty Studio", "📸 AURALITH Lookbook", "📱 Mobile Beauty Experience"].index(
                st.session_state.current_page if st.session_state.current_page in ["✨ AURALITH Home", "💄 Virtual Try-On Studio", "🎥 Live AI Beauty Studio", "📸 AURALITH Lookbook", "📱 Mobile Beauty Experience"] else "✨ AURALITH Home"
            ), 
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
            st.session_state.processed_captures = set()
            st.session_state.current_page = "✨ AURALITH Home"
            st.rerun()

def render_home_page():
    # Hero Section
    st.markdown("""
    <div class="auralith-hero">
        <h1 style="color: #ffffff !important; font-size: 3.2rem; font-weight: 800; letter-spacing: 4px; margin: 0 0 10px 0; text-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;">A U R A L I T H</h1>
        <p style="font-size: 1.25rem; font-weight: 500; color: #f9f9fb; letter-spacing: 1.5px; margin-bottom: 25px;">Where Futuristic AI Meets Luxury Beauty</p>
        <p style="font-size: 0.95rem; line-height: 1.7; max-width: 750px; margin: 0 auto 30px auto; color: rgba(255,255,255,0.9); font-weight: 300;">
            AURALITH V3.1 represents the pinnacle of luxury beauty-tech. By fusing real-time facial intelligence with professional-grade cosmetic rendering, we deliver a highly personalized canvas mapping experience for digital shade discovery.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # CTA Buttons
    cta_col1, cta_col2 = st.columns(2)
    with cta_col1:
        if st.button("🎥 Try Live AI Beauty Studio (Webcam) ✦", use_container_width=True):
            st.session_state.current_page = "🎥 Live AI Beauty Studio"
            st.rerun()
    with cta_col2:
        if st.button("💄 Try Virtual Try-On Studio (Photo Upload) ✦", use_container_width=True):
            st.session_state.current_page = "💄 Virtual Try-On Studio"
            st.rerun()
            
    st.divider()
    
    # Feature Cards Showcase
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px; color:#2b1020;'>✦ The AURALITH V3.1 Suite</h2>", unsafe_allow_html=True)
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 4px solid #fc2779 !important;">
            <h4 style="margin-top:0; color:#fc2779 !important;">🎥 Live Webcam Studio</h4>
            <p style="font-size: 13px; color:#555; line-height: 1.6; margin-bottom:0;">
                Test lipstick shades instantly through your webcam. Features continuous tracking and dynamic lipstick/liner overlays at 20-30 FPS.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with f_col2:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 4px solid #d4a373 !important;">
            <h4 style="margin-top:0; color:#d4a373 !important;">📐 Lip liner & Volume Enhancement</h4>
            <p style="font-size: 13px; color:#555; line-height: 1.6; margin-bottom:0;">
                Simulate professional lip liners (Natural, Soft Volume, Precision, Dramatic) and non-destructive shape volume adjustments.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with f_col3:
        st.markdown("""
        <div class="glass-card" style="height: 100%; border-top: 4px solid #2b1020 !important;">
            <h4 style="margin-top:0; color:#2b1020 !important;">🔮 AI Beauty Score™</h4>
            <p style="font-size: 13px; color:#555; line-height: 1.6; margin-bottom:0;">
                Calculates compatibility using skin tone (60%), collection (20%), finish (20%), and undertone mapping for detailed harmony analytics.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Beauty Journey Section
    st.markdown("<h2 style='text-align: center; margin-top: 40px; margin-bottom: 25px; color:#2b1020;'>✨ Your AURALITH Beauty Journey</h2>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background: #ffffff; border-radius: 16px; border: 1.5px solid #e8e8f2; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.01); margin-bottom: 30px;">
        <div style="display: flex; justify-content: space-around; align-items: center; flex-wrap: wrap; text-align: center; gap: 15px;">
            <div style="flex: 1; min-width: 130px;">
                <div style="font-size: 20px; margin-bottom: 8px;">1️⃣</div>
                <div style="font-weight: 700; font-size: 12px; color: #2b1020; margin-bottom: 4px;">Upload Canvas</div>
                <div style="font-size: 10px; color: #8b8b9c;">Upload portrait or start camera feed</div>
            </div>
            <div style="color: #d4a373; font-weight: 700; font-size: 16px;">→</div>
            <div style="flex: 1; min-width: 130px;">
                <div style="font-size: 20px; margin-bottom: 8px;">2️⃣</div>
                <div style="font-weight: 700; font-size: 12px; color: #2b1020; margin-bottom: 4px;">AI Analysis</div>
                <div style="font-size: 10px; color: #8b8b9c;">Detects complexion & undertones</div>
            </div>
            <div style="color: #d4a373; font-weight: 700; font-size: 16px;">→</div>
            <div style="flex: 1; min-width: 130px;">
                <div style="font-size: 20px; margin-bottom: 8px;">3️⃣</div>
                <div style="font-weight: 700; font-size: 12px; color: #2b1020; margin-bottom: 4px;">Experience Shades</div>
                <div style="font-size: 10px; color: #8b8b9c;">Try 30 shades and 5 finishes</div>
            </div>
            <div style="color: #d4a373; font-weight: 700; font-size: 16px;">→</div>
            <div style="flex: 1; min-width: 130px;">
                <div style="font-size: 20px; margin-bottom: 8px;">4️⃣</div>
                <div style="font-weight: 700; font-size: 12px; color: #2b1020; margin-bottom: 4px;">Compare Views</div>
                <div style="font-size: 10px; color: #8b8b9c;">Draggable slider, side-by-side, zoom</div>
            </div>
            <div style="color: #d4a373; font-weight: 700; font-size: 16px;">→</div>
            <div style="flex: 1; min-width: 130px;">
                <div style="font-size: 20px; margin-bottom: 8px;">5️⃣</div>
                <div style="font-weight: 700; font-size: 12px; color: #2b1020; margin-bottom: 4px;">Save Looks</div>
                <div style="font-size: 10px; color: #8b8b9c;">Save customized styles to lookbook</div>
            </div>
            <div style="color: #d4a373; font-weight: 700; font-size: 16px;">→</div>
            <div style="flex: 1; min-width: 130px;">
                <div style="font-size: 20px; margin-bottom: 8px;">6️⃣</div>
                <div style="font-weight: 700; font-size: 12px; color: #2b1020; margin-bottom: 4px;">Build Profile</div>
                <div style="font-size: 10px; color: #8b8b9c;">Access interactive analytics dashboard</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    
    # Homepage Beauty Discovery (5 tabs)
    st.markdown("<h2 style='text-align: center; margin-bottom: 5px; color:#2b1020;'>✦ Discover Luxury Shades</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#8b8b9c; font-size:13px; margin-bottom:30px;'>Explore trending products and editorial recommendations. Try them instantly in the Studio.</p>", unsafe_allow_html=True)
    
    last_skin_tone = "Medium"
    for look in reversed(st.session_state.saved_looks):
        if look.get("skin_tone") and look["skin_tone"] != "Not Detected":
            last_skin_tone = look["skin_tone"]
            break
            
    tab_trend, tab_editor, tab_rec, tab_new, tab_signature = st.tabs([
        "🔥 Trending Shades", 
        "✨ Editor's Choice", 
        "💖 Recommended For You", 
        "🌟 New Arrivals", 
        "👑 AURALITH Signature Picks"
    ])
    
    def render_shade_card_grid(shades_list, btn_key_prefix):
        cols = st.columns(3)
        for idx, ts in enumerate(shades_list):
            if ts in ALL_SHADES:
                palette = ALL_SHADES[ts]["palette"]
                bgr = ALL_SHADES[ts]["bgr"]
                r, g, b = bgr[2], bgr[1], bgr[0]
                desc = SHADE_DESCRIPTIONS.get(ts, "")
                score, _ = get_match_score(ts, last_skin_tone, "Glossy 💋")
                b_score, harmony, _ = get_beauty_score_and_harmony(score, ts, "Neutral")
                meta = SHADE_METADATA.get(ts, {"mood": "Mysterious", "occasion": "Special Occasion"})
                
                with cols[idx]:
                    st.markdown(f"""
                    <div class="glass-card" style="text-align: center; border-top: 4px solid #fc2779 !important; height: 320px; display: flex; flex-direction: column; justify-content: space-between;">
                        <div>
                            <div style="width:36px; height:36px; border-radius:50%; background:rgb({r},{g},{b}); margin:0 auto 10px auto; border:2px solid #ffffff; box-shadow: 0 4px 10px rgba(0,0,0,0.15);"></div>
                            <h4 style="margin: 0 0 4px 0; font-size: 15px; color:#2b1020 !important;">{ts}</h4>
                            <span style="font-size: 9px; color: #8b8b9c; text-transform: uppercase; font-weight: 700; display: block; margin-bottom: 6px;">{palette.replace(" Collection", "").replace(" Series", "").replace(" Edition", "")}</span>
                            <p style="font-size:11px; color:#555; line-height:1.4; height: 48px; overflow: hidden; margin-bottom: 8px;">{desc}</p>
                            <div style="font-size: 10px; color: #d4a373; font-weight: 700;">Mood: {meta['mood']}</div>
                            <div style="font-size: 10px; color: #d4a373; font-weight: 700; margin-top:2px;">Occasion: {meta['occasion']}</div>
                        </div>
                        <div style="margin-top: 10px; font-size:11px; font-weight:700; color:#fc2779;">{b_score}% Score ({harmony})</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Try shade ✦", key=f"{btn_key_prefix}_{ts}", use_container_width=True):
                        st.session_state.selected_shade = ts
                        st.session_state.selected_palette = palette
                        st.session_state.current_page = "💄 Virtual Try-On Studio"
                        st.rerun()

    with tab_trend:
        render_shade_card_grid(["Scarlet Ember", "Peach Sunrise", "Violet Eclipse"], "trend")
    with tab_editor:
        render_shade_card_grid(["Velvet Mulberry", "Almond Silk", "Pink Sapphire"], "editor")
    with tab_rec:
        recs = SKIN_TONE_RECOMMENDATIONS.get(last_skin_tone, ["Ruby Aura", "Peach Cashmere", "Plum Crystal"])[:3]
        render_shade_card_grid(recs, "rec")
    with tab_new:
        render_shade_card_grid(["Rose Opal", "Sunset Coral", "Midnight Plum"], "new")
    with tab_signature:
        render_shade_card_grid(["Ruby Aura", "Silk Caramel", "Deep Amethyst"], "sig")

    st.divider()

    # Brand Catalog Showcase
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px; color:#2b1020;'>✦ Luxury Signature Collections</h2>", unsafe_allow_html=True)
    for p_name, p_shades in lipstick_palettes.items():
        st.markdown(f"#### {p_name}")
        cols = st.columns(len(p_shades))
        for s_idx, (s_name, bgr) in enumerate(p_shades.items()):
            r, g, b = bgr[2], bgr[1], bgr[0]
            with cols[s_idx]:
                st.markdown(f"""
                <div style="text-align: center; margin-bottom: 10px; background:#ffffff; padding:15px; border-radius:12px; border:1px solid #e8e8f2;">
                    <div title="{SHADE_DESCRIPTIONS.get(s_name, '')}" style="width:28px; height:28px; border-radius:50%; background:rgb({r},{g},{b}); margin:0 auto 6px auto; border:2px solid #ffffff; box-shadow: 0 3px 8px rgba(43,16,32,0.18);"></div>
                    <span style="font-size:10px; font-weight:600; display:block; color:#2b1020; height:24px; overflow:hidden; line-height:1.2; margin-bottom:5px;">{s_name}</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Try ✦", key=f"home_cat_{s_name}", use_container_width=True):
                    st.session_state.selected_shade = s_name
                    st.session_state.selected_palette = p_name
                    st.session_state.current_page = "💄 Virtual Try-On Studio"
                    st.rerun()
        st.write("")

def render_try_on_page():
    BEAUTY_INSIGHTS = {
        "Fair": {
            "undertones": ["Cool Mauve", "Pastel Rose", "Soft Pink"],
            "collections": ["🌸 Pink Aura Collection", "🌿 Quartz Nude Series", "🍇 Berry Luxe Collection"],
            "advice": "Your fair skin tone with cool undertones looks stunning with soft pinks, pastel mauve, and cool-toned berry shades. Avoid warm corals."
        },
        "Light": {
            "undertones": ["Peach Cashmere", "Warm Pink", "Coral Glow"],
            "collections": ["🌿 Quartz Nude Series", "🌸 Pink Aura Collection", "🌊 Coral Glow Collection"],
            "advice": "Your light warm complexion pairs beautifully with warm peach, nude-caramels, and fresh coral tones. A satin or glossy finish enhances your natural glow."
        },
        "Medium": {
            "undertones": ["Warm Honey", "Rose Pink", "Soft Terracotta"],
            "collections": ["🌿 Quartz Nude Series", "💋 Aura Rouge Collection", "🌊 Coral Glow Collection"],
            "advice": "Your balanced medium skin tone is incredibly versatile. It is elevated by toasted nudes, warm coral sunset shades, and classic ruby reds."
        },
        "Olive": {
            "undertones": ["Warm Rose Pink", "Berry Plum", "Coral Nude"],
            "collections": ["🍇 Berry Luxe Collection", "💋 Aura Rouge Collection", "🌊 Coral Glow Collection"],
            "advice": "Your warm olive complexion is enriched by earthy terracotta tones, deep brick reds, and rich berry-plum pigments."
        },
        "Tan": {
            "undertones": ["Warm Caramel", "Burnt Orange", "Rich Plum"],
            "collections": ["💋 Aura Rouge Collection", "🍇 Berry Luxe Collection", "🔮 Velvet Plum Edition"],
            "advice": "Your golden tan skin tone commands deep, high-contrast colors. Rich crimson, warm sienna, and deep velvet plum shades make an exquisite statement."
        },
        "Deep": {
            "undertones": ["Deep Fuchsia", "Dark Plum", "Royal Berry"],
            "collections": ["🍇 Berry Luxe Collection", "🔮 Velvet Plum Edition", "💋 Aura Rouge Collection"],
            "advice": "Your rich deep complexion is beautifully defined by intense, highly saturated pigments. Deep amethyst, midnight plum, and royal berry tones look regal."
        }
    }

    # Brand Promo Banner
    st.markdown("""
    <div class="auralith-promo-banner">
        <span>✨ AURALITH ARTISTRY: Try on virtual shades, unlock complexion-based match recommendation profiles.</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.title("💄 Virtual Try-On Studio")
    st.markdown("### ✨ Experience Your Perfect Shade")
    
    col_left, col_right = st.columns([1.1, 1.0])
    
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
            circles_html += f'<div style="display:inline-block;width:30px;height:30px;border-radius:50%;background:rgb({r},{g},{b});margin:4px;border:{border};box-shadow:0 3px 6px rgba(0,0,0,0.15);"></div>'
        st.markdown(circles_html, unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:11px; color:#8b8b9c; font-style:italic; margin-top:5px;'>'{SHADE_DESCRIPTIONS.get(shade, '')}'</p>", unsafe_allow_html=True)
        
        # Control parameters
        opacity = st.slider("Texture Coverage (Opacity)", 0.20, 1.00, st.session_state.selected_opacity, step=0.05)
        st.session_state.selected_opacity = opacity
        
        finishes = ["Glossy 💋", "Satin ✨", "Matte 💄", "Velvet Finish 🪄", "Glass Finish 💎"]
        default_finish = st.session_state.selected_finish
        default_finish_idx = finishes.index(default_finish) if default_finish in finishes else 0
        
        finish  = st.selectbox("Cosmetic Finish", finishes, index=default_finish_idx)
        st.session_state.selected_finish = finish

        # Smart Lip Liner and Volume Enhancement defaults
        liner_mode = "None"
        volume_enhancement = "Natural"
        rec_liner = {"name": "Natural Define", "color": (128, 128, 128)}

    # Try-On rendering execution
    if img_file:
        image_pil = Image.open(img_file).convert("RGB")
        image_rgb = np.array(image_pil)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        # Sequenced luxury loaders
        loading_placeholder = st.empty()
        steps = [
            "✦ Initializing Beauty Engine...",
            "✦ Activating Facial Intelligence...",
            "✦ Detecting Lip Structure...",
            "✦ Mapping Beauty Contours...",
            "✦ Analyzing Complexion Profile...",
            "✦ Detecting Undertones...",
            "✦ Calculating Beauty Score...",
            "✦ Generating Luxury Finish...",
            "✦ Rendering AI Beauty Preview...",
            "✦ Finalizing Transformation..."
        ]
        import time
        for step in steps:
            loading_placeholder.markdown(f"<p style='font-size:13px; color:#fc2779; font-weight:600; font-style:italic; margin:10px 0;'>{step}</p>", unsafe_allow_html=True)
            time.sleep(0.12)
        loading_placeholder.empty()
        
        mask, upper_mask, lower_mask, landmarks, h, w = get_lip_mask_and_landmarks(image_bgr)
            
        if mask is None:
            st.error("❌ AURALITH AI could not locate a face in this canvas. Ensure adequate lighting and front alignment.")
            st.stop()
            
        if mask.sum() == 0:
            st.error("❌ Lip contours not isolated correctly. Try capturing with a neutral facial expression.")
            st.stop()
            
        # Detect Skin Tone & Undertone
        skin_tone, _, undertone = detect_skin_tone(image_bgr, landmarks, h, w)
        recommended_shades = SKIN_TONE_RECOMMENDATIONS.get(skin_tone, [])
        
        # Tone & Undertone Badge
        tone_css = SKIN_TONE_COLORS.get(skin_tone, "#888")
        txt_col  = "#fff" if skin_tone in ("Olive", "Tan", "Deep", "Medium") else "#1a1a1a"
        st.markdown(
            f'<div class="skin-badge" style="background:{tone_css};color:{txt_col};margin-right:10px;">'
            f'🎨 Complexion Detected: <b>{skin_tone}</b></div>'
            f'<div class="skin-badge" style="background:#2b1020;color:#ffffff;border-color:#d4a373 !important;">'
            f'🔮 Estimated Undertone: <b>{undertone}</b></div>',
            unsafe_allow_html=True,
        )
        
        # Display AI Undertone Insights Panel
        insights = BEAUTY_INSIGHTS.get(skin_tone, {
            "undertones": ["Warm Rose Pink", "Berry Plum", "Coral Nude"],
            "collections": ["🍇 Berry Luxe Collection", "💋 Aura Rouge Collection"],
            "advice": "Your complexion pairs exceptionally well with rich pigments and luxury finishes."
        })
        undertones_str = ", ".join(insights["undertones"])
        collections_str = ", ".join([c.replace("💋 ", "").replace("🌸 ", "").replace("🌿 ", "").replace("🍇 ", "").replace("🌊 ", "").replace("🔮 ", "") for c in insights["collections"]])
        
        st.markdown(f"""
        <div class="glass-card" style="background: linear-gradient(135deg, rgba(43, 16, 32, 0.03) 0%, rgba(212, 163, 115, 0.08) 100%) !important; border: 1.5px solid #d4a373 !important; padding:22px; margin-top:10px; margin-bottom:20px; border-radius: 16px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                <span style="font-size: 18px;">🔮</span>
                <span style="font-size:12px; text-transform:uppercase; letter-spacing:1.5px; color:#2b1020; font-weight:800; font-family:'Montserrat', sans-serif;">AURALITH AI Complexion Insights</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                <div>
                    <span style="font-size: 9px; text-transform: uppercase; color: #8b8b9c; font-weight: 700; display: block; letter-spacing: 0.5px;">Detected Profile</span>
                    <span style="font-size: 14px; font-weight: 700; color: #2b1020;">{skin_tone} Complexion ({undertone})</span>
                </div>
                <div>
                    <span style="font-size: 9px; text-transform: uppercase; color: #8b8b9c; font-weight: 700; display: block; letter-spacing: 0.5px;">Best Undertones</span>
                    <span style="font-size: 14px; font-weight: 700; color: #fc2779;">{undertones_str}</span>
                </div>
            </div>
            <div style="margin-bottom: 15px;">
                <span style="font-size: 9px; text-transform: uppercase; color: #8b8b9c; font-weight: 700; display: block; letter-spacing: 0.5px;">Recommended Collections</span>
                <span style="font-size: 13px; font-weight: 600; color: #2b1020;">{collections_str}</span>
            </div>
            <div style="border-top: 1px solid rgba(212, 163, 115, 0.2); padding-top: 12px;">
                <span style="font-size: 9px; text-transform: uppercase; color: #8b8b9c; font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Beauty Consultant Advice</span>
                <p style="font-size:12px; color:#555; margin-bottom: 0; line-height:1.6; font-style: italic;">
                    "{insights["advice"]}"
                </p>
            </div>
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
                        conf_rec, rec_cat = get_match_score(rs, skin_tone, finish)
                        if st.button(f"👄 {rs}\n{conf_rec}% Match", key=f"rec_{rs}"):
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
                image_bgr, mask, upper_mask, lower_mask, final_color, opacity, finish,
                volume_enhancement=volume_enhancement, liner_mode=liner_mode, liner_color_bgr=rec_liner["color"]
            )
            # Log try-on to history
            if not st.session_state.try_on_history or st.session_state.try_on_history[-1]["shade"] != active_shade:
                st.session_state.try_on_history.append({
                    "shade": active_shade,
                    "palette": palette,
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
        
        # Calculate match & Beauty Score
        confidence, match_cat = get_match_score(active_shade, skin_tone, finish)
        b_score, harmony, rec_level = get_beauty_score_and_harmony(confidence, active_shade, undertone)
        
        # Match Confidence progress bar UI
        st.markdown(f"""
        <div style="margin: 15px 0 25px 0; background: rgba(255,255,255,0.7); border: 1px solid #e8e8f2; padding: 15px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.01);">
            <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:700; color:#2b1020; text-transform:uppercase; letter-spacing:0.5px;">
                <span>AURALITH BEAUTY SCORE™</span>
                <span style="color:#fc2779;">{b_score} / 100 Harmony ({harmony})</span>
            </div>
            <div style="background-color:#e8e8f2; border-radius:10px; height:8px; width:100%; margin-top:6px; overflow:hidden;">
                <div style="background: linear-gradient(90deg, #fc2779 0%, #d4a373 100%); width:{b_score}%; height:100%; border-radius:10px;"></div>
            </div>
            <div style="font-size: 11px; color:#8b8b9c; margin-top:5px; font-style:italic;">
                Recommendation Level: {rec_level} | Skin Match: {confidence}% ({match_cat})
            </div>
        </div>
        """, unsafe_allow_html=True)

        # OCCASION & MOOD DISPLAY
        meta = SHADE_METADATA.get(active_shade, {"mood": "Bold & Confident", "occasion": "Evening Event"})
        st.markdown(f"""
        <div style="background: rgba(18, 9, 16, 0.03); border: 1.5px solid #d4a373; padding: 12px; border-radius: 12px; margin-bottom: 20px;">
            <div style="font-size: 10px; color:#d4a373; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-bottom: 4px;">Cosmetic Insights</div>
            <div style="font-size: 13px; color:#2b1020; font-weight:600;">✨ Mood: <b>{meta['mood']}</b></div>
            <div style="font-size: 13px; color:#2b1020; font-weight:600; margin-top: 2px;">📍 Occasion: <b>{meta['occasion']}</b></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Before / After Comparison slider
        st.markdown("<h4 style='color:#2b1020;'>Transformation Preview ✨</h4>", unsafe_allow_html=True)
        
        slider_html = render_transformation_studio(image_bgr, result_bgr)
        st.iframe(slider_html, height=600)
        
        st.write("")
        
        # Side by side fallback
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.image(image_rgb, caption="Original Silhouette Canvas", use_container_width=True)
        with col_s2:
            st.image(result_rgb, caption=f"AURALITH Finish: {active_shade} ({finish})", use_container_width=True)
            
        st.success(f"✅ Applied **{active_shade}** ({finish}) | Opacity: {opacity:.0%} | Score: **{b_score}/100** ({harmony})")
        
        # Save Look Button
        st.write("")
        col_save, _ = st.columns([1, 1])
        with col_save:
            if st.button("Save To Lookbook ✦", use_container_width=True):
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
                        "undertone": undertone or "Not Detected",
                        "beauty_score": b_score,
                        "harmony": harmony,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "bgr": tuple(int(c) for c in final_color),
                        "image_path": img_path if image_saved else ""
                    }
                    st.session_state.saved_looks.append(look_data)
                    save_user_looks(st.session_state.username, st.session_state.saved_looks)
                    
                    if skin_tone and skin_tone not in st.session_state.skin_tone_history:
                        st.session_state.skin_tone_history.append(skin_tone)
                    st.success("Beauty canvas saved to your Lookbook! ✦")

def render_dashboard_page():
    st.title("📸 AURALITH Lookbook ✦")
    st.markdown("### ✨ Your Personalized Digital Beauty Portfolio")
    
    # Calculate persistent beauty analytics
    analytics = calculate_beauty_analytics(st.session_state.saved_looks)
    
    total_saved = len(st.session_state.saved_looks)
    last_skin_tone = analytics["last_detected_complexion"]
    last_undertone = analytics.get("last_detected_undertone", "Not Detected")
    fav_palette = analytics["favorite_collection"]
    fav_finish = analytics["preferred_finish"]
    avg_score = analytics["average_match_score"]
    avg_b_score = analytics.get("average_beauty_score", 0)
    most_used_shade = analytics["most_used_shade"]
    style_summary = analytics.get("personality_summary", "Start saving looks to build your personality profile.")
    
    clean_collection = fav_palette.replace("💋 ", "").replace("🌸 ", "").replace("🌿 ", "").replace("🍇 ", "").replace("🌊 ", "").replace("🔮 ", "")
    clean_finish = fav_finish.replace(" 💋", "").replace(" ✨", "").replace(" 💄", "").replace(" 🪄", "").replace(" 💎", "")
    
    # Render Beauty Profile Card
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #2b1020 0%, #d4a373 50%, #fc2779 100%); border-radius: 20px; padding: 30px; color: #ffffff; box-shadow: 0 15px 35px rgba(43, 16, 32, 0.25); border: 2px solid #ffffff; margin-bottom: 30px; position: relative; overflow: hidden;">
        <div style="position: absolute; right: -50px; bottom: -50px; opacity: 0.15; font-size: 200px; font-weight: bold; pointer-events: none; user-select: none;">✦</div>
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 15px; margin-bottom: 20px;">
            <div>
                <h3 style="margin: 0; color: #ffffff !important; font-family: 'Montserrat', sans-serif; font-size: 20px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase;">AURALITH MEMBER</h3>
                <span style="font-size: 10px; color: #d4a373; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;">✦ VIP BEAUTY PROFILE ✦</span>
            </div>
            <div style="font-size: 24px;">✨</div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            <div>
                <span style="font-size: 9px; text-transform: uppercase; color: rgba(255,255,255,0.6); font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Complexion Type</span>
                <span style="font-size: 14px; font-weight: 700;">{last_skin_tone} ({last_undertone})</span>
            </div>
            <div>
                <span style="font-size: 9px; text-transform: uppercase; color: rgba(255,255,255,0.6); font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Preferred Finish</span>
                <span style="font-size: 14px; font-weight: 700;">{clean_finish}</span>
            </div>
            <div>
                <span style="font-size: 9px; text-transform: uppercase; color: rgba(255,255,255,0.6); font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Favorite Collection</span>
                <span style="font-size: 14px; font-weight: 700;">{clean_collection}</span>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
            <div>
                <span style="font-size: 9px; text-transform: uppercase; color: rgba(255,255,255,0.6); font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Most Tried Shade</span>
                <span style="font-size: 14px; font-weight: 700; color: #ffffff;">{most_used_shade}</span>
            </div>
            <div>
                <span style="font-size: 9px; text-transform: uppercase; color: rgba(255,255,255,0.6); font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Average Match Score</span>
                <span style="font-size: 14px; font-weight: 700; color: #ffffff;">{avg_score}% Compatibility</span>
            </div>
            <div>
                <span style="font-size: 9px; text-transform: uppercase; color: rgba(255,255,255,0.6); font-weight: 700; display: block; letter-spacing: 0.5px; margin-bottom: 4px;">Average Beauty Score™</span>
                <span style="font-size: 14px; font-weight: 700; color: #ffffff;">{avg_b_score} / 100</span>
            </div>
        </div>
        <div style="border-top: 1px solid rgba(255,255,255,0.15); padding-top: 15px; font-style: italic; font-size: 12px; color: rgba(255,255,255,0.9); line-height: 1.6;">
            "{style_summary}"
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Statistics Display
    st.markdown("### 📊 AURALITH Signature Statistics")
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card">
            <div class="metric-title">Total Looks Saved</div>
            <div class="metric-value">💖 {total_saved}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Complexion Profile</div>
            <div class="metric-value">🎨 {last_skin_tone}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Undertone Profile</div>
            <div class="metric-value">🔮 {last_undertone}</div>
        </div>
    </div>
    <div class="metric-container" style="margin-top: -15px;">
        <div class="metric-card">
            <div class="metric-title">Most Used Finish</div>
            <div class="metric-value">✨ {clean_finish}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Most Used Shade</div>
            <div class="metric-value">💋 {most_used_shade}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Average Beauty Score™</div>
            <div class="metric-value">📈 {avg_b_score}/100</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Saved Looks Gallery Manager
    st.markdown("### 📸 Your Saved Try-On Gallery")
    if not st.session_state.saved_looks:
        st.info("No saved looks found yet. Try on different lipstick shades, and click 'Save To Lookbook ✦' to create your lookbook!")
    else:
        st.markdown("<p style='color:#8b8b9c; font-size:12px;'>Saved looks inside your luxury Lookbook canvas:</p>", unsafe_allow_html=True)
        
        # Grid layout for looks
        cols = st.columns(3)
        for idx, look in enumerate(st.session_state.saved_looks):
            col_idx = idx % 3
            with cols[col_idx]:
                if "image_path" in look and os.path.exists(look["image_path"]):
                    st.image(look["image_path"], use_container_width=True)
                else:
                    st.markdown('<div style="width:100%; height:200px; border-radius:12px; background:rgba(255,255,255,0.02); display:flex; align-items:center; justify-content:center; color:#555; font-size:12px; border: 1px solid rgba(255,255,255,0.05); margin-bottom:10px;">No Image Preview</div>', unsafe_allow_html=True)
                
                # Metadata card
                r, g, b = look["bgr"][2], look["bgr"][1], look["bgr"][0]
                look_score = look.get("beauty_score", 85)
                look_harmony = look.get("harmony", "Luxury Harmony")
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
                        <strong>Skin Profile:</strong> {look.get("skin_tone", "Medium")} ({look.get("undertone", "Neutral")})<br>
                        <strong>Beauty Score™:</strong> {look_score}/100 ({look_harmony})<br>
                        <span style="font-size: 9px; color: #888;">Saved: {look["timestamp"]}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Delete Look 🗑", key=f"del_{look['id']}", use_container_width=True):
                    if "image_path" in look and os.path.exists(look["image_path"]):
                        try:
                            os.remove(look["image_path"])
                        except Exception:
                            pass
                    st.session_state.saved_looks.pop(idx)
                    save_user_looks(st.session_state.username, st.session_state.saved_looks)
                    st.toast("Look deleted.")
                    st.rerun()

        # Recommended shades summary inside Dashboard
        st.write("")
        st.divider()
        st.markdown("### 💖 Complexion Match Picks")
        st.markdown(f"Based on your profile, your last detected skin tone is **{last_skin_tone} ({last_undertone})**. Here are recommended shades:")
        
        rec_shades = SKIN_TONE_RECOMMENDATIONS.get(last_skin_tone, [])
        if rec_shades:
            rec_cols = st.columns(min(len(rec_shades), 5))
            for idx, shade_name in enumerate(rec_shades[:5]):
                if shade_name in ALL_SHADES:
                    shade_info = ALL_SHADES[shade_name]
                    bgr = shade_info["bgr"]
                    r, g, b = bgr[2], bgr[1], bgr[0]
                    with rec_cols[idx]:
                        conf, _ = get_match_score(shade_name, last_skin_tone, "Glossy 💋")
                        b_score, harmony, _ = get_beauty_score_and_harmony(conf, shade_name, last_undertone)
                        st.markdown(f"""
                        <div style="background: rgba(255,255,255,0.6); padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #e8e8f2; box-shadow: 0 4px 10px rgba(0,0,0,0.01);">
                            <div style="width: 24px; height: 24px; border-radius: 50%; background: rgb({r},{g},{b}); margin: 0 auto 6px auto; border: 1px solid rgba(0,0,0,0.1);"></div>
                            <span style="font-size:11px; font-weight:600; display:block; color:#2b1020; height:32px; overflow:hidden; line-height:1.2;">{shade_name}</span>
                            <span style="font-size:10px; color:#fc2779; font-weight:700;">{b_score}/100 Harmony</span>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("Apply ✦", key=f"rec_dash_{shade_name}", use_container_width=True):
                            st.session_state.selected_shade = shade_name
                            st.session_state.selected_palette = shade_info["palette"]
                            st.session_state.current_page = "💄 Virtual Try-On Studio"
                            st.rerun()

def render_live_studio_page():
    st.markdown("""
    <div class="auralith-promo-banner">
        <span>🎥 AURALITH LIVE BEAUTY STUDIO: Experience luxury beauty in real time.</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.title("🎥 Live AI Beauty Studio")
    st.markdown("### ✦ Real-Time Live Makeup Simulation")
    
    col_left, col_right = st.columns([1.3, 1.0])
    
    with col_right:
        st.markdown("#### 🎨 Color Selection")
        # Palette selection
        default_palette = st.session_state.selected_palette
        if default_palette not in lipstick_palettes:
            default_palette = list(lipstick_palettes.keys())[0]
            
        palette = st.selectbox("Collection", list(lipstick_palettes.keys()), index=list(lipstick_palettes.keys()).index(default_palette), key="live_palette")
        
        # Shade selection
        shade_list = list(lipstick_palettes[palette].keys())
        default_shade = st.session_state.selected_shade
        default_shade_idx = 0
        if default_shade in shade_list:
            default_shade_idx = shade_list.index(default_shade)
            
        shade = st.selectbox("Shade Profile", shade_list, index=default_shade_idx, key="live_shade")
        
        # Sync to session state
        st.session_state.selected_shade = shade
        st.session_state.selected_palette = palette
        
        # Details & swatches
        circles_html = ""
        for name, c in lipstick_palettes[palette].items():
            border = "4px solid #d4a373" if name == shade else "2px solid rgba(255,255,255,0.4)"
            r, g, b = c[2], c[1], c[0]
            circles_html += f'<div style="display:inline-block;width:30px;height:30px;border-radius:50%;background:rgb({r},{g},{b});margin:4px;border:{border};box-shadow:0 3px 6px rgba(0,0,0,0.15);"></div>'
        st.markdown(circles_html, unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:11px; color:#8b8b9c; font-style:italic; margin-top:5px;'>'{SHADE_DESCRIPTIONS.get(shade, '')}'</p>", unsafe_allow_html=True)
        
        # Control parameters
        opacity = st.slider("Texture Coverage (Opacity)", 0.20, 1.00, st.session_state.selected_opacity, step=0.05, key="live_opacity")
        st.session_state.selected_opacity = opacity
        
        finishes = ["Glossy 💋", "Satin ✨", "Matte 💄", "Velvet Finish 🪄", "Glass Finish 💎"]
        default_finish = st.session_state.selected_finish
        default_finish_idx = finishes.index(default_finish) if default_finish in finishes else 0
        finish = st.selectbox("Cosmetic Finish", finishes, index=default_finish_idx, key="live_finish")
        st.session_state.selected_finish = finish
        
        # Smart Lip Liner and Volume Enhancement defaults
        liner_mode = "None"
        volume_enhancement = "Natural"
        rec_liner = {"name": "Natural Define", "color": (128, 128, 128)}
        
        # Match scores calculation
        last_detected_skin = "Medium"
        last_detected_undertone = "Neutral"
        for look in reversed(st.session_state.saved_looks):
            if look.get("skin_tone") and look["skin_tone"] != "Not Detected":
                last_detected_skin = look["skin_tone"]
                last_detected_undertone = look.get("undertone", "Neutral")
                break
                
        match_val, match_cat = get_match_score(shade, last_detected_skin, finish)
        b_score, harmony, rec_level = get_beauty_score_and_harmony(match_val, shade, last_detected_undertone)
        
        # OCCASION & MOOD DISPLAY
        meta = SHADE_METADATA.get(shade, {"mood": "Bold & Confident", "occasion": "Evening Event"})
        st.markdown(f"""
        <div style="background: rgba(18, 9, 16, 0.03); border: 1.5px solid #d4a373; padding: 12px; border-radius: 12px; margin-top: 15px;">
            <div style="font-size: 10px; color:#d4a373; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-bottom: 4px;">Cosmetic Insights</div>
            <div style="font-size: 13px; color:#2b1020; font-weight:600;">✨ Mood: <b>{meta['mood']}</b></div>
            <div style="font-size: 13px; color:#2b1020; font-weight:600; margin-top: 2px;">📍 Occasion: <b>{meta['occasion']}</b></div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_left:
        st.markdown("#### 🎥 Live Camera Studio View")
        final_color = lipstick_palettes[palette][shade]
        liner_color_bgr = rec_liner["color"]
        
        # Render the custom live webcam component!
        res = live_beauty_studio(
            shade_name=shade,
            collection=palette,
            color_bgr=final_color,
            opacity=opacity,
            finish=finish,
            liner_mode=liner_mode,
            liner_color_bgr=liner_color_bgr,
            volume_enhancement=volume_enhancement,
            match_score=match_val,
            beauty_score=b_score,
            harmony=harmony,
            rec_level=rec_level,
            mood=meta["mood"],
            occasion=meta["occasion"]
        )
        
        # Handle captured look from the component
        if res and res.get("action") == "capture_live_look":
            capture_id = res.get("capture_id")
            if "processed_captures" not in st.session_state:
                st.session_state.processed_captures = set()
            
            if capture_id not in st.session_state.processed_captures:
                st.session_state.processed_captures.add(capture_id)
                img_data_base64 = res["image_data"].split(",")[1]
                import base64
                img_bytes = base64.b64decode(img_data_base64)
                
                look_id = str(uuid.uuid4())
                user_dir = get_user_profile_dir(st.session_state.username)
                user_images_dir = os.path.join(user_dir, "images")
                os.makedirs(user_images_dir, exist_ok=True)
                
                img_filename = f"{look_id}.png"
                img_path = os.path.join(user_images_dir, img_filename)
                
                with open(img_path, "wb") as f_img:
                    f_img.write(img_bytes)
                    
                look_data = {
                    "id": look_id,
                    "shade": res["shade"],
                    "palette": palette,
                    "finish": res["finish"],
                    "opacity": opacity,
                    "skin_tone": last_detected_skin,
                    "undertone": last_detected_undertone,
                    "beauty_score": res["beauty_score"],
                    "harmony": res["harmony"],
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "bgr": tuple(int(c) for c in final_color),
                    "image_path": img_path
                }
                st.session_state.saved_looks.append(look_data)
                save_user_looks(st.session_state.username, st.session_state.saved_looks)
                st.success("📸 Live capture saved to your Lookbook! ✦")
                st.rerun()

def render_mobile_page():
    st.markdown("""
    <div class="auralith-promo-banner">
        <span>📱 MOBILE BEAUTY EXPERIENCE: Exquisite try-on access directly from your phone.</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.title("📱 Mobile Beauty Experience")
    st.markdown("### ✦ Take AURALITH with You")
    
    col_left, col_right = st.columns([1.2, 1.0])
    
    with col_left:
        st.markdown("""
        <div class="glass-card" style="border-top: 4px solid #d4a373 !important;">
            <h3 style="margin-top:0; color:#2b1020 !important;">QR CONNECT SYSTEM</h3>
            <p style="font-size:13px; color:#555; line-height:1.6; margin-bottom:15px;">
                Scan the QR code on the right with your smartphone camera to launch the AURALITH V3.1 Live Studio directly on your mobile device.
            </p>
            <h4 style="color:#fc2779; font-size:14px; margin-bottom:5px;">Steps to Connect:</h4>
            <ol style="font-size:12px; color:#555; line-height:1.8; margin-left:20px;">
                <li>Connect your smartphone to the <strong>same Wi-Fi network</strong> as this computer.</li>
                <li>Open your smartphone's Camera app and point it at the QR code.</li>
                <li>Tap the link banner that pops up on your screen.</li>
                <li>Accept camera permissions when prompted in your mobile browser.</li>
                <li>Experience luxury beauty try-on on the go!</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        
    with col_right:
        # Get local IP address
        import socket
        def get_local_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = 'localhost'
            finally:
                s.close()
            return ip
            
        local_ip = get_local_ip()
        mobile_url = f"http://{local_ip}:8501"
        
        # Generate QR code using public web api (extremely reliable, requires no extra python libraries)
        qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={mobile_url}"
        
        st.markdown(f"""
        <div class="glass-card" style="text-align: center; border-top: 4px solid #fc2779 !important;">
            <h4 style="margin-top:0; color:#fc2779 !important;">SCAN ME</h4>
            <div style="margin: 20px 0; background: #ffffff; padding: 15px; border-radius: 12px; display: inline-block; border: 1.5px solid #e8e8f2;">
                <img src="{qr_api_url}" alt="AURALITH Mobile Studio Link" style="width: 200px; height: 200px; display: block;">
            </div>
            <p style="font-size: 11px; font-weight: 700; color: #2b1020; margin-bottom: 2px;">Mobile Connection URL:</p>
            <code style="font-size: 11px; color:#fc2779; background: rgba(252, 39, 121, 0.05); padding: 3px 8px; border-radius: 4px;">{mobile_url}</code>
        </div>
        """, unsafe_allow_html=True)

# -----------------
# CONTROL FLOW & ROUTING
# -----------------
def render_nykaa_header():
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
                    st.session_state.current_page = "💄 Virtual Try-On Studio"
                    st.toast(f"Found and loaded shade: {matched_shade} 💋")
                    st.rerun()
                else:
                    st.toast(f"No shades found matching '{search_query}' 🔍", icon="❌")
                    
        with col_nav:
            nav_cols = st.columns(3)
            bag_count = len(st.session_state.saved_looks)
            
            with nav_cols[0]:
                if st.button("✦ Studio", key="nav_studio_btn", use_container_width=True):
                    st.session_state.current_page = "💄 Virtual Try-On Studio"
                    st.rerun()
            with nav_cols[1]:
                if st.button("✦ Locator", key="nav_locator_btn", use_container_width=True):
                    st.session_state.current_page = "✨ AURALITH Home"
                    st.session_state.show_locator = True
                    st.rerun()
            with nav_cols[2]:
                if st.button(f"✦ Bag ({bag_count})", key="nav_bag_btn", use_container_width=True):
                    st.session_state.current_page = "📸 AURALITH Lookbook"
                    st.rerun()

if not st.session_state.logged_in:
    render_login_page()
else:
    render_nykaa_header()
    render_sidebar()
    
    # Store locator helper
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
    elif st.session_state.current_page == "💄 Virtual Try-On Studio":
        render_try_on_page()
    elif st.session_state.current_page == "🎥 Live AI Beauty Studio":
        render_live_studio_page()
    elif st.session_state.current_page == "📸 AURALITH Lookbook":
        render_dashboard_page()
    elif st.session_state.current_page == "📱 Mobile Beauty Experience":
        render_mobile_page()
