from datetime import date
from decimal import Decimal

import pytest

from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.inversiones import (
    Ahorro, EstadoInversion, Fci, InversionService, OperacionCrypto, OperacionCryptoRegistro, Plazo, TipoTitulo, Titulo,
    tenencias_crypto, tenencias_por_simbolo, totales_crypto, totales_de,
)
from home_budget.app.services.movimientos import MovimientoService


def usd(valor):
    return Money.from_decimal(valor, Moneda.USD)


def ars(valor):
    return Money.from_decimal(valor, Moneda.ARS)


def _titulo(simbolo="NVDA", cantidad="1", precio="1500", tipo=TipoTitulo.ACCION, fecha=date(2026, 1, 10)):
    return Titulo(id=None, tipo=tipo, simbolo=simbolo, fecha_suscripcion=fecha, cantidad=Decimal(cantidad), precio_compra=usd(precio),
                  nombre="Nvidia Corp.", plazo=Plazo.LARGO, meses_pago=[3, 6])


def _balance(conn, moneda):
    resumen = DashboardService(conn).resumen()
    return next((r.balance for r in resumen.por_moneda if r.moneda == moneda), Money.zero(moneda))


def test_ahorro_debitado_genera_egreso_y_retiro_acreditado_genera_ingreso(conn):
    service = InversionService(conn)
    ahorro = service.registrar_ahorro(Ahorro(None, ars("50000"), date(2026, 1, 5), ubicacion="Mercado Pago"), debitar=True)
    assert _balance(conn, Moneda.ARS) == ars("-50000")

    service.retirar_ahorro(ahorro.id, date(2026, 2, 5), ars("52000"), acreditar=True)

    assert _balance(conn, Moneda.ARS) == ars("2000")
    guardado = service.obtener_ahorro(ahorro.id)
    assert guardado.estado == EstadoInversion.FINALIZADA and guardado.monto_salida == ars("52000")


def test_ahorro_sin_debitar_no_toca_la_plata_de_la_app(conn):
    InversionService(conn).registrar_ahorro(Ahorro(None, ars("1000"), date(2026, 1, 5)), debitar=False)
    assert MovimientoService(conn).listar() == []


def test_eliminar_inversion_borra_sus_movimientos(conn):
    service = InversionService(conn)
    t = service.registrar_titulo(_titulo(), debitar=True)
    service.finalizar_titulo(t.id, date(2026, 5, 1), usd("1800"), acreditar=True)
    assert len(MovimientoService(conn).listar()) == 2

    service.eliminar_titulo(t.id)

    assert MovimientoService(conn).listar() == []


def test_editar_titulo_actualiza_el_egreso_vinculado(conn):
    service = InversionService(conn)
    t = service.registrar_titulo(_titulo(cantidad="2", precio="100"), debitar=True)
    t.cantidad = Decimal("3")
    service.editar_titulo(t)

    mov = MovimientoService(conn).obtener(t.entrada_mov_id)
    assert mov.monto == usd("300") and mov.tipo == TipoMovimiento.EGRESO


def test_titulo_guarda_todos_los_datos(conn):
    service = InversionService(conn)
    t = _titulo()
    t.broker, t.transaccion, t.tipo_empresa, t.observaciones = "IOL", "129861459", "Tecnología", "nota"
    guardado = service.obtener_titulo(service.registrar_titulo(t, debitar=False).id)
    assert (guardado.simbolo, guardado.broker, guardado.transaccion, guardado.tipo_empresa, guardado.meses_pago, guardado.observaciones) == (
        "NVDA", "IOL", "129861459", "Tecnología", [3, 6], "nota")
    assert service.listar_titulos(TipoTitulo.BONO) == []


def test_totales_separan_invertido_vigente_y_resultado():
    vigente = _titulo(cantidad="2", precio="100")
    vendida = _titulo(cantidad="1", precio="500")
    vendida.estado, vendida.monto_salida = EstadoInversion.FINALIZADA, usd("650")
    en_pesos = Titulo(None, TipoTitulo.ACCION, "GGAL", date(2026, 1, 1), Decimal(1), ars("3000"))

    t = totales_de([vigente, vendida, en_pesos], Moneda.USD)

    assert (t.invertido, t.vigente, t.recibido, t.resultado, t.cantidad_vigentes) == (usd("700"), usd("200"), usd("650"), usd("150"), 1)


def test_tenencias_suman_las_compras_del_mismo_simbolo():
    compras = [_titulo(cantidad="1", precio="100"), _titulo(simbolo="nvda", cantidad="3", precio="120"), _titulo(simbolo="AAPL", cantidad="1", precio="50")]

    tenencias = tenencias_por_simbolo(compras, Moneda.USD)

    nvda = tenencias[0]
    assert (nvda.simbolo, nvda.cantidad, nvda.costo, nvda.transacciones) == ("NVDA", Decimal(4), usd("460"), 2)
    assert nvda.precio_promedio == usd("115")


