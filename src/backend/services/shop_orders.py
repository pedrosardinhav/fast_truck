"""Catálogo, pedidos e checkout da área do cliente."""

import hashlib
import json
import re
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone

from common import ApiError, money_to_cents, text, utc_now, validate_payload
from db import connect_db, transaction


CUSTOMER_FIELDS = ("id", "cnpj", "legal_name", "trade_name", "contact_name", "phone", "email", "postal_code", "street", "number", "complement", "district", "city", "state")
VEHICLE_FIELDS = ("id", "plate", "brand", "model", "year", "color", "body", "axles", "fuel", "km", "price", "customized", "notes", "status")
PAYMENT_METHODS = {"Pix", "Boleto", "Cartão"}
PICKUP_LOCATION = "FasTruck · retirada na loja"
RESERVATION_MINUTES = 15
DEMO_CARDS = {
    "corporate": {"label": "Cartão corporativo", "brand": "Visa", "last4": "4242", "expiry": "12/30", "outcome": "Aprovado"},
    "alternative": {"label": "Cartão alternativo", "brand": "Mastercard", "last4": "0002", "expiry": "12/30", "outcome": "Recusado"},
}
CUSTOMIZATIONS = (
    {"id": "pintura", "name": "Pintura personalizada", "price_cents": 850000},
    {"id": "rodas", "name": "Rodas especiais", "price_cents": 240000},
    {"id": "cabine", "name": "Personalização de cabine", "price_cents": 620000},
    {"id": "defletor", "name": "Defletor", "price_cents": 390000},
    {"id": "luzes", "name": "Iluminação auxiliar", "price_cents": 175050},
    {"id": "camera", "name": "Câmera", "price_cents": 98000},
)
CUSTOMIZATION_BY_ID = {item["id"]: item for item in CUSTOMIZATIONS}


def _uuid(value, label):
    if not isinstance(value, str):
        raise ApiError(400, f"Informe uma chave UUID válida para {label}.")
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise ApiError(400, f"Informe uma chave UUID válida para {label}.") from None


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _customer_id(user):
    if not isinstance(user, dict) or user.get("role") != "customer" or not user.get("customer_id"):
        raise ApiError(401, "Entre em uma conta de cliente para continuar.")
    return str(user["customer_id"])


def _items(raw):
    if not isinstance(raw, list) or len(raw) > 30:
        raise ApiError(400, "Envie uma lista de até 30 personalizações.")
    result = []
    seen = set()
    for i, raw_item in enumerate(raw, 1):
        item = validate_payload(raw_item)
        if set(item) != {"customization_id", "quantity"}:
            raise ApiError(400, "Cada item deve conter somente customization_id e quantity.")
        customization_id = text(item, "customization_id", f"personalização do item {i}", 40, True).lower()
        if customization_id not in CUSTOMIZATION_BY_ID:
            raise ApiError(400, "Selecione uma personalização disponível no catálogo.")
        if customization_id in seen:
            raise ApiError(400, "Cada personalização pode aparecer uma única vez; ajuste a quantidade.")
        seen.add(customization_id)
        quantity = item.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 100:
            raise ApiError(400, "A quantidade de cada item deve ser um inteiro entre 1 e 100.")
        customization = CUSTOMIZATION_BY_ID[customization_id]
        price = customization["price_cents"]
        result.append({"customization_id": customization_id, "description": customization["name"], "quantity": quantity,
                       "unit_price_cents": price, "subtotal_cents": price * quantity})
    return result


def _total(base, items):
    value = base + sum(item["subtotal_cents"] for item in items)
    if not 0 <= value <= 9999999999:
        raise ApiError(400, "O preço base ou o total ultrapassa o limite de R$ 99.999.999,99.")
    return value


def _refs(conn, customer_id, vehicle_id, eligible=True, allow_reserved=False):
    c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    v = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    if c is None:
        raise ApiError(404, "Conta de cliente não encontrada.")
    if v is None:
        raise ApiError(404, "Caminhão não encontrado.")
    allowed_statuses = {"Disponível", "Reservado"} if allow_reserved else {"Disponível"}
    if eligible and (not c["active"] or v["status"] not in allowed_statuses or v["deleted_at"] or v["sold_at"]):
        raise ApiError(409, "A compra exige uma conta ativa e um caminhão Disponível.")
    return dict(c), dict(v)


