"""
AURALITH — One-time migration script.

Migrates the legacy Streamlit-era data:
  - users.xlsx                           -> users table
  - user_profiles/<username>/looks.json  -> looks table (image files uploaded to Vercel Blob)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras
import requests

BLOB_API_URL = "https://blob.vercel-storage.com"


def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("ERROR: set DATABASE_URL environment variable before running.")
    return psycopg2.connect(db_url)


def upload_to_blob(file_path: Path, blob_token: str) -> str:
    """
    Uploads a local image file to Vercel Blob and returns its public URL.
    """
    with open(file_path, "rb") as f:
        resp = requests.put(
            f"{BLOB_API_URL}/{file_path.name}",
            data=f,
            headers={
                "Authorization": f"Bearer {blob_token}",
                "x-content-type": "image/png",
            },
        )
    resp.raise_for_status()
    return resp.json()["url"]


def migrate_users(conn, users_xlsx_path: str) -> dict:
    """
    Reads users.xlsx and inserts/updates rows in the users table.
    """
    print(f"Reading users from {users_xlsx_path}...")
    df = pd.read_excel(users_xlsx_path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Required columns in the spreadsheet: username, password_hash
    required = {"username", "password_hash"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"ERROR: users.xlsx is missing expected columns: {missing}. "
                 f"Found columns: {list(df.columns)}")

    username_to_id = {}

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            username = str(row["username"]).strip()
            
            # Email is NOT NULL in database, but missing in excel. Generate placeholder.
            if "email" in df.columns and pd.notna(row["email"]):
                email = str(row["email"]).strip().lower()
            else:
                email = f"{username.lower()}@example.com"
                
            stored_hash = str(row["password_hash"]).strip()
            
            if "display_name" in df.columns and pd.notna(row["display_name"]):
                display_name = str(row["display_name"]).strip()
            else:
                display_name = username

            # Insert as-is (we preserve the SHA-256 hash, index.py will handle login/upgrades)
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, display_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                    SET email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        display_name = EXCLUDED.display_name
                RETURNING id;
                """,
                (username, email, stored_hash, display_name),
            )
            user_id = cur.fetchone()[0]
            username_to_id[username] = user_id

    conn.commit()
    print(f"Migrated {len(username_to_id)} users successfully. (Mock emails generated where missing).")
    return username_to_id


def normalize_finish(raw_finish: str) -> str:
    """
    Normalizes look finishes to meet check constraint: 'matte', 'satin', 'glossy', 'velvet', 'glass'
    """
    f = str(raw_finish).lower()
    if "satin" in f or "✨" in f:
        return "satin"
    elif "gloss" in f or "💋" in f:
        return "glossy"
    elif "velvet" in f:
        return "velvet"
    elif "glass" in f:
        return "glass"
    elif "matte" in f or "💄" in f:
        return "matte"
    return "matte"


def migrate_looks(conn, profiles_dir: str, username_to_id: dict, blob_token: str | None):
    """
    Walks user_profiles/<username>/looks.json and inserts rows into the looks table.
    """
    profiles_root = Path(profiles_dir)
    if not profiles_root.exists():
        sys.exit(f"ERROR: profiles directory not found: {profiles_dir}")

    total_looks = 0
    failed_looks = 0
    skipped_users = []

    with conn.cursor() as cur:
        for user_dir in profiles_root.iterdir():
            if not user_dir.is_dir():
                continue

            username = user_dir.name
            user_id = username_to_id.get(username)
            if not user_id:
                skipped_users.append(username)
                continue

            looks_json_path = user_dir / "looks.json"
            if not looks_json_path.exists():
                continue

            with open(looks_json_path, "r", encoding="utf-8") as f:
                looks = json.load(f)

            for look in looks:
                # Find image path
                image_path_raw = look.get("image_path", "")
                image_path = Path(image_path_raw)
                
                # Check absolute / relative to workspace
                if not image_path.exists() and image_path_raw:
                    image_path = user_dir / "images" / Path(image_path_raw).name
                if not image_path.exists() and image_path_raw:
                    image_path = user_dir / image_path_raw

                # Upload to Blob
                if blob_token and image_path.exists():
                    try:
                        image_url = upload_to_blob(image_path, blob_token)
                    except Exception as e:
                        print(f"WARNING: Image upload failed for {image_path}: {e}")
                        image_url = f"UPLOAD_FAILED:{image_path.name}"
                else:
                    image_url = look.get("image_path", "MISSING_IMAGE")

                # Normalize color
                bgr = look.get("bgr")
                if isinstance(bgr, list) and len(bgr) == 3:
                    shade_hex = f"#{bgr[2]:02x}{bgr[1]:02x}{bgr[0]:02x}"
                else:
                    shade_hex = "#000000"

                # Normalize finish
                finish = normalize_finish(look.get("finish", "matte"))

                # Package metadata
                metadata = {
                    "legacy_id": look.get("id"),
                    "palette": look.get("palette"),
                    "opacity": look.get("opacity"),
                    "skin_tone": look.get("skin_tone"),
                    "timestamp": look.get("timestamp"),
                    "bgr": bgr
                }

                # Safe per-row insert using database SAVEPOINTs
                try:
                    cur.execute("SAVEPOINT look_migration_row;")
                    cur.execute(
                        """
                        INSERT INTO looks
                            (user_id, shade_name, shade_hex, finish, confidence,
                             source_path, image_blob_url, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            user_id,
                            look.get("shade", "Unknown"),
                            shade_hex,
                            finish,
                            None,  # Confidence from legacy is null/none
                            "studio",
                            image_url,
                            json.dumps(metadata),
                        ),
                    )
                    cur.execute("RELEASE SAVEPOINT look_migration_row;")
                    total_looks += 1
                except Exception as e:
                    cur.execute("ROLLBACK TO SAVEPOINT look_migration_row;")
                    print(f"ERROR: Failed migrating look {look.get('id')} for user {username}: {e}")
                    failed_looks += 1

    conn.commit()
    print(f"Looks migration complete: {total_looks} succeeded, {failed_looks} failed.")
    if skipped_users:
        print(f"WARNING: {len(skipped_users)} profile directories had no matching user "
              f"in users.xlsx and were skipped: {skipped_users}")


def main():
    parser = argparse.ArgumentParser(description="Migrate AURALITH legacy data to Postgres + Blob.")
    parser.add_argument("--users-xlsx", required=True, help="Path to users.xlsx")
    parser.add_argument("--profiles-dir", required=True, help="Path to user_profiles/ directory")
    args = parser.parse_args()

    blob_token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not blob_token:
        print("WARNING: BLOB_READ_WRITE_TOKEN not set — look images will NOT be uploaded, "
              "only metadata rows will be created with placeholder URLs.")

    conn = get_db_connection()
    try:
        username_to_id = migrate_users(conn, args.users_xlsx)
        migrate_looks(conn, args.profiles_dir, username_to_id, blob_token)
    finally:
        conn.close()

    print("Migration complete.")


if __name__ == "__main__":
    main()
