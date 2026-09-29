from datetime import date

import pytest

from home_budget.app.domain.models import EstadoPrestamo
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.prestamos import PrestamoService


def test_registrar_prestamo_genera_cuotas(conn):
    service = PrestamoService(conn)
    prestamo = service.registrar_prestamo("Prestamo auto", "", Money.from_decimal("6000", Moneda.ARS), 6, date(2026, 1, 1))

    assert len(prestamo.cuotas) == 6
    assert sum(c.monto.cents for c in prestamo.cuotas) == prestamo.monto_original.cents
    assert prestamo.cuotas_pagadas == 0
    assert prestamo.cuotas_restantes == 6
    assert prestamo.total_pendiente.amount == 6000
    assert prestamo.total_pagado.amount == 0


def test_pagar_cuotas_actualiza_totales(conn):
    service = PrestamoService(conn)
    prestamo = service.registrar_prestamo("Prestamo", "", Money.from_decimal("3000", Moneda.ARS), 3, date(2026, 1, 1))

    service.pagar_cuota(prestamo.cuotas[0].id, date(2026, 2, 1))
    prestamo = service.obtener(prestamo.id)

    assert prestamo.cuotas_pagadas == 1
    assert prestamo.cuotas_restantes == 2
    assert prestamo.total_pagado.amount == 1000
    assert prestamo.total_pendiente.amount == 2000
    assert prestamo.estado == EstadoPrestamo.ACTIVO


def test_prestamo_se_marca_pagado_al_completar_cuotas(conn):
    service = PrestamoService(conn)
    prestamo = service.registrar_prestamo("Prestamo chico", "", Money.from_decimal("200", Moneda.ARS), 2, date(2026, 1, 1))

    service.pagar_cuota(prestamo.cuotas[0].id)
    service.pagar_cuota(prestamo.cuotas[1].id)
    prestamo = service.obtener(prestamo.id)

    assert prestamo.estado == EstadoPrestamo.PAGADO
    assert prestamo.cuotas_restantes == 0


def test_cuota_de_prestamo_no_se_puede_pagar_dos_veces(conn):
    service = PrestamoService(conn)
    prestamo = service.registrar_prestamo("Prestamo", "", Money.from_decimal("1000", Moneda.ARS), 2, date(2026, 1, 1))
    service.pagar_cuota(prestamo.cuotas[0].id)
    with pytest.raises(ValueError):
        service.pagar_cuota(prestamo.cuotas[0].id)


def test_editar_datos_prestamo(conn):
    service = PrestamoService(conn)
    prestamo = service.registrar_prestamo("Prestamo auto", "detalle viejo", Money.from_decimal("1000", Moneda.ARS), 2, date(2026, 1, 1))

    editado = service.editar_datos(prestamo.id, "Prestamo del auto (corregido)", "detalle nuevo")

    assert editado.nombre == "Prestamo del auto (corregido)"
    assert editado.detalle == "detalle nuevo"


def test_prestamo_empezando_en_una_cuota_intermedia():
    """Como en tarjetas: si ya se venia pagando, las cuotas anteriores a la
    actual quedan pagadas."""
    from home_budget.app.database import get_connection, init_db
    from home_budget.app.services.prestamos import PrestamoService

    conn = get_connection(":memory:")
    init_db(conn)
    service = PrestamoService(conn)
    p = service.registrar_prestamo("Auto", "", Money.from_decimal("12000", Moneda.ARS), 12, date(2026, 1, 15), cuota_inicial=4)

    assert p.cuotas_pagadas == 3
    assert [c.pagada for c in p.cuotas[:4]] == [True, True, True, False]
    assert p.cuotas[0].fecha_pago == p.cuotas[0].fecha_vencimiento
    assert p.total_pendiente == Money.from_decimal("9000", Moneda.ARS)


def test_prestamo_con_dia_de_vencimiento_propio():
    from home_budget.app.database import get_connection, init_db
    from home_budget.app.services.prestamos import PrestamoService, vencimiento_cuota_prestamo

    conn = get_connection(":memory:")
    init_db(conn)
    p = PrestamoService(conn).registrar_prestamo("Auto", "", Money.from_decimal("300", Moneda.ARS), 3, date(2026, 1, 15), dia_vencimiento=31)

    assert [c.fecha_vencimiento for c in p.cuotas] == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    # sin dia propio: el de la fecha de inicio, como antes
    assert vencimiento_cuota_prestamo(date(2026, 1, 15), 1) == date(2026, 2, 15)


def test_prestamo_valida_cuota_y_dia():
    from home_budget.app.database import get_connection, init_db
    from home_budget.app.services.prestamos import PrestamoService

    conn = get_connection(":memory:")
    init_db(conn)
    service = PrestamoService(conn)
    with pytest.raises(ValueError, match="cuota actual"):
        service.registrar_prestamo("Auto", "", Money.from_decimal("300", Moneda.ARS), 3, date(2026, 1, 15), cuota_inicial=4)
    with pytest.raises(ValueError, match="entre 1 y 31"):
        service.registrar_prestamo("Auto", "", Money.from_decimal("300", Moneda.ARS), 3, date(2026, 1, 15), dia_vencimiento=40)