def _owned(conn, order_id, customer_id):
    row = conn.execute("SELECT * FROM shop_orders WHERE id=? AND customer_id=?", (order_id, customer_id)).fetchone()
    if row is None:
        raise ApiError(404, "Pedido não encontrado.")
    return row


def _serialize(conn, row, detail=False):
    order = dict(row)
    order.pop("idempotency_key", None)
    order.pop("request_hash", None)
    order["customer"] = json.loads(order.pop("customer_snapshot") or "{}")
    order["vehicle"] = json.loads(order.pop("vehicle_snapshot") or "{}")
    order["base_price"] = order["base_price_cents"] / 100
    order["total"] = order["total_cents"] / 100
    try:
        order["billing_snapshot"] = json.loads(order.get("billing_snapshot") or "{}")
    except (TypeError, json.JSONDecodeError):
        order["billing_snapshot"] = {}
    order.setdefault("pickup_location", PICKUP_LOCATION)
    if detail:
        order["items"] = [dict(r) for r in conn.execute("SELECT * FROM shop_order_items WHERE order_id=? ORDER BY id", (order["id"],))]
        for item in order["items"]:
            item["unit_price"] = item["unit_price_cents"] / 100
            item["subtotal"] = item["subtotal_cents"] / 100
        legacy = [dict(r) for r in conn.execute("SELECT id,method,result,status,amount_cents,created_at FROM shop_order_payments WHERE order_id=? ORDER BY seq", (order["id"],))]
        for payment in legacy:
            payment["reference"] = None
            payment["ready_at"] = payment["deadline_at"] = payment["reason"] = None
            payment["receipt"] = None
        current = [dict(r) for r in conn.execute("SELECT p.id,p.method,p.status,p.amount_cents,p.reference,p.created_at,p.ready_at,p.deadline_at,p.saved_card_id,p.reason,p.approved_at,m.brand,m.last4 FROM checkout_payments p LEFT JOIN customer_payment_methods m ON m.id=p.saved_card_id WHERE p.order_id=? ORDER BY p.seq", (order["id"],))]
        for payment in current:
            payment["result"] = payment["status"]
            payment["receipt"] = ({"reference": payment["reference"], "amount_cents": payment["amount_cents"], "method": payment["method"], "approved_at": payment["approved_at"]} if payment["status"] == "Aprovado" else None)
        order["payments"] = sorted(legacy + current, key=lambda p: p.get("created_at", ""))
        for payment in order["payments"]:
            payment["amount"] = payment["amount_cents"] / 100
    return order


