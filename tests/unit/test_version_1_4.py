"""Cambios de la 1.4: total pendiente del mes, metodo de pago y edicion
completa de gastos fijos, filtro de compras por forma de pago, quitar
categorias y buscar / ordenar productos en Compra mensual."""
from datetime import date
from decimal import Decimal

import pytest

from home_budget.app.database import init_db
from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.compra_mensual import (
    CompraMensualService, calcular, coincide_busqueda, ordenar_productos,
)
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.gastos_fijos import GastoFijoService
from home_budget.app.services.movimientos import MovimientoService
from home_budget.app.services.prestamos import PrestamoService
from home_budget.app.services.tarjetas import TarjetaService
from home_budget.ui.desktop.tarjetas_view import filtrar_por_forma


def _cat(conn, nombre):
    return next(c.id for c in CategoriaRepository(conn).listar(incluir_quitadas=True) if c.nombre == nombre)


def _ars(valor):
    return Money.from_decimal(valor, Moneda.ARS)


# ---------------------------------------------------------------- Resumen: pendiente del mes

def test_pendiente_del_mes_suma_fijos_tarjetas_y_prestamos_sin_duplicar_debitos(conn):
    hoy = date(2026, 3, 10)
    fijos, tarjetas, prestamos = GastoFijoService(conn), TarjetaService(conn), PrestamoService(conn)
    servicios, cat_tc = _cat(conn, "Servicios esenciales"), _cat(conn, "Tarjeta de crédito")

    luz = fijos.registrar("Luz", "", _ars("5000"), servicios, 15)
    fijos.registrar("Agua", "", _ars("2000"), servicios, 20)
    fijos.generar_movimiento_del_mes(luz.id, hoy)  # ya pagado: no suma
    visa = tarjetas.crear_tarjeta("Visa", "Galicia", "1234", "ARS", dia_vencimiento=5)
    fijos.registrar("Netflix", "", _ars("1000"), servicios, None, tarjeta_id=visa.id)  # suma una sola vez (en la tarjeta)
    tarjetas.registrar_compra(visa.id, date(2026, 3, 1), "Cena", "", _ars("3000"), cat_tc, 1)  # vence en marzo
    tarjetas.registrar_compra(visa.id, date(2026, 3, 1), "Libro", "", Money.from_decimal("40", Moneda.USD), cat_tc, 1)

    prestamo = prestamos.registrar_prestamo("Auto", "", _ars("12000"), 12, date(2026, 1, 1))
    cuota_marzo = next(c for c in prestamo.cuotas if c.fecha_vencimiento.strftime("%Y-%m") == "2026-03")

    pendiente = DashboardService(conn).resumen(hoy=hoy).pendiente_del_mes

    assert pendiente[Moneda.ARS].amount == 2000 + 1000 + 3000 + cuota_marzo.monto.amount
    assert pendiente[Moneda.USD].amount == 40


def test_pendiente_del_mes_en_cero_si_no_hay_nada(conn):
    pendiente = DashboardService(conn).resumen(hoy=date(2026, 3, 10)).pendiente_del_mes
    assert pendiente[Moneda.ARS].cents == 0 and pendiente[Moneda.USD].cents == 0


# ---------------------------------------------------------------- Gastos fijos

def test_gasto_fijo_guarda_el_metodo_de_pago(conn):
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Alquiler", "", _ars("300000"), _cat(conn, "Casa"), 10, metodo_pago="transferencia")
    assert fijos.obtener(gasto.id).metodo_pago == "transferencia"


def test_metodo_de_pago_invalido_da_error(conn):
    with pytest.raises(ValueError):
        GastoFijoService(conn).registrar("Alquiler", "", _ars("1"), _cat(conn, "Casa"), 10, metodo_pago="trueque")


def test_con_debito_automatico_no_se_guarda_otro_metodo(conn):
    visa = TarjetaService(conn).crear_tarjeta("Visa", "Galicia", "1234", "ARS", dia_vencimiento=5)
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Netflix", "", _ars("1000"), _cat(conn, "Casa"), None, tarjeta_id=visa.id, metodo_pago="efectivo")
    assert fijos.obtener(gasto.id).metodo_pago == ""


def test_editar_gasto_fijo_cambia_todos_los_datos(conn):
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Luz", "Edenor", _ars("5000"), _cat(conn, "Servicios esenciales"), 10, metodo_pago="efectivo")

    fijos.editar(gasto.id, Money.from_decimal("30", Moneda.USD), 20, concepto="  Luz casa ", detalle="Edesur",
                 categoria_id=_cat(conn, "Casa"), metodo_pago="tarjeta_debito")

    editado = fijos.obtener(gasto.id)
    assert (editado.concepto, editado.detalle, editado.categoria_id, editado.metodo_pago, editado.dia_mes) == (
        "Luz casa", "Edesur", _cat(conn, "Casa"), "tarjeta_debito", 20)
    assert editado.monto == Money.from_decimal("30", Moneda.USD)


