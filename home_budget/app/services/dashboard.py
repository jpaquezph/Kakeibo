from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

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
    total_pendiente_un_pago: Money
    total_pendiente_cuotas: Money

    @property
    def total_pendiente(self) -> Money:
        return self.total_pendiente_un_pago + self.total_pendiente_cuotas


@dataclass
class PagoDelMes:
    origen: str  # "fijo" | "tarjeta" | "prestamo"
    concepto: str
    monto: Money
    fecha: date


@dataclass
class ResumenDashboard:
    por_moneda: list[ResumenMoneda] = field(default_factory=list)
    por_categoria: list[TotalCategoria] = field(default_factory=list)
    por_tarjeta: list[TotalTarjeta] = field(default_factory=list)
    prestamos_pendientes_ars: Money = None
    prestamos_pendientes_usd: Money = None
    prestamos_pendientes_cantidad: int = 0
    pagado_este_mes: list[PagoDelMes] = field(default_factory=list)


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

        resumen.prestamos_pendientes_cantidad = self._conn.execute(
            "SELECT COUNT(*) AS total FROM prestamos WHERE estado = 'activo'"
        ).fetchone()["total"]

        hoy = date.today()
        resumen.pagado_este_mes = self.pagado_del_mes(hoy.year, hoy.month)

        return resumen

    def pagado_del_mes(self, anio: int, mes: int) -> list[PagoDelMes]:
        """Gastos fijos, cuotas de tarjeta y cuotas de prestamo pagados en ese mes."""
        anio_s, mes_s = f"{anio:04d}", f"{mes:02d}"
        pagos: list[PagoDelMes] = []

        for r in self._conn.execute(
            """SELECT concepto, monto_centavos, moneda, fecha FROM movimientos
               WHERE fijo = 1 AND tipo = 'egreso'
                 AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?""",
            (anio_s, mes_s),
        ):
            pagos.append(PagoDelMes("fijo", r["concepto"], Money(r["monto_centavos"], r["moneda"]), date.fromisoformat(r["fecha"])))

        for r in self._conn.execute(
            """SELECT t.nombre AS tarjeta_nombre, co.concepto AS concepto, cc.monto_centavos, co.moneda, cc.fecha_pago
               FROM cuotas_compra cc
               JOIN compras co ON co.id = cc.compra_id
               JOIN tarjetas t ON t.id = co.tarjeta_id
               WHERE cc.pagada = 1 AND strftime('%Y', cc.fecha_pago) = ? AND strftime('%m', cc.fecha_pago) = ?""",
            (anio_s, mes_s),
        ):
            concepto = f"{r['tarjeta_nombre']}: {r['concepto']}"
            pagos.append(PagoDelMes("tarjeta", concepto, Money(r["monto_centavos"], r["moneda"]), date.fromisoformat(r["fecha_pago"])))

        for r in self._conn.execute(
            """SELECT p.nombre AS concepto, cp.monto_centavos, p.moneda, cp.fecha_pago
               FROM cuotas_prestamo cp
               JOIN prestamos p ON p.id = cp.prestamo_id
               WHERE cp.pagada = 1 AND strftime('%Y', cp.fecha_pago) = ? AND strftime('%m', cp.fecha_pago) = ?""",
            (anio_s, mes_s),
        ):
            pagos.append(PagoDelMes("prestamo", r["concepto"], Money(r["monto_centavos"], r["moneda"]), date.fromisoformat(r["fecha_pago"])))

        pagos.sort(key=lambda p: p.fecha, reverse=True)
        return pagos

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
            """SELECT t.id AS tarjeta_id, t.nombre, t.moneda,
                      CASE WHEN co.cantidad_cuotas = 1 THEN 'un_pago' ELSE 'cuotas' END AS grupo,
                      SUM(cc.monto_centavos) AS total
               FROM cuotas_compra cc
               JOIN compras co ON co.id = cc.compra_id
               JOIN tarjetas t ON t.id = co.tarjeta_id
               WHERE cc.pagada = 0
               GROUP BY t.id, grupo
               ORDER BY t.nombre"""
        ).fetchall()

        por_tarjeta: dict[int, TotalTarjeta] = {}
        for r in rows:
            tarjeta_id = r["tarjeta_id"]
            if tarjeta_id not in por_tarjeta:
                por_tarjeta[tarjeta_id] = TotalTarjeta(
                    tarjeta_id=tarjeta_id,
                    nombre=r["nombre"],
                    moneda=Moneda(r["moneda"]),
                    total_pendiente_un_pago=Money.zero(r["moneda"]),
                    total_pendiente_cuotas=Money.zero(r["moneda"]),
                )
            monto = Money(r["total"] or 0, r["moneda"])
            if r["grupo"] == "un_pago":
                por_tarjeta[tarjeta_id].total_pendiente_un_pago = monto
            else:
                por_tarjeta[tarjeta_id].total_pendiente_cuotas = monto
        return list(por_tarjeta.values())
