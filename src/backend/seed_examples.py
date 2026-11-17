"""Carga opcional e única de exemplos: python src/backend/seed_examples.py."""

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone

from common import money_to_cents, today_brasilia, utc_now
from db import connect_db, database_path, transaction
from services.customers import _values
from services.proposals import _items, _save_items, _snapshots, _total


SEED_KEY = "examples_modules_v1"
COMPANIES = [
    ("Rota Azul Transportes Ltda", "Rota Azul", "Marina Exemplo", "São Paulo", "SP", "11", "04547000"),
    ("Horizonte Cargas Ltda", "Horizonte Cargas", "Rafael Exemplo", "Curitiba", "PR", "41", "80010000"),
    ("Serra Sul Logística Ltda", "Serra Sul", "Camila Exemplo", "Porto Alegre", "RS", "51", "90010000"),
    ("Via Norte Distribuição Ltda", "Via Norte", "Lucas Exemplo", "Belo Horizonte", "MG", "31", "30110000"),
    ("Campo Forte Transportes Ltda", "Campo Forte", "Beatriz Exemplo", "Goiânia", "GO", "62", "74003010"),
    ("Expresso Litoral Ltda", "Expresso Litoral", "André Exemplo", "Santos", "SP", "13", "11010000"),
]
PROPOSALS = [
    (0, "Em elaboração", [("Pintura azul-marinho personalizada", 1, "8500.00"), ("Rodas de alumínio", 6, "2400.00")]),
    (1, "Em elaboração", [("Revestimento interno premium", 1, "6200.00")]),
    (2, "Enviada", [("Defletor de ar", 1, "3900.00"), ("Iluminação auxiliar", 1, "1750.50")]),
    (0, "Aprovada", [("Faixas exclusivas da transportadora", 1, "2800.00")]),
    (3, "Aprovada", [("Kit multimídia", 1, "3200.00"), ("Câmera de ré", 1, "980.00")]),
    (4, "Aprovada", [("Bancos com acabamento personalizado", 2, "1850.00")]),
    (1, "Aprovada", [("Saias laterais", 1, "4500.00")]),
    (2, "Cancelada", [("Pintura bicolor", 1, "9900.00")]),
]


def example_cnpj(index):
    """Documento alfanumérico sintético, sem consulta a empresas reais."""
    base = f"FTEX{index:08d}"
    values = [ord(char) - 48 for char in base]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        remainder = sum(v * w for v, w in zip(values, weights)) % 11
        values.append(0 if remainder < 2 else 11 - remainder)
    return base + "".join(map(str, values[-2:]))


def _insert(conn, table, values):
    # Tabelas e colunas são constantes internas, nunca entrada do operador.
    return conn.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))