def _create(payload, customer_id):
    payload = validate_payload(payload)
    if set(payload) - {"vehicle_id", "items", "notes", "idempotency_key"}:
        raise ApiError(400, "A requisição contém campos de pedido não permitidos.")
    vehicle_id = text(payload, "vehicle_id", "caminhão", 100, True)
    items = _items(payload.get("items", []))
    notes = text(payload, "notes", "observações", 2000)
    key = _uuid(payload.get("idempotency_key"), "pedido")
    request_hash = _digest({"vehicle_id": vehicle_id, "items": items, "notes": notes, "customer_id": customer_id})
    with transaction() as conn:
        advance_payments(conn)
        previous = conn.execute("SELECT * FROM shop_orders WHERE idempotency_key=?", (key,)).fetchone()
        if previous:
            if previous["customer_id"] != customer_id:
                raise ApiError(409, "A chave de idempotência já foi utilizada.")
            if previous["request_hash"] != request_hash:
                raise ApiError(409, "A chave de idempotência já foi usada com outros dados.")
            return 200, _serialize(conn, previous, True)
        c, v = _refs(conn, customer_id, vehicle_id)
        try:
            base = money_to_cents(v["price"], legacy=True)
        except ApiError:
            raise ApiError(400, "O preço do caminhão deve ser no máximo R$ 99.999.999,99.") from None
        if base > 9999999999:
            raise ApiError(400, "O preço do caminhão deve ser no máximo R$ 99.999.999,99.")
        total = _total(base, items)
        if total <= 0:
            raise ApiError(400, "O pedido deve ter um total maior que zero.")
        cs = json.dumps({k: c.get(k, "") for k in CUSTOMER_FIELDS}, ensure_ascii=False)
        billing = json.dumps({k: c.get(k, "") for k in ("cnpj", "legal_name", "trade_name", "postal_code", "street", "number", "complement", "district", "city", "state")}, ensure_ascii=False)
        vs = json.dumps({k: v.get(k, "") for k in VEHICLE_FIELDS}, ensure_ascii=False)
        now, oid = utc_now(), str(uuid.uuid4())
        expires = (datetime.now(timezone.utc) + timedelta(minutes=RESERVATION_MINUTES)).isoformat(timespec="microseconds")
        cur = conn.execute("INSERT INTO shop_orders (id,number,customer_id,vehicle_id,base_price_cents,total_cents,notes,customer_snapshot,vehicle_snapshot,idempotency_key,request_hash,created_at,updated_at,billing_snapshot,pickup_location,reservation_expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (oid, "TEMP-" + oid, customer_id, vehicle_id, base, total, notes, cs, vs, key, request_hash, now, now, billing, PICKUP_LOCATION, expires))
        conn.execute("UPDATE shop_orders SET number=? WHERE seq=?", (f"PED-{cur.lastrowid:06d}", cur.lastrowid))
        conn.executemany("INSERT INTO shop_order_items (order_id,customization_id,description,quantity,unit_price_cents,subtotal_cents) VALUES (?,?,?,?,?,?)",
                         [(oid, i["customization_id"], i["description"], i["quantity"], i["unit_price_cents"], i["subtotal_cents"]) for i in items])
        from services.inventory import reserve_vehicle
        reserve_vehicle(conn, vehicle_id, oid, expires, actor_id=customer_id)
        return 201, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (oid,)).fetchone(), True)


def _payment(order_id, payload, customer_id):
    payload = validate_payload(payload)
    if set(payload) - {"method", "idempotency_key", "saved_card_id"} or not {"method", "idempotency_key"} <= set(payload):
        raise ApiError(400, "Envie somente method, idempotency_key e saved_card_id opcional.")
    method = text(payload, "method", "forma de pagamento", 20, True)
    if method not in PAYMENT_METHODS:
        raise ApiError(400, "Forma de pagamento inválida.")
    saved_card_id = payload.get("saved_card_id")
    if method == "Cartão":
        saved_card_id = text(payload, "saved_card_id", "cartão salvo", 100, True)
    elif "saved_card_id" in payload:
        raise ApiError(400, "saved_card_id só pode ser usado com Cartão.")
    key = _uuid(payload.get("idempotency_key"), "pagamento")
    request_hash = _digest({"order_id": order_id, "method": method, "saved_card_id": saved_card_id})
    with transaction() as conn:
        order = _owned(conn, order_id, customer_id)
        advance_payments(conn)
        order = _owned(conn, order_id, customer_id)
        old_payment = conn.execute("SELECT * FROM checkout_payments WHERE idempotency_key=?", (key,)).fetchone()
        if old_payment:
            if old_payment["order_id"] != order_id or old_payment["request_hash"] != request_hash:
                raise ApiError(409, "A chave de idempotência já foi usada com outros dados.")
            return 200, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone(), True)
        if order["status"] != "Aguardando pagamento":
            raise ApiError(409, "Este pedido não aceita novas tentativas de pagamento.")
        active = conn.execute("SELECT 1 FROM checkout_payments WHERE order_id=? AND status IN ('Pendente','Processando') LIMIT 1", (order_id,)).fetchone()
        if active:
            raise ApiError(409, "Este pedido já tem uma tentativa de pagamento em andamento.")
        _refs(conn, customer_id, order["vehicle_id"], allow_reserved=True)
        if order["total_cents"] <= 0:
            raise ApiError(400, "O pedido deve ter um total maior que zero.")
        if saved_card_id:
            card = conn.execute("SELECT * FROM customer_payment_methods WHERE id=? AND customer_id=?", (saved_card_id, customer_id)).fetchone()
            if card is None:
                raise ApiError(404, "Cartão salvo não encontrado.")
            if card["demo_card_id"] not in DEMO_CARDS:
                raise ApiError(409, "Este cartão salvo não está disponível.")
        # Legacy pending orders from before checkout v2 can claim stock on first payment.
        reservation = conn.execute("SELECT reserved_order_id,reserved_until,deleted_at,sold_at FROM vehicles WHERE id=?", (order["vehicle_id"],)).fetchone()
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat(timespec="microseconds")
        if reservation is None or reservation["deleted_at"] or reservation["sold_at"]:
            raise ApiError(409, "Este caminhão não está mais disponível.")
        if reservation["reserved_order_id"] != order_id:
            if reservation["reserved_order_id"] or reservation["reserved_until"] or reservation["deleted_at"] or reservation["sold_at"]:
                raise ApiError(409, "Este caminhão não está mais disponível.")
            expires = (now_dt + timedelta(minutes=RESERVATION_MINUTES)).isoformat(timespec="microseconds")
            from services.inventory import reserve_vehicle
            reserve_vehicle(conn, order["vehicle_id"], order_id, expires, actor_id=customer_id)
            conn.execute("UPDATE shop_orders SET reservation_expires_at=? WHERE id=?", (expires, order_id))
            order = conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone()
        elif reservation["reserved_until"] and reservation["reserved_until"] <= now:
            raise ApiError(409, "A reserva deste caminhão expirou.")
        processing_seconds = {"Cartão": 2, "Pix": 5, "Boleto": 8}
        ready = (now_dt + timedelta(seconds=processing_seconds[method])).isoformat(timespec="microseconds")
        status = "Processando" if method == "Cartão" else "Pendente"
        conn.execute("INSERT INTO checkout_payments (id,order_id,method,status,amount_cents,reference,idempotency_key,request_hash,saved_card_id,created_at,updated_at,ready_at,deadline_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (str(uuid.uuid4()), order_id, method, status, order["total_cents"], "PG-" + uuid.uuid4().hex[:12].upper(), key, request_hash, saved_card_id, now, now, ready, order["reservation_expires_at"]))
        advance_payments(conn)
        return 201, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone(), True)


