"""Medição local com 1.000 registros por módulo em banco temporário.

Executar da raiz: python tests/benchmark_modules.py
Não usa o banco do operador nem faz consulta externa.
"""

import json
import platform
import sqlite3
from time import perf_counter
from uuid import uuid4

from test_modules import ModulesTest, cnpj
from db import connect_db


def main():
    case = ModulesTest()
    ModulesTest.setUpClass()
    case.setUp()
    try:
        c, v, p, body = case.setup_proposal(approved=True)
        payment, _ = case.payment(p["id"])
        case.call("POST", f"/api/payments/{payment['id']}/status", {"status": "Recusado", "reason": "Preparação da medição"})
        # Carga sintética por SQL para medir operações, sem cronometrar a preparação.
        conn = connect_db()
        try:
            originals = {table: dict(conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()) for table in ("customers", "proposals", "payments")}
            with conn:
                for n in range(2, 1001):
                    for table, original in originals.items():
                        row = {**original, "id": str(uuid4())}
                        if table == "customers":
                            row.update(cnpj=cnpj(f"{n:012d}"), legal_name=f"Empresa de carga {n:04d}")
                        elif table == "proposals":
                            row.update(seq=n, number=f"PROP-{n:06d}")
                        else:
                            row.update(seq=n, reference=f"SIM-{n:06d}", idempotency_key=str(uuid4()))
                        columns = ",".join(row)
                        marks = ",".join("?" for _ in row)
                        conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values()))
        finally:
            conn.close()

        results = {}

        def measure(label, action, repeats=3):
            times = []
            for _ in range(repeats):
                started = perf_counter()
                action()
                times.append(perf_counter() - started)
            results[label] = round(max(times), 4)

        for module in ("customers", "proposals", "payments"):
            measure(f"{module}_listagem", lambda module=module: case.call("GET", f"/api/{module}"))

        # Clientes/propostas pesquisam a lista já recebida no navegador. Aqui se
        # inclui a transferência e o filtro equivalente; não mede pintura da UI.
        measure("customers_pesquisa", lambda: [x for x in case.call("GET", "/api/customers") if "0999" in x["legal_name"]])
        measure("proposals_pesquisa", lambda: [x for x in case.call("GET", "/api/proposals") if "000999" in x["number"]])
        measure("payments_pesquisa", lambda: case.call("GET", "/api/payments?q=SIM-000999"))
        measure("customers_salvamento", lambda: case.call("PUT", f"/api/customers/{c['id']}", {"notes": "Medição de salvamento"}))
        measure("proposals_salvamento", lambda: case.call("POST", "/api/proposals", body, 201))
        measure("payments_salvamento", lambda: case.payment(p["id"]), repeats=1)

        report = {"python": platform.python_version(), "sistema": platform.platform(),
                  "sqlite": sqlite3.sqlite_version, "registros_por_modulo": 1000,
                  "metrica": "Maior tempo em segundos de 3 execuções; pagamento criado 1 vez. Inclui HTTP local e JSON.",
                  "tempos": results, "meta_2s_atendida": all(t <= 2 for t in results.values())}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["meta_2s_atendida"]:
            raise SystemExit(1)
    finally:
        case.tearDown()
        ModulesTest.tearDownClass()


if __name__ == "__main__":
    main()
