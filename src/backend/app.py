"""Servidor local da FasTruck: API REST e banco SQLite."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


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


def connect_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    with connect_db() as conn:
        schema_path = PROJECT_DIR / "sql" / "schema.sql"
        conn.executescript(schema_path.read_text(encoding="utf-8"))
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

    def send_json(self, status: int, body: object) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Tamanho de requisição inválido.") from None
        if length <= 0 or length > 64_000:
            raise ValueError("O conteúdo enviado está vazio ou excede o limite permitido.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("O conteúdo enviado não é um JSON válido.") from None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/vehicles":
            with connect_db() as conn:
                vehicles = [dict(row) for row in conn.execute(
                    "SELECT * FROM vehicles ORDER BY rowid DESC"
                )]
            self.send_json(200, vehicles)
            return
        if path in {"/", "/index.html"}:
            self.serve_file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self.serve_file(FRONTEND_DIR / "app.js", "text/javascript; charset=utf-8")
            return
        self.send_json(404, {"error": "Página não encontrada."})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/vehicles":
            self.send_json(404, {"error": "Rota não encontrada."})
            return
        try:
            vehicle = validate_vehicle(self.read_json())
            vehicle["id"] = str(uuid.uuid4())
            with connect_db() as conn:
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
        vehicle_id = self.vehicle_id_from_path()
        if not vehicle_id:
            self.send_json(404, {"error": "Rota não encontrada."})
            return
        try:
            vehicle = validate_vehicle(self.read_json())
            vehicle["id"] = vehicle_id
            with connect_db() as conn:
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
        vehicle_id = self.vehicle_id_from_path()
        if not vehicle_id:
            self.send_json(404, {"error": "Rota não encontrada."})
            return
        with connect_db() as conn:
            cursor = conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        if cursor.rowcount == 0:
            self.send_json(404, {"error": "Caminhão não encontrado."})
            return
        self.send_json(200, {"message": "Caminhão removido."})

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
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), FasTruckHandler)
    print(f"FasTruck disponível em http://{HOST}:{PORT}")
    print(f"Banco SQLite: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor FasTruck encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