def test_editar_gasto_fijo_sin_pasar_datos_los_conserva(conn):
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Luz", "Edenor", _ars("5000"), _cat(conn, "Servicios esenciales"), 10, metodo_pago="efectivo")
    fijos.editar(gasto.id, _ars("6000"), 12)
    editado = fijos.obtener(gasto.id)
    assert (editado.concepto, editado.detalle, editado.metodo_pago, editado.monto.amount) == ("Luz", "Edenor", "efectivo", 6000)


def test_editar_gasto_fijo_con_concepto_vacio_da_error(conn):
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Luz", "", _ars("5000"), _cat(conn, "Servicios esenciales"), 10)
    with pytest.raises(ValueError):
        fijos.editar(gasto.id, _ars("5000"), 10, concepto="   ")


def test_editar_no_cambia_los_pagos_ya_registrados(conn):
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Luz", "", _ars("5000"), _cat(conn, "Servicios esenciales"), 10)
    pago = fijos.generar_movimiento_del_mes(gasto.id, date(2026, 3, 20))
    fijos.editar(gasto.id, _ars("7000"), 10, concepto="Electricidad")
    movimiento = MovimientoService(conn).listar()[0]
    assert (movimiento.id, movimiento.concepto, movimiento.monto.amount) == (pago.id, "Luz", 5000)


# ---------------------------------------------------------------- Tarjetas: filtro

def test_filtrar_compras_por_forma_de_pago(conn):
    tarjetas = TarjetaService(conn)
    visa = tarjetas.crear_tarjeta("Visa", "Galicia", "1234", "ARS")
    cat = _cat(conn, "Tarjeta de crédito")
    tarjetas.registrar_compra(visa.id, date(2026, 3, 1), "Cena", "", _ars("3000"), cat, 1)
    tarjetas.registrar_compra(visa.id, date(2026, 3, 1), "Tele", "", _ars("60000"), cat, 6)
    compras = tarjetas.listar_compras(visa.id)

    assert [c.concepto for c in filtrar_por_forma(compras, "cuotas")] == ["Tele"]
    assert [c.concepto for c in filtrar_por_forma(compras, "un_pago")] == ["Cena"]
    assert len(filtrar_por_forma(compras, "todas")) == 2


# ---------------------------------------------------------------- Categorias

def test_quitar_categoria_la_saca_de_la_lista_pero_lo_cargado_la_conserva(conn):
    repo = CategoriaRepository(conn)
    mascotas = _cat(conn, "Mascotas")
    MovimientoService(conn).registrar(TipoMovimiento.EGRESO, date(2026, 3, 1), "Alimento", "", _ars("100"), mascotas)

    repo.quitar(mascotas)

    assert all(c.nombre != "Mascotas" for c in repo.listar())
    assert any(c.nombre == "Mascotas" and not c.activa for c in repo.listar(incluir_quitadas=True))
    assert MovimientoService(conn).listar()[0].categoria_nombre == "Mascotas"


def test_categoria_base_quitada_no_vuelve_al_reabrir_la_app(conn):
    repo = CategoriaRepository(conn)
    repo.quitar(_cat(conn, "Mascotas"))
    init_db(conn)  # lo que pasa al abrir la app
    assert all(c.nombre != "Mascotas" for c in repo.listar())


def test_crear_una_categoria_quitada_la_vuelve_a_agregar(conn):
    repo = CategoriaRepository(conn)
    mascotas = _cat(conn, "Mascotas")
    repo.quitar(mascotas)
    vuelta = repo.crear("Mascotas", "#000000", "pets", TipoMovimiento.EGRESO)
    assert vuelta.id == mascotas and vuelta.activa


def test_no_se_pueden_quitar_las_categorias_que_usa_la_app(conn):
    repo = CategoriaRepository(conn)
    for nombre in ("Tarjeta de crédito", "Inversiones", "Cambio de moneda (recibido)"):
        with pytest.raises(ValueError):
            repo.quitar(_cat(conn, nombre))


def test_tiene_que_quedar_al_menos_una_categoria_de_cada_tipo(conn):
    repo = CategoriaRepository(conn)
    propias = [c for c in repo.listar(TipoMovimiento.INGRESO) if repo.puede_quitarse(c) is None]
    for c in propias[:-1]:
        repo.quitar(c.id)
    with pytest.raises(ValueError):
        repo.quitar(propias[-1].id)
    assert propias[-1].id in {c.id for c in repo.listar(TipoMovimiento.INGRESO)}


