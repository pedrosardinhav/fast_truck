CREATE TABLE IF NOT EXISTS shop_orders (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    number TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    vehicle_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT,
    base_price_cents INTEGER NOT NULL CHECK (base_price_cents BETWEEN 0 AND 9999999999),
    total_cents INTEGER NOT NULL CHECK (total_cents BETWEEN 0 AND 9999999999),
    status TEXT NOT NULL DEFAULT 'Aguardando pagamento' CHECK (status IN ('Aguardando pagamento','Pagamento aprovado','Cancelado')),
    notes TEXT NOT NULL DEFAULT '',
    customer_snapshot TEXT NOT NULL DEFAULT '{}',
    vehicle_snapshot TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shop_orders_customer ON shop_orders(customer_id,seq DESC);
CREATE TABLE IF NOT EXISTS shop_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES shop_orders(id) ON DELETE RESTRICT,
    customization_id TEXT NOT NULL,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents BETWEEN 0 AND 99999999),
    subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents BETWEEN 0 AND 9999999999)
);
CREATE INDEX IF NOT EXISTS idx_shop_order_items_order ON shop_order_items(order_id,id);
CREATE TABLE IF NOT EXISTS shop_order_payments (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL REFERENCES shop_orders(id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('Pix','Boleto','Cartão')),
    result TEXT NOT NULL CHECK (result IN ('Aprovado','Recusado','Cancelado')),
    status TEXT NOT NULL CHECK (status IN ('Aprovado','Recusado','Cancelado')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents BETWEEN 0 AND 9999999999),
    simulated INTEGER NOT NULL DEFAULT 1 CHECK (simulated=1),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shop_order_payments_order ON shop_order_payments(order_id,seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_shop_order_payments_one_approved ON shop_order_payments(order_id) WHERE result='Aprovado';