def seed_examples():
    with transaction() as conn:
        if conn.execute("SELECT 1 FROM app_meta WHERE key=?", (SEED_KEY,)).fetchone():
            return False
        vehicles = [dict(r) for r in conn.execute(
            "SELECT * FROM vehicles WHERE status='Disponível' AND price>0 ORDER BY rowid")]
        if not vehicles:
            raise ValueError("Cadastre ao menos um caminhão Disponível com valor positivo antes de carregar os exemplos.")

        # Não reutilizar ou sobrescrever um cadastro do operador que use um CNPJ da carga.
        documents = [example_cnpj(i) for i in range(1, len(COMPANIES) + 1)]
        for document in documents:
            if conn.execute("SELECT 1 FROM customers WHERE cnpj=?", (document,)).fetchone():
                raise ValueError("Um CNPJ da carga já existe. Nenhum exemplo foi inserido; os cadastros existentes foram preservados.")

        customers = []
        now = utc_now()
        for i, (legal, trade, contact, city, state, ddd, cep) in enumerate(COMPANIES, 1):
            values = _values({
                "cnpj": documents[i - 1], "legal_name": legal, "trade_name": trade,
                "contact_name": contact, "phone": ddd + "9000000" + f"{i:02d}",
                "email": f"comercial@empresa{i}.example.test", "postal_code": cep,
                "street": "Rua de Exemplo", "number": str(i * 100), "complement": "Galpão " + str(i),
                "district": "Centro", "city": city, "state": state,
                "notes": "Empresa fictícia para estudo. CNPJ sintético, sem consulta oficial.",
            })
            values.update(id=str(uuid.uuid4()), active=int(i != 6), created_at=now, updated_at=now)
            _insert(conn, "customers", values)
            customers.append(values)

        proposals = []
        for i, (customer_index, status, extras) in enumerate(PROPOSALS):
            c, v = customers[customer_index], vehicles[i % len(vehicles)]
            items = _items([{"description": description, "quantity": quantity, "unit_price": price}
                            for description, quantity, price in extras])
            base = money_to_cents(v["price"], legacy=True)
            cs, vs = _snapshots(c, v)
            pid = str(uuid.uuid4())
            started = datetime.now(timezone.utc) - timedelta(days=3, hours=8 - i)
            states = ["Em elaboração"]
            if status != "Em elaboração":
                states.append("Enviada")
            if status in {"Aprovada", "Cancelada"}:
                states.append(status)
            final_at = (started + timedelta(minutes=len(states) - 1)).isoformat()
            proposal = {
                "id": pid, "number": "TEMP-" + pid, "customer_id": c["id"], "vehicle_id": v["id"],
                "base_price_cents": base, "total_cents": _total(base, items),
                "valid_until": (today_brasilia() + timedelta(days=30 + i)).isoformat(),
                "notes": "Proposta de exemplo para estudo, com personalizações adicionais.", "status": status,
                "customer_snapshot": cs, "vehicle_snapshot": vs,
                "created_at": started.isoformat(), "updated_at": final_at,
            }
            seq = _insert(conn, "proposals", proposal).lastrowid
            conn.execute("UPDATE proposals SET number=? WHERE id=?", (f"PROP-{seq:06d}", pid))
            _save_items(conn, pid, items)
            for step, target in enumerate(states):
                reason = "Cliente optou por outra configuração (exemplo)." if target == "Cancelada" else "Registro de exemplo para estudo."
                _insert(conn, "proposal_events", {
                    "proposal_id": pid, "from_status": states[step - 1] if step else None,
                    "to_status": target, "reason": reason, "created_at": (started + timedelta(minutes=step)).isoformat(),
                })
            proposals.append(proposal)

        attempts = [
            (3, "Pix", "Aprovado", ""),
            (4, "Boleto", "Pendente", ""),
            (5, "Cartão", "Recusado", "Recusa escolhida pelo operador na simulação de exemplo."),
            (5, "Pix", "Pendente", ""),
            (6, "Boleto", "Cancelado", "Cliente pediu alteração da forma de pagamento (exemplo)."),
        ]
        seq = conn.execute("SELECT COALESCE(MAX(seq),0) FROM payments").fetchone()[0]
        started = datetime.now(timezone.utc) - timedelta(days=1)
        for offset, (proposal_index, method, status, reason) in enumerate(attempts, 1):
            proposal = proposals[proposal_index]
            pid = str(uuid.uuid4())
            created = started + timedelta(minutes=offset * 5)
            result = created + timedelta(minutes=1)
            _insert(conn, "payments", {
                "id": pid, "seq": seq + offset, "reference": f"SIM-{seq + offset:06d}",
                "proposal_id": proposal["id"], "method": method, "amount_cents": proposal["total_cents"],
                "status": status, "idempotency_key": str(uuid.uuid4()), "simulated": 1, "reason": reason,
                "created_at": created.isoformat(),
                "updated_at": (created if status == "Pendente" else result).isoformat(),
                "result_at": None if status == "Pendente" else result.isoformat(),
            })
            for target in (["Pendente"] if status == "Pendente" else ["Pendente", status]):
                _insert(conn, "payment_events", {
                    "id": str(uuid.uuid4()), "payment_id": pid,
                    "from_status": None if target == "Pendente" else "Pendente", "to_status": target,
                    "reason": "Tentativa simulada de exemplo." if target == "Pendente" else reason,
                    "created_at": (created if target == "Pendente" else result).isoformat(),
                })
        conn.execute("INSERT INTO app_meta (key,value) VALUES (?,?)", (SEED_KEY, now))
    return True


def main():
    from app import initialize_database

    initialize_database()
    # Cópia consistente da base atual antes da primeira carga opcional.
    with closing(connect_db()) as conn:
        if conn.execute("SELECT 1 FROM app_meta WHERE key=?", (SEED_KEY,)).fetchone():
            print("Os exemplos já foram carregados. Nenhum dado foi alterado.")
            return
        folder = database_path().parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        with closing(sqlite3.connect(folder / f"before-examples-{stamp}.db")) as backup:
            conn.backup(backup)
    if seed_examples():
        print("Adicionados: 6 empresas fictícias, 8 propostas e 5 pagamentos simulados.")
        print("Cadastros anteriores e estoque preservados. Atualize as páginas no navegador.")
    else:
        print("Os exemplos já foram carregados. Nenhum dado foi alterado.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(f"Não foi possível carregar os exemplos: {exc}") from None
