"""Conexion y esquema de la base de datos SQLite local."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .domain.models import CATEGORIAS_BASE

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "kakeibo.db"


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea el esquema (si no existe) y siembra las categorias base."""
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text(encoding="utf-8"))
    _seed_categorias(conn)
    conn.commit()


def _seed_categorias(conn: sqlite3.Connection) -> None:
    existentes = {row["nombre"] for row in conn.execute("SELECT nombre FROM categorias")}
    for cat in CATEGORIAS_BASE:
        if cat["nombre"] not in existentes:
            conn.execute(
                "INSERT INTO categorias (nombre, color, icono) VALUES (?, ?, ?)",
                (cat["nombre"], cat["color"], cat["icono"]),
            )


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Agrupa operaciones en una transaccion: commit al salir, rollback ante error."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
