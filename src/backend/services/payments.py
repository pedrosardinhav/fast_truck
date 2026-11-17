"""Pagamentos exclusivamente simulados. Autoria do subagente pagamentos."""

import json
import re
import sqlite3
import uuid
from contextlib import closing
from urllib.parse import parse_qs, urlsplit

from common import ApiError, text, today_brasilia, utc_now, validate_payload
from db import connect_db, transaction


METHODS = {"Pix", "Boleto", "Cartão"}
STATUSES = {"Pendente", "Aprovado", "Recusado", "Cancelado"}


def _eligible(conn, proposal_id):
    row = conn.execute("""SELECT p.*,c.active AS customer_active,v.status AS vehicle_status
        FROM proposals p JOIN customers c ON c.id=p.customer_id
        JOIN vehicles v ON v.id=p.vehicle_id WHERE p.id=?""", (proposal_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Proposta não encontrada.")
    if row["status"] != "Aprovada" or row["valid_until"] < today_brasilia().isoformat() or not row["customer_active"] or row["vehicle_status"] != "Disponível" or row["total_cents"] <= 0:
        raise ApiError(409, "O pagamento exige proposta aprovada e vigente, empresa ativa e caminhão Disponível.")
    return row


def _payment(conn, payment_id):
    row = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Pagamento não encontrado.")
    return row


def _serialize(conn, payment, detail=False):
    result = dict(payment)
    p = dict(conn.execute("SELECT * FROM proposals WHERE id=?", (result["proposal_id"],)).fetchone())
    for key in ("customer_snapshot", "vehicle_snapshot"):
        p[key] = json.loads(p[key] or "{}")
    result.update(proposal_number=p["number"], customer_name=p["customer_snapshot"].get("legal_name", ""),
                  cnpj=p["customer_snapshot"].get("cnpj", ""), vehicle_plate=p["vehicle_snapshot"].get("plate", ""))
    if detail:
        result["proposal"] = p
        result["events"] = [dict(r) for r in conn.execute("SELECT * FROM payment_events WHERE payment_id=? ORDER BY created_at,rowid", (result["id"],))]
    return result


def _create(payload):
    data = validate_payload(payload)
    if set(data) != {"proposal_id", "method", "idempotency_key"}:
        raise ApiError(400, "Envie somente proposta, método e chave da tentativa. Não informe dados financeiros reais.")
    proposal_id = text(data, "proposal_id", "proposta", 100, True)
    method = text(data, "method", "método", 20, True)
    if method not in METHODS:
        raise ApiError(400, "Método de pagamento inválido.")
    try:
        key = str(uuid.UUID(text(data, "idempotency_key", "chave da tentativa", 36, True)))
    except (ValueError, AttributeError):
        raise ApiError(400, "A chave da tentativa deve ser um UUID válido.") from None
    try:
        with transaction() as conn:
            existing = conn.execute("SELECT * FROM payments WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                if existing["proposal_id"] != proposal_id or existing["method"] != method:
                    raise ApiError(409, "Esta chave já foi utilizada para outros dados.")
                return 200, _serialize(conn, existing, True)
            p = _eligible(conn, proposal_id)
            if conn.execute("SELECT 1 FROM payments WHERE proposal_id=? AND status IN ('Pendente','Aprovado')", (proposal_id,)).fetchone():
                raise ApiError(409, "Esta proposta já possui pagamento pendente ou aprovado.")
            seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM payments").fetchone()[0]
            pid, now = str(uuid.uuid4()), utc_now()
            conn.execute("""INSERT INTO payments (id,seq,reference,proposal_id,method,amount_cents,status,idempotency_key,simulated,created_at,updated_at)
                VALUES (?,?,?,?,?,?,'Pendente',?,1,?,?)""", (pid, seq, f"SIM-{seq:06d}", proposal_id, method, p["total_cents"], key, now, now))
            conn.execute("INSERT INTO payment_events (id,payment_id,from_status,to_status,reason,created_at) VALUES (?,?,NULL,'Pendente','Tentativa simulada criada',?)", (str(uuid.uuid4()), pid, now))
            return 201, _serialize(conn, _payment(conn, pid), True)
    except sqlite3.IntegrityError:
        raise ApiError(409, "Já existe uma tentativa ativa ou uma chave utilizada para esta operação.") from None


def _status(pid, payload):
    data = validate_payload(payload)
    if set(data) - {"status", "reason"}:
        raise ApiError(400, "A requisição contém campos não permitidos.")
    target = text(data, "status", "status", 20, True)
    if target not in STATUSES:
        raise ApiError(400, "Status de pagamento inválido.")
    with transaction() as conn:
        current = _payment(conn, pid)
        if current["status"] == target:
            return 200, _serialize(conn, current, True)
        if current["status"] != "Pendente":
            raise ApiError(409, "Pagamento finalizado não pode mudar para outro resultado.")
        reason = text(data, "reason", "motivo", 500, required=target in {"Recusado", "Cancelado"}, min_length=3)
        if target == "Aprovado":
            p = _eligible(conn, current["proposal_id"])
            if current["amount_cents"] != p["total_cents"]:
                raise ApiError(409, "O valor não corresponde ao total da proposta.")
        now = utc_now()
        conn.execute("UPDATE payments SET status=?,reason=?,updated_at=?,result_at=? WHERE id=?", (target, reason, now, now, pid))
        conn.execute("INSERT INTO payment_events (id,payment_id,from_status,to_status,reason,created_at) VALUES (?,?,'Pendente',?,?,?)", (str(uuid.uuid4()), pid, target, reason, now))
        return 200, _serialize(conn, _payment(conn, pid), True)


def handle_request(method, path, payload=None):
    parsed = urlsplit(path)
    path = parsed.path
    if path == "/api/payments":
        if method == "POST":
            return _create(payload)
        if method == "GET":
            query = parse_qs(parsed.query)
            with closing(connect_db()) as conn:
                items = [_serialize(conn, r) for r in conn.execute("SELECT * FROM payments ORDER BY seq DESC").fetchall()]
            for field, allowed in (("status", STATUSES), ("method", METHODS)):
                value = query.get(field, [""])[0]
                if value:
                    if value not in allowed:
                        raise ApiError(400, "Filtro de pagamento inválido.")
                    items = [item for item in items if item[field] == value]
            search = query.get("q", [""])[0].casefold()
            if search:
                items = [i for i in items if search in " ".join(str(i[k]) for k in ("reference", "proposal_number", "customer_name", "cnpj", "vehicle_plate")).casefold()]
            return 200, {"items": items}
        raise ApiError(405, "Pagamentos não podem ser editados ou excluídos.")
    match = re.fullmatch(r"/api/payments/([^/]+)(/status)?", path)
    if not match:
        return None
    if match.group(2):
        if method != "POST":
            raise ApiError(405, "Use POST para registrar resultado simulado.")
        return _status(match.group(1), payload)
    if method != "GET":
        raise ApiError(405, "Pagamentos não podem ser editados ou excluídos.")
    with closing(connect_db()) as conn:
        return 200, _serialize(conn, _payment(conn, match.group(1)), True)
