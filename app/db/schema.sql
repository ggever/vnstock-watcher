CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    email            TEXT UNIQUE NOT NULL,
    name             TEXT NOT NULL DEFAULT '',
    telegram_chat_id TEXT,
    is_admin         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS allowed_emails (
    email TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS symbols (
    id        SERIAL PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol    TEXT NOT NULL,
    threshold INTEGER NOT NULL,
    side      TEXT NOT NULL DEFAULT 'Cả hai',
    UNIQUE (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS orders (
    id      SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    time    TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    side    TEXT NOT NULL,
    volume  INTEGER NOT NULL,
    price   DOUBLE PRECISION NOT NULL,
    value   DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user_symbol_time ON orders (user_id, symbol, time);

CREATE TABLE IF NOT EXISTS settings (
    id       INTEGER PRIMARY KEY DEFAULT 1,
    interval INTEGER NOT NULL DEFAULT 10,
    CONSTRAINT settings_singleton CHECK (id = 1)
);
INSERT INTO settings (id, interval) VALUES (1, 10) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS poller_state (
    symbol       TEXT PRIMARY KEY,
    last_seen_at TIMESTAMPTZ
);
