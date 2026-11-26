"""Aceite HTTP do estoque e checkout: apenas SQLite temporário, sem rede externa."""
import copy
import json
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone

import test_modules as legacy
from db import connect_db, transaction


class CheckoutFlowTests(unittest.TestCase):
    setUpClass = classmethod(legacy.ModulesTest.setUpClass.__func__)
    tearDownClass = classmethod(legacy.ModulesTest.tearDownClass.__func__)
    setUp = legacy.ModulesTest.setUp
    tearDown = legacy.ModulesTest.tearDown
    call = legacy.ModulesTest.call

    def client(self, number=1):
        client = copy.copy(self)
        client.cookie = client.csrf = ""
        body = legacy.company(legacy.cnpj(f"7654321000{number:02d}"))
        body.update(account_email=f"empresa{number}@example.test", password="Estudo123!")
        client.user = client.call("POST", "/api/shop/register", body, 201)["user"]
        return client

    def vehicle(self):
        return next(v for v in self.call("GET", "/api/vehicles") if v["status"] == "Disponível")

    def order(self, client, vehicle=None, key=None, expect=201, items=None):
        return client.call("POST", "/api/shop/orders", {"vehicle_id": (vehicle or self.vehicle())["id"], "items": items or [], "idempotency_key": key or str(uuid.uuid4())}, expect)

    def pay(self, client, order, method="Pix", card=None, key=None, expect=201):
        body = {"method": method, "idempotency_key": key or str(uuid.uuid4())}
        if card:
            body["saved_card_id"] = card["id"]
        return client.call("POST", f"/api/shop/orders/{order['id']}/payment", body, expect)

    def card(self, client, name="corporate"):
        return client.call("POST", "/api/shop/payment-methods", {"demo_card_id": name, "holder_name": "Pessoa Teste"}, 201)

    def ready(self, order):
        with transaction() as conn:
            conn.execute("UPDATE checkout_payments SET ready_at=? WHERE order_id=? AND ready_at IS NOT NULL", ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(timespec="microseconds"), order["id"]))

    def detail(self, client, order):
        return client.call("GET", f"/api/shop/orders/{order['id']}")

    def test_vehicle_create_edit_archive_and_consult_history(self):
        body = {"plate":"TST-1A23", "brand":"Volvo", "model":"FH", "year":"2025 / 2026", "color":"Azul", "price":550000, "km":10, "status":"Disponível"}
        v = self.call("POST", "/api/vehicles", body, 201)
        self.call("PUT", f"/api/vehicles/{v['id']}", {**body,"color":"Branco"})
        archived = self.call("DELETE", f"/api/vehicles/{v['id']}", {"reason":"Fim do anúncio"})
        self.assertTrue(archived["deleted_at"])
        self.assertEqual([e["action"] for e in archived["events"]], ["created","updated","deleted"])
        self.assertNotIn(v["id"], [v["id"] for v in self.call("GET", "/api/vehicles")])
        self.assertIn(v["id"], [v["id"] for v in self.call("GET", "/api/vehicles?view=deleted")])
        self.assertNotIn(v["id"], [v["id"] for v in self.call("GET", "/api/shop/catalog")])
        self.call("PUT", f"/api/vehicles/{v['id']}", body, 409)
        self.call("POST", "/api/vehicles", body, 409)
        self.assertEqual(len(self.call("DELETE", f"/api/vehicles/{v['id']}")["events"]),3)

    def test_manual_sale_is_unique_audited_and_survives_archive(self):
        client=self.client(); v=self.vehicle()
        body={"customer_id":client.user["customer_id"],"amount":"499999.99","idempotency_key":str(uuid.uuid4())}
        sale=self.call("POST", f"/api/vehicles/{v['id']}/sell", body,201)
        self.assertEqual(sale["amount_cents"],49999999)
        self.assertEqual(self.call("POST", f"/api/vehicles/{v['id']}/sell",body,201)["id"],sale["id"])
        self.call("POST", f"/api/vehicles/{v['id']}/sell",{**body,"amount":"1"},409)
        self.call("PUT", f"/api/vehicles/{v['id']}",{**v,"status":"Disponível"},409)
        archived=self.call("DELETE", f"/api/vehicles/{v['id']}",{"reason":"Venda concluída"})
        self.assertEqual(archived["sale"]["id"],sale["id"])
        self.assertEqual(archived["status"],"Vendido")

    def test_cannot_mark_sold_without_sale(self):
        v=self.vehicle()
        self.call("PUT", f"/api/vehicles/{v['id']}",{**v,"status":"Vendido"},409)
        self.call("POST", "/api/vehicles",{**v,"plate":"TST-1A23","status":"Vendido"},409)

    def test_card_checkout_total_snapshot_sale_and_idempotency(self):
        client=self.client(); v=self.vehicle(); key=str(uuid.uuid4())
        items=[{"customization_id":"pintura","quantity":2}]
        order=self.order(client,v,key,items=items)
        self.assertEqual(order["total_cents"],round(v["price"]*100)+1700000)
        self.assertEqual(order["billing_snapshot"]["city"],"São Paulo")
        self.assertEqual(self.order(client,v,key,expect=200,items=items)["id"],order["id"])
        reserved=self.call("GET",f"/api/vehicles/{v['id']}")
        self.assertEqual(reserved["reserved_order_id"],order["id"])
        self.call("PUT",f"/api/vehicles/{v['id']}",v,409)
        self.call("DELETE",f"/api/vehicles/{v['id']}",expect=409)
        card=self.card(client); pay_key=str(uuid.uuid4())
        paid=self.pay(client,order,"Cartão",card,pay_key)
        self.assertEqual(paid["payments"][-1]["status"],"Processando")
        self.assertEqual(self.pay(client,order,"Cartão",card,pay_key,200)["payments"][-1]["id"],paid["payments"][-1]["id"])
        self.ready(order); paid=self.detail(client,order)
        self.assertEqual(paid["status"],"Pagamento aprovado")
        self.assertTrue(paid["payments"][-1]["receipt"])
        self.assertEqual(self.call("GET",f"/api/vehicles/{v['id']}")["sale"]["amount_cents"],order["total_cents"])
        self.pay(client,order,expect=409)
        client.call("POST",f"/api/shop/orders/{order['id']}/cancel",{},409)
        with closing(connect_db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM vehicle_sales WHERE vehicle_id=?",(v["id"],)).fetchone()[0],1)

    def test_declined_card_can_retry_with_another_saved_card(self):
        client=self.client();order=self.order(client)
        self.pay(client,order,"Cartão",self.card(client,"alternative"));self.ready(order)
        declined=self.detail(client,order)
        self.assertEqual(declined["payments"][-1]["status"],"Recusado")
        self.assertIsNone(declined["payments"][-1]["receipt"])
        self.pay(client,order,"Cartão",self.card(client));self.ready(order)
        self.assertEqual(self.detail(client,order)["status"],"Pagamento aprovado")

    def test_pix_and_boleto_are_confirmed_automatically(self):
        client=self.client(); pix=self.order(client)
        p=self.pay(client,pix)
        self.assertEqual(p["payments"][-1]["status"],"Pendente")
        self.ready(pix);self.assertEqual(self.detail(client,pix)["status"],"Pagamento aprovado")
        boleto=self.order(client);pending=self.pay(client,boleto,"Boleto")
        payment=pending["payments"][-1]
        self.assertIsNotNone(payment["ready_at"])
        self.assertEqual(self.detail(client,boleto)["status"],"Aguardando pagamento")
        self.ready(boleto)
        self.assertEqual(self.detail(client,boleto)["status"],"Pagamento aprovado")

    def test_reservation_expiry_cancels_payment_and_releases_stock(self):
        client=self.client();order=self.order(client);self.pay(client,order,"Boleto")
        past=(datetime.now(timezone.utc)-timedelta(seconds=3)).isoformat(timespec="microseconds")
        with transaction() as conn:
            conn.execute("UPDATE vehicles SET reserved_until=? WHERE id=?",(past,order["vehicle_id"]))
            conn.execute("UPDATE shop_orders SET reservation_expires_at=? WHERE id=?",(past,order["id"]))
        result=self.detail(client,order)
        self.assertEqual(result["status"],"Cancelado")
        self.assertEqual(result["cancel_reason"],"Reserva expirada")
        self.assertEqual(result["payments"][-1]["status"],"Cancelado")
        self.assertEqual(self.call("GET",f"/api/vehicles/{order['vehicle_id']}")["status"],"Disponível")

    def test_cancel_releases_only_owned_reservation(self):
        a,b=self.client(),self.client(2);v=self.vehicle();order=self.order(a,v);self.pay(a,order,"Boleto")
        b.call("POST",f"/api/shop/orders/{order['id']}/cancel",{},404)
        a.call("POST",f"/api/shop/orders/{order['id']}/cancel",{})
        replacement=self.order(b,v)
        a.call("POST",f"/api/shop/orders/{order['id']}/cancel",{})
        self.assertEqual(self.call("GET",f"/api/vehicles/{v['id']}")["reserved_order_id"],replacement["id"])

    def test_concurrent_buyers_only_one_can_reserve(self):
        a,b=self.client(),self.client(2);v=self.vehicle()
        def create(client):return client.call("POST","/api/shop/orders",{"vehicle_id":v["id"],"items":[],"idempotency_key":str(uuid.uuid4())},expect=None)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(create,[a,b]))
        self.assertEqual(sorted(statuses),[201,409])

    def test_auth_csrf_ownership_and_no_payment_tampering(self):
        a,b=self.client(),self.client(2);order=self.order(a);card=self.card(a)
        b.call("GET",f"/api/shop/orders/{order['id']}",expect=404)
        self.assertEqual(b.call("GET","/api/shop/payment-methods"),[])
        other=self.order(b);self.pay(b,other,"Cartão",card,expect=404)
        for field in ("result","status","amount_cents","card_number","cvv"):
            a.call("POST",f"/api/shop/orders/{order['id']}/payment",{"method":"Pix","idempotency_key":str(uuid.uuid4()),field:"Aprovado"},400)
        a.call("POST","/api/shop/payment-methods",{"demo_card_id":"corporate","holder_name":"Pessoa","card_number":"4242"},400)
        a.csrf="";self.pay(a,order,expect=403)
        a.call("GET","/api/vehicles",expect=403)
        anonymous=copy.copy(self);anonymous.cookie=anonymous.csrf=""
        anonymous.call("GET","/api/vehicles",expect=401)
        self.assertEqual(anonymous.call("GET","/api/shop/checkout-options")["reservation_minutes"],15)

    def test_atomic_sale_failure_rolls_back_payment_order_and_vehicle(self):
        client=self.client();order=self.order(client);self.pay(client,order,"Boleto")
        with transaction() as conn:conn.execute("CREATE TRIGGER fail_sale BEFORE INSERT ON vehicle_events WHEN NEW.action='sold' BEGIN SELECT RAISE(ABORT,'Falha simulada'); END")
        self.ready(order)
        self.call("GET","/api/shop/catalog",expect=409)
        with closing(connect_db()) as conn:
            result=conn.execute("SELECT status FROM shop_orders WHERE id=?",(order["id"],)).fetchone()
            payment=conn.execute("SELECT status FROM checkout_payments WHERE order_id=?",(order["id"],)).fetchone()
            self.assertEqual(result["status"],"Aguardando pagamento")
            self.assertEqual(payment["status"],"Pendente")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM vehicle_sales").fetchone()[0],0)
            self.assertEqual(conn.execute("SELECT status FROM vehicles WHERE id=?",(order["vehicle_id"],)).fetchone()[0],"Reservado")
        with transaction() as conn:conn.execute("DROP TRIGGER fail_sale")
        self.assertEqual(self.detail(client,order)["status"],"Pagamento aprovado")

    def test_legacy_commercial_routes_are_retired_without_dropping_history(self):
        self.call("GET","/api/proposals",expect=404)
        self.call("GET","/api/payments",expect=404)
        with closing(connect_db()) as conn:
            tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"proposals","proposal_items","proposal_events","payments","payment_events"} <= tables)

    def test_ready_payment_before_deadline_wins_even_when_admin_reads_later(self):
        client=self.client();order=self.order(client);self.pay(client,order)
        now=datetime.now(timezone.utc)
        deadline=(now-timedelta(seconds=2)).isoformat(timespec="microseconds")
        ready=(now-timedelta(seconds=4)).isoformat(timespec="microseconds")
        with transaction() as conn:
            conn.execute("UPDATE vehicles SET reserved_until=? WHERE id=?",(deadline,order["vehicle_id"]))
            conn.execute("UPDATE shop_orders SET reservation_expires_at=? WHERE id=?",(deadline,order["id"]))
            conn.execute("UPDATE checkout_payments SET ready_at=? WHERE order_id=?",(ready,order["id"]))
        self.call("GET","/api/vehicles")
        self.assertEqual(self.detail(client,order)["status"],"Pagamento aprovado")
        self.assertEqual(self.call("GET",f"/api/vehicles/{order['vehicle_id']}")["status"],"Vendido")

    def test_legacy_approved_order_keeps_history_without_retroactive_sale(self):
        client=self.client();order=self.order(client)
        with transaction() as conn:
            conn.execute("UPDATE shop_orders SET status='Pagamento aprovado',reservation_expires_at=NULL WHERE id=?",(order["id"],))
            conn.execute("UPDATE vehicles SET status='Disponível',reserved_order_id=NULL,reserved_until=NULL WHERE id=?",(order["vehicle_id"],))
            conn.execute("INSERT INTO shop_order_payments(id,order_id,idempotency_key,request_hash,method,result,status,amount_cents,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),order["id"],str(uuid.uuid4()),"legacy","Pix","Aprovado","Aprovado",order["total_cents"],"2026-01-01T00:00:00+00:00"))
        result=self.detail(client,order)
        self.assertEqual(result["payments"][-1]["result"],"Aprovado")
        self.assertEqual(result["status"],"Pagamento aprovado")
        self.assertIsNone(self.call("GET",f"/api/vehicles/{order['vehicle_id']}")["sale"])
        self.assertIn(order["vehicle_id"],[v["id"] for v in self.call("GET","/api/shop/catalog")])


if __name__ == "__main__":
    unittest.main()
