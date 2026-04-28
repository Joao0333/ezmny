-- supabase_setup.sql
-- Corre este SQL no Supabase Dashboard → SQL Editor

-- ── USERS ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,
    first_name  TEXT,
    last_seen   TIMESTAMPTZ DEFAULT NOW()
);

-- ── MESSAGES (histórico de conversa) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_user_created
    ON messages(user_id, created_at DESC);

-- ── PROMISES ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promises (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    promise_text TEXT NOT NULL,
    fulfilled    BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    deadline     TIMESTAMPTZ,
    fulfilled_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_promises_user_fulfilled
    ON promises(user_id, fulfilled);

-- ── RLS (Row Level Security) — opcional mas recomendado ────────────────────
-- Se quiseres ativar RLS no Supabase, descomenta:
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE promises ENABLE ROW LEVEL SECURITY;
