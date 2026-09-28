from datetime import date

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.tarjetas import TarjetaService


def _categoria_id(conn, nombre="Tarjeta de crédito"):
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    return cats[nombre]


def test_crear_tarjeta_con_moneda_como_string(conn):
    """Regresion: el dropdown de la UI entrega la moneda como string plano
    (ej. 'ARS'), no como Moneda. El servicio debe normalizarlo igual."""
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", "ARS")

    assert tarjeta.moneda == Moneda.ARS
    recargada = service.listar_tarjetas()[0]
    assert recargada.moneda == Moneda.ARS


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


def test_tarjeta_guarda_el_color_elegido(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS, color="#2A78D6")

    assert tarjeta.color == "#2A78D6"
    recargada = service.listar_tarjetas()[0]
    assert recargada.color == "#2A78D6"


def test_compra_con_cuota_inicial_marca_las_anteriores_como_pagadas(conn):
    """Ej: compraste una heladera hace 3 meses y recien ahora cargas la app:
    debes poder indicar que arrancas en la cuota 3 de 12."""
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(
        tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("120000", Moneda.ARS),
        _categoria_id(conn), cantidad_cuotas=12, cuota_inicial=3,
    )

    assert compra.cuotas_pagadas == 2
    assert compra.cuota_actual == 3
    assert compra.cuotas_restantes == 10
    assert compra.cuotas[0].pagada and compra.cuotas[1].pagada
    assert not compra.cuotas[2].pagada


def test_cuota_inicial_invalida_lanza_error(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    with pytest.raises(ValueError):
        service.registrar_compra(
            tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("1000", Moneda.ARS),
            _categoria_id(conn), cantidad_cuotas=6, cuota_inicial=7,
        )


def test_cuotas_marcadas_pagadas_por_cuota_inicial_guardan_fecha_de_pago(conn):
    """Regresion: el INSERT de cuotas no persistia fecha_pago, asi que una
    cuota marcada como pagada via cuota_inicial quedaba sin fecha al releer."""
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(
        tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("1200", Moneda.ARS),
        _categoria_id(conn), cantidad_cuotas=6, cuota_inicial=3,
    )
    recargada = service.obtener_compra(compra.id)
    assert recargada.cuotas[0].fecha_pago is not None
    assert recargada.cuotas[1].fecha_pago is not None
    assert recargada.cuotas[2].fecha_pago is None


def test_editar_tarjeta(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS, color="#D6467E")

    editada = service.editar_tarjeta(tarjeta.id, "Visa Naranja", "Banco Naranja", "5678", "USD", "#EB6834")

    assert editada.nombre == "Visa Naranja"
    assert editada.banco == "Banco Naranja"
    assert editada.ultimos_digitos == "5678"
    assert editada.moneda == Moneda.USD
    assert editada.color == "#EB6834"
    recargada = service.listar_tarjetas()[0]
    assert recargada.nombre == "Visa Naranja"
    assert recargada.color == "#EB6834"


def test_total_pendiente_de_una_tarjeta(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    service.registrar_compra(tarjeta.id, date(2026, 1, 1), "Cena", "", Money.from_decimal("1000", Moneda.ARS), _categoria_id(conn), 1)
    compra_cuotas = service.registrar_compra(tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("6000", Moneda.ARS), _categoria_id(conn), 6)

    assert service.total_pendiente(tarjeta.id).amount == 7000

    service.pagar_cuota(compra_cuotas.cuotas[0].id)
    assert service.total_pendiente(tarjeta.id).amount == 6000


def test_pagar_cuotas_del_mes_marca_solo_las_que_vencen_ese_mes(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    compra = service.registrar_compra(
        tarjeta.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("6000", Moneda.ARS), _categoria_id(conn), 6
    )
    service.registrar_compra(tarjeta.id, date(2026, 2, 1), "Cena", "", Money.from_decimal("500", Moneda.ARS), _categoria_id(conn), 1)

    cantidad = service.pagar_cuotas_del_mes(tarjeta.id, 2026, 2)

    assert cantidad == 2  # la 1ra cuota de la heladera (vence en feb) + la cena (1 pago en feb)
    recargada = service.obtener_compra(compra.id)
    assert recargada.cuotas[0].pagada
    assert not recargada.cuotas[1].pagada


def test_editar_datos_compra(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Galicia", "1234", Moneda.ARS)
    cat_original = _categoria_id(conn, "Tarjeta de crédito")
    cat_nueva = _categoria_id(conn, "Comida")
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 1), "Super", "", Money.from_decimal("500", Moneda.ARS), cat_original, 1)

    editada = service.editar_datos_compra(compra.id, "Supermercado (corregido)", "detalle nuevo", cat_nueva)

    assert editada.concepto == "Supermercado (corregido)"
    assert editada.categoria_id == cat_nueva


def test_vencimiento_cuota_con_tarjeta_cerrada_se_corre_un_mes():
    from home_budget.app.services.tarjetas import vencimiento_cuota

    compra = date(2026, 1, 15)
    assert vencimiento_cuota(compra, 1, 3) == date(2026, 2, 15)
    assert vencimiento_cuota(compra, 1, 3, tarjeta_cerrada=True) == date(2026, 3, 15)
    assert vencimiento_cuota(compra, 3, 3, tarjeta_cerrada=True) == date(2026, 5, 15)
    assert vencimiento_cuota(compra, 1, 1) == compra
    assert vencimiento_cuota(compra, 1, 1, tarjeta_cerrada=True) == date(2026, 2, 15)


def test_registrar_compra_con_tarjeta_cerrada(conn):
    from home_budget.app.repositories.categorias import CategoriaRepository
    from home_budget.app.services.tarjetas import TarjetaService

    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS)
    cat = CategoriaRepository(conn).listar()[0].id
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 10), "TV", "", Money.from_decimal("3000", Moneda.ARS), cat, 3, tarjeta_cerrada=True)

    assert [c.fecha_vencimiento for c in compra.cuotas] == [date(2026, 3, 10), date(2026, 4, 10), date(2026, 5, 10)]


def test_eliminar_tarjeta_con_compras_borra_compras_y_cuotas(conn):
    service = TarjetaService(conn)
    tarjeta = service.crear_tarjeta("Visa", "Banco", "1234", Moneda.ARS)
    otra = service.crear_tarjeta("Master", "Banco", "5678", Moneda.ARS)
    cat = CategoriaRepository(conn).listar()[0].id
    compra = service.registrar_compra(tarjeta.id, date(2026, 1, 10), "TV", "", Money.from_decimal("3000", Moneda.ARS), cat, 3)
    service.pagar_cuota(compra.cuotas[0].id)
    service.registrar_compra(otra.id, date(2026, 1, 10), "Súper", "", Money.from_decimal("100", Moneda.ARS), cat, 1)

    service.eliminar_tarjeta(tarjeta.id)

    assert service.obtener_tarjeta(tarjeta.id) is None
    assert conn.execute("SELECT COUNT(*) FROM cuotas_compra").fetchone()[0] == 1  # solo la cuota de la otra tarjeta
    assert len(service.listar_compras(otra.id)) == 1  # las otras tarjetas no se tocan
