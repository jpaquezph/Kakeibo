from decimal import Decimal

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.compra_mensual import CompraMensualService, calcular


def ars(v):
    return Money.from_decimal(v, Moneda.ARS)


@pytest.fixture
def service(conn):
    return CompraMensualService(conn)


def _armar(service, anio=2026, mes=9):
    lista = service.obtener_o_crear(anio, mes)
    service.agregar_local(lista.id, "COTO")
    service.agregar_local(lista.id, "Carrefour")
    service.agregar_producto(lista.id, "Fideos", Decimal(10))
    service.agregar_producto(lista.id, "Aceite", Decimal(1))
    lista = service.lista_del_mes(anio, mes)
    coto, carrefour = (l.id for l in lista.locales)
    fideos, aceite = (p.id for p in lista.productos)
    return lista, coto, carrefour, fideos, aceite


def test_ejemplo_del_pedido_fideos_mas_baratos_en_coto(service):
    lista, coto, carrefour, fideos, _ = _armar(service)
    service.guardar_precio(fideos, coto, ars("1000"), None, "Luchetti 500g")
    service.guardar_precio(fideos, carrefour, ars("1500"), None, "")

    fila = calcular(service.lista_del_mes(2026, 9)).filas[0]

    assert fila.totales == {coto: ars("10000"), carrefour: ars("15000")}
    assert fila.mas_baratos == {coto}
    assert service.lista_del_mes(2026, 9).precio(fideos, coto).detalle == "Luchetti 500g"


def test_descuento_por_casilla_cambia_el_mas_barato(service):
    _, coto, carrefour, fideos, _ = _armar(service)
    service.guardar_precio(fideos, coto, ars("1000"), None, "")
    service.guardar_precio(fideos, carrefour, ars("1500"), Decimal(50), "2da al 50%")

    fila = calcular(service.lista_del_mes(2026, 9)).filas[0]

    assert fila.totales[carrefour] == ars("7500")
    assert fila.mas_baratos == {carrefour}


def test_totales_por_local_y_total_optimo(service):
    _, coto, carrefour, fideos, aceite = _armar(service)
    service.guardar_precio(fideos, coto, ars("1000"), None, "")
    service.guardar_precio(fideos, carrefour, ars("1500"), None, "")
    service.guardar_precio(aceite, carrefour, ars("5000"), None, "")  # COTO no tiene aceite

    r = calcular(service.lista_del_mes(2026, 9))

    assert r.total_por_local == {coto: ars("10000"), carrefour: ars("20000")}
    assert r.faltantes_por_local == {coto: 1, carrefour: 0}
    assert r.total_optimo == ars("15000")
    assert r.plan_por_local == {coto: (ars("10000"), 1), carrefour: (ars("5000"), 1)}


def test_empate_marca_ambos_y_producto_sin_precio(service):
    _, coto, carrefour, fideos, aceite = _armar(service)
    service.guardar_precio(fideos, coto, ars("1000"), None, "")
    service.guardar_precio(fideos, carrefour, ars("1000"), None, "")

    r = calcular(service.lista_del_mes(2026, 9))

    assert r.filas[0].mas_baratos == {coto, carrefour}
    assert r.filas[1].sin_precio
    assert r.productos_sin_precio == 1
    assert r.total_optimo == ars("10000")
    # el aceite no lo tiene nadie: no cuenta como faltante de ningun local
    assert r.faltantes_por_local == {coto: 0, carrefour: 0}


def test_mes_nuevo_copia_todo_menos_precios_y_descuentos(service):
    _, coto, _, fideos, _ = _armar(service, 2026, 9)
    service.guardar_precio(fideos, coto, ars("1000"), Decimal(10), "Luchetti 500g")

    octubre = service.obtener_o_crear(2026, 10)

    assert [l.nombre for l in octubre.locales] == ["COTO", "Carrefour"]
    assert [(p.nombre, p.cantidad) for p in octubre.productos] == [("Fideos", Decimal(10)), ("Aceite", Decimal(1))]
    celda = octubre.precio(octubre.productos[0].id, octubre.locales[0].id)
    assert (celda.precio, celda.descuento, celda.detalle) == (None, None, "Luchetti 500g")
    # septiembre no se toca
    assert service.lista_del_mes(2026, 9).precio(fideos, coto).precio == ars("1000")


