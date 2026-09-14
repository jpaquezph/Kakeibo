from datetime import date

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.gastos_fijos import GastoFijoService


def _categoria_id(conn, nombre="Servicios esenciales"):
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    return cats[nombre]


def test_registrar_gasto_fijo(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Luz", "", Money.from_decimal("5000", Moneda.ARS), _categoria_id(conn), 10)

    assert gasto.id is not None
    assert service.listar() == [gasto]


def test_dia_mes_invalido_lanza_error(conn):
    service = GastoFijoService(conn)
    with pytest.raises(ValueError):
        service.registrar("Luz", "", Money.from_decimal("5000", Moneda.ARS), _categoria_id(conn), 31)


def test_generar_movimiento_del_mes_lo_vincula_al_gasto_fijo(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Internet", "", Money.from_decimal("8000", Moneda.ARS), _categoria_id(conn), 15)

    hoy = date(2026, 3, 20)
    movimiento = service.generar_movimiento_del_mes(gasto.id, hoy)

    assert movimiento.gasto_fijo_id == gasto.id
    assert movimiento.fecha == date(2026, 3, 15)
    assert movimiento.fijo is True
    assert service.ya_registrado_este_mes(gasto.id, 2026, 3)


def test_no_se_puede_generar_dos_veces_en_el_mismo_mes(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Internet", "", Money.from_decimal("8000", Moneda.ARS), _categoria_id(conn), 15)
    service.generar_movimiento_del_mes(gasto.id, date(2026, 3, 20))

    with pytest.raises(ValueError):
        service.generar_movimiento_del_mes(gasto.id, date(2026, 3, 25))


def test_editar_no_afecta_movimientos_ya_registrados(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Internet", "", Money.from_decimal("8000", Moneda.ARS), _categoria_id(conn), 15)
    movimiento_marzo = service.generar_movimiento_del_mes(gasto.id, date(2026, 3, 20))

    service.editar(gasto.id, Money.from_decimal("9500", Moneda.ARS), 20)
    movimiento_abril = service.generar_movimiento_del_mes(gasto.id, date(2026, 4, 20))

    assert movimiento_marzo.monto.amount == 8000
    assert movimiento_marzo.fecha == date(2026, 3, 15)
    assert movimiento_abril.fecha == date(2026, 4, 20)
    assert movimiento_abril.monto.amount == 9500


def test_editar_con_dia_de_vencimiento_invalido_lanza_error(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Internet", "", Money.from_decimal("8000", Moneda.ARS), _categoria_id(conn), 15)
    with pytest.raises(ValueError):
        service.editar(gasto.id, Money.from_decimal("8000", Moneda.ARS), 31)


def test_proximo_vencimiento_antes_y_despues_del_dia(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Alquiler", "", Money.from_decimal("100000", Moneda.ARS), _categoria_id(conn), 10)

    assert service.proximo_vencimiento(gasto, date(2026, 3, 5)) == date(2026, 3, 10)
    assert service.proximo_vencimiento(gasto, date(2026, 3, 15)) == date(2026, 4, 10)


def test_proximas_ocurrencias_marca_las_ya_registradas(conn):
    service = GastoFijoService(conn)
    gasto = service.registrar("Gas", "", Money.from_decimal("3000", Moneda.ARS), _categoria_id(conn), 5)
    service.generar_movimiento_del_mes(gasto.id, date(2026, 3, 1))

    ocurrencias = service.proximas_ocurrencias(2026, 3)
    assert len(ocurrencias) == 1
    assert ocurrencias[0].ya_registrado is True
    assert ocurrencias[0].fecha == date(2026, 3, 5)
