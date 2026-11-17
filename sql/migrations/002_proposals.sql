CREATE TABLE IF NOT EXISTS proposals (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    number TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    vehicle_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT,
    base_price_cents INTEGER NOT NULL CHECK (base_price_cents >= 0),
    total_cents INTEGER NOT NULL CHECK (total_cents BETWEEN 0 AND 99999999999),
    valid_until TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Em elaboração' CHECK (status IN ('Em elaboração','Enviada','Aprovada','Cancelada')),
    customer_snapshot TEXT NOT NULL DEFAULT '{}',
    vehicle_snapshot TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proposals_customer ON proposals(customer_id);
CREATE INDEX IF NOT EXISTS idx_proposals_vehicle ON proposals(vehicle_id);
CREATE TABLE IF NOT EXISTS proposal_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents BETWEEN 0 AND 99999999),
    subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0)
);
CREATE INDEX IF NOT EXISTS idx_proposal_items_proposal ON proposal_items(proposal_id);
CREATE TABLE IF NOT EXISTS proposal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal ON proposal_events(proposal_id,id);
