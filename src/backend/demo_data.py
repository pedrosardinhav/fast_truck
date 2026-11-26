"""Dados iniciais compartilhados por todos os clones do projeto."""

from services.shop_auth import _hash_password
from db import transaction


DEMO_CUSTOMERS = [
    {
        "key": "rota-azul",
        "cnpj": "FTEX0000000184",
        "legal_name": "Rota Azul Transportes Ltda",
        "trade_name": "Rota Azul",
        "contact_name": "Marina Exemplo",
        "phone": "11900000001",
        "email": "comercial@empresa1.example.test",
        "postal_code": "04547000",
        "street": "Rua de Exemplo",
        "number": "100",
        "complement": "Galpão 1",
        "district": "Centro",
        "city": "São Paulo",
        "state": "SP",
        "active": 1,
    },
    {
        "key": "horizonte-cargas",
        "cnpj": "FTEX0000000265",
        "legal_name": "Horizonte Cargas Ltda",
        "trade_name": "Horizonte Cargas",
        "contact_name": "Rafael Exemplo",
        "phone": "41900000002",
        "email": "comercial@empresa2.example.test",
        "postal_code": "80010000",
        "street": "Rua de Exemplo",
        "number": "200",
        "complement": "Galpão 2",
        "district": "Centro",
        "city": "Curitiba",
        "state": "PR",
        "active": 1,
    },
    {
        "key": "serra-sul",
        "cnpj": "FTEX0000000346",
        "legal_name": "Serra Sul Logística Ltda",
        "trade_name": "Serra Sul",
        "contact_name": "Camila Exemplo",
        "phone": "51900000003",
        "email": "comercial@empresa3.example.test",
        "postal_code": "90010000",
        "street": "Rua de Exemplo",
        "number": "300",
        "complement": "Galpão 3",
        "district": "Centro",
        "city": "Porto Alegre",
        "state": "RS",
        "active": 1,
    },
    {
        "key": "via-norte",
        "cnpj": "FTEX0000000427",
        "legal_name": "Via Norte Distribuição Ltda",
        "trade_name": "Via Norte",
        "contact_name": "Lucas Exemplo",
        "phone": "31900000004",
        "email": "comercial@empresa4.example.test",
        "postal_code": "30110000",
        "street": "Rua de Exemplo",
        "number": "400",
        "complement": "Galpão 4",
        "district": "Centro",
        "city": "Belo Horizonte",
        "state": "MG",
        "active": 1,
    },
    {
        "key": "campo-forte",
        "cnpj": "FTEX0000000508",
        "legal_name": "Campo Forte Transportes Ltda",
        "trade_name": "Campo Forte",
        "contact_name": "Beatriz Exemplo",
        "phone": "62900000005",
        "email": "comercial@empresa5.example.test",
        "postal_code": "74003010",
        "street": "Rua de Exemplo",
        "number": "500",
        "complement": "Galpão 5",
        "district": "Centro",
        "city": "Goiânia",
        "state": "GO",
        "active": 1,
    },
    {
        "key": "expresso-litoral",
        "cnpj": "FTEX0000000699",
        "legal_name": "Expresso Litoral Ltda",
        "trade_name": "Expresso Litoral",
        "contact_name": "André Exemplo",
        "phone": "13900000006",
        "email": "comercial@empresa6.example.test",
        "postal_code": "11010000",
        "street": "Rua de Exemplo",
        "number": "600",
        "complement": "Galpão 6",
        "district": "Centro",
        "city": "Santos",
        "state": "SP",
        "active": 0,
    },
    {
        "key": "horizonte-azul",
        "cnpj": "12345678000195",
        "legal_name": "Transportadora Horizonte Azul Ltda.",
        "trade_name": "Horizonte Azul Transportes",
        "contact_name": "Pedro Vieira",
        "phone": "1134567890",
        "email": "compras@horizonteazul.com.br",
        "postal_code": "01310100",
        "street": "Avenida Paulista",
        "number": "1500",
        "complement": "Conjunto 82",
        "district": "Bela Vista",
        "city": "São Paulo",
        "state": "SP",
        "active": 1,
    },
]

DEMO_CUSTOMER_EMAIL = "compras@horizonteazul.com.br"
DEMO_CUSTOMER_PASSWORD = "teste123"


def seed_demo_data() -> None:
    """Inclui dados acadêmicos ausentes sem alterar cadastros existentes."""
    timestamp = "2026-01-15T12:00:00+00:00"
    note = "Empresa de exemplo incluída na carga inicial da FasTruck."
    with transaction() as conn:
        for customer in DEMO_CUSTOMERS:
            conn.execute(
                """INSERT OR IGNORE INTO customers
                (id, cnpj, legal_name, trade_name, contact_name, phone, email,
                 postal_code, street, number, complement, district, city, state,
                 notes, active, lookup_source, lookup_at, lookup_status,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', '', ?, ?)""",
                (
                    f"demo-customer-{customer['key']}", customer["cnpj"],
                    customer["legal_name"], customer["trade_name"],
                    customer["contact_name"], customer["phone"], customer["email"],
                    customer["postal_code"], customer["street"], customer["number"],
                    customer["complement"], customer["district"], customer["city"],
                    customer["state"], note, customer["active"], timestamp, timestamp,
                ),
            )

        customer = conn.execute(
            "SELECT id FROM customers WHERE cnpj=?",
            ("12345678000195",),
        ).fetchone()
        account = conn.execute(
            "SELECT id FROM accounts WHERE email=? OR customer_id=? LIMIT 1",
            (DEMO_CUSTOMER_EMAIL, customer["id"]),
        ).fetchone()
        if account is None:
            conn.execute(
                """INSERT INTO accounts
                (id, customer_id, email, password_hash, role, created_at)
                VALUES ('demo-account-horizonte-azul', ?, ?, ?, 'customer', ?)""",
                (
                    customer["id"], DEMO_CUSTOMER_EMAIL,
                    _hash_password(DEMO_CUSTOMER_PASSWORD), timestamp,
                ),
            )

