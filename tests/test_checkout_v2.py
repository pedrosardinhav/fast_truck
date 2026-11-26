import os
import sys
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))

from db import connect_db, initialize_database
from common import ApiError
from services import shop_orders


class CheckoutV2Tests(unittest.TestCase):
    def setUp(self):
        self.old_db_path = os.environ.get("FASTRUCK_DB_PATH")
        self.temp = tempfile.TemporaryDirectory()
        os.environ["FASTRUCK_DB_PATH"] = str(Path(self.temp.name) / "checkout-test.db")
        initialize_database()
        self.cid = "customer-1"
        with closing(connect_db()) as conn:
            conn.execute("INSERT INTO customers(id,cnpj,legal_name,contact_name,phone,email,postal_code,street,number,district,city,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (self.cid,"12345678000199","Empresa Teste","Pessoa","11999990000","pessoa@example.test","01000000","Rua A","1","Centro","São Paulo","SP","now","now"))
            conn.execute("INSERT INTO vehicles(id,plate,brand,model,year,color,price,status) VALUES(?,?,?,?,?,?,?,?)",
                         ("vehicle-1","ABC1D23","Marca","Modelo","2025","Branco",100000,"Disponível"))
            conn.commit()
        self.user = {"role": "customer", "customer_id": self.cid}

    def tearDown(self):
        self.temp.cleanup()
        if self.old_db_path is None:
            os.environ.pop("FASTRUCK_DB_PATH", None)
        else:
            os.environ["FASTRUCK_DB_PATH"] = self.old_db_path

    def _order(self):
        return shop_orders.handle_request("POST", "/api/shop/orders", {
            "vehicle_id": "vehicle-1", "items": [], "idempotency_key": str(uuid.uuid4())
        }, self.user)[1]

    def test_order_reserves_vehicle_and_card_approves_once(self):
        order = self._order()
        self.assertEqual(order["pickup_location"], shop_orders.PICKUP_LOCATION)
        self.assertEqual(order["reservation_expires_at"] is not None, True)
        with closing(connect_db()) as conn:
            self.assertEqual(conn.execute("SELECT reserved_order_id FROM vehicles WHERE id='vehicle-1'").fetchone()[0], order["id"])
        card = shop_orders.handle_request("POST", "/api/shop/payment-methods", {"demo_card_id":"corporate","holder_name":"Pessoa Teste"}, self.user)[1]
        result = shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
            "method":"Cartão", "saved_card_id":card["id"], "idempotency_key":str(uuid.uuid4())
        }, self.user)[1]
        self.assertIn(result["payments"][0]["status"], {"Processando", "Aprovado"})
        with closing(connect_db()) as conn:
            conn.execute("UPDATE checkout_payments SET ready_at='2000-01-01T00:00:00+00:00' WHERE order_id=?", (order["id"],))
            conn.commit()
        detail = shop_orders.handle_request("GET", f"/api/shop/orders/{order['id']}", user=self.user)[1]
        self.assertEqual(detail["status"], "Pagamento aprovado")
        self.assertEqual(detail["payments"][0]["status"], "Aprovado")
        self.assertEqual(detail["payments"][0]["last4"], "4242")
        with closing(connect_db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM vehicle_sales WHERE order_id=?", (order["id"],)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT status FROM vehicles WHERE id='vehicle-1'").fetchone()[0], "Vendido")

    def test_client_cannot_submit_payment_result_or_card_data(self):
        order = self._order()
        with self.assertRaises(ApiError) as captured:
            shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
                "method":"Pix", "result":"Aprovado", "idempotency_key":str(uuid.uuid4())
            }, self.user)
        self.assertEqual(captured.exception.status, 400)

    def test_pending_attempt_blocks_second_and_recusal_allows_retry(self):
        order = self._order()
        card = shop_orders.handle_request("POST", "/api/shop/payment-methods", {"demo_card_id":"alternative","holder_name":"Pessoa Teste"}, self.user)[1]
        first_key = str(uuid.uuid4())
        shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
            "method":"Cartão", "saved_card_id":card["id"], "idempotency_key":first_key
        }, self.user)
        with self.assertRaises(ApiError) as captured:
            shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
                "method":"Boleto", "idempotency_key":str(uuid.uuid4())
            }, self.user)
        self.assertEqual(captured.exception.status, 409)
        with closing(connect_db()) as conn:
            conn.execute("UPDATE checkout_payments SET ready_at='2000-01-01T00:00:00+00:00' WHERE order_id=?", (order["id"],))
            conn.commit()
        detail = shop_orders.handle_request("GET", f"/api/shop/orders/{order['id']}", user=self.user)[1]
        self.assertEqual(detail["payments"][0]["status"], "Recusado")
        approved_card = shop_orders.handle_request("POST", "/api/shop/payment-methods", {"demo_card_id":"corporate","holder_name":"Pessoa Teste"}, self.user)[1]
        retry = shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
            "method":"Cartão", "saved_card_id":approved_card["id"], "idempotency_key":str(uuid.uuid4())
        }, self.user)[1]
        self.assertEqual(len(retry["payments"]), 2)

    def test_boleto_is_confirmed_automatically(self):
        order = self._order()
        detail = shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
            "method":"Boleto", "idempotency_key":str(uuid.uuid4())
        }, self.user)[1]
        self.assertIsNotNone(detail["payments"][0]["ready_at"])
        with closing(connect_db()) as conn:
            conn.execute("UPDATE checkout_payments SET ready_at='2000-01-01T00:00:00+00:00' WHERE order_id=?", (order["id"],))
            conn.commit()
        approved = shop_orders.handle_request("GET", f"/api/shop/orders/{order['id']}", user=self.user)[1]
        self.assertEqual(approved["status"], "Pagamento aprovado")

    def test_inactive_company_cannot_approve_and_does_not_break_catalog(self):
        order = self._order()
        card = shop_orders.handle_request("POST", "/api/shop/payment-methods", {"demo_card_id":"corporate","holder_name":"Pessoa Teste"}, self.user)[1]
        shop_orders.handle_request("POST", f"/api/shop/orders/{order['id']}/payment", {
            "method":"Cartão", "saved_card_id":card["id"], "idempotency_key":str(uuid.uuid4())
        }, self.user)
        with closing(connect_db()) as conn:
            conn.execute("UPDATE checkout_payments SET ready_at='2000-01-01T00:00:00+00:00' WHERE order_id=?", (order["id"],))
            conn.execute("UPDATE customers SET active=0 WHERE id=?", (self.cid,))
            conn.commit()
        status, catalog = shop_orders.handle_request("GET", "/api/shop/catalog")
        self.assertEqual(status, 200)
        self.assertTrue(any(v["id"] == "vehicle-1" for v in catalog))
        with closing(connect_db()) as conn:
            self.assertEqual(conn.execute("SELECT status FROM shop_orders WHERE id=?", (order["id"],)).fetchone()[0], "Cancelado")


if __name__ == "__main__":
    unittest.main()
