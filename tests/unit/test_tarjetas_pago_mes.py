"""Tarjetas: resumen del mes, pagar la tarjeta completa (con el saldo
corregible) y compras cargadas ya empezadas."""
import sqlite3
from datetime import date

import pytest

from home_budget.app.database import get_connection, init_db
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.gastos_fijos import GastoFijoService
from home_budget.app.services.tarjetas import TarjetaService


def ars(v):
    return Money.from_decimal(v, Moneda.ARS)


def usd(v):
    return Money.from_decimal(v, Moneda.USD)


def _cat(conn, nombre="Tarjeta de crédito"):
    return next(c.id for c in CategoriaRepository(conn).listar() if c.nombre == nombre)


@pytest.fixture
def service(conn):
    return TarjetaService(conn)


# --- compra cargada ya empezada ---

def test_la_cuota_en_la_que_se_empieza_vence_el_mes_siguiente_a_la_carga(conn, service):
    """El caso del usuario: carga el 29/9 una compra en 12 cuotas diciendo que
    esta en la 4. Antes la cuota 4 quedaba para enero y octubre no tenia nada."""
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 9, 29), "Heladera", "", ars("1200"), _cat(conn), 12, cuota_inicial=4)

    assert compra.cuota_inicial == 4
    assert [c.fecha_vencimiento for c in compra.cuotas[:5]] == [
        date(2026, 7, 29), date(2026, 8, 29), date(2026, 9, 29), date(2026, 10, 29), date(2026, 11, 29)]
    assert [c.pagada for c in compra.cuotas[:5]] == [True, True, True, False, False]
    assert [c.numero_cuota for c in service.cuotas_pendientes_del_mes(visa.id, 2026, 10)] == [4]
    assert not service.tarjeta_estaba_cerrada(compra)


def test_editar_una_compra_empezada_mantiene_su_calendario(conn, service):
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 9, 29), "Heladera", "", ars("1200"), _cat(conn), 12, cuota_inicial=4)

    editada = service.editar_compra(compra.id, visa.id, compra.fecha, "Heladera nueva", "", ars("1200"), 12, 3)

    assert editada.cuota_inicial == 4
    assert editada.cuotas[3].fecha_vencimiento == date(2026, 10, 29)


# --- resumen y pago del mes ---

def _octubre(conn, service):
    gastos = GastoFijoService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234", dia_vencimiento=10)
    service.registrar_compra(visa.id, date(2026, 9, 29), "Heladera", "", ars("1200"), _cat(conn), 12, cuota_inicial=4)  # 100 en oct
    service.registrar_compra(visa.id, date(2026, 9, 4), "Cena", "", ars("500"), _cat(conn), 1)  # quedo sin pagar en sept
    service.registrar_compra(visa.id, date(2026, 10, 2), "Libro", "", usd("30"), _cat(conn), 1)
    service.registrar_compra(visa.id, date(2026, 10, 3), "Tele", "", ars("600"), _cat(conn), 6)  # 1ra cuota en noviembre
    gastos.registrar("Netflix", "", ars("50"), _cat(conn, "Servicios no esenciales"), None, tarjeta_id=visa.id)
    return visa, gastos


def test_resumen_del_mes_junta_cuotas_un_pago_y_lo_vencido(conn, service):
    visa, _gastos = _octubre(conn, service)

    resumen = service.resumen_del_mes(visa.id, 2026, 10)

    assert sorted((co.concepto, cu.monto) for co, cu in resumen.pendientes) == [
        ("Cena", ars("500")), ("Heladera", ars("100")), ("Libro", usd("30"))]
    assert resumen.pagadas == [] and resumen.pagos == []


def test_pagar_mes_paga_todo_lo_del_mes_y_registra_el_pago(conn, service):
    visa, gastos = _octubre(conn, service)
    debitos = [o.gasto.monto for o in gastos.debitos_del_mes(visa.id, 2026, 10)]

    pagos = service.pagar_mes(visa.id, 2026, 10, debitos, fecha_pago=date(2026, 10, 6))
    gastos.registrar_debitos_del_mes(visa.id, 2026, 10)

    assert {(p.monto, p.calculado) for p in pagos} == {(ars("650"), ars("650")), (usd("30"), usd("30"))}
    resumen = service.resumen_del_mes(visa.id, 2026, 10)
    assert resumen.pendientes == []
    assert len(resumen.pagos) == 2
    assert service.cuotas_pendientes_del_mes(visa.id, 2026, 11) != []  # noviembre sigue pendiente
    assert all(o.ya_registrado for o in gastos.debitos_del_mes(visa.id, 2026, 10))


def test_pagar_mes_con_el_saldo_corregido_guarda_la_diferencia(conn, service):
    visa, gastos = _octubre(conn, service)
    debitos = [o.gasto.monto for o in gastos.debitos_del_mes(visa.id, 2026, 10)]

    service.pagar_mes(visa.id, 2026, 10, debitos, {Moneda.ARS: ars("700"), Moneda.USD: usd("30")}, fecha_pago=date(2026, 10, 6))

    pago_ars = next(p for p in service.resumen_del_mes(visa.id, 2026, 10).pagos if p.monto.moneda == Moneda.ARS)
    assert (pago_ars.monto, pago_ars.calculado) == (ars("700"), ars("650"))
    ajustes = [p for p in DashboardService(conn).pagado_del_mes(2026, 10) if "ajuste" in p.concepto]
    assert [(p.concepto, p.monto) for p in ajustes] == [("Visa: ajuste del resumen", ars("50"))]


