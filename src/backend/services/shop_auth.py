"""Autenticação de contas da área e-commerce."""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone

from common import ApiError, utc_now, validate_payload
from db import connect_db, database_path, transaction
from services import customers


SESSION_TTL = timedelta(days=7)
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _account_email(value):
    if not isinstance(value, str):
        raise ApiError(400, "Informe um e-mail válido para a conta.")
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ApiError(400, "Informe um e-mail válido para a conta.")
    return email


def _password(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        raise ApiError(400, "A senha deve ter entre 8 e 128 caracteres.")
    return value


def _hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N,
                             r=_SCRYPT_R, p=_SCRYPT_P, dklen=64)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def _verify_password(password, encoded):
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                 n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(expected_hex)))
        return hmac.compare_digest(derived.hex(), expected_hex)
    except (ValueError, TypeError, MemoryError):
        return False


def _public_user(conn, account_id):
    row = conn.execute(
        "SELECT a.id, a.email, a.role, a.customer_id FROM accounts a WHERE a.id=?",
        (account_id,),
    ).fetchone()
    return dict(row) if row else None


def register(payload):
    payload = validate_payload(payload)
    if "account_email" not in payload or "password" not in payload:
        raise ApiError(400, "Informe account_email e password para criar a conta.")
    account_email = _account_email(payload["account_email"])
    password = _password(payload["password"])
    customer_payload = {key: value for key, value in payload.items()
                        if key not in {"account_email", "password"}}
    values = customers._values(customer_payload)
    now = utc_now()
    customer_id, account_id = str(uuid.uuid4()), str(uuid.uuid4())
    customer_values = {
        **values, "id": customer_id, "active": 1,
        "created_at": now, "updated_at": now,
    }
    try:
        with transaction() as conn:
            columns = ",".join(customer_values)
            conn.execute(
                f"INSERT INTO customers ({columns}) VALUES ({','.join('?' for _ in customer_values)})",
                list(customer_values.values()),
            )
            conn.execute(
                "INSERT INTO accounts (id, customer_id, email, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?, 'customer', ?)",
                (account_id, customer_id, account_email, _hash_password(password), now),
            )
            return _public_user(conn, account_id)
    except sqlite3.IntegrityError:
        raise ApiError(409, "Já existe uma empresa ou conta com esses dados.") from None


def login(payload):
    payload = validate_payload(payload)
    try:
        email = _account_email(payload.get("email"))
    except ApiError:
        raise ApiError(401, "E-mail ou senha inválidos.") from None
    password = payload.get("password")
    if not isinstance(password, str) or len(password) > 128:
        raise ApiError(401, "E-mail ou senha inválidos.")
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + SESSION_TTL).isoformat(timespec="microseconds")
    try:
        with transaction() as conn:
            row = conn.execute(
                "SELECT a.id, a.password_hash, a.role, c.active AS customer_active "
                "FROM accounts a LEFT JOIN customers c ON c.id=a.customer_id WHERE a.email=?",
                (email,),
            ).fetchone()
            if (row is None or not _verify_password(password, row["password_hash"])
                    or (row["role"] == "customer" and not row["customer_active"])):
                raise ApiError(401, "E-mail ou senha inválidos.")
            token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
            conn.execute(
                "INSERT INTO shop_sessions (token_hash, account_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash, row["id"], csrf_token, expires_at),
            )
            return _public_user(conn, row["id"]), raw_token, csrf_token
    except sqlite3.IntegrityError:
        raise ApiError(401, "E-mail ou senha inválidos.") from None


def logout(raw_token):
    if not isinstance(raw_token, str) or not raw_token:
        return
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with transaction() as conn:
        conn.execute("DELETE FROM shop_sessions WHERE token_hash=?", (token_hash,))


def session(raw_token):
    if not isinstance(raw_token, str) or not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with closing(connect_db()) as conn:
        row = conn.execute(
            "SELECT a.id, a.email, a.role, a.customer_id, s.csrf_token, s.expires_at, c.active AS customer_active "
            "FROM shop_sessions s JOIN accounts a ON a.id=s.account_id "
            "LEFT JOIN customers c ON c.id=a.customer_id WHERE s.token_hash=?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        if expires_at <= now:
            return None
        if row["role"] == "customer" and not row["customer_active"]:
            return None
        return {key: row[key] for key in ("id", "email", "role", "customer_id", "csrf_token")}


def _write_admin_access(path, email, password):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
    except AttributeError:
        pass
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"email={email}\npassword={password}\n")


def ensure_admin():
    """Garante uma conta administrativa e seu acesso local recuperável."""
    credential_path = database_path().parent / ".admin-access"
    with transaction() as conn:
        existing = conn.execute(
            "SELECT id, email FROM accounts WHERE role='admin' LIMIT 1"
        ).fetchone()
        if existing and credential_path.is_file():
            return None
        email = existing["email"] if existing else "admin@fastruck.local"
        password = secrets.token_urlsafe(12)
        if existing:
            conn.execute(
                "UPDATE accounts SET password_hash=? WHERE id=?",
                (_hash_password(password), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO accounts (id, customer_id, email, password_hash, role, created_at) "
                "VALUES (?, NULL, ?, ?, 'admin', ?)",
                (str(uuid.uuid4()), email, _hash_password(password), utc_now()),
            )
    _write_admin_access(credential_path, email, password)
    return {"email": email}


def admin_access():
    """Lê o acesso administrativo gerado para esta instalação local."""
    credential_path = database_path().parent / ".admin-access"
    try:
        values = dict(
            line.split("=", 1)
            for line in credential_path.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        email, password = values["email"].strip(), values["password"].strip()
    except (OSError, KeyError, ValueError):
        raise ApiError(503, "O acesso administrativo ainda não foi gerado. Reinicie o servidor.") from None
    if not email or not password:
        raise ApiError(503, "O acesso administrativo está incompleto. Reinicie o servidor.")
    return {"email": email, "password": password}
