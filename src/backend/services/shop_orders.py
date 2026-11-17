"""Catálogo e checkout simulado da área do cliente."""

import hashlib
import json
import re
import uuid
from contextlib import closing

from common import ApiError, money_to_cents, text, utc_now, validate_payload
from db import connect_db, transaction


CUSTOMER_FIELDS = ("id", "cnpj", "legal_name", "trade_name", "contact_name", "phone", "email", "postal_code", "street", "number", "complement", "district", "city", "state")
VEHICLE_FIELDS = ("id", "plate", "brand", "model", "year", "color", "body", "axles", "fuel", "km", "price", "customized", "notes", "status")
PAYMENT_METHODS = {"Pix", "Boleto", "Cartão"}
PAYMENT_RESULTS = {"Aprovado", "Recusado", "Cancelado"}
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


def _refs(conn, customer_id, vehicle_id, eligible=True):
    c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    v = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    if c is None:
        raise ApiError(404, "Conta de cliente não encontrada.")
    if v is None:
        raise ApiError(404, "Caminhão não encontrado.")
    if eligible and (not c["active"] or v["status"] != "Disponível"):
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
    if detail:
        order["items"] = [dict(r) for r in conn.execute("SELECT * FROM shop_order_items WHERE order_id=? ORDER BY id", (order["id"],))]
        for item in order["items"]:
            item["unit_price"] = item["unit_price_cents"] / 100
            item["subtotal"] = item["subtotal_cents"] / 100
        order["payments"] = [dict(r) for r in conn.execute("SELECT id,method,result,status,amount_cents,simulated,created_at FROM shop_order_payments WHERE order_id=? ORDER BY seq", (order["id"],))]
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
        vs = json.dumps({k: v.get(k, "") for k in VEHICLE_FIELDS}, ensure_ascii=False)
        now, oid = utc_now(), str(uuid.uuid4())
        cur = conn.execute("INSERT INTO shop_orders (id,number,customer_id,vehicle_id,base_price_cents,total_cents,notes,customer_snapshot,vehicle_snapshot,idempotency_key,request_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (oid, "TEMP-" + oid, customer_id, vehicle_id, base, total, notes, cs, vs, key, request_hash, now, now))
        conn.execute("UPDATE shop_orders SET number=? WHERE seq=?", (f"PED-{cur.lastrowid:06d}", cur.lastrowid))
        conn.executemany("INSERT INTO shop_order_items (order_id,customization_id,description,quantity,unit_price_cents,subtotal_cents) VALUES (?,?,?,?,?,?)",
                         [(oid, i["customization_id"], i["description"], i["quantity"], i["unit_price_cents"], i["subtotal_cents"]) for i in items])
        return 201, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (oid,)).fetchone(), True)


def _payment(order_id, payload, customer_id):
    payload = validate_payload(payload)
    if set(payload) != {"method", "result", "idempotency_key"}:
        raise ApiError(400, "Envie somente method, result e idempotency_key; dados de cartão não são aceitos.")
    method, result = text(payload, "method", "forma de pagamento", 20, True), text(payload, "result", "resultado", 20, True)
    if method not in PAYMENT_METHODS or result not in PAYMENT_RESULTS:
        raise ApiError(400, "Forma ou resultado de pagamento inválido.")
    key = _uuid(payload.get("idempotency_key"), "pagamento")
    request_hash = _digest({"order_id": order_id, "method": method, "result": result})
    with transaction() as conn:
        order = _owned(conn, order_id, customer_id)
        old_payment = conn.execute("SELECT * FROM shop_order_payments WHERE idempotency_key=?", (key,)).fetchone()
        if old_payment:
            if old_payment["order_id"] != order_id or old_payment["request_hash"] != request_hash:
                raise ApiError(409, "A chave de idempotência já foi usada com outros dados.")
            return 200, _serialize(conn, order, True)
        if order["status"] != "Aguardando pagamento":
            raise ApiError(409, "Este pedido não aceita novas tentativas de pagamento.")
        if result == "Aprovado":
            c, v = _refs(conn, customer_id, order["vehicle_id"])
            # A validade da simulação é confirmada, mas o estoque permanece intacto.
            if order["total_cents"] <= 0:
                raise ApiError(400, "O pedido deve ter um total maior que zero para aprovar o pagamento.")
        now = utc_now()
        conn.execute("INSERT INTO shop_order_payments (id,order_id,idempotency_key,request_hash,method,result,status,amount_cents,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (str(uuid.uuid4()), order_id, key, request_hash, method, result, result, order["total_cents"], now))
        if result == "Aprovado":
            conn.execute("UPDATE shop_orders SET status='Pagamento aprovado',updated_at=? WHERE id=?", (now, order_id))
        return 201, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone(), True)


def handle_request(method, path, payload=None, user=None):
    if path == "/api/shop/customizations":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar as personalizações.")
        return 200, [dict(item) for item in CUSTOMIZATIONS]
    if path == "/api/shop/catalog":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar o catálogo.")
        with closing(connect_db()) as conn:
            rows = conn.execute("SELECT * FROM vehicles WHERE status='Disponível' ORDER BY rowid DESC")
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
    if path == "/api/shop/admin/orders":
        if not isinstance(user, dict) or user.get("role") != "admin":
            raise ApiError(403, "Acesso restrito à administração.")
        if method != "GET":
            raise ApiError(405, "Use GET para consultar os pedidos.")
        with closing(connect_db()) as conn:
            return 200, [_serialize(conn, r, True) for r in conn.execute("SELECT * FROM shop_orders ORDER BY seq DESC")]
    if path in {"/api/shop/orders", "/api/shop/me/orders"}:
        cid = _customer_id(user)
        if method == "GET":
            with closing(connect_db()) as conn:
                return 200, [_serialize(conn, r) for r in conn.execute("SELECT * FROM shop_orders WHERE customer_id=? ORDER BY seq DESC", (cid,))]
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
            order = _owned(conn, order_id, cid)
            if order["status"] == "Pagamento aprovado":
                raise ApiError(409, "Um pedido com pagamento aprovado não pode ser cancelado.")
            if order["status"] != "Cancelado":
                conn.execute("UPDATE shop_orders SET status='Cancelado',updated_at=? WHERE id=?", (utc_now(), order_id))
            return 200, _serialize(conn, conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone(), True)
    if method != "GET":
        raise ApiError(405, "Use GET para consultar o pedido.")
    with closing(connect_db()) as conn:
        return 200, _serialize(conn, _owned(conn, order_id, cid), True)
