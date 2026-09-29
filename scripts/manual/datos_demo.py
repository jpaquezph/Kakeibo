"""Base de ejemplo para las capturas del manual (datos ficticios)."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROYECTO))

from home_budget.app.auth.service import AuthService  # noqa: E402
from home_budget.app.database import get_connection, init_db  # noqa: E402
from home_budget.app.domain.models import TipoMovimiento  # noqa: E402
from home_budget.app.domain.money import Money, Moneda  # noqa: E402
from home_budget.app.repositories.categorias import CategoriaRepository  # noqa: E402
from home_budget.app.services.cambio import CambioDivisaService  # noqa: E402
from home_budget.app.services.compra_mensual import CompraMensualService  # noqa: E402
from home_budget.app.services.gastos_fijos import GastoFijoService  # noqa: E402
from home_budget.app.services.inversiones import (  # noqa: E402
    Ahorro, Fci, InversionService, OperacionCrypto, OperacionCryptoRegistro, Plazo, TipoTitulo, Titulo,
)
from home_budget.app.services.movimientos import MovimientoService  # noqa: E402
from home_budget.app.services.prestamos import PrestamoService  # noqa: E402
from home_budget.app.services.tarjetas import TarjetaService  # noqa: E402

USUARIO, CLAVE = "ana", "ana12345"


def ars(v):
    return Money.from_decimal(Decimal(str(v)), Moneda.ARS)


def usd(v):
    return Money.from_decimal(Decimal(str(v)), Moneda.USD)


def crear(db: Path) -> None:
    if db.exists():
        db.unlink()
    conn = get_connection(db)
    init_db(conn)
    AuthService(conn).crear_usuario(USUARIO, CLAVE, "¿Nombre de tu primera mascota?", "Toby")
    AuthService(conn).crear_usuario("martin", "martin123", "¿Ciudad donde naciste?", "Rosario")
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    ms, ts, gf, ps = MovimientoService(conn), TarjetaService(conn), GastoFijoService(conn), PrestamoService(conn)
    E, I = TipoMovimiento.EGRESO, TipoMovimiento.INGRESO

    # --- movimientos de agosto y septiembre ---
    for f, tipo, concepto, detalle, monto, cat in [
        (date(2026, 8, 1), I, "Sueldo", "Agosto", ars(1750000), "Sueldo"),
        (date(2026, 9, 1), I, "Sueldo", "Septiembre", ars(1800000), "Sueldo"),
        (date(2026, 9, 12), I, "Trabajo freelance", "Diseño de logo para cliente", usd(450), "Extra"),
        (date(2026, 9, 3), E, "Supermercado", "Compra semanal en Coto", ars(98500), "Comida"),
        (date(2026, 9, 10), E, "Supermercado", "Día", ars(64300), "Comida"),
        (date(2026, 9, 17), E, "Verdulería", "", ars(18200), "Comida"),
        (date(2026, 9, 6), E, "Farmacia", "Antibiótico y vitaminas", ars(23500), "Farmacia"),
        (date(2026, 9, 8), E, "Nafta", "YPF, tanque lleno", ars(62000), "Auto"),
        (date(2026, 9, 13), E, "Cena con amigos", "Cumpleaños de Sofi", ars(45000), "Salidas"),
        (date(2026, 9, 20), E, "Veterinaria", "Vacuna antirrábica de Toby", ars(28000), "Mascotas"),
        (date(2026, 9, 22), E, "Ferretería", "Lámparas LED", ars(15800), "Casa"),
        (date(2026, 8, 15), E, "Supermercado", "", ars(112000), "Comida"),
        (date(2026, 8, 20), E, "Cine", "", ars(21000), "Salidas"),
    ]:
        ms.registrar(tipo, f, concepto, detalle, monto, cats[cat])
    CambioDivisaService(conn).comprar_dolares(date(2026, 9, 5), usd(300), Decimal("1350"))

    # --- tarjetas y compras ---
    visa = ts.crear_tarjeta("Visa Galicia", "Galicia", "4821", color="#1F4E79", dia_cierre=24, dia_vencimiento=5)
    master = ts.crear_tarjeta("Mastercard BBVA", "BBVA", "1934", color="#D6467E", dia_cierre=20, dia_vencimiento=2)
    ts.crear_tarjeta("Amex", "Santander", "7002", color="#2E7D6B")
    tc = cats["Tarjeta de crédito"]
    ts.registrar_compra(visa.id, date(2026, 6, 15), "Heladera", "Samsung no frost 360 L", ars(1200000), tc, 6, cuota_inicial=4)
    ts.registrar_compra(visa.id, date(2026, 8, 28), "Zapatillas", "Nike Pegasus, talle 42", ars(180000), tc, 3)
    ts.registrar_compra(visa.id, date(2026, 9, 9), "Supermercado", "Compra grande del mes", ars(85000), tc, 1)
    ts.registrar_compra(visa.id, date(2026, 9, 14), "Libros", "Amazon, dos novelas", usd(38), tc, 1)
    ts.registrar_compra(visa.id, date(2026, 7, 2), "Notebook", "Lenovo IdeaPad para la facu", ars(1440000), tc, 12, cuota_inicial=3)
    ts.registrar_compra(master.id, date(2026, 5, 10), "Televisor", "LG 55 pulgadas", ars(960000), tc, 12, cuota_inicial=5)
    ts.registrar_compra(master.id, date(2026, 9, 18), "Nafta", "", ars(58000), tc, 1)

    # --- gastos fijos ---
    fijos = {}
    for concepto, detalle, monto, cat, dia, tarjeta in [
        ("Alquiler", "Depto Palermo", ars(450000), "Casa", 10, None),
        ("Expensas", "", ars(120000), "Casa", 10, None),
        ("Luz", "Edenor", ars(45000), "Servicios esenciales", None, visa.id),
        ("Internet", "Fibertel 300 megas", ars(32000), "Servicios esenciales", None, master.id),
        ("Netflix", "Plan estándar", usd(12), "Servicios no esenciales", None, visa.id),
        ("Gimnasio", "Pase libre", ars(30000), "Otros", 5, None),
        ("Seguro del auto", "La Caja", ars(68000), "Auto", 20, None),
        ("Celular", "Personal", ars(15000), "Servicios esenciales", None, visa.id),
    ]:
        fijos[concepto] = gf.registrar(concepto, detalle, monto, cats[cat], dia, tarjeta)
    for concepto in ("Alquiler", "Expensas", "Gimnasio"):
        gf.generar_movimiento_del_mes(fijos[concepto].id, date(2026, 9, 29))

    # --- prestamos ---
    ps.registrar_prestamo("Préstamo personal", "Banco Galicia", ars(1200000), 12, date(2026, 3, 10), cuota_inicial=7, dia_vencimiento=10)
    uva = ps.registrar_prestamo("Crédito UVA auto", "Cuota ajustable por UVA", ars(3000000), 24, date(2026, 5, 15), cuota_inicial=5, dia_vencimiento=15)
    ps.cambiar_monto_cuota(uva.cuotas[4].id, ars(131500), tambien_las_siguientes=True)

    # --- inversiones ---
    inv = InversionService(conn)
    inv.registrar_ahorro(Ahorro(None, usd(1500), date(2026, 4, 2), "Caja de seguridad", "Fondo de emergencia"), debitar=False)
    inv.registrar_ahorro(Ahorro(None, ars(500000), date(2026, 9, 2), "Plazo fijo Galicia", "30 días"), debitar=False)
    inv.registrar_titulo(Titulo(None, TipoTitulo.ACCION, "GGAL", date(2026, 3, 15), Decimal("200"), ars(4800), "Grupo Financiero Galicia",
                                "Banco", Plazo.LARGO, "IOL", "", [5, 11]), debitar=False)
    inv.registrar_titulo(Titulo(None, TipoTitulo.ACCION, "KO", date(2026, 6, 1), Decimal("10"), usd(62), "Coca-Cola", "Consumo",
                                Plazo.LARGO, "IOL", "", [4, 7, 10, 12]), debitar=False)
    inv.registrar_titulo(Titulo(None, TipoTitulo.BONO, "AL30", date(2026, 7, 10), Decimal("500"), usd(0.62), "Bonar 2030", "",
                                Plazo.MEDIANO, "IOL", "", [1, 7]), debitar=False)
    inv.registrar_fci(Fci(None, "Fima Premium", date(2026, 9, 1), ars(300000), "FIMAPA", Plazo.CORTO, "Galicia", tna=Decimal("32.5")), debitar=False)
    inv.registrar_crypto(OperacionCryptoRegistro(None, date(2026, 8, 5), OperacionCrypto.COMPRA, "BTC", usd(200), Decimal("58000"),
                                                 Decimal("0.00344828")), operar_con_cuenta=False)

    # --- compra mensual de septiembre ---
    cm = CompraMensualService(conn)
    lista = cm.obtener_o_crear(2026, 9)
    for local in ("Coto", "Carrefour", "Día"):
        cm.agregar_local(lista.id, local)
    for producto, cantidad in [("Leche", 6), ("Yerba 1 kg", 2), ("Arroz", 3), ("Aceite", 2), ("Café", 1), ("Detergente", 2)]:
        cm.agregar_producto(lista.id, producto, Decimal(cantidad))
    lista = cm.lista_del_mes(2026, 9)
    locales = {l.nombre: l.id for l in lista.locales}
    productos = {p.nombre: p.id for p in lista.productos}
    precios = {
        "Leche": (1450, 1390, 1320), "Yerba 1 kg": (4200, 4350, 3990), "Arroz": (1600, None, 1480),
        "Aceite": (3100, 2950, 3050), "Café": (8900, 8400, None), "Detergente": (2200, 2100, 2350),
    }
    for producto, valores in precios.items():
        for local, valor in zip(("Coto", "Carrefour", "Día"), valores):
            if valor is not None:
                cm.guardar_precio(productos[producto], locales[local], ars(valor),
                                  Decimal("10") if (producto, local) == ("Café", "Carrefour") else None,
                                  "La Serenísima" if producto == "Leche" and local == "Coto" else "")
    conn.close()


if __name__ == "__main__":
    crear(Path(sys.argv[1]))
    print("ok")
