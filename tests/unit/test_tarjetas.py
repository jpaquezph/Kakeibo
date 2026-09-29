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


def test_misma_tarjeta_en_pesos_y_en_dolares(conn):
    """Regresion: una tarjeta que acepta ARS y USD se carga dos veces con el
    mismo nombre; antes rompia por el UNIQUE sobre 'nombre'."""
    service = TarjetaService(conn)
    ars = service.crear_tarjeta("Visa", "Galicia", "1234", "ARS")
    usd = service.crear_tarjeta("Visa", "Galicia", "1234", "USD")

    assert ars.id != usd.id
    assert {t.moneda for t in service.listar_tarjetas()} == {Moneda.ARS, Moneda.USD}


def test_tarjeta_duplicada_en_la_misma_moneda_da_error_legible(conn):
    service = TarjetaService(conn)
    service.crear_tarjeta("Visa", "Galicia", "1234", "ARS")
    otra = service.crear_tarjeta("Master", "Galicia", "5678", "ARS")

    with pytest.raises(ValueError, match="Ya existe"):
        service.crear_tarjeta("Visa", "Galicia", "1234", "ARS")
    with pytest.raises(ValueError, match="Ya existe"):
        service.editar_tarjeta(otra.id, "Visa", "Galicia", "5678", "ARS", otra.color)
    assert len(service.listar_tarjetas()) == 2


