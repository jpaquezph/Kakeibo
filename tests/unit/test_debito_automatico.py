from datetime import date

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.gastos_fijos import GastoFijoService
from home_budget.app.services.prestamos import PrestamoService
from home_budget.app.services.tarjetas import TarjetaService
from home_budget.app.services.vencimientos import VencimientoService


def _setup(conn):
    tarjetas, fijos = TarjetaService(conn), GastoFijoService(conn)
    visa = tarjetas.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS)
    cat = CategoriaRepository(conn).listar()[0].id
    agua = fijos.registrar("Agua", "", Money.from_decimal("8000", Moneda.ARS), cat, 10, tarjeta_id=visa.id)
    return tarjetas, fijos, visa, agua


def test_debito_aparece_en_el_resumen_de_su_tarjeta(conn):
    _, fijos, visa, agua = _setup(conn)

    debitos = fijos.debitos_del_mes(visa.id, 2026, 3)

    assert [(o.gasto.id, o.fecha, o.ya_registrado) for o in debitos] == [(agua.id, date(2026, 3, 10), False)]


def test_pagar_debitos_del_mes_registra_el_gasto_fijo_una_sola_vez(conn):
    _, fijos, visa, agua = _setup(conn)

    assert fijos.registrar_debitos_del_mes(visa.id, 2026, 3) == 1
    assert fijos.registrar_debitos_del_mes(visa.id, 2026, 3) == 0  # ya estaba pagado
    assert fijos.ya_registrado_este_mes(agua.id, 2026, 3)

    pagos = DashboardService(conn).pagado_del_mes(2026, 3)
    assert [(p.origen, p.concepto) for p in pagos] == [("fijo", "Agua")]


def test_debito_no_duplica_vencimientos(conn):
    tarjetas, fijos, _, _ = _setup(conn)

    vencimientos = VencimientoService(tarjetas, PrestamoService(conn), fijos).pendientes_del_mes(2026, 3)

    assert [(v.origen, v.titulo) for v in vencimientos] == [("fijo", "Agua")]
    assert "Visa" in vencimientos[0].etiqueta


def test_debito_requiere_misma_moneda_que_la_tarjeta(conn):
    tarjetas, fijos, _, _ = _setup(conn)
    usd = tarjetas.crear_tarjeta("Amex", "Banco", "9999", Moneda.USD)
    cat = CategoriaRepository(conn).listar()[0].id
    with pytest.raises(ValueError):
        fijos.registrar("Netflix", "", Money.from_decimal("10", Moneda.ARS), cat, 5, tarjeta_id=usd.id)


def test_editar_puede_quitar_o_mantener_el_debito(conn):
    _, fijos, visa, agua = _setup(conn)

    fijos.editar(agua.id, Money.from_decimal("9000", Moneda.ARS), 12)
    assert fijos.obtener(agua.id).tarjeta_id == visa.id

    fijos.editar(agua.id, Money.from_decimal("9000", Moneda.ARS), 12, tarjeta_id=None)
    assert fijos.obtener(agua.id).tarjeta_id is None


def test_debito_suma_al_pendiente_de_la_tarjeta_pero_el_consumo_es_uno(conn):
    tarjetas, fijos, visa, agua = _setup(conn)
    cat = CategoriaRepository(conn).listar()[0].id
    tarjetas.registrar_compra(visa.id, date.today(), "Súper", "", Money.from_decimal("2000", Moneda.ARS), cat, 1)

    tt = next(t for t in DashboardService(conn).resumen().por_tarjeta if t.tarjeta_id == visa.id)
    assert tt.total_pendiente_debitos == Money.from_decimal("8000", Moneda.ARS)
    assert tt.total_pendiente == Money.from_decimal("10000", Moneda.ARS)

    hoy = date.today()
    fijos.registrar_debitos_del_mes(visa.id, hoy.year, hoy.month)
    tt = next(t for t in DashboardService(conn).resumen().por_tarjeta if t.tarjeta_id == visa.id)
    assert tt.total_pendiente == Money.from_decimal("2000", Moneda.ARS)  # pagado: ya no suma al pendiente
    ars = next(r for r in DashboardService(conn).resumen().por_moneda if r.moneda == Moneda.ARS)
    assert ars.egresos == Money.from_decimal("8000", Moneda.ARS)  # el consumo se registro una sola vez


def test_borrar_la_tarjeta_deja_el_gasto_fijo_sin_debito(conn):
    tarjetas, fijos, visa, agua = _setup(conn)

    tarjetas.eliminar_tarjeta(visa.id)

    assert fijos.obtener(agua.id).tarjeta_id is None
