"""Conexion y esquema de la base de datos SQLite local."""
from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

from .domain.models import CATEGORIAS_BASE


def _migrations_dir() -> Path:
    """Ubicacion de las migraciones SQL (solo lectura).

    Cuando la app corre empaquetada (PyInstaller), los datos agregados con
    --add-data se extraen a `sys._MEIPASS`, no junto al ejecutable.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "migrations"
    return Path(__file__).resolve().parent.parent.parent / "migrations"


def _default_db_path() -> Path:
    """Ubicacion de la base de datos (debe persistir entre ejecuciones).

    Empaquetada como .exe de un solo archivo, `sys._MEIPASS` es una carpeta
    temporal que se borra al cerrar la app, asi que la base se guarda junto
    al ejecutable en su lugar.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "kakeibo.db"
    return Path(__file__).resolve().parent.parent.parent / "kakeibo.db"


MIGRATIONS_DIR = _migrations_dir()
DEFAULT_DB_PATH = _default_db_path()


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea el esquema (si no existe), aplica migraciones incrementales y siembra las categorias base."""
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text(encoding="utf-8"))
    _ensure_categoria_tipo_column(conn)
    _ensure_tarjeta_color_column(conn)
    _ensure_usuario_recuperacion_columnas(conn)
    _ensure_movimiento_gasto_fijo_column(conn)
    _seed_categorias(conn)
    conn.commit()


def _ensure_categoria_tipo_column(conn: sqlite3.Connection) -> None:
    """Agrega la columna 'tipo' a categorias si la base es de una version anterior."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(categorias)")}
    if "tipo" not in columnas:
        conn.execute("ALTER TABLE categorias ADD COLUMN tipo TEXT NOT NULL DEFAULT 'egreso'")


def _ensure_tarjeta_color_column(conn: sqlite3.Connection) -> None:
    """Agrega la columna 'color' a tarjetas si la base es de una version anterior."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(tarjetas)")}
    if "color" not in columnas:
        conn.execute("ALTER TABLE tarjetas ADD COLUMN color TEXT NOT NULL DEFAULT '#D6467E'")


def _ensure_usuario_recuperacion_columnas(conn: sqlite3.Connection) -> None:
    """Agrega las columnas de pregunta secreta (recuperacion de contrasena) si faltan."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(usuarios)")}
    if "pregunta_secreta" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN pregunta_secreta TEXT NOT NULL DEFAULT ''")
    if "respuesta_hash" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN respuesta_hash TEXT NOT NULL DEFAULT ''")
    if "respuesta_salt" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN respuesta_salt TEXT NOT NULL DEFAULT ''")


def _ensure_movimiento_gasto_fijo_column(conn: sqlite3.Connection) -> None:
    """Agrega la columna 'gasto_fijo_id' a movimientos si la base es de una version anterior.
    Vincula un movimiento con el gasto fijo (plantilla recurrente) que lo genero."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(movimientos)")}
    if "gasto_fijo_id" not in columnas:
        conn.execute("ALTER TABLE movimientos ADD COLUMN gasto_fijo_id INTEGER REFERENCES gastos_fijos(id)")


def _seed_categorias(conn: sqlite3.Connection) -> None:
    existentes = {row["nombre"] for row in conn.execute("SELECT nombre FROM categorias")}
    for cat in CATEGORIAS_BASE:
        if cat["nombre"] not in existentes:
            conn.execute(
                "INSERT INTO categorias (nombre, color, icono, tipo) VALUES (?, ?, ?, ?)",
                (cat["nombre"], cat["color"], cat["icono"], cat["tipo"]),
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
