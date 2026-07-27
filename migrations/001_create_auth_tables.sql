-- Migration: 001_create_auth_tables.sql
-- Run this once against the Supabase PostgreSQL database
-- to create auth tables in the rico schema.

CREATE TABLE IF NOT EXISTS rico.app_user (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL DEFAULT 'user',
    plant_id        VARCHAR(100),
    plant_name      VARCHAR(255),
    created_by      INT REFERENCES rico.app_user(id) ON DELETE SET NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rico.invite_token (
    id              SERIAL PRIMARY KEY,
    token           VARCHAR(255) UNIQUE NOT NULL,
    email           VARCHAR(255),
    invited_by      INT REFERENCES rico.app_user(id) ON DELETE CASCADE NOT NULL,
    plant_id        VARCHAR(100),
    used            BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_app_user_email ON rico.app_user(email);

-- Index for token lookups
CREATE INDEX IF NOT EXISTS idx_invite_token_token ON rico.invite_token(token);

-- Index for plant-based user queries
CREATE INDEX IF NOT EXISTS idx_app_user_plant_id ON rico.app_user(plant_id);
