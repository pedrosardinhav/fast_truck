"""Propostas comerciais. Autoria inicial do subagente propostas, integrada à API."""

import json
import re
import uuid
from contextlib import closing
from datetime import date

from common import ApiError, money_to_cents, text, today_brasilia, utc_now, validate_payload
from db import connect_db, transaction


STATUSES = {"Em elaboração", "Enviada", "Aprovada", "Cancelada"}
MAX_TOTAL = 99999999999
CUSTOMER_FIELDS = ("id", "cnpj", "legal_name", "trade_name", "contact_name", "phone", "email", "postal_code", "street", "number", "complement", "district", "city", "state")
VEHICLE_FIELDS = ("id", "plate", "brand", "model", "year", "color", "body", "axles", "fuel", "km", "customized", "notes")


def _refs(conn, customer_id, vehicle_id, eligible=True):
    c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    v = conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    if c is None or v is None:
        raise ApiError(404, "Empresa ou caminhão não encontrado.")
    if eligible and (not c["active"] or v["status"] != "Disponível"):
        raise ApiError(409, "A ação exige empresa ativa e caminhão Disponível.")
    return dict(c), dict(v)


def _snapshots(c, v):
    return (json.dumps({k: c.get(k, "") for k in CUSTOMER_FIELDS}, ensure_ascii=False),
            json.dumps({k: v.get(k, "") for k in VEHICLE_FIELDS}, ensure_ascii=False))


def _get(conn, proposal_id):
    row = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Proposta não encontrada.")
    return row


def _serialize(conn, row, detail=False):
    p = dict(row)
    p["customer"] = json.loads(p.pop("customer_snapshot") or "{}")
    p["vehicle"] = json.loads(p.pop("vehicle_snapshot") or "{}")
    p["expired"] = p["valid_until"] < today_brasilia().isoformat()
    c, v = _refs(conn, p["customer_id"], p["vehicle_id"], False)
    p["customer_active"] = bool(c["active"])
    p["vehicle_status"] = v["status"]
    if p["status"] == "Em elaboração":
        cs, vs = _snapshots(c, v)
        p["customer"], p["vehicle"] = json.loads(cs), json.loads(vs)
    payments = [dict(r) for r in conn.execute("SELECT id,reference,status,amount_cents,method FROM payments WHERE proposal_id=? ORDER BY seq DESC", (p["id"],))]
    p["eligible_for_payment"] = p["status"] == "Aprovada" and not p["expired"] and p["customer_active"] and v["status"] == "Disponível" and p["total_cents"] > 0 and not any(r["status"] in {"Pendente", "Aprovado"} for r in payments)
    if detail:
        p["items"] = [dict(r) for r in conn.execute("SELECT * FROM proposal_items WHERE proposal_id=? ORDER BY id", (p["id"],))]
        p["events"] = [dict(r) for r in conn.execute("SELECT * FROM proposal_events WHERE proposal_id=? ORDER BY id", (p["id"],))]
        p["payments"] = payments
    return p


def _items(raw):
    if not isinstance(raw, list) or len(raw) > 30:
        raise ApiError(400, "Envie uma lista de até 30 personalizações.")
    result = []
    for i, item in enumerate(raw, 1):
        item = validate_payload(item)
        description = text(item, "description", f"descrição do item {i}", 160, True, 2)
        quantity = item.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 100:
            raise ApiError(400, "A quantidade de cada item deve ser um inteiro entre 1 e 100.")
        price = money_to_cents(item.get("unit_price"))
        if price > 99999999:
            raise ApiError(400, "O preço unitário não pode ultrapassar R$ 999.999,99.")
        result.append({"description": description, "quantity": quantity, "unit_price_cents": price, "subtotal_cents": price * quantity})
    return result


def _form(payload):
    payload = validate_payload(payload)
    customer_id = text(payload, "customer_id", "empresa", 100, True)
    vehicle_id = text(payload, "vehicle_id", "caminhão", 100, True)
    until = text(payload, "valid_until", "validade", 10, True)
    try:
        parsed = date.fromisoformat(until)
        if parsed.isoformat() != until or parsed < today_brasilia():
            raise ValueError
    except ValueError:
        raise ApiError(400, "A validade deve ser uma data de hoje ou futura no formato AAAA-MM-DD.") from None
    return customer_id, vehicle_id, until, text(payload, "notes", "observações", 2000), _items(payload.get("items", []))


def _total(base, items):
    total = base + sum(i["subtotal_cents"] for i in items)
    if not 0 <= total <= MAX_TOTAL:
        raise ApiError(400, "O total ultrapassou o limite de R$ 999.999.999,99.")
    return total


def _save_items(conn, proposal_id, items):
    conn.executemany("INSERT INTO proposal_items (proposal_id,description,quantity,unit_price_cents,subtotal_cents) VALUES (?,?,?,?,?)",
                     [(proposal_id, i["description"], i["quantity"], i["unit_price_cents"], i["subtotal_cents"]) for i in items])