def test_pagar_mes_rechaza_un_saldo_negativo(conn, service):
    visa, _gastos = _octubre(conn, service)
    with pytest.raises(ValueError):
        service.pagar_mes(visa.id, 2026, 10, [], {Moneda.ARS: Money(-100, Moneda.ARS)})
    assert len(service.resumen_del_mes(visa.id, 2026, 10).pendientes) == 3  # no pago nada


def test_eliminar_la_tarjeta_borra_sus_pagos(conn, service):
    visa, _gastos = _octubre(conn, service)
    service.pagar_mes(visa.id, 2026, 10)
    service.eliminar_tarjeta(visa.id)
    assert conn.execute("SELECT COUNT(*) FROM pagos_tarjeta").fetchone()[0] == 0


# --- migracion de las compras ya cargadas ---

def test_migracion_corrige_las_compras_cargadas_ya_empezadas(tmp_path):
    """Base de la 1.5: compra del 29/9 cargada "en la cuota 4" (las 3 primeras
    pagadas con fecha de octubre a diciembre) y una compra normal con su 1ra
    cuota pagada de verdad, que no se toca."""
    db = tmp_path / "vieja.db"
    conn = get_connection(db)
    init_db(conn)
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    cat = _cat(conn)
    empezada = service.registrar_compra(visa.id, date(2026, 9, 29), "Heladera", "", ars("1200"), cat, 12)
    normal = service.registrar_compra(visa.id, date(2026, 8, 10), "Tele", "", ars("600"), cat, 6)
    service.pagar_cuota(normal.cuotas[0].id, date(2026, 9, 10))  # pagada el dia que vencia
    conn.execute("UPDATE cuotas_compra SET pagada = 1, fecha_pago = fecha_vencimiento WHERE compra_id = ? AND numero_cuota <= 3",
                 (empezada.id,))
    conn.execute("UPDATE compras SET created_at = '2026-09-29 15:00:00'")
    conn.commit()
    conn.close()
    # Se quita la columna para dejar la base como en la 1.5
    cruda = sqlite3.connect(db)
    cruda.execute("ALTER TABLE compras DROP COLUMN cuota_inicial")
    cruda.commit()
    cruda.close()

    conn = get_connection(db)
    init_db(conn)
    service = TarjetaService(conn)
    empezada, normal = service.obtener_compra(empezada.id), service.obtener_compra(normal.id)

    assert empezada.cuota_inicial == 4
    assert [c.fecha_vencimiento for c in empezada.cuotas[:4]] == [
        date(2026, 7, 29), date(2026, 8, 29), date(2026, 9, 29), date(2026, 10, 29)]
    assert empezada.cuotas[2].fecha_pago == date(2026, 9, 29) and not empezada.cuotas[3].pagada
    assert normal.cuota_inicial == 1
    assert normal.cuotas[0].fecha_vencimiento == date(2026, 9, 10) and normal.cuotas[1].fecha_vencimiento == date(2026, 10, 10)
    assert len(list(tmp_path.glob("vieja_antes-de-corregir-cuotas_*.db"))) == 1
    conn.close()


# --- fichas de las compras al pagar la tarjeta ---

def test_al_pagar_la_tarjeta_las_compras_pasan_a_la_cuota_siguiente(conn, service):
    visa, _gastos = _octubre(conn, service)
    heladera = next(c for c in service.listar_compras(visa.id) if c.concepto == "Heladera")
    assert heladera.cuota_actual == 4

    service.pagar_mes(visa.id, 2026, 10, fecha_pago=date(2026, 10, 6))

    compras = {c.concepto: c for c in service.listar_compras(visa.id)}
    proxima = next(cu for cu in compras["Heladera"].cuotas if not cu.pagada)
    assert compras["Heladera"].cuota_actual == 5
    assert proxima.fecha_vencimiento == date(2026, 11, 29)
    assert compras["Tele"].cuota_actual == 1  # su 1ra cuota vence en noviembre: no se paga todavia
    assert compras["Cena"].cuotas_restantes == 0  # en 1 pago: queda saldada


def test_la_ficha_muestra_el_vencimiento_del_resumen_de_la_tarjeta():
    from home_budget.ui.desktop.tarjetas_view import vencimiento_en_resumen

    assert vencimiento_en_resumen(date(2026, 11, 29), 10) == date(2026, 11, 10)
    assert vencimiento_en_resumen(date(2027, 2, 15), 31) == date(2027, 2, 28)
    assert vencimiento_en_resumen(date(2026, 11, 29), None) == date(2026, 11, 29)


# --- los pagos de tarjeta cuentan como egresos ---

def _egresos(conn):
    return {(m.moneda, m.egresos) for m in DashboardService(conn).resumen().por_moneda if m.egresos.cents}