def test_editar_prestamo_completo_sin_tocar_las_cuotas_pagadas(conn):
    service = PrestamoService(conn)
    p = service.registrar_prestamo("Auto", "", Money.from_decimal("1200", Moneda.ARS), 12, date(2026, 1, 15))
    service.pagar_cuota(p.cuotas[0].id, date(2026, 2, 14))

    editado = service.editar_prestamo(p.id, "Auto 0km", "Banco", Money.from_decimal("2200", Moneda.ARS), 11, 1, date(2026, 1, 15), 10)

    primera = editado.cuotas[0]
    assert (primera.monto, primera.fecha_vencimiento, primera.fecha_pago) == (p.cuotas[0].monto, p.cuotas[0].fecha_vencimiento, date(2026, 2, 14))
    assert [c.monto for c in editado.cuotas[1:]] == [Money.from_decimal("210", Moneda.ARS)] * 10  # (2200 - 100) / 10
    assert editado.cuotas[1].fecha_vencimiento == date(2026, 3, 10)  # nuevo dia de vencimiento
    assert (editado.nombre, editado.cantidad_cuotas, editado.dia_vencimiento) == ("Auto 0km", 11, 10)
    assert service.dia_vencimiento_de(editado) == 10


def test_dia_de_vencimiento_de_prestamos_cargados_antes(conn):
    """Los prestamos anteriores no guardaban el dia: se toma de sus cuotas."""
    service = PrestamoService(conn)
    p = service.registrar_prestamo("Auto", "", Money.from_decimal("300", Moneda.ARS), 3, date(2026, 1, 31))
    conn.execute("UPDATE prestamos SET dia_vencimiento = NULL WHERE id = ?", (p.id,))
    conn.commit()

    assert service.dia_vencimiento_de(service.obtener(p.id)) == 31  # aunque febrero lo recorte a 28


def test_cambiar_el_monto_de_una_cuota_y_las_siguientes(conn):
    """Prestamos con cuota variable (UVA, sistema aleman): el monto de cada
    cuota se puede corregir; el total pasa a ser la suma de las cuotas."""
    service = PrestamoService(conn)
    p = service.registrar_prestamo("Hipoteca", "", Money.from_decimal("400", Moneda.ARS), 4, date(2026, 1, 10))
    service.pagar_cuota(p.cuotas[0].id)

    p = service.cambiar_monto_cuota(p.cuotas[1].id, Money.from_decimal("130", Moneda.ARS))
    assert [c.monto.amount for c in p.cuotas] == [100, 130, 100, 100]
    assert p.monto_original == Money.from_decimal("430", Moneda.ARS)

    p = service.cambiar_monto_cuota(p.cuotas[2].id, Money.from_decimal("150", Moneda.ARS), tambien_las_siguientes=True)
    assert [c.monto.amount for c in p.cuotas] == [100, 130, 150, 150]

    with pytest.raises(ValueError, match="ya está pagada"):
        service.cambiar_monto_cuota(p.cuotas[0].id, Money.from_decimal("1", Moneda.ARS))


def test_pagar_cuota_con_otro_monto(conn):
    service = PrestamoService(conn)
    p = service.registrar_prestamo("UVA", "", Money.from_decimal("300", Moneda.ARS), 3, date(2026, 1, 10))

    service.pagar_cuota(p.cuotas[0].id, date(2026, 2, 10), monto=Money.from_decimal("112.5", Moneda.ARS))

    p = service.obtener(p.id)
    assert p.cuotas[0].pagada and p.cuotas[0].monto == Money.from_decimal("112.5", Moneda.ARS)
    assert p.total_pagado == Money.from_decimal("112.5", Moneda.ARS)


def test_resumen_muestra_la_proxima_cuota_de_cada_prestamo(conn):
    from home_budget.app.services.dashboard import DashboardService

    service = PrestamoService(conn)
    p = service.registrar_prestamo("Auto", "", Money.from_decimal("1200", Moneda.ARS), 12, date(2026, 1, 15), cuota_inicial=4)
    service.registrar_prestamo("Pagado", "", Money.from_decimal("100", Moneda.ARS), 1, date(2026, 1, 15))
    pagado = service.listar()[0] if service.listar()[0].nombre == "Pagado" else service.listar()[1]
    service.pagar_cuota(pagado.cuotas[0].id)

    proximas = DashboardService(conn).resumen().prestamos_activos
    assert [(pc.nombre, pc.numero_cuota, pc.cantidad_cuotas, pc.monto, pc.fecha_vencimiento) for pc in proximas] == [
        ("Auto", 4, 12, Money.from_decimal("100", Moneda.ARS), p.cuotas[3].fecha_vencimiento),
    ]
