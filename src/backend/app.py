"""Servidor local da FasTruck: API REST e banco SQLite."""

from __future__ import annotations

import json
import math
import mimetypes
import hmac
import re
import sqlite3
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import unquote, urlparse

from common import ApiError
from db import connect_db, transaction, initialize_database as migrate_database, database_path


PROJECT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_DIR / "src" / "frontend"
DB_DIR = PROJECT_DIR / "data"
DB_PATH = DB_DIR / "fasttruck.db"
HOST = "127.0.0.1"
PORT = 8000
VALID_STATUSES = {"Disponível", "Reservado", "Vendido"}
PLATE_PATTERN = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")

DEMO_VEHICLES = [
    {
        "plate": "RTA-4C27", "brand": "Volvo", "model": "FH 540",
        "year": "2022 / 2023", "color": "Cinza grafite", "body": "Trator",
        "axles": "6x2", "fuel": "Diesel", "km": 186000, "price": 689900,
        "customized": "sim", "notes": "Pintura especial grafite, rodas de alumínio e interior premium.",
        "status": "Disponível",
    },
    {
        "plate": "BZX-8H41", "brand": "Scania", "model": "R 450",
        "year": "2021 / 2022", "color": "Branco", "body": "Baú",
        "axles": "6x2", "fuel": "Diesel", "km": 224500, "price": 572000,
        "customized": "sim", "notes": "Baú refrigerado e defletor personalizado.",
        "status": "Reservado",
    },
    {
        "plate": "GKM-2D96", "brand": "Mercedes-Benz", "model": "Actros 2651",
        "year": "2023 / 2023", "color": "Azul", "body": "Trator",
        "axles": "6x4", "fuel": "Diesel", "km": 98000, "price": 745000,
        "customized": "nao", "notes": "", "status": "Disponível",
    },
]

DEMO_VEHICLES_EXTRA = [
    {"plate": "HJK-5A14", "brand": "Iveco", "model": "S-Way 480", "year": "2022 / 2023", "color": "Branco", "body": "Trator", "axles": "6x2", "fuel": "Diesel", "km": 142000, "price": 625000, "customized": "sim", "notes": "Defletor de ar e acabamento interno personalizado.", "status": "Disponível"},
    {"plate": "PQR-8B36", "brand": "DAF", "model": "XF 530", "year": "2022 / 2023", "color": "Preto", "body": "Trator", "axles": "6x2", "fuel": "Diesel", "km": 168000, "price": 675000, "customized": "sim", "notes": "Pintura preta perolizada e rodas de alumínio.", "status": "Disponível"},
    {"plate": "VWX-2C59", "brand": "Volkswagen", "model": "Meteor 29.520", "year": "2023 / 2024", "color": "Prata", "body": "Trator", "axles": "6x4", "fuel": "Diesel", "km": 83000, "price": 710000, "customized": "sim", "notes": "Faixas exclusivas e pacote de iluminação auxiliar.", "status": "Disponível"},
    {"plate": "MNO-7D82", "brand": "Volvo", "model": "VM 330", "year": "2020 / 2021", "color": "Azul", "body": "Baú", "axles": "6x2", "fuel": "Diesel", "km": 285000, "price": 438900, "customized": "nao", "notes": "Baú de 10 metros.", "status": "Reservado"},
    {"plate": "JKL-3E47", "brand": "Scania", "model": "G 420", "year": "2019 / 2020", "color": "Vermelho", "body": "Graneleiro", "axles": "6x2", "fuel": "Diesel", "km": 340000, "price": 389000, "customized": "sim", "notes": "Pintura renovada e protetor de cabine.", "status": "Vendido"},
    {"plate": "CDE-9F20", "brand": "Mercedes-Benz", "model": "Atego 2429", "year": "2021 / 2022", "color": "Branco", "body": "Basculante", "axles": "6x2", "fuel": "Diesel", "km": 190000, "price": 462000, "customized": "nao", "notes": "Caçamba basculante revisada.", "status": "Disponível"},
    {"plate": "YZA-4G63", "brand": "MAN", "model": "TGX 29.480", "year": "2020 / 2021", "color": "Branco", "body": "Trator", "axles": "6x4", "fuel": "Diesel", "km": 320000, "price": 518000, "customized": "sim", "notes": "Cabine com acabamento premium.", "status": "Reservado"},
    {"plate": "FGH-6H18", "brand": "Ford", "model": "Cargo 2429", "year": "2018 / 2019", "color": "Prata", "body": "Baú", "axles": "6x2", "fuel": "Diesel", "km": 410000, "price": 285000, "customized": "nao", "notes": "Baú lonado.", "status": "Vendido"},
    {"plate": "LMN-1J75", "brand": "Iveco", "model": "Tector 240E28", "year": "2022 / 2023", "color": "Branco", "body": "Tanque", "axles": "6x2", "fuel": "Diesel", "km": 110000, "price": 410000, "customized": "sim", "notes": "Tanque inox e escada lateral personalizada.", "status": "Disponível"},
    {"plate": "RST-8K29", "brand": "Scania", "model": "R 540", "year": "2024 / 2024", "color": "Azul-marinho", "body": "Trator", "axles": "6x4", "fuel": "Diesel", "km": 45000, "price": 920000, "customized": "sim", "notes": "Pintura azul-marinho exclusiva, rodas e saias laterais.", "status": "Disponível"},
]


