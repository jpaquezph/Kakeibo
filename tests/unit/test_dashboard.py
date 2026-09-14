from datetime import date

from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.movimientos import MovimientoService
from home_budget.app.services.gastos_fijos import GastoFijoService
from home_budget.app.services.prestamos import PrestamoService
from home_budget.app.services.tarjetas import TarjetaService


def _categoria_id(conn, nombre):
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    return cats[nombre]


def test_totales_de_dashboard_coinciden_con_los_movimientos(conn):
    movs = MovimientoService(conn)
    cat_comida = _categoria_id(conn, "Comida")
    cat_casa = _categoria_id(conn, "Casa")

    movs.registrar(TipoMovimiento.INGRESO, date(2026, 1, 1), "Sueldo", "", Money.from_decimal("100000", Moneda.ARS), cat_casa)
    movs.registrar(TipoMovimiento.EGRESO, date(2026, 1, 2), "Super", "", Money.from_decimal("15000", Moneda.ARS), cat_comida)
    movs.registrar(TipoMovimiento.EGRESO, date(2026, 1, 3), "Alquiler", "", Money.from_decimal("30000", Moneda.ARS), cat_casa)
    movs.registrar(TipoMovimiento.INGRESO, date(2026, 1, 1), "Freelance", "", Money.from_decimal("200", Moneda.USD), cat_casa)

    resumen = DashboardService(conn).resumen()

    ars = next(r for r in resumen.por_moneda if r.moneda == Moneda.ARS)
    usd = next(r for r in resumen.por_moneda if r.moneda == Moneda.USD)

    assert ars.ingresos.amount == 100000
    assert ars.egresos.amount == 45000
    assert ars.balance.amount == 55000
    assert usd.ingresos.amount == 200
    assert usd.egresos.amount == 0

    total_comida = next(c for c in resumen.por_categoria if c.nombre == "Comida")
    assert total_comida.total.amount == 15000


def test_pendiente_por_tarjeta_separa_un_pago_de_cuotas(conn):
    tarjetas = TarjetaService(conn)
    cat = _categoria_id(conn, "Tarjeta de crédito")
    tarjeta = tarjetas.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)

    tarjetas.registrar_compra(tarjeta.id, date(2026, 1, 1), "Cena", "", Money.from_decimal("10000", Moneda.ARS), cat, 1)
    tarjetas.registrar_compra(tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("1000000", Moneda.ARS), cat, 10)

    resumen = DashboardService(conn).resumen()
    total_tarjeta = next(t for t in resumen.por_tarjeta if t.tarjeta_id == tarjeta.id)

    assert total_tarjeta.total_pendiente_un_pago.amount == 10000
    assert total_tarjeta.total_pendiente_cuotas.amount == 1000000
    assert total_tarjeta.total_pendiente.amount == 1010000


def test_cantidad_de_prestamos_pendientes(conn):
    prestamos = PrestamoService(conn)
    activo = prestamos.registrar_prestamo("Auto", "", Money.from_decimal("1000", Moneda.ARS), 2, date(2026, 1, 1))
    chico = prestamos.registrar_prestamo("Chico", "", Money.from_decimal("100", Moneda.ARS), 1, date(2026, 1, 1))
    prestamos.pagar_cuota(prestamos.obtener(activo.id).cuotas[0].id)
    prestamos.pagar_cuota(chico.cuotas[0].id)  # queda saldado por completo

    # "Chico" queda pagado (estado != activo); "Auto" sigue activo con 1 cuota pendiente.
    resumen = DashboardService(conn).resumen()
    assert resumen.prestamos_pendientes_cantidad == 1


def test_pagado_del_mes_junta_fijos_tarjetas_y_prestamos(conn):
    cat = _categoria_id(conn, "Servicios esenciales")
    cat_tc = _categoria_id(conn, "Tarjeta de crédito")

    gastos_fijos = GastoFijoService(conn)
    gasto = gastos_fijos.registrar("Luz", "", Money.from_decimal("5000", Moneda.ARS), cat, 10)
    gastos_fijos.generar_movimiento_del_mes(gasto.id, date(2026, 3, 15))

    tarjetas = TarjetaService(conn)
    tarjeta = tarjetas.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = tarjetas.registrar_compra(tarjeta.id, date(2026, 3, 1), "Super", "", Money.from_decimal("2000", Moneda.ARS), cat_tc, 1)
    tarjetas.pagar_cuota(compra.cuotas[0].id, date(2026, 3, 20))

    prestamos = PrestamoService(conn)
    prestamo = prestamos.registrar_prestamo("Auto", "", Money.from_decimal("3000", Moneda.ARS), 1, date(2026, 2, 1))
    prestamos.pagar_cuota(prestamo.cuotas[0].id, date(2026, 3, 25))

    pagos = DashboardService(conn).pagado_del_mes(2026, 3)

    origenes = {p.origen for p in pagos}
    assert origenes == {"fijo", "tarjeta", "prestamo"}
    assert sum(p.monto.amount for p in pagos) == 10000
