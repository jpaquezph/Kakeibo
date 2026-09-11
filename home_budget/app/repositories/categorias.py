from __future__ import annotations

import sqlite3

from ..domain.models import Categoria, TipoMovimiento


class CategoriaRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map(self, row: sqlite3.Row) -> Categoria:
        return Categoria(
            id=row["id"],
            nombre=row["nombre"],
            color=row["color"],
            icono=row["icono"],
            tipo=TipoMovimiento(row["tipo"]),
        )

    def listar(self, tipo: TipoMovimiento | None = None) -> list[Categoria]:
        if tipo is None:
            rows = self._conn.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM categorias WHERE tipo = ? ORDER BY nombre", (tipo.value,)
            ).fetchall()
        return [self._map(r) for r in rows]

    def obtener(self, categoria_id: int) -> Categoria | None:
        row = self._conn.execute("SELECT * FROM categorias WHERE id = ?", (categoria_id,)).fetchone()
        return self._map(row) if row else None

    def crear(self, nombre: str, color: str, icono: str, tipo: TipoMovimiento) -> Categoria:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre de la categoria no puede estar vacio")
        try:
            cur = self._conn.execute(
                "INSERT INTO categorias (nombre, color, icono, tipo) VALUES (?, ?, ?, ?)",
                (nombre, color, icono, tipo.value),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe una categoria con ese nombre") from exc
        return Categoria(id=cur.lastrowid, nombre=nombre, color=color, icono=icono, tipo=tipo)
