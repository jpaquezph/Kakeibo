from __future__ import annotations

import sqlite3
from datetime import date

from ..domain.models import CuotaPrestamo, EstadoPrestamo, Prestamo
from ..domain.money import Money


class PrestamoRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map_cuota(self, row: sqlite3.Row) -> CuotaPrestamo:
        return CuotaPrestamo(
            id=row["id"],
            prestamo_id=row["prestamo_id"],
            numero_cuota=row["numero_cuota"],
            monto=Money(row["monto_centavos"], row["moneda_prestamo"]),
            fecha_vencimiento=date.fromisoformat(row["fecha_vencimiento"]),
            pagada=bool(row["pagada"]),
            fecha_pago=date.fromisoformat(row["fecha_pago"]) if row["fecha_pago"] else None,
        )

    def _map_prestamo(self, row: sqlite3.Row, cuotas: list[CuotaPrestamo]) -> Prestamo:
        return Prestamo(
            id=row["id"],
            nombre=row["nombre"],
            detalle=row["detalle"],
            monto_original=Money(row["monto_original_centavos"], row["moneda"]),
            cantidad_cuotas=row["cantidad_cuotas"],
            fecha_inicio=date.fromisoformat(row["fecha_inicio"]),
            estado=EstadoPrestamo(row["estado"]),
            cuotas=cuotas,
        )

    def crear_con_cuotas(self, prestamo: Prestamo) -> int:
        cur = self._conn.execute(
            """INSERT INTO prestamos
               (nombre, detalle, monto_original_centavos, moneda, cantidad_cuotas, fecha_inicio, estado)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                prestamo.nombre,
                prestamo.detalle,
                prestamo.monto_original.cents,
                prestamo.monto_original.moneda.value,
                prestamo.cantidad_cuotas,
                prestamo.fecha_inicio.isoformat(),
                prestamo.estado.value,
            ),
        )
        prestamo_id = cur.lastrowid
        for cuota in prestamo.cuotas:
            self._conn.execute(
                """INSERT INTO cuotas_prestamo (prestamo_id, numero_cuota, monto_centavos, fecha_vencimiento, pagada, fecha_pago)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    prestamo_id, cuota.numero_cuota, cuota.monto.cents, cuota.fecha_vencimiento.isoformat(),
                    int(cuota.pagada), cuota.fecha_pago.isoformat() if cuota.fecha_pago else None,
                ),
            )
        self._conn.commit()
        return prestamo_id

    def actualizar_datos(self, prestamo_id: int, nombre: str, detalle: str) -> None:
        self._conn.execute(
            "UPDATE prestamos SET nombre = ?, detalle = ? WHERE id = ?",
            (nombre, detalle, prestamo_id),
        )
        self._conn.commit()
        return prestamo_id

    def marcar_cuota_pagada(self, cuota_id: int, fecha_pago: date) -> None:
        row = self._conn.execute("SELECT pagada, prestamo_id FROM cuotas_prestamo WHERE id = ?", (cuota_id,)).fetchone()
        if row is None:
            raise ValueError("Cuota inexistente")
        if row["pagada"]:
            raise ValueError("La cuota ya fue registrada como pagada")
        self._conn.execute(
            "UPDATE cuotas_prestamo SET pagada = 1, fecha_pago = ? WHERE id = ?",
            (fecha_pago.isoformat(), cuota_id),
        )
        self._actualizar_estado_si_completo(row["prestamo_id"])
        self._conn.commit()

    def _actualizar_estado_si_completo(self, prestamo_id: int) -> None:
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, SUM(pagada) AS pagadas FROM cuotas_prestamo WHERE prestamo_id = ?",
            (prestamo_id,),
        ).fetchone()
        if row["total"] and row["pagadas"] == row["total"]:
            self._conn.execute("UPDATE prestamos SET estado = 'pagado' WHERE id = ?", (prestamo_id,))

    def eliminar(self, prestamo_id: int) -> None:
        self._conn.execute("DELETE FROM prestamos WHERE id = ?", (prestamo_id,))
        self._conn.commit()

    def listar(self) -> list[Prestamo]:
        rows = self._conn.execute("SELECT * FROM prestamos ORDER BY fecha_inicio DESC, id DESC").fetchall()
        return [self._con_cuotas(r) for r in rows]

    def obtener(self, prestamo_id: int) -> Prestamo | None:
        row = self._conn.execute("SELECT * FROM prestamos WHERE id = ?", (prestamo_id,)).fetchone()
        return self._con_cuotas(row) if row else None

    def _con_cuotas(self, row: sqlite3.Row) -> Prestamo:
        cuota_rows = self._conn.execute(
            "SELECT cp.*, p.moneda AS moneda_prestamo FROM cuotas_prestamo cp "
            "JOIN prestamos p ON p.id = cp.prestamo_id "
            "WHERE cp.prestamo_id = ? ORDER BY cp.numero_cuota",
            (row["id"],),
        ).fetchall()
        cuotas = [self._map_cuota(r) for r in cuota_rows]
        return self._map_prestamo(row, cuotas)
