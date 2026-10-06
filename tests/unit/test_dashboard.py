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

    tarjetas.registrar_compra(tarjeta.id, date(2026, 2, 3), "Cena", "", Money.from_decimal("10000", Moneda.ARS), cat, 1)
    tarjetas.registrar_compra(tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("1000000", Moneda.ARS), cat, 10)

    resumen = DashboardService(conn).resumen(hoy=date(2026, 2, 10))
    total_tarjeta = next(t for t in resumen.por_tarjeta if t.tarjeta_id == tarjeta.id)

    assert total_tarjeta.total_pendiente_un_pago.amount == 10000
    assert total_tarjeta.total_pendiente_cuotas.amount == 100000  # solo la cuota de febrero
    assert total_tarjeta.total_pendiente.amount == 110000


def test_pendiente_en_tarjetas_solo_suma_las_cuotas_del_mes(conn):
    """Regresion: "Pendiente en tarjetas" sumaba todas las cuotas que faltan
    de cada compra, no las que corresponden al mes."""
    tarjetas = TarjetaService(conn)
    cat = _categoria_id(conn, "Tarjeta de crédito")
    visa = tarjetas.crear_tarjeta("Visa", "Galicia", "1234")
    tarjetas.registrar_compra(visa.id, date(2026, 1, 15), "Tele", "", Money.from_decimal("600", Moneda.ARS), cat, 6)  # feb a jul
    tarjetas.registrar_compra(visa.id, date(2026, 1, 15), "Libro", "", Money.from_decimal("30", Moneda.USD), cat, 3)  # feb a abr

    def pendientes(hoy):
        return {(tt.moneda, tt.total_pendiente.amount) for tt in DashboardService(conn).resumen(hoy=hoy).por_tarjeta}

    def pagar_hasta(mes):
        for m in range(2, mes + 1):
            tarjetas.pagar_cuotas_del_mes(visa.id, 2026, m)

    assert pendientes(date(2026, 2, 1)) == {(Moneda.ARS, 100), (Moneda.USD, 10)}
    # Lo que no se pago en febrero se sigue debiendo en marzo
    assert pendientes(date(2026, 3, 1)) == {(Moneda.ARS, 200), (Moneda.USD, 20)}
    pagar_hasta(2)
    assert pendientes(date(2026, 3, 1)) == {(Moneda.ARS, 100), (Moneda.USD, 10)}
    pagar_hasta(5)
    assert pendientes(date(2026, 6, 1)) == {(Moneda.ARS, 100)}  # el libro ya termino
    pagar_hasta(7)
    assert pendientes(date(2026, 9, 1)) == set()  # nada vence en septiembre


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


def _total(nombre, cents, moneda=Moneda.ARS):
    from home_budget.app.services.dashboard import TotalCategoria
    return TotalCategoria(categoria_id=0, nombre=nombre, color="#000000", icono="", moneda=moneda, total=Money(cents, moneda))


def test_distribucion_por_categoria_calcula_porcentajes_por_moneda():
    from home_budget.app.services.dashboard import distribucion_por_categoria

    porciones = distribucion_por_categoria(
        [_total("Comida", 3000), _total("Casa", 1000), _total("Viaje", 500, Moneda.USD)], Moneda.ARS
    )

    assert [(p.nombre, p.porcentaje) for p in porciones] == [("Comida", 75.0), ("Casa", 25.0)]


def test_distribucion_por_categoria_excluye_la_compra_de_dolares():
    from home_budget.app.services.cambio import CATEGORIA_EGRESO
    from home_budget.app.services.dashboard import distribucion_por_categoria

    porciones = distribucion_por_categoria([_total("Comida", 1000), _total(CATEGORIA_EGRESO, 9000)], Moneda.ARS)

    assert [(p.nombre, p.porcentaje) for p in porciones] == [("Comida", 100.0)]


def test_distribucion_por_categoria_agrupa_las_mas_chicas_en_resto():
    from home_budget.app.services.dashboard import NOMBRE_RESTO, distribucion_por_categoria

    totales = [_total(f"Cat{i}", 1000 - i * 100) for i in range(5)]
    porciones = distribucion_por_categoria(totales, Moneda.ARS, max_porciones=3)

    assert [p.nombre for p in porciones] == ["Cat0", "Cat1", NOMBRE_RESTO]
    assert porciones[-1].total.cents == 800 + 700 + 600
    assert round(sum(p.porcentaje for p in porciones), 6) == 100


def test_distribucion_por_categoria_sin_gastos_devuelve_vacio():
    from home_budget.app.services.dashboard import distribucion_por_categoria

    assert distribucion_por_categoria([], Moneda.ARS) == []
