"""Conexões e migrações SQLite sem substituir o banco existente."""

import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from common import utc_now


PROJECT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_DIR / "data" / "fasttruck.db"


def database_path() -> Path:
    return Path(os.environ.get("FASTRUCK_DB_PATH", str(DB_PATH))).resolve()


def connect_db() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def transaction():
    conn = connect_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _execute_script(conn: sqlite3.Connection, script: str) -> None:
    """Não usar executescript aqui: ele pode encerrar a transação corrente."""
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            conn.execute(pending)
            pending = ""
    if pending.strip():
        conn.execute(pending)


def initialize_database() -> None:
    migrations = sorted((PROJECT_DIR / "sql" / "migrations").glob("*.sql"))
    with closing(connect_db()) as conn:
        conn.executescript((PROJECT_DIR / "sql" / "schema.sql").read_text(encoding="utf-8-sig"))
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.commit()
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        pending = [path for path in migrations if path.name not in applied]
        # Uma cópia consistente antes da evolução do banco com dados já cadastrados.
        has_vehicles = conn.execute("SELECT EXISTS(SELECT 1 FROM vehicles)").fetchone()[0]
        if pending and has_vehicles:
            backup_dir = database_path().parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            with closing(sqlite3.connect(backup_dir / f"fasttruck-{stamp}.db")) as backup:
                conn.backup(backup)
    # Aplicar todas as novas versões juntas: falha desfaz a evolução inteira.
    with transaction() as conn:
        for path in pending:
            if conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (path.name,)).fetchone():
                continue
            _execute_script(conn, path.read_text(encoding="utf-8-sig"))
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (path.name, utc_now()))