def initialize_database() -> None:
    migrate_database()
    with transaction() as conn:
        seeded = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'demo_seeded'"
        ).fetchone()
        if not seeded:
            conn.executemany(
                """INSERT INTO vehicles
                (id, plate, brand, model, year, color, body, axles, fuel, km,
                 price, customized, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(
                    f"demo-{i}", v["plate"], v["brand"], v["model"], v["year"],
                    v["color"], v["body"], v["axles"], v["fuel"], v["km"],
                    v["price"], v["customized"], v["notes"], v["status"],
                ) for i, v in enumerate(DEMO_VEHICLES, start=1)],
            )
            conn.execute(
                "INSERT INTO app_meta (key, value) VALUES ('demo_seeded', '1')"
            )
        extra_seeded = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'demo_seeded_extra_10'"
        ).fetchone()
        if not extra_seeded:
            conn.executemany(
                """INSERT OR IGNORE INTO vehicles
                (id, plate, brand, model, year, color, body, axles, fuel, km,
                 price, customized, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(
                    f"demo-extra-{i}", v["plate"], v["brand"], v["model"],
                    v["year"], v["color"], v["body"], v["axles"], v["fuel"],
                    v["km"], v["price"], v["customized"], v["notes"], v["status"],
                ) for i, v in enumerate(DEMO_VEHICLES_EXTRA, start=1)],
            )
            conn.execute(
                "INSERT INTO app_meta (key, value) VALUES ('demo_seeded_extra_10', '1')"
            )


def normalize_plate(value: object) -> str:
    plate = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    if not PLATE_PATTERN.fullmatch(plate):
        raise ValueError("Informe uma placa válida no padrão antigo ou Mercosul.")
    return f"{plate[:3]}-{plate[3:]}"


