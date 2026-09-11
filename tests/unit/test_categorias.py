import pytest

from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.repositories.categorias import CategoriaRepository


def test_categorias_base_incluyen_ingreso_y_egreso(conn):
    repo = CategoriaRepository(conn)
    ingresos = repo.listar(TipoMovimiento.INGRESO)
    egresos = repo.listar(TipoMovimiento.EGRESO)

    assert len(ingresos) > 0
    assert len(egresos) > 0
    assert all(c.tipo == TipoMovimiento.INGRESO for c in ingresos)
    assert all(c.tipo == TipoMovimiento.EGRESO for c in egresos)


def test_crear_categoria_nueva(conn):
    repo = CategoriaRepository(conn)
    nueva = repo.crear("Alquiler cobrado", "#EB6834", "label_rounded", TipoMovimiento.INGRESO)

    assert nueva.id is not None
    assert nueva.tipo == TipoMovimiento.INGRESO

    recargadas = repo.listar(TipoMovimiento.INGRESO)
    assert any(c.nombre == "Alquiler cobrado" for c in recargadas)


def test_no_se_puede_crear_categoria_con_nombre_duplicado(conn):
    repo = CategoriaRepository(conn)
    with pytest.raises(ValueError):
        repo.crear("Comida", "#EB6834", "restaurant", TipoMovimiento.EGRESO)


def test_no_se_puede_crear_categoria_sin_nombre(conn):
    repo = CategoriaRepository(conn)
    with pytest.raises(ValueError):
        repo.crear("   ", "#EB6834", "label_rounded", TipoMovimiento.EGRESO)
