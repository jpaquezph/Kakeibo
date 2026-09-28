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
            tarjeta_id=row["tarjeta_id"],
        )

    def crear(self, g: GastoFijo) -> int:
        cur = self._conn.execute(
            """INSERT INTO gastos_fijos (concepto, detalle, monto_centavos, moneda, categoria_id, dia_mes, activo, tarjeta_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (g.concepto, g.detalle, g.monto.cents, g.monto.moneda.value, g.categoria_id, g.dia_mes, int(g.activo), g.tarjeta_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def actualizar(self, g: GastoFijo) -> None:
        self._conn.execute(
            """UPDATE gastos_fijos SET concepto = ?, detalle = ?, monto_centavos = ?, moneda = ?,
                 categoria_id = ?, dia_mes = ?, activo = ?, tarjeta_id = ? WHERE id = ?""",
            (g.concepto, g.detalle, g.monto.cents, g.monto.moneda.value, g.categoria_id, g.dia_mes, int(g.activo), g.tarjeta_id, g.id),
        )
        self._conn.commit()

    def eliminar(self, gasto_fijo_id: int) -> None:
        """Borrado logico: los movimientos ya generados referencian este id
        por clave foranea, asi que un DELETE fisico rompe con
        'FOREIGN KEY constraint failed' en cuanto el gasto tuvo algun pago."""
        self._conn.execute("UPDATE gastos_fijos SET activo = 0 WHERE id = ?", (gasto_fijo_id,))
        self._conn.commit()

    def listar(self, solo_activos: bool = True) -> list[GastoFijo]:
        sql = "SELECT * FROM gastos_fijos"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY dia_mes"
        return [self._map(r) for r in self._conn.execute(sql).fetchall()]
