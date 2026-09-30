from __future__ import annotations

import sqlite3

from ..domain.models import CATEGORIAS_DEL_SISTEMA, Categoria, TipoMovimiento


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
            activa=bool(row["activa"]),
        )

    def listar(self, tipo: TipoMovimiento | None = None, incluir_quitadas: bool = False) -> list[Categoria]:
        """Las categorias que se ofrecen en los formularios. Con
        `incluir_quitadas`, tambien las que el usuario quito (para mostrar lo
        ya cargado con ellas)."""
        condiciones, params = [], []
        if tipo is not None:
            condiciones.append("tipo = ?")
            params.append(tipo.value)
        if not incluir_quitadas:
            condiciones.append("activa = 1")
        where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
        rows = self._conn.execute(f"SELECT * FROM categorias{where} ORDER BY nombre", params).fetchall()
        return [self._map(r) for r in rows]

    def obtener(self, categoria_id: int) -> Categoria | None:
        row = self._conn.execute("SELECT * FROM categorias WHERE id = ?", (categoria_id,)).fetchone()
        return self._map(row) if row else None

    def crear(self, nombre: str, color: str, icono: str, tipo: TipoMovimiento) -> Categoria:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre de la categoria no puede estar vacio")
        existente = self._conn.execute("SELECT * FROM categorias WHERE nombre = ?", (nombre,)).fetchone()
        if existente is not None and not existente["activa"] and existente["tipo"] == tipo.value:
            # Se habia quitado: vuelve, con sus movimientos de antes.
            self._conn.execute("UPDATE categorias SET activa = 1 WHERE id = ?", (existente["id"],))
            self._conn.commit()
            return self.obtener(existente["id"])
        try:
            cur = self._conn.execute(
                "INSERT INTO categorias (nombre, color, icono, tipo) VALUES (?, ?, ?, ?)",
                (nombre, color, icono, tipo.value),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe una categoria con ese nombre") from exc
        return Categoria(id=cur.lastrowid, nombre=nombre, color=color, icono=icono, tipo=tipo)

    def usos_detalle(self, categoria_id: int) -> dict[str, int]:
        """Cuantos movimientos, compras con tarjeta y gastos fijos activos la usan."""
        row = self._conn.execute(
            """SELECT (SELECT COUNT(*) FROM movimientos WHERE categoria_id = :id) AS movimientos,
                      (SELECT COUNT(*) FROM compras WHERE categoria_id = :id) AS compras,
                      (SELECT COUNT(*) FROM gastos_fijos WHERE categoria_id = :id AND activo = 1) AS gastos_fijos""",
            {"id": categoria_id},
        ).fetchone()
        return {k: row[k] for k in ("movimientos", "compras", "gastos_fijos")}

    def usos(self, categoria_id: int) -> int:
        return sum(self.usos_detalle(categoria_id).values())

    def puede_quitarse(self, categoria: Categoria) -> str | None:
        """None si se puede quitar; si no, el motivo."""
        if categoria.nombre in CATEGORIAS_DEL_SISTEMA:
            return "La usa la app (tarjetas, dólares o inversiones), no se puede quitar"
        propias = [c for c in self.listar(categoria.tipo) if c.nombre not in CATEGORIAS_DEL_SISTEMA]
        if len(propias) <= 1:
            return f"Tiene que quedar al menos una categoría de {categoria.tipo.value}"
        return None

    def quitar(self, categoria_id: int) -> None:
        """La categoria deja de ofrecerse. No se borra: lo ya cargado con ella
        (movimientos, compras, gastos fijos) la sigue mostrando."""
        categoria = self.obtener(categoria_id)
        if categoria is None or not categoria.activa:
            return
        motivo = self.puede_quitarse(categoria)
        if motivo:
            raise ValueError(motivo)
        self._conn.execute("UPDATE categorias SET activa = 0 WHERE id = ?", (categoria_id,))
        self._conn.commit()
