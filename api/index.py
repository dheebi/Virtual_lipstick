import base64
import datetime
import hashlib
import io
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add root folder to sys.path to guarantee import of model_storage
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
import psycopg2
import psycopg2.errors
import psycopg2.extras
import bcrypt
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
from scipy import ndimage

from model_storage import get_session

app = FastAPI()


def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


# ---------------------------------------------------------------------------
# Password Validation Utilities
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hashes a password using direct bcrypt library.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies the password against the stored hash. Supports legacy SHA-256 hashes
    as well as standard bcrypt hashes.
    """
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False
    else:
        # Legacy SHA-256 hashing
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        return legacy_hash == stored_hash


# ---------------------------------------------------------------------------
# Session Auth Dependency
# ---------------------------------------------------------------------------

async def get_current_user(authorization: str = Header(None)) -> str:
    """
    Dependency that extracts the Bearer token from the Authorization header,
    verifies it against the sessions table in the database, and returns the user_id.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Must be 'Bearer <token>'."
        )
    
    token = authorization.split(" ")[1]
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id, expires_at 
                FROM sessions 
                WHERE token_hash = %s;
                """,
                (token_hash,)
            )
            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=401, detail="Session is invalid or has logged out.")
            
            expires_at = session["expires_at"]
            
            if expires_at.tzinfo is not None:
                expires_at = expires_at.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            
            if expires_at < datetime.utcnow():
                cur.execute("DELETE FROM sessions WHERE token_hash = %s;", (token_hash,))
                conn.commit()
                raise HTTPException(status_code=401, detail="Session has expired.")
            
            return str(session["user_id"])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Segmentation endpoint (Studio Path)
# ---------------------------------------------------------------------------

@app.post("/api/segment")
async def segment(
    image: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user)
):
    session = get_session()

    raw_bytes = await image.read()
    try:
        pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image payload. Must be a valid image file.")

    orig_w, orig_h = pil_img.size

    # --- Preprocessing & Letterboxing (preserves aspect ratio without distortion) ---
    scale = 128.0 / max(orig_w, orig_h)
    new_w = int(round(orig_w * scale))
    new_h = int(round(orig_h * scale))
    
    img_resized = pil_img.resize((new_w, new_h), resample=Image.Resampling.BILINEAR)
    img_array = np.array(img_resized).astype(np.float32) / 255.0
    
    pad_x = 128 - new_w
    pad_y = 128 - new_h
    pad_left = pad_x // 2
    pad_top = pad_y // 2
    
    input_tensor = np.zeros((1, 128, 128, 3), dtype=np.float32)
    input_tensor[0, pad_top:pad_top+new_h, pad_left:pad_left+new_w, :] = img_array

    # --- Run Inference ---
    outputs = session.run(None, {"Input": input_tensor})
    pred = outputs[0][0]  # shape (128, 128, 3)

    # --- Post-Processing & Extraction ---
    pred_channel = np.mean(pred, axis=-1)  # shape (128, 128)
    cropped_mask = pred_channel[pad_top:pad_top+new_h, pad_left:pad_left+new_w]

    # Calculate confidence: mean predicted probability of foreground pixels (p > 0.5)
    lip_pixels = cropped_mask[cropped_mask > 0.5]
    confidence = float(np.mean(lip_pixels)) if lip_pixels.size > 0 else 0.0

    # Create binary mask for morphological operations
    binary_mask = (cropped_mask > 0.5).astype(bool)

    # Morphological refinement using scipy:
    structure_3 = np.ones((3, 3), dtype=bool)
    structure_5 = np.ones((5, 5), dtype=bool)
    
    opened = ndimage.binary_opening(binary_mask, structure=structure_3)
    closed = ndimage.binary_closing(opened, structure=structure_5)
    smoothed = ndimage.gaussian_filter(closed.astype(float), sigma=1.5)

    # Resize back to original dimensions using PIL
    smoothed_u8 = (smoothed * 255).astype(np.uint8)
    mask_pil = Image.fromarray(smoothed_u8)
    mask_resized = mask_pil.resize((orig_w, orig_h), resample=Image.Resampling.BILINEAR)

    # Convert to base64 PNG
    buffered = io.BytesIO()
    mask_resized.save(buffered, format="PNG")
    mask_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return JSONResponse({
        "mask": f"data:image/png;base64,{mask_base64}",
        "confidence": round(confidence, 4),
    })


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(None)
):
    username = username.strip()
    email = email.strip().lower()
    display_name = (display_name or username).strip()
    password_hash = hash_password(password)
    
    conn = get_db()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO users (username, email, password_hash, display_name)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (username, email, password_hash, display_name),
                )
                row = cur.fetchone()
                user_id = str(row[0])
            except psycopg2.errors.UniqueViolation:
                raise HTTPException(status_code=409, detail="Username or email already exists")
            
            # Issue a session token
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(days=7)
            cur.execute(
                """
                INSERT INTO sessions (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s);
                """,
                (user_id, token_hash, expires_at)
            )
            conn.commit()
            return {
                "user_id": user_id,
                "session_token": token,
                "email_needs_update": False
            }
    finally:
        conn.close()


@app.post("/api/auth/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    username = username.strip()
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, password_hash, email FROM users WHERE username = %s;", (username,))
            user = cur.fetchone()
            if not user or not verify_password(password, user["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            user_id = str(user["id"])
            stored_hash = user["password_hash"]
            
            # Upgrade legacy SHA-256 hash to bcrypt immediately upon successful validation
            if not (stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")):
                new_bcrypt_hash = hash_password(password)
                cur.execute("UPDATE users SET password_hash = %s WHERE id = %s;", (new_bcrypt_hash, user_id))

            cur.execute("UPDATE users SET last_login_at = now() WHERE id = %s;", (user_id,))
            
            # Issue a session token
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(days=7)
            cur.execute(
                """
                INSERT INTO sessions (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s);
                """,
                (user_id, token_hash, expires_at)
            )
            
            # Check if email is a placeholder mock
            email_is_placeholder = user["email"].endswith("@example.com")
            
            conn.commit()
            return {
                "user_id": user_id,
                "session_token": token,
                "email_needs_update": email_is_placeholder
            }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Looks (Lookbook) endpoints
# ---------------------------------------------------------------------------

@app.get("/api/looks")
async def list_looks(
    current_user_id: str = Depends(get_current_user)
):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, shade_name, shade_hex, finish, confidence,
                       source_path, image_blob_url, thumbnail_url, metadata, created_at
                FROM looks
                WHERE user_id = %s
                ORDER BY created_at DESC;
                """,
                (current_user_id,),
            )
            return {"looks": cur.fetchall()}
    finally:
        conn.close()


@app.post("/api/looks")
async def save_look(
    shade_name: str = Form(...),
    shade_hex: str = Form(...),
    finish: str = Form(...),
    image_url: str = Form(...),
    confidence: float | None = Form(None),
    source_path: str = Form("studio"),
    metadata_json: str = Form(None),  # raw JSON string of any extra options
    current_user_id: str = Depends(get_current_user)
):
    from migrate_data import normalize_finish
    normalized_finish = normalize_finish(finish)
    
    extra_metadata = {}
    if metadata_json:
        try:
            extra_metadata = json.loads(metadata_json)
        except Exception:
            pass

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO looks
                    (user_id, shade_name, shade_hex, finish, confidence, source_path, image_blob_url, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    current_user_id,
                    shade_name,
                    shade_hex,
                    normalized_finish,
                    confidence,
                    source_path,
                    image_url,
                    json.dumps(extra_metadata),
                ),
            )
            look_id = cur.fetchone()[0]
            conn.commit()
            return {"look_id": str(look_id)}
    finally:
        conn.close()