def validate_vehicle(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Os dados enviados são inválidos.")

    def required(name: str, label: str) -> str:
        value = str(payload.get(name, "")).strip()
        if not value:
            raise ValueError(f"O campo {label} é obrigatório.")
        return value

    status = required("status", "status")
    if status not in VALID_STATUSES:
        raise ValueError("Selecione um status válido.")

    try:
        price = float(payload.get("price", ""))
        km = int(payload.get("km") or 0)
    except (TypeError, ValueError):
        raise ValueError("Valor e quilometragem devem ser números válidos.") from None
    if not math.isfinite(price) or price < 0 or km < 0:
        raise ValueError("Valor e quilometragem devem ser iguais ou maiores que zero.")

    customized = str(payload.get("customized", "sim")).lower()
    if customized not in {"sim", "nao"}:
        raise ValueError("Informe se o caminhão é personalizado.")

    text_fields = {
        "brand": required("brand", "marca"),
        "model": required("model", "modelo"),
        "year": required("year", "ano"),
        "color": required("color", "cor"),
    }
    if len(text_fields["year"]) > 20:
        raise ValueError("Confira o ano de fabricação/modelo informado.")

    return {
        "plate": normalize_plate(payload.get("plate")),
        **text_fields,
        "body": str(payload.get("body", "")).strip(),
        "axles": str(payload.get("axles", "")).strip(),
        "fuel": str(payload.get("fuel", "")).strip(),
        "km": km,
        "price": price,
        "customized": customized,
        "notes": str(payload.get("notes", "")).strip(),
        "status": status,
    }


class FasTruckHandler(BaseHTTPRequestHandler):
    server_version = "FasTruck/1.0"

    def send_json(self, status: int, body: object, headers=None) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def read_json(self, exact_numbers=False) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Tamanho de requisição inválido.") from None
        if length <= 0 or length > 64_000:
            raise ValueError("O conteúdo enviado está vazio ou excede o limite permitido.")
        try:
            options = {"parse_float": str} if exact_numbers else {}
            return json.loads(self.rfile.read(length).decode("utf-8"), **options)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("O conteúdo enviado não é um JSON válido.") from None

    def do_GET(self) -> None:
        if self.route_access("GET") or self.route_new_modules("GET"):
            return
        path = urlparse(self.path).path
        if path == "/api/vehicles":
            with closing(connect_db()) as conn:
                vehicles = [dict(row) for row in conn.execute(
                    "SELECT * FROM vehicles ORDER BY rowid DESC"
                )]
            self.send_json(200, vehicles)
            return
        if path in {"/", "/index.html", "/loja", "/loja/", "/loja.html"}:
            self.serve_file(FRONTEND_DIR / "loja.html", "text/html; charset=utf-8")
            return
        if path in {"/admin", "/admin/", "/admin/index.html"}:
            self.serve_file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self.serve_file(FRONTEND_DIR / "app.js", "text/javascript; charset=utf-8")
            return
        candidate = (FRONTEND_DIR / unquote(path).lstrip("/")).resolve()
        if candidate.is_relative_to(FRONTEND_DIR.resolve()) and candidate.suffix in {".html", ".css", ".js", ".svg", ".png"} and candidate.is_file():
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.serve_file(candidate, content_type + ("; charset=utf-8" if candidate.suffix in {".html", ".css", ".js"} else ""))
            return
        self.send_json(404, {"error": "Página não encontrada."})

    def do_POST(self) -> None:
        if self.route_access("POST") or self.route_new_modules("POST"):
            return
        if urlparse(self.path).path != "/api/vehicles":
            self.send_json(404, {"error": "Rota não encontrada."})
            return
        try:
            vehicle = validate_vehicle(self.read_json())
            vehicle["id"] = str(uuid.uuid4())
            with transaction() as conn:
                conn.execute(
                    """INSERT INTO vehicles
                    (id, plate, brand, model, year, color, body, axles, fuel, km,
                     price, customized, notes, status)
                    VALUES (:id, :plate, :brand, :model, :year, :color, :body,
                            :axles, :fuel, :km, :price, :customized, :notes, :status)""",
                    vehicle,
                )
            self.send_json(201, vehicle)
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except sqlite3.IntegrityError as exc:
            message = "Já existe um caminhão cadastrado com essa placa." if "plate" in str(exc).lower() else "Os dados não puderam ser gravados."
            self.send_json(409, {"error": message})

    def do_PUT(self) -> None:
        if self.route_access("PUT") or self.route_new_modules("PUT"):
            return
        vehicle_id = self.vehicle_id_from_path()
        if not vehicle_id:
            self.send_json(404, {"error": "Rota não encontrada."})
            return
        try:
            vehicle = validate_vehicle(self.read_json())
            vehicle["id"] = vehicle_id
            with transaction() as conn:
                cursor = conn.execute(
                    """UPDATE vehicles SET
                    plate=:plate, brand=:brand, model=:model, year=:year,
                    color=:color, body=:body, axles=:axles, fuel=:fuel,
                    km=:km, price=:price, customized=:customized, notes=:notes,
                    status=:status WHERE id=:id""",
                    vehicle,
                )
                if cursor.rowcount == 0:
                    self.send_json(404, {"error": "Caminhão não encontrado."})
                    return
            self.send_json(200, vehicle)
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except sqlite3.IntegrityError as exc:
            message = "Já existe um caminhão cadastrado com essa placa." if "plate" in str(exc).lower() else "Os dados não puderam ser gravados."
            self.send_json(409, {"error": message})

    def do_DELETE(self) -> None:
        if self.route_access("DELETE") or self.route_new_modules("DELETE"):
            return
        vehicle_id = self.vehicle_id_from_path()
        if not vehicle_id:
            self.send_json(404, {"error": "Rota não encontrada."})
            return
        try:
            with transaction() as conn:
                if conn.execute("SELECT 1 FROM proposals WHERE vehicle_id=? LIMIT 1", (vehicle_id,)).fetchone():
                    self.send_json(409, {"error": "Caminhão com propostas vinculadas não pode ser excluído."})
                    return
                cursor = conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        except sqlite3.IntegrityError:
            self.send_json(409, {"error": "Há registros vinculados a este caminhão."})
            return
        if cursor.rowcount == 0:
            self.send_json(404, {"error": "Caminhão não encontrado."})
            return
        self.send_json(200, {"message": "Caminhão removido."})

    def cookie_token(self):
        try:
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie.get("fastruck_session")
            return token.value if token and len(token.value) <= 256 else ""
        except CookieError:
            return ""

    def current_user(self):
        from services.shop_auth import session
        return session(self.cookie_token())

    def require_user(self, admin=False):
        user = self.current_user()
        if not user:
            raise ApiError(401, "Entre na sua conta para continuar.")
        if admin and user["role"] != "admin":
            raise ApiError(403, "Esta área é exclusiva da administração.")
        return user

    def check_origin(self):
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != self.headers.get("Host", "").lower():
                raise ApiError(403, "Origem da requisição não permitida.")

    def check_csrf(self, user):
        self.check_origin()
        supplied = self.headers.get("X-CSRF-Token", "")
        if not supplied or not hmac.compare_digest(supplied, user["csrf_token"]):
            raise ApiError(403, "Sessão desatualizada. Atualize a página e tente novamente.")

    def route_access(self, method):
        """Loja pública; dados administrativos exigem conta de administrador."""
        path = unquote(urlparse(self.path).path).rstrip("/")
        if path == "/api/shop" or path.startswith("/api/shop/"):
            self.route_shop(method, path)
            return True
        try:
            if path == "/api" or path.startswith("/api/"):
                user = self.require_user(admin=True)
                if method not in {"GET", "HEAD"}:
                    self.check_csrf(user)
            elif path in {"/admin", "/admin/index.html", "/clientes.html", "/propostas.html", "/pagamentos.html", "/pedidos.html"}:
                user = self.current_user()
                if not user or user["role"] != "admin":
                    self.send_response(302)
                    self.send_header("Location", "/loja.html#entrar")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return True
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})
            return True
        return False

    def route_shop(self, method, path):
        from services import shop_auth, shop_orders
        try:
            if method not in {"GET", "POST"}:
                raise ApiError(405, "Método não permitido.")
            if method == "GET" and path == "/api/shop/session":
                current = self.current_user()
                user = {k: current[k] for k in ("id", "email", "role", "customer_id")} if current else None
                self.send_json(200, {"user": user, "csrf_token": current["csrf_token"] if current else None})
                return
            payload = self.read_json(exact_numbers=True) if method == "POST" else None
            if method == "POST":
                self.check_origin()
            if path in {"/api/shop/login", "/api/shop/register"}:
                if method != "POST":
                    raise ApiError(405, "Use POST para acessar sua conta.")
                if path.endswith("/register"):
                    shop_auth.register(payload)
                    user, token, csrf = shop_auth.login({"email": payload["account_email"], "password": payload["password"]})
                else:
                    user, token, csrf = shop_auth.login(payload)
                shop_auth.logout(self.cookie_token())
                self.send_json(201 if path.endswith("/register") else 200, {"user": user, "csrf_token": csrf},
                               {"Set-Cookie": f"fastruck_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800"})
                return
            user = None
            public = method == "GET" and path in {"/api/shop/catalog", "/api/shop/customizations"}
            if not public:
                user = self.require_user()
                if method == "POST":
                    self.check_csrf(user)
            if path == "/api/shop/logout" and method == "POST":
                shop_auth.logout(self.cookie_token())
                self.send_json(200, {"ok": True}, {"Set-Cookie": "fastruck_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})
                return
            result = shop_orders.handle_request(method, path, payload, user)
            if result is None:
                raise ApiError(404, "Página ou pedido não encontrado.")
            self.send_json(*result)
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except sqlite3.IntegrityError:
            self.send_json(409, {"error": "Já existe um registro ou uma operação com esses dados."})
        except sqlite3.OperationalError:
            self.send_json(503, {"error": "Banco temporariamente indisponível. Tente novamente."})
        except Exception:
            self.send_json(500, {"error": "Não foi possível concluir a operação. Tente novamente."})

    def route_new_modules(self, method):
        url = urlparse(self.path)
        path = unquote(url.path).rstrip("/")
        if not any(path == p or path.startswith(p + "/") for p in ("/api/customers", "/api/cnpj", "/api/proposals", "/api/payments")):
            return False
        try:
            from services import customers, proposals, payments
            payload = self.read_json(exact_numbers=True) if method in {"POST", "PUT"} else None
            module_path = path + ("?" + url.query if url.query and path == "/api/payments" else "")
            for module in (customers, proposals, payments):
                result = module.handle_request(method, module_path, payload)
                if result is not None:
                    self.send_json(*result)
                    return True
            self.send_json(404, {"error": "Rota não encontrada."})
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except sqlite3.IntegrityError:
            self.send_json(409, {"error": "Operação bloqueada por vínculo ou registro duplicado."})
        except sqlite3.OperationalError:
            self.send_json(503, {"error": "Banco temporariamente indisponível. Tente novamente."})
        except Exception:
            self.send_json(500, {"error": "Não foi possível concluir a operação. Tente novamente."})
        return True

    def do_PATCH(self):
        if not self.route_access("PATCH") and not self.route_new_modules("PATCH"):
            self.send_json(405, {"error": "Método não permitido."})

    def vehicle_id_from_path(self) -> str | None:
        match = re.fullmatch(r"/api/vehicles/([^/]+)", urlparse(self.path).path)
        return unquote(match.group(1)) if match else None

    def serve_file(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
        except OSError:
            self.send_json(404, {"error": "Arquivo não encontrado."})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    initialize_database()
    from services.shop_auth import ensure_admin
    ensure_admin()
    server = ThreadingHTTPServer((HOST, PORT), FasTruckHandler)
    print(f"FasTruck disponível em http://{HOST}:{PORT}")
    print(f"Banco SQLite: {database_path()}")
    print("Administração: /admin — acesso inicial em data/.admin-access")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor FasTruck encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
