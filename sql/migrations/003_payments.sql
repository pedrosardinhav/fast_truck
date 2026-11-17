CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE,
    proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,
    method TEXT NOT NULL CHECK (method IN ('Pix','Boleto','Cartão')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    status TEXT NOT NULL CHECK (status IN ('Pendente','Aprovado','Recusado','Cancelado')),
    idempotency_key TEXT NOT NULL UNIQUE,
    simulated INTEGER NOT NULL DEFAULT 1 CHECK (simulated = 1),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    result_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_active_proposal ON payments(proposal_id) WHERE status IN ('Pendente','Aprovado');
CREATE INDEX IF NOT EXISTS ix_payments_created ON payments(created_at DESC);
CREATE TABLE IF NOT EXISTS payment_events (
    id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    from_status TEXT,
    to_status TEXT NOT NULL CHECK (to_status IN ('Pendente','Aprovado','Recusado','Cancelado')),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_payment_events_payment ON payment_events(payment_id,created_at);
