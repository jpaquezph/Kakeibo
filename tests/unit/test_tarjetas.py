from datetime import date

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.tarjetas import TarjetaService


def _categoria_id(conn, nombre="Tarjeta de crédito"):
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    return cats[nombre]


def test_tarjetas_multiples_son_independientes(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    amex = service.crear_tarjeta("Amex", "BBVA", "5678", Moneda.USD)

    service.registrar_compra(visa.id, date(2026, 1, 1), "Compra visa", "", Money.from_decimal("100", Moneda.ARS), _categoria_id(conn), 1)
    service.registrar_compra(amex.id, date(2026, 1, 1), "Compra amex", "", Money.from_decimal("50", Moneda.USD), _categoria_id(conn), 1)

    assert len(service.listar_compras(visa.id)) == 1
    assert len(service.listar_compras(amex.id)) == 1


def test_compra_de_un_pago(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 1), "Compra", "", Money.from_decimal("300", Moneda.ARS), _categoria_id(conn), 1)
    assert compra.cantidad_cuotas == 1
    assert len(compra.cuotas) == 1
    assert compra.cuotas[0].monto.amount == 300


def test_compra_en_cuotas_genera_cuotas_correctas(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 15), "Notebook", "", Money.from_decimal("1000", Moneda.ARS), _categoria_id(conn), 4)

    assert compra.cantidad_cuotas == 4
    assert len(compra.cuotas) == 4
    assert sum(c.monto.cents for c in compra.cuotas) == compra.monto_total.cents
    assert compra.cuotas[0].fecha_vencimiento == date(2026, 2, 15)
    assert compra.cuotas[3].fecha_vencimiento == date(2026, 5, 15)


def test_cuota_actual_restantes_y_pendiente(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 1), "TV", "", Money.from_decimal("1200", Moneda.ARS), _categoria_id(conn), 3)

    assert compra.cuota_actual == 1
    assert compra.cuotas_restantes == 3
    assert compra.monto_pendiente.amount == 1200

    service.pagar_cuota(compra.cuotas[0].id, date(2026, 2, 1))
    compra = service.obtener_compra(compra.id)

    assert compra.cuota_actual == 2
    assert compra.cuotas_restantes == 2
    assert compra.monto_pendiente.amount == 800


def test_una_cuota_no_puede_pagarse_dos_veces(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 1), "TV", "", Money.from_decimal("300", Moneda.ARS), _categoria_id(conn), 3)

    service.pagar_cuota(compra.cuotas[0].id)
    with pytest.raises(ValueError):
        service.pagar_cuota(compra.cuotas[0].id)
