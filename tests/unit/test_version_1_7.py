"""1.7: el resumen en el que entra una compra sale del dia de cierre y de
vencimiento de la tarjeta, y el resumen de un mes que todavia no llego no
arrastra lo anterior."""
from datetime import date

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.tarjetas import TarjetaService, meses_hasta_el_resumen, vencimiento_cuota


def ars(v):
    return Money.from_decimal(v, Moneda.ARS)


def _cat(conn):
    return next(c.id for c in CategoriaRepository(conn).listar() if c.nombre == "Tarjeta de crédito")


@pytest.fixture
def service(conn):
    return TarjetaService(conn)


@pytest.mark.parametrize("fecha, cierre, vence, meses", [
    (date(2026, 10, 7), 1, 9, 1),    # el caso del usuario: cerro el 1, la compra del 7 va a noviembre
    (date(2026, 10, 1), 1, 9, 0),    # el dia del cierre todavia entra
    (date(2026, 10, 2), 22, 7, 1),   # cierra el 22/10 y se paga el 7/11
    (date(2026, 10, 22), 22, 7, 1),
    (date(2026, 10, 25), 22, 7, 2),  # ya cerro: cierra el 22/11 y se paga el 7/12
    (date(2026, 12, 25), 22, 7, 2),  # cruza el anio
    (date(2026, 2, 28), 30, 10, 1),  # febrero no tiene 30: cierra el 28
])
def test_meses_hasta_el_resumen(fecha, cierre, vence, meses):
    assert meses_hasta_el_resumen(fecha, cierre, vence) == meses


def test_sin_dia_de_cierre_o_de_vencimiento_no_se_puede_calcular():
    assert meses_hasta_el_resumen(date(2026, 10, 7), None, 9) is None
    assert meses_hasta_el_resumen(date(2026, 10, 7), 1, None) is None


def test_vencimiento_cuota_con_meses_al_resumen():
    compra = date(2026, 10, 7)
    assert vencimiento_cuota(compra, 1, 1, meses_al_resumen=1) == date(2026, 11, 7)
    assert vencimiento_cuota(compra, 1, 3, meses_al_resumen=1) == date(2026, 11, 7)  # la 1ra cuota, en el mismo resumen
    assert vencimiento_cuota(compra, 3, 3, meses_al_resumen=1) == date(2027, 1, 7)
    assert vencimiento_cuota(compra, 4, 12, cuota_inicial=4, meses_al_resumen=1) == date(2026, 11, 7)
    assert vencimiento_cuota(compra, 1, 1, meses_al_resumen=0) == compra


def test_el_servicio_propone_el_mes_segun_la_tarjeta(service):
    galicia = service.crear_tarjeta("Galicia", "Master", "1111", dia_cierre=1, dia_vencimiento=9)
    sin_dias = service.crear_tarjeta("Otra", "Banco", "2222")

    assert service.meses_al_resumen(galicia.id, date(2026, 10, 7)) == 1
    assert service.meses_al_resumen(galicia.id, date(2026, 10, 7), 6) == 1
    # Sin los dias cargados vale la regla anterior.
    assert service.meses_al_resumen(sin_dias.id, date(2026, 10, 7)) == 0
    assert service.meses_al_resumen(sin_dias.id, date(2026, 10, 7), 6) == 1


def test_compra_despues_del_cierre_entra_en_el_resumen_siguiente(conn, service):
    """Pago octubre, compro el 7/10 con la tarjeta ya cerrada: va a noviembre."""
    galicia = service.crear_tarjeta("Galicia", "Master", "1111", dia_cierre=1, dia_vencimiento=9)
    fecha = date(2026, 10, 7)
    meses = service.meses_al_resumen(galicia.id, fecha)
    luz = service.registrar_compra(galicia.id, fecha, "Luz", "", ars("1000"), _cat(conn), meses_al_resumen=meses)
    tv = service.registrar_compra(galicia.id, fecha, "TV", "", ars("3000"), _cat(conn), 3, meses_al_resumen=meses)

    hoy = date(2026, 10, 7)
    assert service.resumen_del_mes(galicia.id, 2026, 10, hoy).pendientes == []
    noviembre = service.resumen_del_mes(galicia.id, 2026, 11, hoy).pendientes
    assert {(co.concepto, cu.numero_cuota) for co, cu in noviembre} == {("Luz", 1), ("TV", 1)}
    assert service.meses_al_resumen_de(luz) == service.meses_al_resumen_de(tv) == 1


def test_editar_compra_cambia_el_resumen_en_el_que_entra(conn, service):
    visa = service.crear_tarjeta("Visa", "Banco", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 10, 7), "TV", "", ars("3000"), _cat(conn), 3, meses_al_resumen=1)

    editada = service.editar_compra(compra.id, visa.id, compra.fecha, "TV", "", ars("3000"), 3, 0, meses_al_resumen=2)

    assert [c.fecha_vencimiento for c in editada.cuotas] == [date(2026, 12, 7), date(2027, 1, 7), date(2027, 2, 7)]
    assert service.meses_al_resumen_de(editada) == 2


def test_un_mes_que_no_llego_no_arrastra_lo_anterior(conn, service):
    visa = service.crear_tarjeta("Visa", "Banco", "1234")
    service.registrar_compra(visa.id, date(2026, 10, 5), "Super", "", ars("1000"), _cat(conn))  # octubre, sin pagar
    service.registrar_compra(visa.id, date(2026, 11, 5), "Nafta", "", ars("500"), _cat(conn))

    hoy = date(2026, 10, 7)
    assert [co.concepto for co, _cu in service.resumen_del_mes(visa.id, 2026, 11, hoy).pendientes] == ["Nafta"]
    # Ya en noviembre, lo de octubre sin pagar se sigue debiendo.
    en_noviembre = service.resumen_del_mes(visa.id, 2026, 11, date(2026, 11, 3)).pendientes
    assert {co.concepto for co, _cu in en_noviembre} == {"Nafta", "Super"}


def test_lo_atrasado_figura_pagado_en_el_mes_en_que_se_pago(conn, service):
    visa = service.crear_tarjeta("Visa", "Banco", "1234")
    service.registrar_compra(visa.id, date(2026, 9, 29), "Super", "", ars("1000"), _cat(conn))  # vencia en septiembre

    service.pagar_mes(visa.id, 2026, 10, fecha_pago=date(2026, 10, 6))

    hoy = date(2026, 10, 7)
    assert [co.concepto for co, _cu in service.resumen_del_mes(visa.id, 2026, 10, hoy).pagadas] == ["Super"]
    assert service.resumen_del_mes(visa.id, 2026, 9, hoy).pagadas == []
