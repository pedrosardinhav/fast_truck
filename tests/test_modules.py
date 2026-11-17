"""Aceite integrado dos módulos, sempre em banco temporário (stdlib unittest)."""

import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))
import app
import db
from common import ApiError, money_to_cents, today_brasilia
from integrations import brasilapi
from services import customers


def cnpj(base="123456780001"):
    values = [ord(char) - 48 for char in base]
    for weights in ((5,4,3,2,9,8,7,6,5,4,3,2), (6,5,4,3,2,9,8,7,6,5,4,3,2)):
        remainder = sum(v*w for v,w in zip(values, weights)) % 11
        values.append(0 if remainder < 2 else 11-remainder)
    return base + "".join(map(str, values[-2:]))


def company(document=None):
    return {"cnpj": document or cnpj(), "legal_name": "Transportadora de Teste Ltda", "trade_name": "Empresa Teste",
            "contact_name": "Contato de Teste", "phone": "(11) 99999-9999", "email": "contato@example.test",
            "postal_code": "01000-000", "street": "Rua de Teste", "number": "10", "complement": "",
            "district": "Centro", "city": "São Paulo", "state": "SP", "notes": "Cadastro de teste local"}


class QuietHandler(app.FasTruckHandler):
    def log_message(self, *args):
        pass


class ModulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=5)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fastruck-test-")
        self.env = patch.dict(os.environ, {"FASTRUCK_DB_PATH": str(Path(self.temp.name) / "test.db")})
        self.env.start()
        app.initialize_database()
        from services.shop_auth import ensure_admin
        ensure_admin()
        credentials = dict(line.split("=", 1) for line in (Path(self.temp.name) / ".admin-access").read_text(encoding="utf-8").splitlines())
        self.cookie = ""
        self.csrf = ""
        self.call("POST", "/api/shop/login", {"email": credentials["email"], "password": credentials["password"]})

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def call(self, method, path, payload=None, expect=200):
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        request = Request(self.origin + path, data=data, method=method, headers=headers)
        try:
            response = urlopen(request, timeout=8)
        except HTTPError as response_error:
            response = response_error
        with response:
            cookie = response.headers.get("Set-Cookie")
            if cookie:
                self.cookie = cookie.split(";", 1)[0]
            status, result = response.code, json.loads(response.read())
        if isinstance(result, dict) and result.get("csrf_token"):
            self.csrf = result["csrf_token"]
        if expect is not None:
            self.assertEqual(status, expect, f"{method} {path}: {result}")
        return result if expect is not None else (status, result)

    def setup_proposal(self, approved=False, document=None):
        c = self.call("POST", "/api/customers", company(document), 201)
        v = next(v for v in self.call("GET", "/api/vehicles") if v["status"] == "Disponível")
        v["price"] = 500000
        self.call("PUT", "/api/vehicles/" + v["id"], v)
        body = {"customer_id": c["id"], "vehicle_id": v["id"], "valid_until": (today_brasilia()+timedelta(days=7)).isoformat(), "notes": "Condições de teste",
                "items": [{"description": "Rodas adicionais", "quantity": 2, "unit_price": "1500.00"}, {"description": "Pintura adicional", "quantity": 1, "unit_price": "4000.00"}]}
        p = self.call("POST", "/api/proposals", body, 201)
        if approved:
            self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"})
            p = self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Aprovada"})
        return c, v, p, body

    def payment(self, proposal_id, method="Pix", key=None, expect=201):
        data = {"proposal_id": proposal_id, "method": method, "idempotency_key": key or str(uuid.uuid4())}
        return self.call("POST", "/api/payments", data, expect), data

    def test_customer_validation_uniqueness_and_lifecycle(self):
        c = self.call("POST", "/api/customers", company(), 201)
        self.assertEqual(c["phone"], "11999999999")
        self.call("POST", "/api/customers", company(), 409)
        self.call("PUT", f"/api/customers/{c['id']}", {"active": False})
        self.assertEqual(self.call("GET", f"/api/customers/{c['id']}")["active"], 0)
        self.call("PUT", f"/api/customers/{c['id']}", {"active": True})
        changed = self.call("PUT", f"/api/customers/{c['id']}", {"cnpj": cnpj("123456780002")})
        self.assertEqual(changed["id"], c["id"])
        self.call("DELETE", f"/api/customers/{c['id']}")
        self.call("GET", f"/api/customers/{c['id']}", expect=404)

    def test_customer_required_fields_alphanumeric_and_invalid_inputs(self):
        for field in ("legal_name", "contact_name", "phone", "email", "postal_code", "street", "number", "district", "city", "state"):
            body = company(); body[field] = ""
            self.call("POST", "/api/customers", body, 400)
        for field, value in (("cnpj", "11111111111111"), ("cnpj", "12345678901"), ("state", "XX"), ("phone", "1234"), ("email", "invalido")):
            body = company(); body[field] = value
            self.call("POST", "/api/customers", body, 400)
        alpha = cnpj("12ABC34501DE")
        c = self.call("POST", "/api/customers", company(alpha.lower()), 201)
        self.assertEqual(c["cnpj"], alpha)
        self.call("POST", "/api/customers", company(alpha), 409)

    def test_lookup_metadata_requires_token_does_not_save_automatically(self):
        result = {"cnpj": cnpj(), "legal_name": "Empresa da Consulta", "lookup_status": "ATIVA"}
        with patch.object(customers, "lookup_cnpj", return_value=result):
            lookup = self.call("GET", "/api/cnpj/" + cnpj())
        self.assertEqual(self.call("GET", "/api/customers"), [])
        # Simular novo processo: a assinatura deve continuar válida com a chave em disco.
        customers._SECRET_CACHE.clear()
        body = company(); body["lookup_token"] = lookup["lookup_token"]
        c = self.call("POST", "/api/customers", body, 201)
        self.assertEqual(c["lookup_source"], "BrasilAPI")
        self.assertEqual(c["lookup_status"], "ATIVA")
        self.call("PUT", f"/api/customers/{c['id']}", {"lookup_source": "forjado"}, 400)
        self.call("PUT", f"/api/customers/{c['id']}", {"cnpj": cnpj("123456780002"), "lookup_token": lookup["lookup_token"]}, 400)
        updated = self.call("PUT", f"/api/customers/{c['id']}", {"cnpj": cnpj("123456780002")})
        self.assertEqual(updated["lookup_source"], "")

    def test_lookup_offline_manual_and_mapping(self):
        with patch.object(customers, "lookup_cnpj", side_effect=ApiError(504, "Consulta indisponível")):
            self.call("GET", "/api/cnpj/" + cnpj(), expect=504)
        self.call("POST", "/api/customers", company(), 201)
        class FakeReply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                return json.dumps({"razao_social": "Empresa", "logradouro": "Rua X", "municipio": "São Paulo", "uf": "SP", "numero": "1", "cep": "01000000", "descricao_situacao_cadastral": "ATIVA"}).encode()
        with patch.object(brasilapi, "urlopen", return_value=FakeReply()) as call:
            result = brasilapi.lookup_cnpj(cnpj("12ABC34501DE"))
            self.assertEqual(result["street"], "Rua X")
            self.assertEqual(result["city"], "São Paulo")
            self.assertEqual(call.call_args.kwargs["timeout"], 5)
        for exc, status in ((TimeoutError(),504), (URLError("offline"),503), (HTTPError("https://example.test",429,"limite",{},None),503), (HTTPError("https://example.test",404,"não encontrado",{},None),404)):
            with patch.object(brasilapi, "urlopen", side_effect=exc):
                with self.assertRaises(ApiError) as captured:
                    brasilapi.lookup_cnpj(cnpj())
                self.assertEqual(captured.exception.status, status)

    def test_proposal_cents_snapshots_and_base_price_preserved(self):
        c, v, p, body = self.setup_proposal()
        self.assertEqual(p["total_cents"], 50700000)
        v["price"] = 800000; v["color"] = "Vermelho"
        self.call("PUT", f"/api/vehicles/{v['id']}", v)
        self.call("PUT", f"/api/customers/{c['id']}", {"legal_name": "Nome no Envio"})
        body["total_cents"] = 1
        p = self.call("PUT", f"/api/proposals/{p['id']}", body)
        self.assertEqual(p["base_price_cents"], 50000000)
        p = self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"})
        self.assertEqual(p["total_cents"], 50700000)
        self.assertEqual(p["customer"]["legal_name"], "Nome no Envio")
        self.assertEqual(p["vehicle"]["color"], "Vermelho")
        self.call("PUT", f"/api/customers/{c['id']}", {"legal_name": "Nome Atualizado Depois"})
        v["color"] = "Branco"; self.call("PUT", f"/api/vehicles/{v['id']}", v)
        again = self.call("GET", f"/api/proposals/{p['id']}")
        self.assertEqual(again["customer"]["legal_name"], "Nome no Envio")
        self.assertEqual(again["vehicle"]["color"], "Vermelho")
        self.call("PUT", f"/api/proposals/{p['id']}", body, 409)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"})
        self.assertEqual(len(self.call("GET", f"/api/proposals/{p['id']}")["events"]), 2)

    def test_items_limits_and_transactional_update(self):
        _, _, p, body = self.setup_proposal()
        for invalid in (1.5, True, 0, 101):
            bad = {**body, "items": [{"description": "Item inválido", "quantity": invalid, "unit_price": "1.00"}]}
            self.call("PUT", f"/api/proposals/{p['id']}", bad, 400)
        for invalid in ("-1", "1.001", "1.000", "NaN", "Infinity", "1000000.00"):
            bad = {**body, "items": [{"description": "Preço inválido", "quantity": 1, "unit_price": invalid}]}
            self.call("PUT", f"/api/proposals/{p['id']}", bad, 400)
        self.call("PUT", f"/api/proposals/{p['id']}", {**body, "items": body["items"]*16}, 400)
        self.assertEqual(self.call("GET", f"/api/proposals/{p['id']}")["total_cents"], 50700000)
        self.assertEqual(len(self.call("GET", f"/api/proposals/{p['id']}")["items"]), 2)

    def test_proposal_state_validity_links_and_cancel(self):
        c, v, p, body = self.setup_proposal()
        self.call("DELETE", f"/api/customers/{c['id']}", expect=409)
        self.call("DELETE", f"/api/vehicles/{v['id']}", expect=409)
        self.call("PUT", f"/api/customers/{c['id']}", {"cnpj": cnpj("123456780002")}, 409)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Aprovada"}, 409)
        self.call("PUT", f"/api/customers/{c['id']}", {"active": False})
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"}, 409)
        self.call("PUT", f"/api/customers/{c['id']}", {"active": True})
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"})
        with db.transaction() as conn:
            conn.execute("UPDATE proposals SET valid_until=? WHERE id=?", ((today_brasilia()-timedelta(days=1)).isoformat(), p["id"]))
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Aprovada"}, 409)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Cancelada"}, 400)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Cancelada", "reason": "Prazo vencido"})
        self.call("DELETE", f"/api/proposals/{p['id']}", expect=409)

    def test_draft_changes_validate_only_changed_reference(self):
        c, v, p, body = self.setup_proposal()
        other = self.call("POST", "/api/customers", company(cnpj("123456780002")), 201)
        v["status"] = "Reservado"
        self.call("PUT", f"/api/vehicles/{v['id']}", v)
        body["customer_id"] = other["id"]
        self.call("PUT", f"/api/proposals/{p['id']}", body)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"}, 409)
        self.call("PUT", f"/api/customers/{other['id']}", {"active": False})
        new_vehicle = next(x for x in self.call("GET", "/api/vehicles") if x["status"] == "Disponível")
        body["vehicle_id"] = new_vehicle["id"]
        self.call("PUT", f"/api/proposals/{p['id']}", body)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"}, 409)
        body["vehicle_id"] = v["id"]
        self.call("PUT", f"/api/proposals/{p['id']}", body, 409)
        body["vehicle_id"] = new_vehicle["id"]
        body["customer_id"] = c["id"]
        self.call("PUT", f"/api/proposals/{p['id']}", body)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"})

    def test_delete_draft_and_vehicle_price_switch(self):
        _, _, p, body = self.setup_proposal()
        new_vehicle = next(v for v in self.call("GET", "/api/vehicles") if v["status"]=="Disponível" and v["id"] != body["vehicle_id"])
        changed = self.call("PUT", f"/api/proposals/{p['id']}", {**body, "vehicle_id": new_vehicle["id"]})
        self.assertEqual(changed["base_price_cents"], money_to_cents(new_vehicle["price"], legacy=True))
        self.call("DELETE", f"/api/proposals/{p['id']}")
        self.call("GET", f"/api/proposals/{p['id']}", expect=404)
        with closing(db.connect_db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM proposal_items").fetchone()[0], 0)

    def test_payment_idempotency_retries_receipt_data_and_no_stock_change(self):
        c, v, p, _ = self.setup_proposal(approved=True)
        payment, body = self.payment(p["id"])
        repeat = self.call("POST", "/api/payments", body)
        self.assertEqual(payment["id"], repeat["id"])
        self.call("POST", "/api/payments", {**body, "method": "Cartão"}, 409)
        self.payment(p["id"], expect=409)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Cancelada", "reason": "Cancelar"}, 409)
        self.call("POST", f"/api/payments/{payment['id']}/status", {"status": "Recusado", "reason": "Cenário de recusa"})
        payment2, body2 = self.payment(p["id"], "Cartão")
        approved = self.call("POST", f"/api/payments/{payment2['id']}/status", {"status": "Aprovado"})
        self.assertEqual(approved["amount_cents"], p["total_cents"])
        self.assertEqual(len(approved["events"]), 2)
        self.assertEqual(len(self.call("POST", f"/api/payments/{payment2['id']}/status", {"status": "Aprovado"})["events"]), 2)
        self.call("PUT", f"/api/customers/{c['id']}", {"legal_name": "Nome Alterado", "active": True}, 400)
        self.call("PUT", f"/api/customers/{c['id']}", {"legal_name": "Nome Alterado"})
        again = self.call("GET", f"/api/payments/{payment2['id']}")
        self.assertEqual(again["customer_name"], "Transportadora de Teste Ltda")
        self.call("POST", f"/api/payments/{payment2['id']}/status", {"status": "Cancelado", "reason": "Teste"}, 409)
        self.payment(p["id"], expect=409)
        self.call("DELETE", f"/api/payments/{payment2['id']}", expect=405)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Cancelada", "reason": "Teste"}, 409)
        vehicles = self.call("GET", "/api/vehicles")
        self.assertEqual(next(row for row in vehicles if row["id"] == v["id"])["status"], "Disponível")
        self.call("PUT", f"/api/customers/{c['id']}", {"active": False})
        self.assertEqual(self.call("POST", "/api/payments", body2)["id"], payment2["id"])

    def test_payment_blocks_invalid_and_real_data_and_allows_cleanup(self):
        c, v, p, _ = self.setup_proposal()
        self.payment(p["id"], expect=409)
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Enviada"})
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Aprovada"})
        for field in ("amount_cents", "card_number", "cvv", "account", "simulated"):
            self.call("POST", "/api/payments", {"proposal_id": p["id"], "method": "Pix", "idempotency_key": str(uuid.uuid4()), field: "123"}, 400)
        pay, _ = self.payment(p["id"], "Boleto")
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Recusado"}, 400)
        self.call("PUT", f"/api/customers/{c['id']}", {"active": False})
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Aprovado"}, 409)
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Cancelado", "reason": "Condição mudou"})
        self.call("POST", f"/api/proposals/{p['id']}/status", {"status": "Cancelada", "reason": "Sem interesse"})

    def test_payment_expiry_and_vehicle_status_revalidated(self):
        _, v, p, _ = self.setup_proposal(approved=True)
        pay, _ = self.payment(p["id"])
        v["status"] = "Reservado"; self.call("PUT", f"/api/vehicles/{v['id']}", v)
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Aprovado"}, 409)
        v["status"] = "Disponível"; self.call("PUT", f"/api/vehicles/{v['id']}", v)
        with db.transaction() as conn:
            conn.execute("UPDATE proposals SET valid_until=? WHERE id=?", ((today_brasilia()-timedelta(days=1)).isoformat(), p["id"]))
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Aprovado"}, 409)
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Recusado", "reason": "Prazo vencido"})

    def test_simultaneous_creations_allow_only_one_active(self):
        _, _, p, _ = self.setup_proposal(approved=True)
        def attempt(_):
            return self.call("POST", "/api/payments", {"proposal_id": p["id"], "method": "Pix", "idempotency_key": str(uuid.uuid4())}, expect=None)[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(attempt, range(4)))
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(409), 3)

    def test_event_failure_rolls_back_creation_and_status(self):
        _, _, p, _ = self.setup_proposal(approved=True)
        with db.transaction() as conn:
            conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON payment_events BEGIN SELECT RAISE(ABORT,'Falha simulada'); END")
        self.payment(p["id"], expect=409)
        self.assertEqual(self.call("GET", "/api/payments")["items"], [])
        with db.transaction() as conn:
            conn.execute("DROP TRIGGER fail_event")
        pay, _ = self.payment(p["id"])
        with db.transaction() as conn:
            conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON payment_events BEGIN SELECT RAISE(ABORT,'Falha simulada'); END")
        self.call("POST", f"/api/payments/{pay['id']}/status", {"status": "Aprovado"}, 409)
        after = self.call("GET", f"/api/payments/{pay['id']}")
        self.assertEqual(after["status"], "Pendente")
        self.assertEqual(len(after["events"]), 1)

    def test_migration_restart_keeps_data_and_applies_once(self):
        _, _, p, _ = self.setup_proposal(approved=True)
        pay, _ = self.payment(p["id"])
        app.initialize_database()
        self.assertEqual(self.call("GET", f"/api/payments/{pay['id']}")["id"], pay["id"])
        with closing(db.connect_db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], len(list((ROOT / "sql" / "migrations").glob("*.sql"))))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0], 13)

    def test_existing_database_backup_and_custom_vehicle_preserved(self):
        old_path = Path(self.temp.name) / "old.db"
        with patch.dict(os.environ, {"FASTRUCK_DB_PATH": str(old_path)}):
            with closing(db.connect_db()) as conn:
                conn.executescript((ROOT/"sql"/"schema.sql").read_text(encoding="utf-8-sig"))
                conn.execute("INSERT INTO vehicles (id,plate,brand,model,year,color,price,status) VALUES ('own','ABC-1D23','Marca','Modelo','2025','Azul',123,'Disponível')")
                conn.commit()
            app.initialize_database()
            with closing(db.connect_db()) as conn:
                self.assertEqual(conn.execute("SELECT price FROM vehicles WHERE id='own'").fetchone()[0], 123)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0], 14)
            self.assertTrue(list((old_path.parent/"backups").glob("*.db")))

    def test_static_pages_and_assets_are_served(self):
        for route in ("/", "/clientes.html", "/propostas.html", "/pagamentos.html", "/css/shared.css", "/js/shared.js", "/js/clientes.js", "/js/propostas.js", "/js/pagamentos.js"):
            with urlopen(self.origin+route, timeout=5) as response:
                self.assertEqual(response.code, 200)
                self.assertTrue(response.read())
        self.call("GET", "/%2e%2e/sql/schema.sql", expect=404)


if __name__ == "__main__":
    unittest.main()