def test_migra_base_vieja_con_nombre_unico(tmp_path):
    from home_budget.app.database import get_connection, init_db

    vieja = get_connection(tmp_path / "vieja.db")
    init_db(vieja)
    # Simula el esquema anterior: nombre UNIQUE.
    vieja.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE tarjetas;
        CREATE TABLE tarjetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            banco TEXT NOT NULL DEFAULT '',
            ultimos_digitos TEXT NOT NULL DEFAULT '',
            moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
            color TEXT NOT NULL DEFAULT '#D6467E',
            activa INTEGER NOT NULL DEFAULT 1
        );
        PRAGMA foreign_keys = ON;
        """
    )
    # Datos cargados con la version anterior (sin dia de cierre/vencimiento).
    visa_id = vieja.execute(
        "INSERT INTO tarjetas (nombre, banco, ultimos_digitos, moneda, color) VALUES ('Visa', 'Galicia', '1234', 'ARS', '#123456')"
    ).lastrowid
    vieja.commit()
    service = TarjetaService(vieja)
    service.registrar_compra(visa_id, date(2026, 1, 1), "Compra", "", Money.from_decimal("100", Moneda.ARS), _categoria_id(vieja), 3)

    init_db(vieja)  # al reabrir la app

    service = TarjetaService(vieja)
    usd = service.crear_tarjeta("Visa", "Galicia", "1234", "USD")
    recargada = service.obtener_tarjeta(visa_id)
    assert recargada.color == "#123456"
    assert recargada.dia_vencimiento is None
    assert len(service.listar_compras(visa_id)) == 1
    assert usd.id != visa_id
    assert vieja.execute("PRAGMA foreign_key_check").fetchall() == []
    assert vieja.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    vieja.close()


def test_tarjeta_guarda_dia_de_cierre_y_vencimiento(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234", "ARS", dia_cierre=24, dia_vencimiento=5)

    assert (service.obtener_tarjeta(visa.id).dia_cierre, service.obtener_tarjeta(visa.id).dia_vencimiento) == (24, 5)

    service.editar_tarjeta(visa.id, "Visa", "Galicia", "1234", "ARS", visa.color)  # sin pasarlos, se mantienen
    assert service.obtener_tarjeta(visa.id).dia_vencimiento == 5
    service.editar_tarjeta(visa.id, "Visa", "Galicia", "1234", "ARS", visa.color, dia_cierre=None, dia_vencimiento=None)
    assert service.obtener_tarjeta(visa.id).dia_vencimiento is None

    with pytest.raises(ValueError, match="entre 1 y 31"):
        service.crear_tarjeta("Amex", "BBVA", "", "USD", dia_vencimiento=32)


def test_una_tarjeta_opera_en_pesos_y_en_dolares(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    cat = _categoria_id(conn)
    service.registrar_compra(visa.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("900", Moneda.ARS), cat, 3)
    service.registrar_compra(visa.id, date(2026, 1, 1), "Libro", "", Money.from_decimal("30", Moneda.USD), cat, 1)

    assert service.total_pendiente(visa.id, Moneda.ARS) == Money.from_decimal("900", Moneda.ARS)
    assert service.total_pendiente(visa.id, Moneda.USD) == Money.from_decimal("30", Moneda.USD)
    assert {c.monto_total.moneda for c in service.listar_compras(visa.id)} == {Moneda.ARS, Moneda.USD}


def test_resumen_separa_el_pendiente_de_la_tarjeta_por_moneda(conn):
    from home_budget.app.services.dashboard import DashboardService

    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    cat = _categoria_id(conn)
    service.registrar_compra(visa.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("900", Moneda.ARS), cat, 1)
    service.registrar_compra(visa.id, date(2026, 1, 1), "Libro", "", Money.from_decimal("30", Moneda.USD), cat, 1)

    por_tarjeta = DashboardService(conn).resumen(hoy=date(2026, 1, 20)).por_tarjeta
    assert [(tt.nombre, tt.moneda, tt.total_pendiente) for tt in por_tarjeta] == [
        ("Visa", Moneda.ARS, Money.from_decimal("900", Moneda.ARS)),
        ("Visa", Moneda.USD, Money.from_decimal("30", Moneda.USD)),
    ]


def test_une_la_tarjeta_cargada_dos_veces_una_por_moneda(tmp_path):
    """Antes de la 1.3 una tarjeta en ARS y USD se cargaba dos veces. Al abrir
    la base se unen: compras, debitos y movimientos pasan a la original, la
    copia se borra y antes queda un backup de la base."""
    from home_budget.app.database import get_connection, init_db
    from home_budget.app.services.gastos_fijos import GastoFijoService

    db = tmp_path / "kakeibo.db"
    conn = get_connection(db)
    init_db(conn)
    service, fijos = TarjetaService(conn), GastoFijoService(conn)
    cat = _categoria_id(conn)
    ars = service.crear_tarjeta("Galicia", "Master", "9475", Moneda.ARS, dia_vencimiento=None)
    usd = service.crear_tarjeta("Galicia ", "master", "9475", Moneda.USD, dia_cierre=20, dia_vencimiento=5)
    otra = service.crear_tarjeta("BNA", "Visa", "0948", Moneda.ARS)
    service.registrar_compra(ars.id, date(2026, 1, 1), "Heladera", "", Money.from_decimal("900", Moneda.ARS), cat, 3)
    service.registrar_compra(usd.id, date(2026, 1, 1), "Libro", "", Money.from_decimal("30", Moneda.USD), cat, 1)
    spotify = fijos.registrar("Spotify", "", Money.from_decimal("11", Moneda.USD), cat, None, tarjeta_id=usd.id)

    init_db(conn)  # al abrir la version nueva

    assert [t.id for t in service.listar_tarjetas()] == [otra.id, ars.id]  # ordenadas por nombre
    unida = service.obtener_tarjeta(ars.id)
    assert (unida.dia_cierre, unida.dia_vencimiento) == (20, 5)  # tomados de la copia
    assert len(service.listar_compras(ars.id)) == 2
    assert fijos.obtener(spotify.id).tarjeta_id == ars.id
    assert service.total_pendiente(ars.id, Moneda.USD) == Money.from_decimal("30", Moneda.USD)
    backups = list(tmp_path.glob("kakeibo_antes-de-unir-tarjetas_*.db"))
    assert len(backups) == 1
    with get_connection(backups[0]) as copia:
        assert copia.execute("SELECT COUNT(*) FROM tarjetas").fetchone()[0] == 3

    init_db(conn)  # abrir de nuevo no hace nada mas: sin otra copia de backup
    assert len(list(tmp_path.glob("kakeibo_antes-de-unir-tarjetas_*.db"))) == 1
    conn.close()


def test_editar_compra_cambia_todo_y_recalcula_las_cuotas(conn):
    """Si el usuario se equivoco al cargar, puede corregir monto, cuotas,
    tarjeta y fecha: las cuotas pendientes se rearman y las ya pagadas no se
    modifican."""
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    master = service.crear_tarjeta("Master", "BBVA", "5678")
    compra = service.registrar_compra(visa.id, date(2026, 1, 10), "Heladera", "", Money.from_decimal("600", Moneda.ARS),
                                      _categoria_id(conn), 3)
    service.pagar_cuota(compra.cuotas[0].id, date(2026, 2, 3))

    editada = service.editar_compra(compra.id, master.id, date(2026, 1, 12), "Heladera no frost", "Samsung",
                                    Money.from_decimal("1200", Moneda.ARS), 6, 1)

    assert (editada.tarjeta_id, editada.fecha, editada.concepto, editada.detalle) == (master.id, date(2026, 1, 12), "Heladera no frost", "Samsung")
    assert editada.monto_total == Money.from_decimal("1200", Moneda.ARS)
    assert [c.monto for c in editada.cuotas] == [Money.from_decimal("200", Moneda.ARS)] * 6
    assert [c.pagada for c in editada.cuotas] == [True] + [False] * 5
    assert editada.cuotas[0].fecha_pago == date(2026, 2, 3)  # la fecha real del pago se conserva
    assert editada.cuotas[1].fecha_vencimiento == date(2026, 3, 12)
    assert service.listar_compras(visa.id) == []


def test_editar_compra_de_cuotas_a_un_pago_en_dolares(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 1, 10), "Libro", "", Money.from_decimal("600", Moneda.ARS),
                                      _categoria_id(conn), 3, tarjeta_cerrada=True)
    assert service.tarjeta_estaba_cerrada(compra)

    editada = service.editar_compra(compra.id, visa.id, compra.fecha, "Libro", "", Money.from_decimal("30", Moneda.USD), 1, 0)

    assert editada.cantidad_cuotas == 1 and len(editada.cuotas) == 1
    assert editada.monto_total.moneda == Moneda.USD
    assert not service.tarjeta_estaba_cerrada(editada)


def test_editar_compra_valida_los_datos(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 1, 10), "Libro", "", Money.from_decimal("600", Moneda.ARS), _categoria_id(conn), 3)

    with pytest.raises(ValueError, match="pagadas"):
        service.editar_compra(compra.id, visa.id, compra.fecha, "Libro", "", compra.monto_total, 3, 4)
    with pytest.raises(ValueError, match="concepto"):
        service.editar_compra(compra.id, visa.id, compra.fecha, "  ", "", compra.monto_total, 3, 0)
    assert len(service.obtener_compra(compra.id).cuotas) == 3  # sin cambios si falla


def test_editar_compra_no_modifica_las_cuotas_pagadas(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 1, 10), "Tele", "", Money.from_decimal("600", Moneda.ARS), _categoria_id(conn), 3)
    pagada = compra.cuotas[0]
    service.pagar_cuota(pagada.id, date(2026, 2, 3))

    editada = service.editar_compra(compra.id, visa.id, date(2026, 1, 20), "Tele", "", Money.from_decimal("900", Moneda.ARS), 3, 1)

    primera = editada.cuotas[0]
    assert (primera.monto, primera.fecha_vencimiento, primera.fecha_pago, primera.pagada) == (
        pagada.monto, pagada.fecha_vencimiento, date(2026, 2, 3), True)
    assert [c.monto for c in editada.cuotas[1:]] == [Money.from_decimal("350", Moneda.ARS)] * 2  # (900 - 200) / 2
    assert editada.cuotas[1].fecha_vencimiento == date(2026, 3, 20)


def test_editar_compra_con_cuotas_pagadas_valida_el_monto(conn):
    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    compra = service.registrar_compra(visa.id, date(2026, 1, 10), "Tele", "", Money.from_decimal("600", Moneda.ARS),
                                      _categoria_id(conn), 3, cuota_inicial=3)  # 2 pagadas: 400

    with pytest.raises(ValueError, match="mayor a lo ya pagado"):
        service.editar_compra(compra.id, visa.id, compra.fecha, "Tele", "", Money.from_decimal("400", Moneda.ARS), 3, 2)
    with pytest.raises(ValueError, match="moneda"):
        service.editar_compra(compra.id, visa.id, compra.fecha, "Tele", "", Money.from_decimal("600", Moneda.USD), 3, 2)
    with pytest.raises(ValueError, match="menos cuotas pagadas"):
        service.editar_compra(compra.id, visa.id, compra.fecha, "Tele", "", Money.from_decimal("700", Moneda.ARS), 2, 2)
    # indicando menos cuotas pagadas, se puede
    editada = service.editar_compra(compra.id, visa.id, compra.fecha, "Tele", "", Money.from_decimal("700", Moneda.ARS), 2, 1)
    assert [c.monto for c in editada.cuotas] == [Money.from_decimal("200", Moneda.ARS), Money.from_decimal("500", Moneda.ARS)]


def test_compra_cargada_por_valor_de_cuota(conn):
    """En cuotas se puede cargar el valor de la cuota: el total es cuota x
    cantidad y cada cuota queda exactamente en ese valor."""
    from home_budget.app.services.tarjetas import monto_total_desde_cuota

    service = TarjetaService(conn)
    visa = service.crear_tarjeta("Visa", "Galicia", "1234")
    total = monto_total_desde_cuota(Money.from_decimal("33333.33", Moneda.ARS), 12)
    assert total == Money.from_decimal("399999.96", Moneda.ARS)

    compra = service.registrar_compra(visa.id, date(2026, 1, 10), "Tele", "", total, _categoria_id(conn), 12)
    assert {c.monto for c in compra.cuotas} == {Money.from_decimal("33333.33", Moneda.ARS)}