def test_fci_rescate(conn):
    service = InversionService(conn)
    f = service.registrar_fci(Fci(None, "Fondo Money Market", date(2026, 1, 1), ars("100000"), tna=Decimal("35.5")), debitar=True)
    service.rescatar_fci(f.id, date(2026, 3, 1), ars("108000"), acreditar=True)

    guardado = service.obtener_fci(f.id)
    assert guardado.estado == EstadoInversion.FINALIZADA and guardado.fecha_rescate == date(2026, 3, 1)
    assert guardado.tna == Decimal("35.5")
    assert totales_de([guardado], Moneda.ARS).resultado == ars("8000")


def _op(operacion, cantidad, monto, activo="USDT"):
    return OperacionCryptoRegistro(None, date(2026, 1, 1), operacion, activo, usd(monto), Decimal("1"), Decimal(cantidad))


def test_crypto_tenencia_neta_a_costo_promedio():
    ops = [_op(OperacionCrypto.COMPRA, "100", "100"), _op(OperacionCrypto.COMPRA, "100", "120"), _op(OperacionCrypto.VENTA, "50", "70")]

    ten = tenencias_crypto(ops, Moneda.USD)[0]
    assert (ten.cantidad, ten.invertido, ten.recibido, ten.vigente) == (Decimal(150), usd("220"), usd("70"), usd("165"))

    t = totales_crypto(ops, Moneda.USD)
    assert (t.invertido, t.vigente, t.recibido, t.resultado) == (usd("220"), usd("165"), usd("70"), usd("15"))


def test_crypto_no_permite_vender_mas_de_lo_que_se_tiene(conn):
    service = InversionService(conn)
    service.registrar_crypto(_op(OperacionCrypto.COMPRA, "10", "10"), operar_con_cuenta=False)
    with pytest.raises(ValueError):
        service.registrar_crypto(_op(OperacionCrypto.VENTA, "11", "11"), operar_con_cuenta=False)


def test_crypto_venta_con_cuenta_suma_a_la_plata(conn):
    service = InversionService(conn)
    service.registrar_crypto(_op(OperacionCrypto.COMPRA, "10", "10"), operar_con_cuenta=True)
    service.registrar_crypto(_op(OperacionCrypto.VENTA, "10", "12"), operar_con_cuenta=True)
    assert _balance(conn, Moneda.USD) == usd("2")


def test_lo_invertido_no_aparece_como_gasto_en_la_torta_del_resumen(conn):
    from home_budget.app.services.dashboard import distribucion_por_categoria
    InversionService(conn).registrar_ahorro(Ahorro(None, ars("1000"), date(2026, 1, 5)), debitar=True)

    resumen = DashboardService(conn).resumen()

    assert distribucion_por_categoria(resumen.por_categoria, Moneda.ARS) == []


def test_totales_por_apartado(conn):
    service = InversionService(conn)
    service.registrar_ahorro(Ahorro(None, usd("100"), date(2026, 1, 5)), debitar=False)
    service.registrar_titulo(_titulo(cantidad="2", precio="50"), debitar=False)
    service.registrar_titulo(_titulo(simbolo="AL30", tipo=TipoTitulo.BONO, precio="60"), debitar=False)

    totales = service.totales_por_apartado(Moneda.USD)

    assert {k: v.vigente for k, v in totales.items()} == {
        "ahorro": usd("100"), "acciones": usd("100"), "bonos": usd("60"), "fci": usd("0"), "crypto": usd("0"),
    }


def test_pagos_por_mes_agrupa_simbolos_vigentes(conn):
    service = InversionService(conn)
    service.registrar_titulo(_titulo(simbolo="KO"), debitar=False)            # meses 3 y 6
    service.registrar_titulo(_titulo(simbolo="KO", cantidad="2"), debitar=False)  # misma accion, otra compra
    bono = _titulo(simbolo="AL30", tipo=TipoTitulo.BONO)
    bono.meses_pago = [1, 7]
    service.registrar_titulo(bono, debitar=False)
    vendida = service.registrar_titulo(_titulo(simbolo="MSFT"), debitar=False)
    service.finalizar_titulo(vendida.id, date(2026, 2, 1), usd("10"), acreditar=False)

    pagos = service.pagos_por_mes()

    assert [t.simbolo for t in pagos[3]] == ["KO"]
    assert [t.simbolo for t in pagos[7]] == ["AL30"]
    assert pagos[2] == []


def test_eventos_del_mes(conn):
    service = InversionService(conn)
    service.registrar_ahorro(Ahorro(None, ars("100"), date(2026, 3, 2)), debitar=False)
    t = service.registrar_titulo(_titulo(fecha=date(2026, 3, 10)), debitar=False)
    service.finalizar_titulo(t.id, date(2026, 4, 1), usd("2000"), acreditar=False)
    service.registrar_fci(Fci(None, "Fondo", date(2026, 1, 1), ars("500"), fecha_rescate=date(2026, 3, 20)), debitar=False)

    eventos = service.eventos_del_mes(2026, 3)

    assert [(e.fecha.day, e.apartado, e.previsto) for e in eventos] == [(2, "ahorro", False), (10, "acciones", False), (20, "fci", True)]
    assert [e.detalle for e in service.eventos_del_mes(2026, 4)] == ["Venta"]