def _approve_payment(conn, payment, now, valid_at=None):
    order = conn.execute("SELECT * FROM shop_orders WHERE id=?", (payment["order_id"],)).fetchone()
    if order is None or order["status"] != "Aguardando pagamento":
        return False
    try:
        _refs(conn, order["customer_id"], order["vehicle_id"], allow_reserved=True)
    except ApiError as exc:
        if exc.status in {404, 409}:
            return False
        raise
    vehicle = conn.execute("SELECT reserved_order_id,reserved_until,deleted_at,sold_at FROM vehicles WHERE id=?", (order["vehicle_id"],)).fetchone()
    effective_time = valid_at or now
    if vehicle is None or vehicle["deleted_at"] or vehicle["sold_at"] or vehicle["reserved_order_id"] != order["id"] or not vehicle["reserved_until"] or vehicle["reserved_until"] <= effective_time:
        return False
    from services.inventory import complete_sale
    complete_sale(conn, order["vehicle_id"], order["customer_id"], payment["amount_cents"], order_id=order["id"], actor_id=order["customer_id"], idempotency_key=payment["idempotency_key"], channel="shop", notes=order["notes"], valid_at=effective_time)
    conn.execute("UPDATE checkout_payments SET status='Aprovado',approved_at=?,updated_at=? WHERE id=?", (now, now, payment["id"]))
    conn.execute("UPDATE shop_orders SET status='Pagamento aprovado',updated_at=? WHERE id=?", (now, order["id"]))
    conn.execute("UPDATE checkout_payments SET status='Cancelado',reason='Outra tentativa foi aprovada',updated_at=? WHERE order_id=? AND id<>? AND status IN ('Pendente','Processando')", (now, order["id"], payment["id"]))
    return True


