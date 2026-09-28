from datetime import date

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.gastos_fijos import GastoFijoService
from home_budget.app.services.prestamos import PrestamoService
from home_budget.app.services.tarjetas import TarjetaService
from home_budget.app.services.vencimientos import VencimientoService


def _servicios(conn):
    tarjetas, prestamos, fijos = TarjetaService(conn), PrestamoService(conn), GastoFijoService(conn)
    return tarjetas, prestamos, fijos, VencimientoService(tarjetas, prestamos, fijos)


def _categoria_id(conn):
    return CategoriaRepository(conn).listar()[0].id


def test_pendientes_del_mes_junta_tarjetas_prestamos_y_fijos_ordenados_por_fecha(conn):
    tarjetas, prestamos, fijos, vencimientos = _servicios(conn)
    tarjeta = tarjetas.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS)
    compra = tarjetas.registrar_compra(tarjeta.id, date(2026, 3, 1), "Super", "", Money.from_decimal("2000", Moneda.ARS), _categoria_id(conn), 1)
    prestamo = prestamos.registrar_prestamo("Auto", "", Money.from_decimal("3000", Moneda.ARS), 1, date(2026, 2, 1))
    fijos.registrar("Luz", "", Money.from_decimal("5000", Moneda.ARS), _categoria_id(conn), 2)

    cuota_tc = compra.cuotas[0].fecha_vencimiento
    cuota_prestamo = prestamo.cuotas[0].fecha_vencimiento
    assert (cuota_prestamo.year, cuota_prestamo.month) == (cuota_tc.year, cuota_tc.month)
    anio, mes = cuota_tc.year, cuota_tc.month
    resultado = vencimientos.pendientes_del_mes(anio, mes)

    assert {v.origen for v in resultado} == {"tarjeta", "prestamo", "fijo"}
    assert [v.fecha for v in resultado] == sorted(v.fecha for v in resultado)
    assert all(v.fecha.year == anio and v.fecha.month == mes for v in resultado)
    tc = next(v for v in resultado if v.origen == "tarjeta")
    assert tc.color == tarjeta.color


def test_pendientes_del_mes_excluye_lo_ya_pagado(conn):
    tarjetas, _, fijos, vencimientos = _servicios(conn)
    tarjeta = tarjetas.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS)
    compra = tarjetas.registrar_compra(tarjeta.id, date(2026, 3, 1), "Super", "", Money.from_decimal("2000", Moneda.ARS), _categoria_id(conn), 1)
    cuota = compra.cuotas[0]
    tarjetas.pagar_cuota(cuota.id)

    resultado = vencimientos.pendientes_del_mes(cuota.fecha_vencimiento.year, cuota.fecha_vencimiento.month)

    assert [v for v in resultado if v.origen == "tarjeta"] == []