def test_mes_nuevo_copia_del_ultimo_mes_con_lista_aunque_haya_meses_vacios(service):
    _armar(service, 2026, 7)
    diciembre = service.obtener_o_crear(2026, 12)
    assert len(diciembre.productos) == 2


def test_primera_lista_arranca_vacia(service):
    lista = service.obtener_o_crear(2026, 9)
    assert lista.locales == [] and lista.productos == []
    assert lista.titulo == "Septiembre 2026"


def test_validaciones(service):
    lista, coto, _, fideos, _ = _armar(service)
    with pytest.raises(ValueError):
        service.agregar_local(lista.id, " coto ")  # repetido
    with pytest.raises(ValueError):
        service.agregar_producto(lista.id, "Yerba", Decimal(0))
    with pytest.raises(ValueError):
        service.guardar_precio(fideos, coto, ars("100"), Decimal(120), "")


def test_eliminar_local_y_producto_borran_sus_precios(service, conn):
    lista, coto, carrefour, fideos, _ = _armar(service)
    service.guardar_precio(fideos, coto, ars("1000"), None, "")
    service.guardar_precio(fideos, carrefour, ars("1500"), None, "")

    service.eliminar_local(coto)
    service.eliminar_producto(fideos)

    assert conn.execute("SELECT COUNT(*) FROM compra_precios").fetchone()[0] == 0
    assert [l.nombre for l in service.lista_del_mes(2026, 9).locales] == ["Carrefour"]


def _categoria(conn, nombre="Comida"):
    from home_budget.app.repositories.categorias import CategoriaRepository
    return next(c.id for c in CategoriaRepository(conn).listar() if c.nombre == nombre)


def test_registrar_como_egreso_y_deshacer(service, conn):
    from datetime import date
    from home_budget.app.services.movimientos import MovimientoService

    lista = service.obtener_o_crear(2026, 9)
    service.registrar_egreso(lista.id, date(2026, 9, 5), "Compra mensual Septiembre 2026", ars("62500"),
                             _categoria(conn), "Egreso · Comida")

    registro = service.registros(lista.id)[0]
    mov = MovimientoService(conn).obtener(registro.referencia_id)
    assert (registro.tipo, registro.monto, mov.monto, mov.concepto) == ("egreso", ars("62500"), ars("62500"), "Compra mensual Septiembre 2026")

    service.deshacer_registro(registro.id)
    assert service.registros(lista.id) == [] and MovimientoService(conn).listar() == []


def test_registrar_en_tarjeta_en_cuotas_con_tarjeta_cerrada(service, conn):
    from datetime import date
    from home_budget.app.services.tarjetas import TarjetaService

    tarjetas = TarjetaService(conn)
    visa = tarjetas.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS)
    lista = service.obtener_o_crear(2026, 9)

    service.registrar_en_tarjeta(lista.id, visa.id, date(2026, 9, 10), "Compra mensual", ars("60000"), _categoria(conn), 3, True)

    registro = service.registros(lista.id)[0]
    compra = tarjetas.obtener_compra(registro.referencia_id)
    assert registro.descripcion == "Visa · 3 cuotas"
    assert [c.fecha_vencimiento for c in compra.cuotas] == [date(2026, 11, 10), date(2026, 12, 10), date(2027, 1, 10)]

    service.deshacer_registro(registro.id)
    assert tarjetas.listar_compras(visa.id) == []


def test_registro_valida_monto_y_moneda_de_la_tarjeta(service, conn):
    from datetime import date
    from home_budget.app.services.tarjetas import TarjetaService

    amex = TarjetaService(conn).crear_tarjeta("Amex", "Banco", "9999", Moneda.USD)
    lista = service.obtener_o_crear(2026, 9)
    with pytest.raises(ValueError):
        service.registrar_egreso(lista.id, date(2026, 9, 5), "Compra", ars("0"), _categoria(conn), "")
    with pytest.raises(ValueError):
        service.registrar_en_tarjeta(lista.id, amex.id, date(2026, 9, 5), "Compra", ars("100"), _categoria(conn))
    assert service.registros(lista.id) == []
