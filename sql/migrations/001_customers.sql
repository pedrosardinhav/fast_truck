CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    cnpj TEXT NOT NULL UNIQUE,
    legal_name TEXT NOT NULL,
    trade_name TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    street TEXT NOT NULL,
    number TEXT NOT NULL,
    complement TEXT NOT NULL DEFAULT '',
    district TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    lookup_source TEXT NOT NULL DEFAULT '',
    lookup_at TEXT NOT NULL DEFAULT '',
    lookup_status TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(legal_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_customers_active ON customers(active);
