from __future__ import annotations

import sqlite3
from datetime import date

from ..domain.models import Compra, CuotaCompra, Tarjeta
from ..domain.money import Money, Moneda


class TarjetaRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map(self, row: sqlite3.Row) -> Tarjeta:
        return Tarjeta(
            id=row["id"],
            nombre=row["nombre"],
            banco=row["banco"],
            ultimos_digitos=row["ultimos_digitos"],
            moneda=Moneda(row["moneda"]),
            color=row["color"],
            activa=bool(row["activa"]),
        )

    def crear(self, t: Tarjeta) -> int:
        try:
            cur = self._conn.execute(
                "INSERT INTO tarjetas (nombre, banco, ultimos_digitos, moneda, color, activa) VALUES (?, ?, ?, ?, ?, ?)",
                (t.nombre, t.banco, t.ultimos_digitos, t.moneda.value, t.color, int(t.activa)),
            )
        except sqlite3.IntegrityError:
            self._conn.rollback()
            raise ValueError(f'Ya existe una tarjeta "{t.nombre}" en {t.moneda.value}')
        self._conn.commit()
        return cur.lastrowid

    def actualizar(self, t: Tarjeta) -> None:
        try:
            self._conn.execute(
                "UPDATE tarjetas SET nombre=?, banco=?, ultimos_digitos=?, moneda=?, color=?, activa=? WHERE id=?",
                (t.nombre, t.banco, t.ultimos_digitos, t.moneda.value, t.color, int(t.activa), t.id),
            )
        except sqlite3.IntegrityError:
            self._conn.rollback()
            raise ValueError(f'Ya existe una tarjeta "{t.nombre}" en {t.moneda.value}')
        self._conn.commit()

    def eliminar(self, tarjeta_id: int) -> None:
        """Borra la tarjeta con sus compras y cuotas (compras no tiene ON DELETE
        CASCADE, asi que se borran a mano). Los gastos fijos que se debitaban de
        ella pasan a ser gastos fijos comunes y los movimientos que la
        mencionaban quedan sin tarjeta."""
        try:
            self._conn.execute("DELETE FROM compras WHERE tarjeta_id = ?", (tarjeta_id,))  # cuotas_compra cae en cascada
            self._conn.execute("UPDATE gastos_fijos SET tarjeta_id = NULL WHERE tarjeta_id = ?", (tarjeta_id,))
            self._conn.execute("UPDATE movimientos SET tarjeta_id = NULL WHERE tarjeta_id = ?", (tarjeta_id,))
            self._conn.execute("DELETE FROM tarjetas WHERE id = ?", (tarjeta_id,))
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def listar(self, solo_activas: bool = False) -> list[Tarjeta]:
        sql = "SELECT * FROM tarjetas"
        if solo_activas:
            sql += " WHERE activa = 1"
        sql += " ORDER BY nombre"
        return [self._map(r) for r in self._conn.execute(sql).fetchall()]

    def obtener(self, tarjeta_id: int) -> Tarjeta | None:
        row = self._conn.execute("SELECT * FROM tarjetas WHERE id = ?", (tarjeta_id,)).fetchone()
        return self._map(row) if row else None


class CompraRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _map_cuota(self, row: sqlite3.Row) -> CuotaCompra:
        return CuotaCompra(
            id=row["id"],
            compra_id=row["compra_id"],
            numero_cuota=row["numero_cuota"],
            monto=Money(row["monto_centavos"], row["moneda_compra"]),
            fecha_vencimiento=date.fromisoformat(row["fecha_vencimiento"]),
            pagada=bool(row["pagada"]),
            fecha_pago=date.fromisoformat(row["fecha_pago"]) if row["fecha_pago"] else None,
        )

    def _map_compra(self, row: sqlite3.Row, cuotas: list[CuotaCompra]) -> Compra:
        return Compra(
            id=row["id"],
            tarjeta_id=row["tarjeta_id"],
            fecha=date.fromisoformat(row["fecha"]),
            concepto=row["concepto"],
            detalle=row["detalle"],
            monto_total=Money(row["monto_total_centavos"], row["moneda"]),
            categoria_id=row["categoria_id"],
            cantidad_cuotas=row["cantidad_cuotas"],
            cuotas=cuotas,
        )

    def crear_con_cuotas(self, compra: Compra) -> int:
        cur = self._conn.execute(
            """INSERT INTO compras
               (tarjeta_id, fecha, concepto, detalle, monto_total_centavos, moneda, categoria_id, cantidad_cuotas)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                compra.tarjeta_id,
                compra.fecha.isoformat(),
                compra.concepto,
                compra.detalle,
                compra.monto_total.cents,
                compra.monto_total.moneda.value,
                compra.categoria_id,
                compra.cantidad_cuotas,
            ),
        )
        compra_id = cur.lastrowid
        for cuota in compra.cuotas:
            self._conn.execute(
                """INSERT INTO cuotas_compra (compra_id, numero_cuota, monto_centavos, fecha_vencimiento, pagada, fecha_pago)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    compra_id, cuota.numero_cuota, cuota.monto.cents, cuota.fecha_vencimiento.isoformat(),
                    int(cuota.pagada), cuota.fecha_pago.isoformat() if cuota.fecha_pago else None,
                ),
            )
        self._conn.commit()
        return compra_id

    def actualizar_datos(self, compra_id: int, concepto: str, detalle: str, categoria_id: int) -> None:
        self._conn.execute(
            "UPDATE compras SET concepto = ?, detalle = ?, categoria_id = ? WHERE id = ?",
            (concepto, detalle, categoria_id, compra_id),
        )
        self._conn.commit()

    def marcar_cuota_pagada(self, cuota_id: int, fecha_pago: date) -> None:
        row = self._conn.execute("SELECT pagada FROM cuotas_compra WHERE id = ?", (cuota_id,)).fetchone()
        if row is None:
            raise ValueError("Cuota inexistente")
        if row["pagada"]:
            raise ValueError("La cuota ya fue registrada como pagada")
        self._conn.execute(
            "UPDATE cuotas_compra SET pagada = 1, fecha_pago = ? WHERE id = ?",
            (fecha_pago.isoformat(), cuota_id),
        )
        self._conn.commit()

    def eliminar(self, compra_id: int) -> None:
        self._conn.execute("DELETE FROM compras WHERE id = ?", (compra_id,))
        self._conn.commit()

    def total_pendiente_centavos(self, tarjeta_id: int) -> int:
        row = self._conn.execute(
            """SELECT SUM(cc.monto_centavos) AS total
               FROM cuotas_compra cc JOIN compras co ON co.id = cc.compra_id
               WHERE co.tarjeta_id = ? AND cc.pagada = 0""",
            (tarjeta_id,),
        ).fetchone()
        return row["total"] or 0

    def listar_por_tarjeta(self, tarjeta_id: int) -> list[Compra]:
        rows = self._conn.execute(
            "SELECT * FROM compras WHERE tarjeta_id = ? ORDER BY fecha DESC, id DESC", (tarjeta_id,)
        ).fetchall()
        return [self._con_cuotas(r) for r in rows]

    def obtener(self, compra_id: int) -> Compra | None:
        row = self._conn.execute("SELECT * FROM compras WHERE id = ?", (compra_id,)).fetchone()
        return self._con_cuotas(row) if row else None

    def _con_cuotas(self, row: sqlite3.Row) -> Compra:
        cuota_rows = self._conn.execute(
            "SELECT cc.*, c.moneda AS moneda_compra FROM cuotas_compra cc "
            "JOIN compras c ON c.id = cc.compra_id "
            "WHERE cc.compra_id = ? ORDER BY cc.numero_cuota",
            (row["id"],),
        ).fetchall()
        cuotas = [self._map_cuota(r) for r in cuota_rows]
        return self._map_compra(row, cuotas)
