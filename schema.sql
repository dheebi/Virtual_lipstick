-- AURALITH AI Lipstick Studio — Postgres Schema
-- Target: Vercel Postgres / Supabase / Neon (any standard Postgres 14+)
-- Run this once against a fresh database before running migrate_data.py

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64)  UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   TEXT         NOT NULL,        -- bcrypt/argon2 hash, never plaintext
    display_name    VARCHAR(128),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users (email);

-- One row per saved look (a captured/rendered lipstick try-on result)
CREATE TABLE IF NOT EXISTS looks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shade_name      VARCHAR(128) NOT NULL,
    shade_hex       VARCHAR(7)   NOT NULL,         -- e.g. '#fc2779'
    finish          VARCHAR(16)  NOT NULL CHECK (finish IN ('matte','satin','glossy','velvet','glass')),
    confidence      REAL,                          -- segmentation confidence score from Studio Path, nullable
    source_path     VARCHAR(16)  NOT NULL DEFAULT 'studio' CHECK (source_path IN ('live','studio')),
    image_blob_url  TEXT NOT NULL,                 -- Vercel Blob URL for the rendered image
    thumbnail_url   TEXT,                          -- optional smaller preview, also Blob-hosted
    metadata        JSONB,                         -- free-form: lighting conditions, roi bounds, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_looks_user_id    ON looks (user_id);
CREATE INDEX IF NOT EXISTS idx_looks_created_at ON looks (created_at DESC);

-- Optional: session/auth token tracking if you're not using a hosted auth provider
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,                 -- store a hash of the session token, never the raw token
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions (token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id    ON sessions (user_id);

-- Keep updated_at current on row changes
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
