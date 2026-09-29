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
    visa = tarjetas.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS, dia_vencimiento=10)
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


def test_debitos_en_pesos_y_en_dolares_en_la_misma_tarjeta(conn):
    """Una tarjeta opera en las dos monedas: sus debitos pendientes se suman
    por moneda, nunca mezclados."""
    _, fijos, visa, _ = _setup(conn)  # Agua: 8000 ARS
    cat = CategoriaRepository(conn).listar()[0].id
    fijos.registrar("Spotify", "", Money.from_decimal("11", Moneda.USD), cat, None, tarjeta_id=visa.id)

    assert fijos.total_debitos_pendientes(visa.id, 2026, 3, Moneda.ARS) == Money.from_decimal("8000", Moneda.ARS)
    assert fijos.total_debitos_pendientes(visa.id, 2026, 3, Moneda.USD) == Money.from_decimal("11", Moneda.USD)


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


def test_debito_vence_el_dia_de_vencimiento_de_la_tarjeta(conn):
    """Con debito automatico el dia que se cargue en el gasto no cuenta: vence
    cuando vence la tarjeta, y si se cambia el dia de la tarjeta lo sigue."""
    tarjetas, fijos = TarjetaService(conn), GastoFijoService(conn)
    visa = tarjetas.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS, dia_cierre=25, dia_vencimiento=7)
    cat = CategoriaRepository(conn).listar()[0].id
    luz = fijos.registrar("Luz", "", Money.from_decimal("5000", Moneda.ARS), cat, None, tarjeta_id=visa.id)

    assert fijos.debitos_del_mes(visa.id, 2026, 3)[0].fecha == date(2026, 3, 7)

    tarjetas.editar_tarjeta(visa.id, "Visa", "Banco", "1234", "ARS", visa.color, dia_vencimiento=30)
    assert fijos.debitos_del_mes(visa.id, 2026, 4)[0].fecha == date(2026, 4, 30)
    assert fijos.debitos_del_mes(visa.id, 2026, 2)[0].fecha == date(2026, 2, 28)  # febrero no tiene 30
    assert fijos.dia_vencimiento(fijos.obtener(luz.id)) == 30


def test_debito_pide_que_la_tarjeta_tenga_dia_de_vencimiento(conn):
    tarjetas, fijos = TarjetaService(conn), GastoFijoService(conn)
    sin_dia = tarjetas.crear_tarjeta("Master", "Banco", "1111", Moneda.ARS)
    cat = CategoriaRepository(conn).listar()[0].id

    with pytest.raises(ValueError, match="día de vencimiento"):
        fijos.registrar("Gas", "", Money.from_decimal("100", Moneda.ARS), cat, None, tarjeta_id=sin_dia.id)


def test_quitar_el_debito_vuelve_a_pedir_el_dia_propio(conn):
    _, fijos, _, agua = _setup(conn)

    with pytest.raises(ValueError, match="entre 1 y 28"):
        fijos.editar(agua.id, Money.from_decimal("8000", Moneda.ARS), None, tarjeta_id=None)
    fijos.editar(agua.id, Money.from_decimal("8000", Moneda.ARS), 15, tarjeta_id=None)
    assert fijos.dia_vencimiento(fijos.obtener(agua.id)) == 15


def test_filtrar_y_ordenar_gastos_fijos(conn):
    from home_budget.app.domain.models import TipoMovimiento
    from home_budget.app.services.gastos_fijos import FiltroGastosFijos

    tarjetas, fijos, visa, agua = _setup(conn)  # Agua: 8000 ARS, debito en Visa (vence el 10)
    cats = CategoriaRepository(conn).listar(TipoMovimiento.EGRESO)
    otra_cat = cats[1].id
    luz = fijos.registrar("luz", "", Money.from_decimal("20000", Moneda.ARS), otra_cat, 5)
    gym = fijos.registrar("Gimnasio", "", Money.from_decimal("15000", Moneda.ARS), agua.categoria_id, 20)
    netflix = fijos.registrar("Netflix", "", Money.from_decimal("10", Moneda.USD), agua.categoria_id, 1)
    hoy = date(2026, 3, 2)
    fijos.generar_movimiento_del_mes(luz.id, hoy)  # luz: pagado este mes
    todos = fijos.listar()

    def ids(**kw):
        return [g.id for g in fijos.filtrar_y_ordenar(todos, FiltroGastosFijos(**kw), hoy)]

    # vencimiento: el mas proximo primero (Netflix vence el 1: ya paso, el proximo es el 1/4)
    assert ids() == [luz.id, agua.id, gym.id, netflix.id]
    assert ids(orden="alfabetico") == [agua.id, gym.id, luz.id, netflix.id]
    assert ids(orden="monto_mayor") == [luz.id, gym.id, agua.id, netflix.id]  # ARS primero, USD aparte
    assert ids(orden="monto_menor") == [agua.id, gym.id, luz.id, netflix.id]
    assert ids(estado="finalizados") == [luz.id]
    assert set(ids(estado="en_curso")) == {agua.id, gym.id, netflix.id}
    assert ids(debito="con") == [agua.id]
    assert agua.id not in ids(debito="sin")
    assert ids(categoria_id=otra_cat) == [luz.id]
    assert not FiltroGastosFijos(orden="alfabetico").activo and FiltroGastosFijos(debito="con").activo
