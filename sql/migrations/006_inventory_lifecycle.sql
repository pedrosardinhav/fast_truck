ALTER TABLE vehicles ADD COLUMN deleted_at TEXT;
ALTER TABLE vehicles ADD COLUMN deleted_by TEXT;
ALTER TABLE vehicles ADD COLUMN deleted_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE vehicles ADD COLUMN reserved_order_id TEXT;
ALTER TABLE vehicles ADD COLUMN reserved_until TEXT;
ALTER TABLE vehicles ADD COLUMN sold_at TEXT;

CREATE TABLE vehicle_sales (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    number TEXT NOT NULL UNIQUE,
    vehicle_id TEXT NOT NULL UNIQUE REFERENCES vehicles(id) ON DELETE RESTRICT,
    customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    order_id TEXT UNIQUE REFERENCES shop_orders(id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL UNIQUE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    channel TEXT NOT NULL CHECK (channel IN ('admin','shop')),
    created_by TEXT,
    created_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE vehicle_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    vehicle_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('created','updated','deleted','reserved','released','sold')),
    actor_id TEXT,
    order_id TEXT,
    reason TEXT NOT NULL DEFAULT '',
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_vehicle_events_vehicle ON vehicle_events(vehicle_id,seq DESC);
