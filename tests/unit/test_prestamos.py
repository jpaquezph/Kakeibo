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
