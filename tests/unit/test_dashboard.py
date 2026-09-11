from datetime import date

from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.movimientos import MovimientoService
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
