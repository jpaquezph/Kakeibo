from __future__ import annotations

import sqlite3

CLAVE_TEMA = "tema"  # "claro" | "oscuro"


class ConfigService:
    """Configuracion clave/valor guardada en la base local. Se guarda en texto plano en el
    sqlite del usuario: no viaja a ningun servidor, es el mismo modelo de confianza que
    un archivo de config local de cualquier app de escritorio de un solo
    usuario."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def obtener(self, clave: str) -> str | None:
        row = self._conn.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
        return row["valor"] if row else None

    def guardar(self, clave: str, valor: str) -> None:
        self._conn.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, valor),
        )
        self._conn.commit()

    def eliminar(self, clave: str) -> None:
        self._conn.execute("DELETE FROM configuracion WHERE clave = ?", (clave,))
        self._conn.commit()
