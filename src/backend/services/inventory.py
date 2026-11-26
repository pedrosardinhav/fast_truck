"""Lifecycle and administration endpoints for vehicle inventory."""
import json
import re
import uuid
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import parse_qs

from common import ApiError, money_to_cents, text, utc_now, validate_payload
from db import connect_db, transaction


def _now(value=None):
    value = value or utc_now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("now/expires_at must be an ISO UTC datetime") from None


def _iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def record_event(conn, vehicle_id, action, actor_id=None, order_id=None, reason="", before=None, after=None):
    if action not in {"created", "updated", "deleted", "reserved", "released", "sold"}:
        raise ValueError("invalid vehicle event action")
    conn.execute(
        "INSERT INTO vehicle_events(id,vehicle_id,action,actor_id,order_id,reason,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), vehicle_id, action, actor_id, order_id, reason or "",
         json.dumps(before, ensure_ascii=False, sort_keys=True) if before is not None else None,
         json.dumps(after, ensure_ascii=False, sort_keys=True) if after is not None else None, utc_now()),
    )


def expire_reservations(conn, now=None):
    """Cancel expired pending checkouts and release only their owned reservations."""
    cutoff = _iso(_now(now))
    rows = conn.execute(
        "SELECT id,reserved_order_id,reserved_until FROM vehicles WHERE reserved_order_id IS NOT NULL AND reserved_until IS NOT NULL"
    ).fetchall()
    expired = []
    for row in rows:
        if _iso(_now(row["reserved_until"])) <= cutoff:
            expired.append((row["id"], row["reserved_order_id"]))
    for vehicle_id, order_id in expired:
        order = conn.execute("SELECT status FROM shop_orders WHERE id=?", (order_id,)).fetchone()
        if order and order["status"] == "Aguardando pagamento":
            conn.execute("UPDATE shop_orders SET status='Cancelado',cancel_reason='Reserva expirada',updated_at=? WHERE id=? AND status='Aguardando pagamento'", (cutoff, order_id))
        # 007 checkout integrations may persist payment attempts separately.
        has_checkout_payments = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkout_payments'").fetchone()
        if has_checkout_payments:
            conn.execute("UPDATE checkout_payments SET status='Cancelado',reason='Reserva expirada',updated_at=? WHERE order_id=? AND status IN ('Processando','Pendente')", (cutoff, order_id))
        before = dict(conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone())
        cur = conn.execute("UPDATE vehicles SET status='Disponível',reserved_order_id=NULL,reserved_until=NULL WHERE id=? AND reserved_order_id=? AND status='Reservado' AND deleted_at IS NULL", (vehicle_id, order_id))
        if cur.rowcount:
            after = dict(conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone())
            record_event(conn, vehicle_id, "released", order_id=order_id, reason="Reserva expirada", before=before, after=after)
    return len(expired)


def _advance_checkout(conn, now=None):
    """Resolve ready checkout attempts before expiry releases their reservations."""
    from services.shop_orders import advance_payments
    return advance_payments(conn, now=now)


def reserve_vehicle(conn, vehicle_id, order_id, expires_at, actor_id=None):
    expiry = _iso(_now(expires_at))
    if _now(expires_at) <= _now():
        raise ApiError(400, "A validade da reserva deve estar no futuro.")
    before = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    if before is None:
        raise ApiError(404, "Caminhão não encontrado.")
    before = dict(before)
    cur = conn.execute("UPDATE vehicles SET status='Reservado',reserved_order_id=?,reserved_until=? WHERE id=? AND status='Disponível' AND deleted_at IS NULL AND reserved_order_id IS NULL",
                       (order_id, expiry, vehicle_id))
    if not cur.rowcount:
        raise ApiError(409, "Este caminhão não está disponível para reserva.")
    after = dict(conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone())
    record_event(conn, vehicle_id, "reserved", actor_id, order_id, before=before, after=after)
    return after


def release_vehicle(conn, order_id, actor_id=None, reason=""):
    rows = conn.execute("SELECT * FROM vehicles WHERE reserved_order_id=? AND status='Reservado' AND deleted_at IS NULL", (order_id,)).fetchall()
    for row in rows:
        before = dict(row)
        conn.execute("UPDATE vehicles SET status='Disponível',reserved_order_id=NULL,reserved_until=NULL WHERE id=? AND reserved_order_id=? AND status='Reservado' AND deleted_at IS NULL", (row["id"], order_id))
        after = dict(conn.execute("SELECT * FROM vehicles WHERE id=?", (row["id"],)).fetchone())
        record_event(conn, row["id"], "released", actor_id, order_id, reason, before, after)
    return len(rows)


