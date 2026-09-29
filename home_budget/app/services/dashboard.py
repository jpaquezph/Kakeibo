from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from ..domain.models import TipoMovimiento
from ..domain.money import Money, Moneda
from .cambio import CATEGORIA_EGRESO as CATEGORIA_CAMBIO_EGRESO
from .gastos_fijos import GastoFijoService
from .inversiones import CATEGORIA_INVERSION


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
class PorcionCategoria:
    nombre: str
    color: str
    total: Money
    porcentaje: float  # 0-100


NOMBRE_RESTO = "Resto"
COLOR_RESTO = "#898781"


def distribucion_por_categoria(
    por_categoria: list[TotalCategoria], moneda: Moneda, max_porciones: int = 7
) -> list[PorcionCategoria]:
    """Porcentaje de lo gastado en cada categoria para una moneda (no se
    mezclan ARS y USD). Se excluyen la compra de dolares y lo invertido, que
    no son gastos sino plata que cambia de lugar. Si hay mas de `max_porciones` categorias, las
    mas chicas se agrupan en "Resto" para que la torta siga siendo legible."""
    totales = sorted(
        (tc for tc in por_categoria
         if tc.moneda == moneda and tc.nombre not in (CATEGORIA_CAMBIO_EGRESO, CATEGORIA_INVERSION) and tc.total.cents > 0),
        key=lambda tc: tc.total.cents, reverse=True,
    )
    suma = sum(tc.total.cents for tc in totales)
    if suma == 0:
        return []

    porciones = [(tc.nombre, tc.color, tc.total.cents) for tc in totales]
    if len(porciones) > max_porciones:
        resto = sum(c for _, _, c in porciones[max_porciones - 1:])
        porciones = porciones[:max_porciones - 1] + [(NOMBRE_RESTO, COLOR_RESTO, resto)]

    return [
        PorcionCategoria(nombre=n, color=col, total=Money(c, moneda), porcentaje=c * 100 / suma)
        for n, col, c in porciones
    ]


@dataclass
class TotalTarjeta:
    tarjeta_id: int
    nombre: str
    moneda: Moneda
    total_pendiente_un_pago: Money
    total_pendiente_cuotas: Money
    # Debitos automaticos del mes sin pagar: suman a lo que hay que pagar de
    # la tarjeta, aunque como consumo se cuentan en Gastos fijos.
    total_pendiente_debitos: Money | None = None

    @property
    def total_pendiente(self) -> Money:
        total = self.total_pendiente_un_pago + self.total_pendiente_cuotas
        return total + self.total_pendiente_debitos if self.total_pendiente_debitos else total


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
    prestamos_activos: list[ProximaCuotaPrestamo] = field(default_factory=list)
    pagado_este_mes: list[PagoDelMes] = field(default_factory=list)


@dataclass
class ProximaCuotaPrestamo:
    """Un prestamo activo con la proxima cuota que hay que pagar."""
    nombre: str
    numero_cuota: int
    cantidad_cuotas: int
    monto: Money
    fecha_vencimiento: date


class DashboardService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _proximas_cuotas_prestamos(self) -> list[ProximaCuotaPrestamo]:
        rows = self._conn.execute(
            """SELECT p.nombre, p.moneda, p.cantidad_cuotas, cp.numero_cuota, cp.monto_centavos, cp.fecha_vencimiento
               FROM prestamos p
               JOIN cuotas_prestamo cp ON cp.prestamo_id = p.id
               WHERE cp.id = (SELECT id FROM cuotas_prestamo WHERE prestamo_id = p.id AND pagada = 0
                              ORDER BY numero_cuota LIMIT 1)
               ORDER BY cp.fecha_vencimiento, p.nombre"""
        ).fetchall()
        return [
            ProximaCuotaPrestamo(r["nombre"], r["numero_cuota"], r["cantidad_cuotas"], Money(r["monto_centavos"], r["moneda"]),
                                 date.fromisoformat(r["fecha_vencimiento"]))
            for r in rows
        ]

    def resumen(self, hoy: date | None = None) -> ResumenDashboard:
        hoy = hoy or date.today()
        resumen = ResumenDashboard(
            prestamos_pendientes_ars=Money.zero(Moneda.ARS),
            prestamos_pendientes_usd=Money.zero(Moneda.USD),
        )

        for moneda in (Moneda.ARS, Moneda.USD):
            ingresos = self._sumar_movimientos(TipoMovimiento.INGRESO, moneda)
            egresos = self._sumar_movimientos(TipoMovimiento.EGRESO, moneda)
            resumen.por_moneda.append(ResumenMoneda(moneda=moneda, ingresos=ingresos, egresos=egresos))

        resumen.por_categoria = self._totales_por_categoria()
        resumen.por_tarjeta = self._totales_por_tarjeta(hoy)

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
        resumen.prestamos_activos = self._proximas_cuotas_prestamos()

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

    def _totales_por_tarjeta(self, hoy: date) -> list[TotalTarjeta]:
        """Lo que hay que pagar este mes de cada tarjeta: las cuotas (y compras en
        1 pago) sin pagar que vencen en el mes, mas sus debitos automaticos. Las
        cuotas de meses siguientes no se suman. Uno por moneda: una tarjeta
        opera en ARS y en USD, y esos montos nunca se suman entre si."""
        mes = f"{hoy.year:04d}-{hoy.month:02d}"
        rows = self._conn.execute(
            """SELECT t.id AS tarjeta_id, t.nombre, co.moneda,
                      CASE WHEN co.cantidad_cuotas = 1 THEN 'un_pago' ELSE 'cuotas' END AS grupo,
                      SUM(cc.monto_centavos) AS total
               FROM cuotas_compra cc
               JOIN compras co ON co.id = cc.compra_id
               JOIN tarjetas t ON t.id = co.tarjeta_id
               WHERE cc.pagada = 0 AND substr(cc.fecha_vencimiento, 1, 7) = ?
               GROUP BY t.id, co.moneda, grupo
               ORDER BY t.nombre""",
            (mes,),
        ).fetchall()

        por_tarjeta: dict[tuple[int, str], TotalTarjeta] = {}

        def _total(tarjeta_id: int, nombre: str, moneda: str) -> TotalTarjeta:
            clave = (tarjeta_id, moneda)
            if clave not in por_tarjeta:
                cero = Money.zero(moneda)
                por_tarjeta[clave] = TotalTarjeta(tarjeta_id, nombre, Moneda(moneda), cero, cero)
            return por_tarjeta[clave]

        for r in rows:
            tt = _total(r["tarjeta_id"], r["nombre"], r["moneda"])
            monto = Money(r["total"] or 0, r["moneda"])
            if r["grupo"] == "un_pago":
                tt.total_pendiente_un_pago = monto
            else:
                tt.total_pendiente_cuotas = monto

        gastos_fijos = GastoFijoService(self._conn)
        for t in self._conn.execute("SELECT id, nombre FROM tarjetas ORDER BY nombre").fetchall():
            for moneda in Moneda:
                debitos = gastos_fijos.total_debitos_pendientes(t["id"], hoy.year, hoy.month, moneda)
                if debitos.cents:
                    _total(t["id"], t["nombre"], moneda.value).total_pendiente_debitos = debitos
        return sorted(por_tarjeta.values(), key=lambda tt: (tt.nombre, tt.moneda.value))
