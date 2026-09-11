from datetime import date

from home_budget.app.database import get_connection, init_db
from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.movimientos import MovimientoService


def test_datos_persisten_entre_reaperturas_de_la_app(tmp_path):
    db_path = tmp_path / "persist.db"

    conn1 = get_connection(db_path)
    init_db(conn1)
    cat_id = {c.nombre: c.id for c in CategoriaRepository(conn1).listar()}["Comida"]
    MovimientoService(conn1).registrar(
        TipoMovimiento.EGRESO, date(2026, 1, 1), "Super", "", Money.from_decimal("100", Moneda.ARS), cat_id
    )
    conn1.close()

    conn2 = get_connection(db_path)
    init_db(conn2)
    movimientos = MovimientoService(conn2).listar()
    conn2.close()

    assert len(movimientos) == 1
    assert movimientos[0].concepto == "Super"
