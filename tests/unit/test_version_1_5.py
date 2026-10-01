"""Kakeibo 1.5: Compra mensual con copiar de otro mes y cerrar / reabrir."""
from datetime import date
from decimal import Decimal

import pytest

from home_budget.app.database import init_db
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.compra_mensual import MAX_LOCALES, CompraMensualService


def ars(v):
    return Money.from_decimal(v, Moneda.ARS)


@pytest.fixture
def service(conn):
    return CompraMensualService(conn)


def _categoria(conn, nombre="Comida"):
    from home_budget.app.repositories.categorias import CategoriaRepository
    return next(c.id for c in CategoriaRepository(conn).listar() if c.nombre == nombre)


def _septiembre(service):
    lista = service.obtener_o_crear(2026, 9)
    service.agregar_local(lista.id, "COTO")
    service.agregar_local(lista.id, "Día")
    service.agregar_producto(lista.id, "Fideos", Decimal(10))
    service.agregar_producto(lista.id, "Aceite", Decimal(1))
    lista = service.lista_del_mes(2026, 9)
    coto, dia = (l.id for l in lista.locales)
    fideos, aceite = (p.id for p in lista.productos)
    service.guardar_precio(fideos, coto, ars("1000"), None, "Matarazzo")
    service.guardar_precio(fideos, dia, ars("1200"), None, "")
    service.guardar_precio(aceite, coto, ars("3000"), Decimal(10), "Natura 1,5 l")
    return lista


# --- copiar de otro mes ---

def test_copiar_a_una_lista_que_ya_existe_vacia(service):
    """El caso del usuario: octubre se creo vacio antes de cargar septiembre."""
    octubre = service.obtener_o_crear(2026, 10)
    septiembre = _septiembre(service)

    assert service.copiar_de(octubre.id, septiembre.id) == (2, 2)
    octubre = service.lista_del_mes(2026, 10)
    assert [l.nombre for l in octubre.locales] == ["COTO", "Día"]
    assert [(p.nombre, p.cantidad) for p in octubre.productos] == [("Fideos", Decimal(10)), ("Aceite", Decimal(1))]
    # Sin precios ni descuentos; el detalle (marca) si
    celdas = list(octubre.precios.values())
    assert all(c.precio is None and c.descuento is None for c in celdas)
    assert sorted(c.detalle for c in celdas) == ["Matarazzo", "Natura 1,5 l"]


def test_copiar_no_duplica_y_respeta_lo_cargado(service):
    octubre = service.obtener_o_crear(2026, 10)
    septiembre = _septiembre(service)
    service.agregar_local(octubre.id, "coto")
    service.agregar_producto(octubre.id, "FIDEOS", Decimal(3))

    assert service.copiar_de(octubre.id, septiembre.id) == (1, 1)
    octubre = service.lista_del_mes(2026, 10)
    assert [l.nombre for l in octubre.locales] == ["coto", "Día"]
    assert [(p.nombre, p.cantidad) for p in octubre.productos] == [("FIDEOS", Decimal(3)), ("Aceite", Decimal(1))]
    # Copiar dos veces no agrega nada
    assert service.copiar_de(octubre.id, septiembre.id) == (0, 0)


def test_copiar_solo_locales_o_solo_productos(service):
    octubre = service.obtener_o_crear(2026, 10)
    septiembre = _septiembre(service)
    assert service.copiar_de(octubre.id, septiembre.id, locales=True, productos=False) == (2, 0)
    assert service.copiar_de(octubre.id, septiembre.id, locales=False, productos=True) == (0, 2)
    with pytest.raises(ValueError):
        service.copiar_de(octubre.id, septiembre.id, locales=False, productos=False)
    with pytest.raises(ValueError):
        service.copiar_de(octubre.id, octubre.id)


def test_copiar_respeta_el_maximo_de_locales(service):
    destino = service.obtener_o_crear(2026, 10)
    origen = service.obtener_o_crear(2026, 9)
    for i in range(MAX_LOCALES):
        service.agregar_local(origen.id, f"Origen {i}")
    service.agregar_local(destino.id, "Propio")
    copiados, _ = service.copiar_de(destino.id, origen.id, productos=False)
    assert copiados == MAX_LOCALES - 1
    assert len(service.lista_del_mes(2026, 10).locales) == MAX_LOCALES


# --- cerrar y reabrir ---

