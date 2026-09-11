from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..domain.models import TipoMovimiento
from ..domain.money import Money, Moneda


@dataclass
class ResumenMoneda:
    moneda: Moneda
    ingresos: Money
    egresos: Money

    @property
    def balance(self) -> Money:
        return self.ingresos - self.egresos


@dataclass
class TotalCategoria:
    categoria_id: int
    nombre: str
    color: str
    icono: str
    moneda: Moneda
    total: Money


@dataclass
class TotalTarjeta:
    tarjeta_id: int
    nombre: str
    moneda: Moneda
    total_pendiente: Money


@dataclass
class ResumenDashboard:
    por_moneda: list[ResumenMoneda] = field(default_factory=list)
    por_categoria: list[TotalCategoria] = field(default_factory=list)
    por_tarjeta: list[TotalTarjeta] = field(default_factory=list)
    prestamos_pendientes_ars: Money = None
    prestamos_pendientes_usd: Money = None


class DashboardService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def resumen(self) -> ResumenDashboard:
        resumen = ResumenDashboard(
            prestamos_pendientes_ars=Money.zero(Moneda.ARS),
            prestamos_pendientes_usd=Money.zero(Moneda.USD),
        )

        for moneda in (Moneda.ARS, Moneda.USD):
            ingresos = self._sumar_movimientos(TipoMovimiento.INGRESO, moneda)
            egresos = self._sumar_movimientos(TipoMovimiento.EGRESO, moneda)
            resumen.por_moneda.append(ResumenMoneda(moneda=moneda, ingresos=ingresos, egresos=egresos))

        resumen.por_categoria = self._totales_por_categoria()
        resumen.por_tarjeta = self._totales_por_tarjeta()

        pendientes = self._conn.execute(
            """SELECT p.moneda AS moneda, SUM(cp.monto_centavos) AS total
               FROM cuotas_prestamo cp
               JOIN prestamos p ON p.id = cp.prestamo_id
               WHERE cp.pagada = 0
               GROUP BY p.moneda"""
        ).fetchall()
        for row in pendientes:
            monto = Money(row["total"] or 0, row["moneda"])
            if row["moneda"] == Moneda.ARS.value:
                resumen.prestamos_pendientes_ars = monto
            else:
                resumen.prestamos_pendientes_usd = monto

        return resumen

    def _sumar_movimientos(self, tipo: TipoMovimiento, moneda: Moneda) -> Money:
        row = self._conn.execute(
            "SELECT SUM(monto_centavos) AS total FROM movimientos WHERE tipo = ? AND moneda = ?",
            (tipo.value, moneda.value),
        ).fetchone()
        return Money(row["total"] or 0, moneda)

    def _totales_por_categoria(self) -> list[TotalCategoria]:
        rows = self._conn.execute(
            """SELECT c.id AS categoria_id, c.nombre, c.color, c.icono, m.moneda, SUM(m.monto_centavos) AS total
               FROM movimientos m
               JOIN categorias c ON c.id = m.categoria_id
               WHERE m.tipo = 'egreso'
               GROUP BY c.id, m.moneda
               ORDER BY total DESC"""
        ).fetchall()
        return [
            TotalCategoria(
                categoria_id=r["categoria_id"],
                nombre=r["nombre"],
                color=r["color"],
                icono=r["icono"],
                moneda=Moneda(r["moneda"]),
                total=Money(r["total"], r["moneda"]),
            )
            for r in rows
        ]

    def _totales_por_tarjeta(self) -> list[TotalTarjeta]:
        rows = self._conn.execute(
            """SELECT t.id AS tarjeta_id, t.nombre, t.moneda, SUM(cc.monto_centavos) AS total
               FROM cuotas_compra cc
               JOIN compras co ON co.id = cc.compra_id
               JOIN tarjetas t ON t.id = co.tarjeta_id
               WHERE cc.pagada = 0
               GROUP BY t.id"""
        ).fetchall()
        return [
            TotalTarjeta(
                tarjeta_id=r["tarjeta_id"],
                nombre=r["nombre"],
                moneda=Moneda(r["moneda"]),
                total_pendiente=Money(r["total"] or 0, r["moneda"]),
            )
            for r in rows
        ]