def advance_payments(conn, now=None):
    now = now or utc_now()
    from services.inventory import expire_reservations, release_vehicle
    rows = conn.execute("SELECT p.*,o.status AS order_status,o.reservation_expires_at FROM checkout_payments p JOIN shop_orders o ON o.id=p.order_id WHERE p.status IN ('Pendente','Processando') AND p.ready_at IS NOT NULL AND p.ready_at<=? ORDER BY p.seq", (now,)).fetchall()
    for row in rows:
        payment = dict(row)
        if payment["order_status"] != "Aguardando pagamento" or (payment["reservation_expires_at"] and payment["reservation_expires_at"] <= payment["ready_at"]):
            conn.execute("UPDATE checkout_payments SET status='Cancelado',reason='Reserva expirada',updated_at=? WHERE id=?", (now, payment["id"]))
        elif payment["method"] == "Cartão":
            card = conn.execute("SELECT demo_card_id FROM customer_payment_methods WHERE id=?", (payment["saved_card_id"],)).fetchone()
            outcome = DEMO_CARDS.get(card["demo_card_id"], {}).get("outcome") if card else None
            if outcome == "Aprovado":
                if not _approve_payment(conn, payment, now, valid_at=payment["ready_at"]):
                    _cancel_invalid_approval(conn, payment["order_id"], payment["id"], now)
            else:
                conn.execute("UPDATE checkout_payments SET status='Recusado',reason='Pagamento não autorizado',updated_at=? WHERE id=?", (now, payment["id"]))
        elif not _approve_payment(conn, payment, now, valid_at=payment["ready_at"]):
            _cancel_invalid_approval(conn, payment["order_id"], payment["id"], now)
    expire_reservations(conn, now=now)
    expired = conn.execute("SELECT id FROM shop_orders WHERE status='Aguardando pagamento' AND reservation_expires_at IS NOT NULL AND reservation_expires_at<=?", (now,)).fetchall()
    for row in expired:
        conn.execute("UPDATE checkout_payments SET status='Cancelado',reason='Reserva expirada',updated_at=? WHERE order_id=? AND status IN ('Pendente','Processando')", (now, row["id"]))
        conn.execute("UPDATE shop_orders SET status='Cancelado',cancel_reason='Reserva expirada',updated_at=? WHERE id=?", (now, row["id"]))
        release_vehicle(conn, row["id"], reason="Reserva expirada")


def _cancel_invalid_approval(conn, order_id, payment_id, now):
    order = conn.execute("SELECT status FROM shop_orders WHERE id=?", (order_id,)).fetchone()
    reason = "Empresa ou reserva indisponível"
    conn.execute("UPDATE checkout_payments SET status='Cancelado',reason=?,updated_at=? WHERE id=?", (reason, now, payment_id))
    if order and order["status"] == "Aguardando pagamento":
        conn.execute("UPDATE checkout_payments SET status='Cancelado',reason=?,updated_at=? WHERE order_id=? AND id<>? AND status IN ('Pendente','Processando')", (reason, now, order_id, payment_id))
        conn.execute("UPDATE shop_orders SET status='Cancelado',cancel_reason=?,updated_at=? WHERE id=?", (reason, now, order_id))
        from services.inventory import release_vehicle
        release_vehicle(conn, order_id, reason=reason)


def _read_with_advance(customer_id, order_id=None):
    with transaction() as conn:
        advance_payments(conn)
        if order_id:
            return _serialize(conn, _owned(conn, order_id, customer_id), True)
        return [_serialize(conn, r) for r in conn.execute("SELECT * FROM shop_orders WHERE customer_id=? ORDER BY seq DESC", (customer_id,))]