def _movimientos(conn):
    return [(r["concepto"], r["detalle"], r["monto_centavos"], r["moneda"], r["fijo"])
            for r in conn.execute("SELECT * FROM movimientos ORDER BY id")]


def test_comprar_con_tarjeta_no_es_egreso_hasta_que_se_paga(conn, service):
    _octubre(conn, service)
    assert _egresos(conn) == set()


def test_pagar_una_cuota_suelta_registra_el_egreso(conn, service):
    visa, _gastos = _octubre(conn, service)
    heladera = next(c for c in service.listar_compras(visa.id) if c.concepto == "Heladera")

    service.pagar_cuota(heladera.cuotas[3].id, date(2026, 10, 6))

    assert _movimientos(conn) == [("Visa: Heladera", "Cuota 4 de 12", 10000, "ARS", 0)]
    assert _egresos(conn) == {(Moneda.ARS, ars("100"))}


def test_pagar_la_tarjeta_registra_el_egreso_sin_contar_dos_veces_los_debitos(conn, service):
    visa, gastos = _octubre(conn, service)
    debitos = [o.gasto.monto for o in gastos.debitos_del_mes(visa.id, 2026, 10)]

    pagos = service.pagar_mes(visa.id, 2026, 10, debitos, {Moneda.ARS: ars("700"), Moneda.USD: usd("30")}, fecha_pago=date(2026, 10, 6))
    gastos.registrar_debitos_del_mes(visa.id, 2026, 10)

    # Pagado 700 (650 de la cuenta + 50 de ajuste): 650 por la tarjeta y 50 del debito (Netflix), como gasto fijo
    assert sorted(_movimientos(conn)) == [
        ("Netflix", "", 5000, "ARS", 1),
        ("Pago tarjeta Visa", "Resumen 10/2026", 3000, "USD", 0),
        ("Pago tarjeta Visa", "Resumen 10/2026", 65000, "ARS", 0),
    ]
    assert _egresos(conn) == {(Moneda.ARS, ars("700")), (Moneda.USD, usd("30"))}
    assert all(p.movimiento_id for p in pagos)


def test_migracion_crea_el_egreso_de_los_pagos_que_no_lo_tenian(tmp_path):
    """Base del primer armado de la 1.6: pago del resumen registrado (con el
    saldo corregido) pero sin egreso; el debito automatico si tenia el suyo."""
    db = tmp_path / "vieja.db"
    conn = get_connection(db)
    init_db(conn)
    service = TarjetaService(conn)
    visa, gastos = _octubre(conn, service)
    debitos = [o.gasto.monto for o in gastos.debitos_del_mes(visa.id, 2026, 10)]
    service.pagar_mes(visa.id, 2026, 10, debitos, {Moneda.ARS: ars("700"), Moneda.USD: usd("30")}, fecha_pago=date(2026, 10, 6))
    gastos.registrar_debitos_del_mes(visa.id, 2026, 10)
    conn.execute("DELETE FROM movimientos WHERE fijo = 0")
    conn.commit()
    conn.close()
    cruda = sqlite3.connect(db)
    cruda.execute("ALTER TABLE pagos_tarjeta DROP COLUMN movimiento_id")
    cruda.commit()
    cruda.close()

    conn = get_connection(db)
    init_db(conn)
    init_db(conn)  # abrir de nuevo no los duplica

    assert sorted(_movimientos(conn)) == [
        ("Netflix", "", 5000, "ARS", 1),
        ("Pago tarjeta Visa", "Resumen 10/2026", 3000, "USD", 0),
        ("Pago tarjeta Visa", "Resumen 10/2026", 65000, "ARS", 0),
    ]
    assert conn.execute("SELECT COUNT(*) FROM pagos_tarjeta WHERE movimiento_id IS NULL").fetchone()[0] == 0
    conn.close()


# --- las cuotas de prestamos tambien ---

def test_pagar_una_cuota_de_prestamo_registra_el_egreso(conn):
    from home_budget.app.services.prestamos import PrestamoService

    prestamos = PrestamoService(conn)
    auto = prestamos.registrar_prestamo("Auto", "", ars("1200"), 12, date(2026, 1, 15), cuota_inicial=4)
    assert _egresos(conn) == set()  # tomar el prestamo y las cuotas ya pagadas al cargarlo no son egresos

    prestamos.pagar_cuota(auto.cuotas[3].id, date(2026, 5, 10))
    prestamos.pagar_cuota(auto.cuotas[4].id, date(2026, 6, 10), monto=ars("130"))  # la cuota vino con otro valor

    assert _movimientos(conn) == [
        ("Auto", "Préstamo · cuota 4 de 12", 10000, "ARS", 0),
        ("Auto", "Préstamo · cuota 5 de 12", 13000, "ARS", 0),
    ]
    assert _egresos(conn) == {(Moneda.ARS, ars("230"))}
    categoria = conn.execute("SELECT c.nombre FROM movimientos m JOIN categorias c ON c.id = m.categoria_id").fetchone()[0]
    assert categoria == "Préstamos"
