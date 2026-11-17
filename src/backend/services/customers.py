"""Cadastro PJ. Autoria inicial do subagente clientes; integração pela raiz."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import threading
import uuid
from contextlib import closing

from common import ApiError, text, utc_now, validate_payload
from db import connect_db, transaction, database_path
from integrations.brasilapi import lookup_cnpj


FIELDS = {
    "legal_name": ("razão social", 160, True, 2), "trade_name": ("nome fantasia", 160, False, 1),
    "contact_name": ("responsável", 120, True, 2), "phone": ("telefone", 30, True, 1),
    "email": ("e-mail", 254, True, 1), "postal_code": ("CEP", 12, True, 1),
    "street": ("logradouro", 160, True, 2), "number": ("número", 20, True, 1),
    "complement": ("complemento", 100, False, 1), "district": ("bairro", 100, True, 2),
    "city": ("cidade", 100, True, 2), "state": ("UF", 2, True, 2),
    "notes": ("observações", 1000, False, 1),
}
STATES = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
_SECRET_LOCK = threading.Lock()
_SECRET_CACHE = {}


def _lookup_secret():
    """Manter a assinatura válida após reinício, sem incluir chave no Git."""
    path = database_path().parent / ".cnpj-lookup-key"
    with _SECRET_LOCK:
        if path not in _SECRET_CACHE:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                key = path.read_bytes()
            else:
                key = secrets.token_bytes(32)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(key)
            if len(key) != 32:
                raise ApiError(503, "Consulta indisponível. Continue o cadastro manualmente.")
            _SECRET_CACHE[path] = key
        return _SECRET_CACHE[path]


def normalize_cnpj(value):
    if not isinstance(value, str):
        raise ApiError(400, "Informe o CNPJ como texto.")
    normalized = re.sub(r"[./\-\s]", "", value).upper()
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized):
        raise ApiError(400, "Informe um CNPJ com 12 caracteres e dois dígitos verificadores.")
    if normalized.isdigit() and len(set(normalized)) == 1:
        raise ApiError(400, "O CNPJ informado é inválido.")
    values = [ord(char) - 48 for char in normalized[:12]]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        remainder = sum(v * w for v, w in zip(values, weights)) % 11
        values.append(0 if remainder < 2 else 11 - remainder)
    if normalized[-2:] != "".join(map(str, values[-2:])):
        raise ApiError(400, "Os dígitos verificadores do CNPJ são inválidos.")
    return normalized


def _lookup_token(result):
    data = {key: result[key] for key in ("cnpj", "lookup_source", "lookup_at", "lookup_status")}
    data["expires"] = int(time.time()) + 86400
    encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    signature = hmac.new(_lookup_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def _lookup_metadata(token, cnpj):
    try:
        if not isinstance(token, str) or len(token) > 2048:
            raise ValueError
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(_lookup_secret(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(encoded))
        if data["cnpj"] != cnpj or data["expires"] < time.time():
            raise ValueError
        return {key: data[key] for key in ("lookup_source", "lookup_at", "lookup_status")}
    except (ValueError, TypeError, KeyError):
        raise ApiError(400, "Consulta expirada ou referente a outro CNPJ. Consulte novamente ou salve sem a consulta.") from None


def _get(conn, customer_id, detail=False):
    row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Cliente não encontrado.")
    result = dict(row)
    if detail:
        result["proposals"] = [dict(r) for r in conn.execute(
            "SELECT id,number,status,total_cents,valid_until FROM proposals WHERE customer_id=? ORDER BY seq DESC", (customer_id,))]
    return result


def _values(payload, current=None):
    payload = validate_payload(payload)
    if set(payload) - {"cnpj", "lookup_token", *FIELDS}:
        raise ApiError(400, "A requisição contém campos de cliente não permitidos.")
    merged = {**(current or {}), **payload}
    values = {"cnpj": normalize_cnpj(merged.get("cnpj"))}
    for key, (label, limit, required, minimum) in FIELDS.items():
        values[key] = text(merged, key, label, limit, required=required, min_length=minimum)
    if not re.fullmatch(r"[0-9+() .-]+", values["phone"]):
        raise ApiError(400, "Informe um telefone nacional com DDD.")
    values["phone"] = re.sub(r"\D", "", values["phone"])
    if len(values["phone"]) not in (10, 11):
        raise ApiError(400, "O telefone deve ter 10 ou 11 dígitos, incluindo DDD.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
        raise ApiError(400, "Informe um e-mail válido.")
    if not re.fullmatch(r"[0-9\s.-]+", values["postal_code"]):
        raise ApiError(400, "Informe um CEP com oito dígitos.")
    values["postal_code"] = re.sub(r"\D", "", values["postal_code"])
    if len(values["postal_code"]) != 8:
        raise ApiError(400, "O CEP deve ter oito dígitos.")
    values["state"] = values["state"].upper()
    if values["state"] not in STATES:
        raise ApiError(400, "Selecione uma UF brasileira válida.")
    changed = current is None or current["cnpj"] != values["cnpj"]
    metadata = {key: "" if changed else current[key] for key in ("lookup_source", "lookup_at", "lookup_status")}
    if payload.get("lookup_token"):
        metadata = _lookup_metadata(payload["lookup_token"], values["cnpj"])
    return {**values, **metadata}


def _create(payload):
    values = _values(payload)
    now = utc_now()
    values.update(id=str(uuid.uuid4()), active=1, created_at=now, updated_at=now)
    try:
        with transaction() as conn:
            columns = ",".join(values)
            conn.execute(f"INSERT INTO customers ({columns}) VALUES ({','.join('?' for _ in values)})", list(values.values()))
            return 201, _get(conn, values["id"], True)
    except sqlite3.IntegrityError:
        raise ApiError(409, "Já existe uma empresa com esse CNPJ.") from None


def _update(customer_id, payload):
    payload = validate_payload(payload)
    if not payload:
        raise ApiError(400, "Informe os dados a atualizar.")
    try:
        with transaction() as conn:
            current = _get(conn, customer_id)
            if set(payload) == {"active"}:
                if not isinstance(payload["active"], bool):
                    raise ApiError(400, "Informe o status ativo como verdadeiro ou falso.")
                values = {"active": int(payload["active"])}
            else:
                values = _values(payload, current)
                if values["cnpj"] != current["cnpj"] and (conn.execute("SELECT 1 FROM proposals WHERE customer_id=? LIMIT 1", (customer_id,)).fetchone()
                        or conn.execute("SELECT 1 FROM shop_orders WHERE customer_id=? LIMIT 1", (customer_id,)).fetchone()
                        or conn.execute("SELECT 1 FROM accounts WHERE customer_id=? LIMIT 1", (customer_id,)).fetchone()):
                    raise ApiError(409, "Não é possível alterar CNPJ de uma empresa com conta, proposta ou pedido vinculado.")
            values["updated_at"] = utc_now()
            conn.execute(f"UPDATE customers SET {','.join(k+'=?' for k in values)} WHERE id=?", [*values.values(), customer_id])
            return 200, _get(conn, customer_id, True)
    except sqlite3.IntegrityError:
        raise ApiError(409, "Já existe uma empresa com esse CNPJ.") from None


def handle_request(method, path, payload=None):
    if path.startswith("/api/cnpj/"):
        if method != "GET":
            raise ApiError(405, "Use GET para consultar CNPJ.")
        cnpj = normalize_cnpj(path[len("/api/cnpj/"):])
        result = lookup_cnpj(cnpj)
        result.update(lookup_source="BrasilAPI", lookup_at=utc_now())
        result["lookup_token"] = _lookup_token(result)
        return 200, result
    if path == "/api/customers":
        if method == "GET":
            with closing(connect_db()) as conn:
                return 200, [dict(row) for row in conn.execute("SELECT * FROM customers ORDER BY active DESC,legal_name COLLATE NOCASE")]
        if method == "POST":
            return _create(payload)
        raise ApiError(405, "Método não permitido para clientes.")
    match = re.fullmatch(r"/api/customers/([^/]+)", path)
    if not match:
        return None
    customer_id = match.group(1)
    if method == "GET":
        with closing(connect_db()) as conn:
            return 200, _get(conn, customer_id, True)
    if method == "PUT":
        return _update(customer_id, payload)
    if method == "DELETE":
        with transaction() as conn:
            _get(conn, customer_id)
            if conn.execute("SELECT 1 FROM proposals WHERE customer_id=? LIMIT 1", (customer_id,)).fetchone():
                raise ApiError(409, "Empresa com propostas vinculadas não pode ser excluída. Use Inativar.")
            if conn.execute("SELECT 1 FROM accounts WHERE customer_id=? LIMIT 1", (customer_id,)).fetchone() or conn.execute("SELECT 1 FROM shop_orders WHERE customer_id=? LIMIT 1", (customer_id,)).fetchone():
                raise ApiError(409, "Empresa com conta ou pedido vinculado não pode ser excluída. Use Inativar.")
            conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))
            return 200, {"message": "Empresa excluída."}
    raise ApiError(405, "Método não permitido para este cliente.")
