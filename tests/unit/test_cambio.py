from datetime import date
from decimal import Decimal

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.cambio import CambioDivisaService
from home_budget.app.services.dashboard import DashboardService


def test_comprar_dolares_genera_egreso_ars_e_ingreso_usd(conn):
    service = CambioDivisaService(conn)
    egreso, ingreso = service.comprar_dolares(date(2026, 1, 1), Money.from_decimal("100", Moneda.USD), Decimal("1000"))

    assert egreso.monto.moneda == Moneda.ARS
    assert egreso.monto.amount == 100000
    assert ingreso.monto.moneda == Moneda.USD
    assert ingreso.monto.amount == 100

    resumen = DashboardService(conn).resumen()
    ars = next(r for r in resumen.por_moneda if r.moneda == Moneda.ARS)
    usd = next(r for r in resumen.por_moneda if r.moneda == Moneda.USD)
    assert ars.egresos.amount == 100000
    assert usd.ingresos.amount == 100


def test_vender_dolares_genera_egreso_usd_e_ingreso_ars(conn):
    service = CambioDivisaService(conn)
    egreso, ingreso = service.vender_dolares(date(2026, 1, 1), Money.from_decimal("50", Moneda.USD), Decimal("1200"))

    assert egreso.monto.moneda == Moneda.USD
    assert egreso.monto.amount == 50
    assert ingreso.monto.moneda == Moneda.ARS
    assert ingreso.monto.amount == 60000


def test_cantidad_en_pesos_o_cotizacion_invalida_lanza_error(conn):
    service = CambioDivisaService(conn)
    with pytest.raises(ValueError):
        service.comprar_dolares(date(2026, 1, 1), Money.from_decimal("100", Moneda.ARS), Decimal("1000"))
    with pytest.raises(ValueError):
        service.comprar_dolares(date(2026, 1, 1), Money.from_decimal("100", Moneda.USD), Decimal("0"))
