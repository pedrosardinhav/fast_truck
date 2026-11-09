CREATE TABLE IF NOT EXISTS vehicles (
    id TEXT PRIMARY KEY,
    plate TEXT NOT NULL UNIQUE,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    year TEXT NOT NULL,
    color TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    axles TEXT NOT NULL DEFAULT '',
    fuel TEXT NOT NULL DEFAULT '',
    km INTEGER NOT NULL DEFAULT 0 CHECK (km >= 0),
    price REAL NOT NULL CHECK (price >= 0),
    customized TEXT NOT NULL DEFAULT 'sim' CHECK (customized IN ('sim', 'nao')),
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('Disponível', 'Reservado', 'Vendido'))
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
