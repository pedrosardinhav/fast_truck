CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    customer_id TEXT UNIQUE REFERENCES customers(id) ON DELETE RESTRICT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'customer')),
    created_at TEXT NOT NULL,
    CHECK ((role = 'admin' AND customer_id IS NULL) OR (role = 'customer' AND customer_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS shop_sessions (
    token_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shop_sessions_expiry ON shop_sessions(expires_at);
