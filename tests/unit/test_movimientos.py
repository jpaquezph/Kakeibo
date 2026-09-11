from datetime import date

import pytest

from home_budget.app.domain.models import EstadoMovimiento, TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.repositories.movimientos import FiltroMovimientos
from home_budget.app.services.movimientos import MovimientoService


def _categoria_id(conn, nombre="Comida"):
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    return cats[nombre]


def test_registrar_editar_y_eliminar_movimiento(conn):
    service = MovimientoService(conn)
    cat_id = _categoria_id(conn)

    m = service.registrar(
        tipo=TipoMovimiento.EGRESO,
        fecha=date(2026, 1, 10),
        concepto="Supermercado",
        detalle="Compra semanal",
        monto=Money.from_decimal("15000", Moneda.ARS),
        categoria_id=cat_id,
    )
    assert m.id is not None

    m.concepto = "Supermercado (editado)"
    service.editar(m)
    recargado = service.obtener(m.id)
    assert recargado.concepto == "Supermercado (editado)"

    service.eliminar(m.id)
    assert service.obtener(m.id) is None


def test_monto_debe_ser_mayor_a_cero(conn):
    with pytest.raises(ValueError):
        MovimientoService(conn).registrar(
            tipo=TipoMovimiento.EGRESO,
            fecha=date(2026, 1, 1),
            concepto="x",
            detalle="",
            monto=Money.zero(Moneda.ARS),
            categoria_id=_categoria_id(conn),
        )


def test_concepto_no_puede_estar_vacio(conn):
    with pytest.raises(ValueError):
        MovimientoService(conn).registrar(
            tipo=TipoMovimiento.EGRESO,
            fecha=date(2026, 1, 1),
            concepto="   ",
            detalle="",
            monto=Money.from_decimal("100", Moneda.ARS),
            categoria_id=_categoria_id(conn),
        )


def test_ars_y_usd_se_acumulan_por_separado(conn):
    service = MovimientoService(conn)
    cat_id = _categoria_id(conn)
    service.registrar(TipoMovimiento.EGRESO, date(2026, 1, 1), "Gasto ARS", "", Money.from_decimal("100", Moneda.ARS), cat_id)
    service.registrar(TipoMovimiento.EGRESO, date(2026, 1, 1), "Gasto USD", "", Money.from_decimal("50", Moneda.USD), cat_id)

    total_ars = service.total_por_moneda(TipoMovimiento.EGRESO, Moneda.ARS)
    total_usd = service.total_por_moneda(TipoMovimiento.EGRESO, Moneda.USD)

    assert total_ars.amount == 100
    assert total_usd.amount == 50


def test_filtro_por_categoria_y_estado(conn):
    service = MovimientoService(conn)
    cat_comida = _categoria_id(conn, "Comida")
    cat_casa = _categoria_id(conn, "Casa")
    service.registrar(TipoMovimiento.EGRESO, date(2026, 1, 1), "Verduleria", "", Money.from_decimal("10", Moneda.ARS), cat_comida)
    service.registrar(TipoMovimiento.EGRESO, date(2026, 1, 1), "Alquiler", "", Money.from_decimal("500", Moneda.ARS), cat_casa, estado=EstadoMovimiento.PENDIENTE)

    resultado = service.listar(FiltroMovimientos(categoria_id=cat_comida))
    assert len(resultado) == 1
    assert resultado[0].concepto == "Verduleria"

    pendientes = service.listar(FiltroMovimientos(estado=EstadoMovimiento.PENDIENTE))
    assert len(pendientes) == 1
    assert pendientes[0].concepto == "Alquiler"