def _create(payload):
    cid, vid, until, notes, items = _form(payload)
    with transaction() as conn:
        c, v = _refs(conn, cid, vid)
        base = money_to_cents(v["price"], legacy=True)
        total = _total(base, items)
        cs, vs = _snapshots(c, v)
        pid, now = str(uuid.uuid4()), utc_now()
        cursor = conn.execute("INSERT INTO proposals (id,number,customer_id,vehicle_id,base_price_cents,total_cents,valid_until,notes,customer_snapshot,vehicle_snapshot,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                              (pid, "TEMP-" + pid, cid, vid, base, total, until, notes, cs, vs, now, now))
        conn.execute("UPDATE proposals SET number=? WHERE id=?", (f"PROP-{cursor.lastrowid:06d}", pid))
        _save_items(conn, pid, items)
        conn.execute("INSERT INTO proposal_events (proposal_id,from_status,to_status,reason,created_at) VALUES (?,NULL,'Em elaboração','Proposta criada',?)", (pid, now))
        return 201, _serialize(conn, _get(conn, pid), True)


def _update(pid, payload):
    cid, vid, until, notes, items = _form(payload)
    with transaction() as conn:
        old = _get(conn, pid)
        if old["status"] != "Em elaboração":
            raise ApiError(409, "Somente propostas em elaboração podem ser editadas.")
        c, v = _refs(conn, cid, vid, eligible=False)
        if cid != old["customer_id"] and not c["active"]:
            raise ApiError(409, "Selecione uma empresa ativa para trocar o cliente.")
        if vid != old["vehicle_id"] and v["status"] != "Disponível":
            raise ApiError(409, "Selecione um caminhão Disponível para trocar o veículo.")
        base = old["base_price_cents"] if vid == old["vehicle_id"] else money_to_cents(v["price"], legacy=True)
        total = _total(base, items)
        cs, vs = _snapshots(c, v)
        conn.execute("UPDATE proposals SET customer_id=?,vehicle_id=?,base_price_cents=?,total_cents=?,valid_until=?,notes=?,customer_snapshot=?,vehicle_snapshot=?,updated_at=? WHERE id=?",
                     (cid, vid, base, total, until, notes, cs, vs, utc_now(), pid))
        conn.execute("DELETE FROM proposal_items WHERE proposal_id=?", (pid,))
        _save_items(conn, pid, items)
        return 200, _serialize(conn, _get(conn, pid), True)


def _change_status(pid, payload):
    payload = validate_payload(payload)
    target = text(payload, "status", "status", 30, True)
    if target not in STATUSES:
        raise ApiError(400, "Status de proposta inválido.")
    with transaction() as conn:
        p = _get(conn, pid)
        old = p["status"]
        if old == target:
            return 200, _serialize(conn, p, True)
        allowed = {"Em elaboração": {"Enviada", "Cancelada"}, "Enviada": {"Aprovada", "Cancelada"}, "Aprovada": {"Cancelada"}, "Cancelada": set()}
        if target not in allowed[old]:
            raise ApiError(409, f"Não é permitido mudar de {old} para {target}.")
        reason = text(payload, "reason", "motivo", 500, required=target == "Cancelada", min_length=3)
        if target in {"Enviada", "Aprovada"}:
            c, v = _refs(conn, p["customer_id"], p["vehicle_id"])
            if p["valid_until"] < today_brasilia().isoformat():
                raise ApiError(409, "A validade da proposta expirou.")
            items = [dict(r) for r in conn.execute("SELECT * FROM proposal_items WHERE proposal_id=?", (pid,))]
            total = _total(p["base_price_cents"], items)
            if total <= 0:
                raise ApiError(400, "A proposta deve ter um total maior que zero.")
            if target == "Enviada":
                cs, vs = _snapshots(c, v)
                conn.execute("UPDATE proposals SET customer_snapshot=?,vehicle_snapshot=?,total_cents=? WHERE id=?", (cs, vs, total, pid))
        if target == "Cancelada" and conn.execute("SELECT 1 FROM payments WHERE proposal_id=? AND status IN ('Pendente','Aprovado') LIMIT 1", (pid,)).fetchone():
            raise ApiError(409, "Cancele a tentativa pendente primeiro. Pagamento aprovado impede cancelar a proposta.")
        now = utc_now()
        conn.execute("UPDATE proposals SET status=?,updated_at=? WHERE id=?", (target, now, pid))
        conn.execute("INSERT INTO proposal_events (proposal_id,from_status,to_status,reason,created_at) VALUES (?,?,?,?,?)", (pid, old, target, reason, now))
        return 200, _serialize(conn, _get(conn, pid), True)


def handle_request(method, path, payload=None):
    if path == "/api/proposals":
        if method == "GET":
            with closing(connect_db()) as conn:
                return 200, [_serialize(conn, r) for r in conn.execute("SELECT * FROM proposals ORDER BY seq DESC").fetchall()]
        if method == "POST":
            return _create(payload)
        raise ApiError(405, "Método não permitido para propostas.")
    match = re.fullmatch(r"/api/proposals/([^/]+)(/status)?", path)
    if not match:
        return None
    pid = match.group(1)
    if match.group(2):
        if method != "POST":
            raise ApiError(405, "Use POST para mudar o status da proposta.")
        return _change_status(pid, payload)
    if method == "PUT":
        return _update(pid, payload)
    if method == "GET":
        with closing(connect_db()) as conn:
            return 200, _serialize(conn, _get(conn, pid), True)
    if method == "DELETE":
        with transaction() as conn:
            p = _get(conn, pid)
            if p["status"] != "Em elaboração" or conn.execute("SELECT 1 FROM payments WHERE proposal_id=? LIMIT 1", (pid,)).fetchone():
                raise ApiError(409, "Só é possível excluir rascunho sem pagamentos.")
            conn.execute("DELETE FROM proposals WHERE id=?", (pid,))
            return 200, {"message": "Rascunho excluído."}
    raise ApiError(405, "Método não permitido para esta proposta.")
