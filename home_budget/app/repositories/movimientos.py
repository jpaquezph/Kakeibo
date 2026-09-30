from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from ..domain.models import EstadoMovimiento, Movimiento, TipoMovimiento
from ..domain.money import Money, Moneda


@dataclass
class FiltroMovimientos:
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    tipo: TipoMovimiento | None = None
    categoria_id: int | None = None
    tarjeta_id: int | None = None
    moneda: Moneda | None = None
    estado: EstadoMovimiento | None = None
    concepto: str | None = None


class MovimientoRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map(self, row: sqlite3.Row) -> Movimiento:
        return Movimiento(
            id=row["id"],
            tipo=TipoMovimiento(row["tipo"]),
            fecha=date.fromisoformat(row["fecha"]),
            concepto=row["concepto"],
            detalle=row["detalle"],
            monto=Money(row["monto_centavos"], row["moneda"]),
            categoria_id=row["categoria_id"],
            estado=EstadoMovimiento(row["estado"]),
            fijo=bool(row["fijo"]),
            tarjeta_id=row["tarjeta_id"],
            gasto_fijo_id=row["gasto_fijo_id"] if "gasto_fijo_id" in row.keys() else None,
            categoria_nombre=row["categoria_nombre"] if "categoria_nombre" in row.keys() else None,
            categoria_color=row["categoria_color"] if "categoria_color" in row.keys() else None,
            categoria_icono=row["categoria_icono"] if "categoria_icono" in row.keys() else None,
            metodo_pago=row["metodo_pago"],
        )

    _SELECT_CON_CATEGORIA = """
        SELECT m.*, c.nombre AS categoria_nombre, c.color AS categoria_color, c.icono AS categoria_icono
        FROM movimientos m
        JOIN categorias c ON c.id = m.categoria_id
    """

    def crear(self, m: Movimiento) -> int:
        cur = self._conn.execute(
            """INSERT INTO movimientos
               (tipo, fecha, concepto, detalle, monto_centavos, moneda, categoria_id, estado, fijo, tarjeta_id, gasto_fijo_id,
                metodo_pago)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m.tipo.value,
                m.fecha.isoformat(),
                m.concepto,
                m.detalle,
                m.monto.cents,
                m.monto.moneda.value,
                m.categoria_id,
                m.estado.value,
                int(m.fijo),
                m.tarjeta_id,
                m.gasto_fijo_id,
                m.metodo_pago,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def existe_para_gasto_fijo(self, gasto_fijo_id: int, anio: int, mes: int) -> bool:
        row = self._conn.execute(
            """SELECT 1 FROM movimientos
               WHERE gasto_fijo_id = ? AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?
               LIMIT 1""",
            (gasto_fijo_id, f"{anio:04d}", f"{mes:02d}"),
        ).fetchone()
        return row is not None

    def actualizar(self, m: Movimiento) -> None:
        if m.id is None:
            raise ValueError("No se puede actualizar un movimiento sin id")
        self._conn.execute(
            """UPDATE movimientos SET
                 tipo = ?, fecha = ?, concepto = ?, detalle = ?, monto_centavos = ?, moneda = ?,
                 categoria_id = ?, estado = ?, fijo = ?, tarjeta_id = ?, metodo_pago = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (
                m.tipo.value,
                m.fecha.isoformat(),
                m.concepto,
                m.detalle,
                m.monto.cents,
                m.monto.moneda.value,
                m.categoria_id,
                m.estado.value,
                int(m.fijo),
                m.tarjeta_id,
                m.metodo_pago,
                m.id,
            ),
        )
        self._conn.commit()

    def eliminar(self, movimiento_id: int) -> None:
        self._conn.execute("DELETE FROM movimientos WHERE id = ?", (movimiento_id,))
        self._conn.commit()

    def obtener(self, movimiento_id: int) -> Movimiento | None:
        row = self._conn.execute(
            self._SELECT_CON_CATEGORIA + " WHERE m.id = ?", (movimiento_id,)
        ).fetchone()
        return self._map(row) if row else None

    def listar(self, filtro: FiltroMovimientos | None = None) -> list[Movimiento]:
        sql = self._SELECT_CON_CATEGORIA
        clausulas: list[str] = []
        params: list = []

        if filtro:
            if filtro.fecha_desde:
                clausulas.append("m.fecha >= ?")
                params.append(filtro.fecha_desde.isoformat())
            if filtro.fecha_hasta:
                clausulas.append("m.fecha <= ?")
                params.append(filtro.fecha_hasta.isoformat())
            if filtro.tipo:
                clausulas.append("m.tipo = ?")
                params.append(filtro.tipo.value)
            if filtro.categoria_id:
                clausulas.append("m.categoria_id = ?")
                params.append(filtro.categoria_id)
            if filtro.tarjeta_id:
                clausulas.append("m.tarjeta_id = ?")
                params.append(filtro.tarjeta_id)
            if filtro.moneda:
                clausulas.append("m.moneda = ?")
                params.append(filtro.moneda.value)
            if filtro.estado:
                clausulas.append("m.estado = ?")
                params.append(filtro.estado.value)
            if filtro.concepto:
                clausulas.append("(m.concepto LIKE ? OR m.detalle LIKE ?)")
                like = f"%{filtro.concepto}%"
                params.extend([like, like])

        if clausulas:
            sql += " WHERE " + " AND ".join(clausulas)
        sql += " ORDER BY m.fecha DESC, m.id DESC"

        rows = self._conn.execute(sql, params).fetchall()
        return [self._map(r) for r in rows]