def test_usos_cuenta_movimientos_compras_y_gastos_fijos(conn):
    casa = _cat(conn, "Casa")
    MovimientoService(conn).registrar(TipoMovimiento.EGRESO, date(2026, 3, 1), "Pintura", "", _ars("100"), casa)
    GastoFijoService(conn).registrar("Expensas", "", _ars("100"), casa, 10)
    visa = TarjetaService(conn).crear_tarjeta("Visa", "Galicia", "1234", "ARS")
    TarjetaService(conn).registrar_compra(visa.id, date(2026, 3, 1), "Silla", "", _ars("100"), casa, 1)
    assert CategoriaRepository(conn).usos(casa) == 3


# ---------------------------------------------------------------- Compra mensual

def test_busqueda_sin_mayusculas_ni_acentos_y_por_palabras():
    assert coincide_busqueda("Leche descremada", "LECHE")
    assert coincide_busqueda("Azúcar", "azucar")
    assert coincide_busqueda("Leche descremada", "desc leche")
    assert not coincide_busqueda("Leche descremada", "yogur")
    assert coincide_busqueda("Fideos", "   ")  # busqueda vacia: todo


def test_ordenar_productos(conn):
    service = CompraMensualService(conn)
    lista = service.crear_lista(2026, 3)
    service.agregar_local(lista.id, "COTO")
    for nombre in ("Fideos", "Arroz", "Yerba", "Café"):
        service.agregar_producto(lista.id, nombre, Decimal(1))
    lista = service.lista_del_mes(2026, 3)
    coto = lista.locales[0].id
    prod = {p.nombre: p for p in lista.productos}
    for nombre, precio in (("Fideos", "900"), ("Arroz", "1500"), ("Yerba", "3000")):
        service.guardar_precio(prod[nombre].id, coto, _ars(precio), None, "")
    resumen = calcular(service.lista_del_mes(2026, 3))

    def nombres(orden):
        return [p.nombre for p in ordenar_productos(resumen, orden)]

    assert nombres("carga") == ["Fideos", "Arroz", "Yerba", "Café"]
    assert nombres("az") == ["Arroz", "Café", "Fideos", "Yerba"]
    assert nombres("za") == ["Yerba", "Fideos", "Café", "Arroz"]
    assert nombres("barato") == ["Fideos", "Arroz", "Yerba", "Café"]  # sin precio al final
    assert nombres("caro") == ["Yerba", "Arroz", "Fideos", "Café"]
    assert nombres("sin_precio")[0] == "Café"


# ---------------------------------------------------------------- Movimientos: metodo de pago

def test_movimiento_guarda_y_edita_el_metodo_de_pago(conn):
    service = MovimientoService(conn)
    m = service.registrar(TipoMovimiento.EGRESO, date(2026, 3, 1), "Verdulería", "", _ars("100"), _cat(conn, "Comida"),
                          metodo_pago="billetera")
    assert service.obtener(m.id).metodo_pago == "billetera"
    m.metodo_pago = "efectivo"
    service.editar(m)
    assert service.obtener(m.id).metodo_pago == "efectivo"


def test_movimiento_no_acepta_tarjeta_de_credito_como_metodo(conn):
    with pytest.raises(ValueError):
        MovimientoService(conn).registrar(TipoMovimiento.EGRESO, date(2026, 3, 1), "X", "", _ars("100"), _cat(conn, "Comida"),
                                          metodo_pago="tarjeta_credito")


def test_el_pago_de_un_gasto_fijo_lleva_su_metodo_de_pago(conn):
    fijos = GastoFijoService(conn)
    gasto = fijos.registrar("Alquiler", "", _ars("1000"), _cat(conn, "Casa"), 10, metodo_pago="transferencia")
    pago = fijos.generar_movimiento_del_mes(gasto.id, date(2026, 3, 20))
    assert MovimientoService(conn).obtener(pago.id).metodo_pago == "transferencia"


def test_usos_detalle_separa_por_tipo_de_registro(conn):
    casa = _cat(conn, "Casa")
    MovimientoService(conn).registrar(TipoMovimiento.EGRESO, date(2026, 3, 1), "Pintura", "", _ars("100"), casa)
    MovimientoService(conn).registrar(TipoMovimiento.EGRESO, date(2026, 3, 2), "Clavos", "", _ars("100"), casa)
    GastoFijoService(conn).registrar("Expensas", "", _ars("100"), casa, 10)
    assert CategoriaRepository(conn).usos_detalle(casa) == {"movimientos": 2, "compras": 0, "gastos_fijos": 1}


def test_compra_mensual_admite_hasta_5_locales(conn):
    service = CompraMensualService(conn)
    lista = service.crear_lista(2026, 3)
    for nombre in ("A", "B", "C", "D", "E"):
        service.agregar_local(lista.id, nombre)
    with pytest.raises(ValueError, match="hasta 5 locales"):
        service.agregar_local(lista.id, "F")
    assert len(service.lista_del_mes(2026, 3).locales) == 5