def complete_sale(conn, vehicle_id, customer_id, amount_cents, order_id=None, actor_id=None,
                  idempotency_key=None, channel="shop", notes="", valid_at=None):
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ApiError(400, "O valor da venda deve ser maior que zero.")
    if channel not in {"admin", "shop"}:
        raise ApiError(400, "Canal de venda inválido.")
    key = idempotency_key or str(uuid.uuid4())
    try:
        key = str(uuid.UUID(key))
    except (ValueError, TypeError, AttributeError):
        raise ApiError(400, "Informe uma chave UUID válida para a venda.") from None
    prior = conn.execute("SELECT * FROM vehicle_sales WHERE idempotency_key=?", (key,)).fetchone()
    if prior:
        if prior["vehicle_id"] != vehicle_id or prior["customer_id"] != customer_id or prior["amount_cents"] != amount_cents or prior["order_id"] != order_id:
            raise ApiError(409, "A chave de idempotência já foi usada com outros dados.")
        return dict(prior)
    vehicle = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    customer = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if vehicle is None:
        raise ApiError(404, "Caminhão não encontrado.")
    if customer is None:
        raise ApiError(404, "Empresa não encontrada.")
    if not customer["active"]:
        raise ApiError(409, "A venda exige uma empresa ativa.")
    if vehicle["deleted_at"]:
        raise ApiError(409, "Não é possível vender um caminhão arquivado.")
    if vehicle["status"] == "Vendido" or conn.execute("SELECT 1 FROM vehicle_sales WHERE vehicle_id=?", (vehicle_id,)).fetchone():
        raise ApiError(409, "Este caminhão já foi vendido.")
    if channel == "shop":
        if not order_id or vehicle["status"] != "Reservado" or vehicle["reserved_order_id"] != order_id:
            raise ApiError(409, "A venda da loja exige a reserva correspondente ao pedido.")
        if not vehicle["reserved_until"] or _now(vehicle["reserved_until"]) <= _now(valid_at):
            raise ApiError(409, "A reserva do pedido expirou.")
    elif vehicle["status"] == "Reservado" and vehicle["reserved_order_id"] != order_id:
        raise ApiError(409, "A reserva pertence a outro pedido.")
    if vehicle["status"] not in {"Disponível", "Reservado"}:
        raise ApiError(409, "Este caminhão não pode ser vendido.")
    if order_id:
        order = conn.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone()
        if not order or order["vehicle_id"] != vehicle_id or order["customer_id"] != customer_id:
            raise ApiError(409, "O pedido não corresponde à empresa e ao caminhão.")
        if order["status"] not in {"Aguardando pagamento", "Pagamento aprovado"}:
            raise ApiError(409, "O pedido não pode concluir esta venda.")
    before = dict(vehicle)
    now = utc_now()
    cur = conn.execute("UPDATE vehicles SET status='Vendido',sold_at=?,reserved_order_id=NULL,reserved_until=NULL WHERE id=? AND deleted_at IS NULL AND status IN ('Disponível','Reservado')",
                       (now, vehicle_id))
    if not cur.rowcount:
        raise ApiError(409, "Este caminhão deixou de estar disponível.")
    sale_id = str(uuid.uuid4())
    sale_cur = conn.execute("INSERT INTO vehicle_sales(id,number,vehicle_id,customer_id,order_id,idempotency_key,amount_cents,channel,created_by,created_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (sale_id, "TEMP-" + sale_id, vehicle_id, customer_id, order_id, key, amount_cents, channel, actor_id, now, notes or ""))
    conn.execute("UPDATE vehicle_sales SET number=? WHERE seq=?", (f"VEN-{sale_cur.lastrowid:06d}", sale_cur.lastrowid))
    after = dict(conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone())
    record_event(conn, vehicle_id, "sold", actor_id, order_id, before=before, after=after)
    return dict(conn.execute("SELECT * FROM vehicle_sales WHERE id=?", (sale_id,)).fetchone())


def _serialize_vehicle(conn, row, detail=False):
    result = dict(row)
    if detail:
        result["events"] = [dict(e) for e in conn.execute("SELECT * FROM vehicle_events WHERE vehicle_id=? ORDER BY seq", (row["id"],))]
        for event in result["events"]:
            for key in ("before_json", "after_json"):
                if event[key]:
                    event[key.removesuffix("_json")] = json.loads(event.pop(key))
        sale = conn.execute("SELECT * FROM vehicle_sales WHERE vehicle_id=?", (row["id"],)).fetchone()
        result["sale"] = dict(sale) if sale else None
    return result


def _admin(user):
    if not isinstance(user, dict) or user.get("role") != "admin":
        raise ApiError(403, "Acesso restrito à administração.")


def _sale_amount(value, default):
    if value is None or value == "":
        cents = money_to_cents(default, legacy=True)
    elif isinstance(value, str) and ("," in value or value.strip().startswith("R$")):
        raw = value.strip().replace("R$", "").replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        cents = money_to_cents(raw)
    else:
        cents = money_to_cents(value)
    if cents <= 0:
        raise ApiError(400, "O valor da venda deve ser maior que zero.")
    return cents


def handle_request(method, path, payload=None, user=None):
    if not path.startswith("/api/vehicles"):
        return None
    _admin(user)
    raw_path, _, query = path.partition("?")
    match = re.fullmatch(r"/api/vehicles/([^/]+)(/sell)?", raw_path)
    if raw_path != "/api/vehicles" and not match:
        return None
    if raw_path == "/api/vehicles":
        if method != "GET":
            raise ApiError(405, "Use GET para consultar o estoque.")
        view = parse_qs(query).get("view", ["active"])[0]
        if view not in {"active", "deleted", "all"}:
            raise ApiError(400, "A visão deve ser active, deleted ou all.")
        with transaction() as conn:
            _advance_checkout(conn)
            where = "" if view == "all" else "WHERE deleted_at IS NULL" if view == "active" else "WHERE deleted_at IS NOT NULL"
            return 200, [_serialize_vehicle(conn, row) for row in conn.execute(f"SELECT * FROM vehicles {where} ORDER BY rowid DESC")]
    vehicle_id, action = match.group(1), match.group(2)
    if action == "/sell":
        if method != "POST":
            raise ApiError(405, "Use POST para registrar uma venda.")
        data = validate_payload(payload)
        if set(data) - {"customer_id", "amount", "notes", "idempotency_key"}:
            raise ApiError(400, "A requisição contém campos de venda não permitidos.")
        cid = text(data, "customer_id", "empresa", 100, True)
        notes = text(data, "notes", "observações", 2000)
        key = data.get("idempotency_key")
        if key is not None:
            try:
                key = str(uuid.UUID(key))
            except (ValueError, TypeError, AttributeError):
                raise ApiError(400, "Informe uma chave UUID válida para a venda.") from None
        with transaction() as conn:
            _advance_checkout(conn)
            vehicle = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
            if vehicle is None:
                raise ApiError(404, "Caminhão não encontrado.")
            sale = complete_sale(conn, vehicle_id, cid, _sale_amount(data.get("amount"), vehicle["price"]), actor_id=user.get("id"), idempotency_key=key, channel="admin", notes=notes)
            return 201, sale
    if method == "DELETE":
        data = validate_payload(payload or {})
        if set(data) - {"reason"}:
            raise ApiError(400, "Envie somente o motivo do arquivamento.")
        reason = text(data, "reason", "motivo", 500, min_length=0) or "Arquivado pela administração"
        if len(reason) < 3:
            raise ApiError(400, "O motivo deve conter pelo menos 3 caracteres.")
        with transaction() as conn:
            _advance_checkout(conn)
            row = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
            if row is None:
                raise ApiError(404, "Caminhão não encontrado.")
            if row["deleted_at"]:
                return 200, _serialize_vehicle(conn, row, True)
            if row["status"] == "Reservado":
                raise ApiError(409, "Não é possível arquivar um caminhão reservado.")
            before = dict(row)
            now = utc_now()
            conn.execute("UPDATE vehicles SET deleted_at=?,deleted_by=?,deleted_reason=? WHERE id=? AND deleted_at IS NULL", (now, user.get("id"), reason, vehicle_id))
            after = dict(conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone())
            record_event(conn, vehicle_id, "deleted", user.get("id"), reason=reason, before=before, after=after)
            return 200, _serialize_vehicle(conn, conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone(), True)
    if method != "GET":
        raise ApiError(405, "Use GET para consultar o caminhão.")
    with transaction() as conn:
        _advance_checkout(conn)
        row = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if row is None:
            raise ApiError(404, "Caminhão não encontrado.")
        return 200, _serialize_vehicle(conn, row, True)
