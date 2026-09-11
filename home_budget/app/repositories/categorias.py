from __future__ import annotations

import sqlite3

from ..domain.models import Categoria


class CategoriaRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map(self, row: sqlite3.Row) -> Categoria:
        return Categoria(id=row["id"], nombre=row["nombre"], color=row["color"], icono=row["icono"])

    def listar(self) -> list[Categoria]:
        rows = self._conn.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()
        return [self._map(r) for r in rows]

    def obtener(self, categoria_id: int) -> Categoria | None:
        row = self._conn.execute("SELECT * FROM categorias WHERE id = ?", (categoria_id,)).fetchone()
        return self._map(row) if row else None