def handle_request(method, path, payload=None, user=None):
    if path == "/api/shop/customizations":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar as personalizações.")
        return 200, [dict(item) for item in CUSTOMIZATIONS]
    if path == "/api/shop/checkout-options":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar as opções de checkout.")
        with transaction() as conn:
            advance_payments(conn)
            return 200, {"pickup_location": PICKUP_LOCATION, "reservation_minutes": RESERVATION_MINUTES,
                         "demo_cards": [{"id": card_id, **{k: v[k] for k in ("label", "brand", "last4", "expiry")}} for card_id, v in DEMO_CARDS.items()]}
    if path == "/api/shop/catalog":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar o catálogo.")
        with transaction() as conn:
            # Catalog reads must not advertise expired reservations as unavailable.
            advance_payments(conn)
            rows = conn.execute("SELECT * FROM vehicles WHERE status='Disponível' AND deleted_at IS NULL AND sold_at IS NULL AND reserved_order_id IS NULL ORDER BY rowid DESC")
            return 200, [dict(row) for row in rows]
    if path == "/api/shop/account":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar a conta.")
        cid = _customer_id(user)
        with closing(connect_db()) as conn:
            row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
            if row is None:
                raise ApiError(404, "Conta de cliente não encontrada.")
            return 200, dict(row)
    if path == "/api/shop/payment-methods":
        cid = _customer_id(user)
        if method == "GET":
            with closing(connect_db()) as conn:
                rows = conn.execute("SELECT id,brand,last4,holder_name,demo_card_id,created_at FROM customer_payment_methods WHERE customer_id=? ORDER BY created_at", (cid,))
                return 200, [dict(row) for row in rows]
        if method == "POST":
            data = validate_payload(payload)
            if set(data) != {"demo_card_id", "holder_name"}:
                raise ApiError(400, "Envie somente demo_card_id e holder_name; dados de cartão não são aceitos.")
            demo_id = text(data, "demo_card_id", "cartão", 30, True)
            holder = text(data, "holder_name", "nome do titular", 120, True)
            demo = DEMO_CARDS.get(demo_id)
            if not demo:
                raise ApiError(400, "Selecione um cartão disponível.")
            with transaction() as conn:
                existing = conn.execute("SELECT * FROM customer_payment_methods WHERE customer_id=? AND demo_card_id=?", (cid, demo_id)).fetchone()
                if existing:
                    conn.execute("UPDATE customer_payment_methods SET holder_name=? WHERE id=?", (holder, existing["id"]))
                    card_id = existing["id"]
                else:
                    card_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO customer_payment_methods (id,customer_id,brand,last4,holder_name,demo_card_id,created_at) VALUES (?,?,?,?,?,?,?)", (card_id,cid,demo["brand"],demo["last4"],holder,demo_id,utc_now()))
                return 201, dict(conn.execute("SELECT id,brand,last4,holder_name,demo_card_id,created_at FROM customer_payment_methods WHERE id=?", (card_id,)).fetchone())
        raise ApiError(405, "Use GET ou POST para formas de pagamento.")
    if path == "/api/shop/admin/orders":
        if not isinstance(user, dict) or user.get("role") != "admin":
            raise ApiError(403, "Acesso restrito à administração.")
        if method != "GET":
            raise ApiError(405, "Use GET para consultar os pedidos.")
        with transaction() as conn:
            advance_payments(conn)
            return 200, [_serialize(conn, r, True) for r in conn.execute("SELECT * FROM shop_orders ORDER BY seq DESC")]
    if path in {"/api/shop/orders", "/api/shop/me/orders"}:
        cid = _customer_id(user)
        if method == "GET":
            return 200, _read_with_advance(cid)
        if method == "POST":
            return _create(payload, cid)
        raise ApiError(405, "Use GET ou POST para pedidos.")
    match = re.fullmatch(r"/api/shop/orders/([^/]+)(/payment|/cancel)?", path)
    if not match:
        return None
    cid = _customer_id(user)
    order_id, action = match.group(1), match.group(2)
    if action == "/payment":
        if method != "POST":
            raise ApiError(405, "Use POST para registrar pagamento.")
        return _payment(order_id, payload, cid)
    if action == "/cancel":
        if method != "POST":
            raise ApiError(405, "Use POST para cancelar o pedido.")
        with transaction() as conn:
            advance_payments(conn)
            order = _owned(conn, order_id, cid)
            if order["status"] == "Pagamento aprovado":
                raise ApiError(409, "Um pedido com pagamento aprovado não pode ser cancelado.")
            if order["status"] != "Cancelado":
                now = utc_now()
                conn.execute("UPDATE shop_orders SET status='Cancelado',cancel_reason='Cancelado pelo cliente',updated_at=? WHERE id=?", (now, order_id))
                conn.execute("UPDATE checkout_payments SET status='Cancelado',reason='Pedido cancelado',updated_at=? WHERE order_id=? AND status IN ('Pendente','Processando')", (now, order_id))
                from services.inventory import release_vehicle
                release_vehicle(conn, order_id, actor_id=cid, reason="Pedido cancelado pelo cliente")
            return 200, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone(), True)
    if method != "GET":
        raise ApiError(405, "Use GET para consultar o pedido.")
    return 200, _read_with_advance(cid, order_id)