def test_cerrar_guarda_el_resumen_y_no_permite_editar(service, conn):
    septiembre = _septiembre(service)
    service.registrar_egreso(septiembre.id, date(2026, 9, 20), "Compra", ars("15000"), _categoria(conn), "Egreso")

    info = service.cerrar_lista(septiembre.id, hoy=date(2026, 10, 1))
    assert info.cerrada and info.cerrada_at == date(2026, 10, 1)
    assert (info.cantidad_productos, info.cantidad_locales) == (2, 2)
    assert info.total_optimo == ars("12700")          # fideos 10x1000 + aceite 3000 -10 %
    assert info.total_registrado == ars("15000")
    assert info.total == ars("15000")                 # se muestra lo registrado
    assert service.listas(solo_cerradas=True)[0].id == septiembre.id

    lista = service.detalle(septiembre.id)
    local, producto = lista.locales[0], lista.productos[0]
    registro = service.registros(septiembre.id)[0]
    for intento in (
        lambda: service.agregar_local(septiembre.id, "Jumbo"),
        lambda: service.renombrar_local(local.id, "Otro"),
        lambda: service.eliminar_local(local.id),
        lambda: service.agregar_producto(septiembre.id, "Arroz", Decimal(1)),
        lambda: service.editar_producto(producto.id, "Otro", Decimal(1)),
        lambda: service.eliminar_producto(producto.id),
        lambda: service.guardar_precio(producto.id, local.id, ars("1"), None, ""),
        lambda: service.registrar_egreso(septiembre.id, date(2026, 9, 21), "Otra", ars("1"), _categoria(conn), ""),
        lambda: service.deshacer_registro(registro.id),
        lambda: service.copiar_de(septiembre.id, service.obtener_o_crear(2026, 10).id),
        lambda: service.cerrar_lista(septiembre.id),
    ):
        with pytest.raises(ValueError):
            intento()
    # Nada cambio: el detalle sigue completo para consultarlo
    assert service.detalle(septiembre.id) == lista


def test_sin_registros_el_total_es_el_mas_barato(service):
    septiembre = _septiembre(service)
    info = service.cerrar_lista(septiembre.id)
    assert info.total_registrado == ars("0") and info.total == ars("12700")


def test_reabrir_vuelve_a_la_lista_editable_sin_duplicar(service, conn):
    septiembre = _septiembre(service)
    antes = service.detalle(septiembre.id)
    service.cerrar_lista(septiembre.id)
    service.reabrir_lista(septiembre.id)

    info = service.info_del_mes(2026, 9)
    assert not info.cerrada and info.cerrada_at is None and info.total is None
    assert service.lista_del_mes(2026, 9) == antes
    assert conn.execute("SELECT COUNT(*) FROM compra_listas").fetchone()[0] == 1
    service.agregar_producto(septiembre.id, "Arroz", Decimal(2))  # se puede editar de nuevo
    assert len(service.lista_del_mes(2026, 9).productos) == 3


def test_copiar_desde_una_lista_cerrada(service):
    octubre = service.obtener_o_crear(2026, 10)
    septiembre = _septiembre(service)
    service.cerrar_lista(septiembre.id)
    assert service.copiar_de(octubre.id, septiembre.id) == (2, 2)


def test_el_estado_queda_guardado_en_la_base(conn, tmp_path):
    service = CompraMensualService(conn)
    septiembre = _septiembre(service)
    service.cerrar_lista(septiembre.id)
    init_db(conn)  # volver a abrir la app no la reabre ni pierde el resumen
    info = CompraMensualService(conn).info_del_mes(2026, 9)
    assert info.cerrada and info.total_optimo == ars("12700")


def test_listas_existentes_quedan_abiertas_al_migrar(tmp_path):
    """Una base de antes de la 1.5 (sin las columnas nuevas) queda con todo abierto."""
    import sqlite3
    from home_budget.app.database import MIGRATIONS_DIR, get_connection

    db = tmp_path / "vieja.db"
    vieja = sqlite3.connect(db)
    vieja.executescript((MIGRATIONS_DIR / "003_compra_mensual.sql").read_text(encoding="utf-8"))
    vieja.execute("INSERT INTO compra_listas (anio, mes) VALUES (2026, 9)")
    vieja.commit()
    vieja.close()

    conn = get_connection(db)
    init_db(conn)
    info = CompraMensualService(conn).info_del_mes(2026, 9)
    assert info is not None and not info.cerrada
    conn.close()
