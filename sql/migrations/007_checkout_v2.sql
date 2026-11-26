ALTER TABLE shop_orders ADD COLUMN billing_snapshot TEXT NOT NULL DEFAULT '{}';
ALTER TABLE shop_orders ADD COLUMN pickup_location TEXT NOT NULL DEFAULT 'FasTruck · retirada na loja';
ALTER TABLE shop_orders ADD COLUMN cancel_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE shop_orders ADD COLUMN reservation_expires_at TEXT;

CREATE TABLE checkout_payments (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL REFERENCES shop_orders(id) ON DELETE RESTRICT,
    method TEXT NOT NULL CHECK (method IN ('Pix','Boleto','Cartão')),
    status TEXT NOT NULL CHECK (status IN ('Pendente','Processando','Aprovado','Recusado','Cancelado')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents BETWEEN 0 AND 9999999999),
    reference TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL,
    saved_card_id TEXT,
    approved_at TEXT,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ready_at TEXT,
    deadline_at TEXT
);
CREATE INDEX idx_checkout_payments_order ON checkout_payments(order_id,seq DESC);
CREATE UNIQUE INDEX idx_checkout_payments_one_approved ON checkout_payments(order_id) WHERE status='Aprovado';

CREATE TABLE customer_payment_methods (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    brand TEXT NOT NULL,
    last4 TEXT NOT NULL CHECK (length(last4)=4 AND last4 NOT GLOB '*[^0-9]*'),
    holder_name TEXT NOT NULL,
    demo_card_id TEXT NOT NULL CHECK (demo_card_id IN ('corporate','alternative')),
    created_at TEXT NOT NULL,
    UNIQUE(customer_id,demo_card_id)
);
CREATE INDEX idx_customer_payment_methods_customer ON customer_payment_methods(customer_id,created_at);
