from __future__ import annotations

import sqlite3

from ..domain.models import GastoFijo
from ..domain.money import Money


class GastoFijoRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map(self, row: sqlite3.Row) -> GastoFijo:
        return GastoFijo(
            id=row["id"],
            concepto=row["concepto"],
            detalle=row["detalle"],
            monto=Money(row["monto_centavos"], row["moneda"]),
            categoria_id=row["categoria_id"],
            dia_mes=row["dia_mes"],
            activo=bool(row["activo"]),
        )

    def crear(self, g: GastoFijo) -> int:
        cur = self._conn.execute(
            """INSERT INTO gastos_fijos (concepto, detalle, monto_centavos, moneda, categoria_id, dia_mes, activo)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (g.concepto, g.detalle, g.monto.cents, g.monto.moneda.value, g.categoria_id, g.dia_mes, int(g.activo)),
        )
        self._conn.commit()
        return cur.lastrowid

    def eliminar(self, gasto_fijo_id: int) -> None:
        self._conn.execute("DELETE FROM gastos_fijos WHERE id = ?", (gasto_fijo_id,))
        self._conn.commit()

    def listar(self, solo_activos: bool = True) -> list[GastoFijo]:
        sql = "SELECT * FROM gastos_fijos"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY dia_mes"
        return [self._map(r) for r in self._conn.execute(sql).fetchall()]
