"""Compra mensual: lista de compras por mes para comparar precios entre locales.

Los productos se cargan una vez (con su cantidad, igual para todos los locales)
y los locales una vez; despues solo se completa el precio de cada producto en
cada local. Para cada producto se marca el local mas barato y se calculan dos
totales: el de comprar todo en cada local y el de comprar cada producto donde
sale mas barato. Todo en pesos.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..domain.models import TipoMovimiento
from ..domain.money import Money, Moneda
from .movimientos import MovimientoService
from .tarjetas import TarjetaService

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@dataclass
class LocalCompra:
    id: int
    nombre: str
    orden: int = 0


@dataclass
class ProductoCompra:
    id: int
    nombre: str
    cantidad: Decimal
    orden: int = 0


@dataclass
class PrecioCompra:
    precio: Money | None = None      # precio unitario; None = el local no lo tiene
    descuento: Decimal | None = None  # porcentaje, ej 25 = 25 %
    detalle: str = ""


@dataclass
class ListaCompra:
    id: int
    anio: int
    mes: int
    locales: list[LocalCompra] = field(default_factory=list)
    productos: list[ProductoCompra] = field(default_factory=list)
    precios: dict[tuple[int, int], PrecioCompra] = field(default_factory=dict)  # (producto_id, local_id)

    @property
    def titulo(self) -> str:
        return f"{MESES[self.mes - 1]} {self.anio}"

    def precio(self, producto_id: int, local_id: int) -> PrecioCompra:
        return self.precios.get((producto_id, local_id), PrecioCompra())


@dataclass
class RegistroCompra:
    """Una compra de la lista ya registrada como egreso o en una tarjeta."""
    id: int
    tipo: str            # "egreso" | "tarjeta"
    referencia_id: int   # movimiento o compra de tarjeta
    monto: Money
    fecha: date
    descripcion: str


def total_celda(cantidad: Decimal, celda: PrecioCompra) -> Money | None:
    """Precio unitario x cantidad, menos el descuento. None si no hay precio."""
    if celda.precio is None:
        return None
    bruto = celda.precio.amount * cantidad
    if celda.descuento:
        bruto = bruto * (Decimal(100) - celda.descuento) / Decimal(100)
    return Money.from_decimal(bruto, Moneda.ARS)


@dataclass
class FilaCalculada:
    producto: ProductoCompra
    totales: dict[int, Money | None]      # local_id -> total de la casilla
    mas_baratos: set[int]                  # locales con el menor total (empates incluidos)
    mejor_total: Money | None              # None si ningun local tiene precio

    @property
    def sin_precio(self) -> bool:
        return self.mejor_total is None


@dataclass
class ResumenCompra:
    filas: list[FilaCalculada]
    total_por_local: dict[int, Money]      # comprar todo lo que ese local tiene
    faltantes_por_local: dict[int, int]    # productos que ese local no tiene
    total_optimo: Money                    # cada producto en su local mas barato
    plan_por_local: dict[int, tuple[Money, int]]  # como se reparte el total optimo: (monto, productos)
    productos_sin_precio: int


def calcular(lista: ListaCompra) -> ResumenCompra:
    cero = Money.zero(Moneda.ARS)
    total_por_local = {l.id: cero for l in lista.locales}
    faltantes = {l.id: 0 for l in lista.locales}
    plan = {l.id: (cero, 0) for l in lista.locales}
    total_optimo = cero
    filas = []
    sin_precio = 0

    for p in lista.productos:
        totales = {l.id: total_celda(p.cantidad, lista.precio(p.id, l.id)) for l in lista.locales}
        con_precio = {lid: t for lid, t in totales.items() if t is not None}
        for lid in faltantes:
            if totales[lid] is not None:
                total_por_local[lid] = total_por_local[lid] + totales[lid]
            elif con_precio:
                # Solo falta si algun otro local lo tiene: un producto sin precio
                # en ningun lado no hace "incompleto" a cada local.
                faltantes[lid] += 1
        if con_precio:
            minimo = min(t.cents for t in con_precio.values())
            baratos = {lid for lid, t in con_precio.items() if t.cents == minimo}
            mejor = Money(minimo, Moneda.ARS)
            total_optimo = total_optimo + mejor
            # En un empate, el plan asigna el producto al primer local de la lista.
            elegido = next(l.id for l in lista.locales if l.id in baratos)
            monto, cantidad = plan[elegido]
            plan[elegido] = (monto + mejor, cantidad + 1)
        else:
            baratos, mejor = set(), None
            sin_precio += 1
        filas.append(FilaCalculada(p, totales, baratos, mejor))

    return ResumenCompra(filas, total_por_local, faltantes, total_optimo, plan, sin_precio)


def _clave_mes(anio: int, mes: int) -> int:
    return anio * 12 + (mes - 1)


class CompraMensualService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._movimientos = MovimientoService(conn)
        self._tarjetas = TarjetaService(conn)

    # --- listas ---

    def _id_lista(self, anio: int, mes: int) -> int | None:
        r = self._conn.execute("SELECT id FROM compra_listas WHERE anio = ? AND mes = ?", (anio, mes)).fetchone()
        return r["id"] if r else None

    def lista_del_mes(self, anio: int, mes: int) -> ListaCompra | None:
        lista_id = self._id_lista(anio, mes)
        return self._cargar(lista_id) if lista_id else None

    def _cargar(self, lista_id: int) -> ListaCompra:
        r = self._conn.execute("SELECT * FROM compra_listas WHERE id = ?", (lista_id,)).fetchone()
        lista = ListaCompra(r["id"], r["anio"], r["mes"])
        lista.locales = [
            LocalCompra(x["id"], x["nombre"], x["orden"])
            for x in self._conn.execute("SELECT * FROM compra_locales WHERE lista_id = ? ORDER BY orden, id", (lista_id,))
        ]
        lista.productos = [
            ProductoCompra(x["id"], x["nombre"], Decimal(x["cantidad"]), x["orden"])
            for x in self._conn.execute("SELECT * FROM compra_productos WHERE lista_id = ? ORDER BY orden, id", (lista_id,))
        ]
        for x in self._conn.execute(
            """SELECT cp.* FROM compra_precios cp JOIN compra_productos p ON p.id = cp.producto_id
               WHERE p.lista_id = ?""", (lista_id,),
        ):
            lista.precios[(x["producto_id"], x["local_id"])] = PrecioCompra(
                precio=Money(x["precio_centavos"], Moneda.ARS) if x["precio_centavos"] is not None else None,
                descuento=Decimal(x["descuento"]) if x["descuento"] else None,
                detalle=x["detalle"],
            )
        return lista

    def lista_anterior(self, anio: int, mes: int) -> ListaCompra | None:
        """La lista mas reciente de un mes anterior al indicado."""
        r = self._conn.execute(
            "SELECT id FROM compra_listas WHERE anio * 12 + (mes - 1) < ? ORDER BY anio DESC, mes DESC LIMIT 1",
            (_clave_mes(anio, mes),),
        ).fetchone()
        return self._cargar(r["id"]) if r else None

    def crear_lista(self, anio: int, mes: int) -> ListaCompra:
        """Crea la lista del mes copiando de la anterior locales, productos,
        cantidades y detalles, pero no precios ni descuentos (cambian cada mes)."""
        if self._id_lista(anio, mes):
            raise ValueError("Ya existe la lista de ese mes")
        anterior = self.lista_anterior(anio, mes)
        cur = self._conn.execute("INSERT INTO compra_listas (anio, mes) VALUES (?, ?)", (anio, mes))
        lista_id = cur.lastrowid
        if anterior:
            locales = {}
            for l in anterior.locales:
                locales[l.id] = self._conn.execute(
                    "INSERT INTO compra_locales (lista_id, nombre, orden) VALUES (?, ?, ?)", (lista_id, l.nombre, l.orden)
                ).lastrowid
            for p in anterior.productos:
                nuevo = self._conn.execute(
                    "INSERT INTO compra_productos (lista_id, nombre, cantidad, orden) VALUES (?, ?, ?, ?)",
                    (lista_id, p.nombre, str(p.cantidad), p.orden),
                ).lastrowid
                for l in anterior.locales:
                    detalle = anterior.precio(p.id, l.id).detalle
                    if detalle:
                        self._conn.execute(
                            "INSERT INTO compra_precios (producto_id, local_id, detalle) VALUES (?, ?, ?)",
                            (nuevo, locales[l.id], detalle),
                        )
        self._conn.commit()
        return self._cargar(lista_id)

    def obtener_o_crear(self, anio: int, mes: int) -> ListaCompra:
        return self.lista_del_mes(anio, mes) or self.crear_lista(anio, mes)

    # --- locales ---

    def _siguiente_orden(self, tabla: str, lista_id: int) -> int:
        r = self._conn.execute(f"SELECT COALESCE(MAX(orden), -1) + 1 AS n FROM {tabla} WHERE lista_id = ?", (lista_id,)).fetchone()
        return r["n"]

    def _validar_nombre_local(self, lista_id: int, nombre: str, excepto: int | None = None) -> str:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("Escribí el nombre del local")
        for r in self._conn.execute("SELECT id, nombre FROM compra_locales WHERE lista_id = ?", (lista_id,)):
            if r["id"] != excepto and r["nombre"].strip().lower() == nombre.lower():
                raise ValueError(f"Ya hay un local llamado {r['nombre']}")
        return nombre

    def agregar_local(self, lista_id: int, nombre: str) -> None:
        nombre = self._validar_nombre_local(lista_id, nombre)
        self._conn.execute(
            "INSERT INTO compra_locales (lista_id, nombre, orden) VALUES (?, ?, ?)",
            (lista_id, nombre, self._siguiente_orden("compra_locales", lista_id)),
        )
        self._conn.commit()

    def renombrar_local(self, local_id: int, nombre: str) -> None:
        lista_id = self._conn.execute("SELECT lista_id FROM compra_locales WHERE id = ?", (local_id,)).fetchone()["lista_id"]
        nombre = self._validar_nombre_local(lista_id, nombre, excepto=local_id)
        self._conn.execute("UPDATE compra_locales SET nombre = ? WHERE id = ?", (nombre, local_id))
        self._conn.commit()

    def eliminar_local(self, local_id: int) -> None:
        self._conn.execute("DELETE FROM compra_locales WHERE id = ?", (local_id,))  # sus precios caen en cascada
        self._conn.commit()

    # --- productos ---

    @staticmethod
    def _validar_producto(nombre: str, cantidad: Decimal) -> str:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("Escribí el nombre del producto")
        if cantidad <= 0:
            raise ValueError("La cantidad tiene que ser mayor a cero")
        return nombre

    def agregar_producto(self, lista_id: int, nombre: str, cantidad: Decimal) -> None:
        nombre = self._validar_producto(nombre, cantidad)
        self._conn.execute(
            "INSERT INTO compra_productos (lista_id, nombre, cantidad, orden) VALUES (?, ?, ?, ?)",
            (lista_id, nombre, str(cantidad), self._siguiente_orden("compra_productos", lista_id)),
        )
        self._conn.commit()

    def editar_producto(self, producto_id: int, nombre: str, cantidad: Decimal) -> None:
        nombre = self._validar_producto(nombre, cantidad)
        self._conn.execute("UPDATE compra_productos SET nombre = ?, cantidad = ? WHERE id = ?", (nombre, str(cantidad), producto_id))
        self._conn.commit()

    def eliminar_producto(self, producto_id: int) -> None:
        self._conn.execute("DELETE FROM compra_productos WHERE id = ?", (producto_id,))
        self._conn.commit()

    # --- precios ---

    def guardar_precio(self, producto_id: int, local_id: int, precio: Money | None, descuento: Decimal | None, detalle: str) -> None:
        if precio is not None and precio.cents < 0:
            raise ValueError("El precio no puede ser negativo")
        if descuento is not None and not (0 <= descuento <= 100):
            raise ValueError("El descuento tiene que estar entre 0 y 100 %")
        self._conn.execute(
            """INSERT INTO compra_precios (producto_id, local_id, precio_centavos, descuento, detalle)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (producto_id, local_id) DO UPDATE SET
                 precio_centavos = excluded.precio_centavos, descuento = excluded.descuento, detalle = excluded.detalle""",
            (producto_id, local_id, precio.cents if precio is not None else None,
             str(descuento) if descuento else None, detalle.strip()),
        )
        self._conn.commit()

    # --- registrar la compra en las cuentas ---

    @staticmethod
    def _validar_registro(monto: Money, concepto: str) -> str:
        if monto.cents <= 0:
            raise ValueError("El monto tiene que ser mayor a cero")
        concepto = concepto.strip()
        if not concepto:
            raise ValueError("Escribí un concepto")
        return concepto

    def _guardar_registro(self, lista_id: int, tipo: str, referencia_id: int, monto: Money, fecha: date, descripcion: str) -> None:
        self._conn.execute(
            """INSERT INTO compra_registros (lista_id, tipo, referencia_id, monto_centavos, fecha, descripcion)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lista_id, tipo, referencia_id, monto.cents, fecha.isoformat(), descripcion),
        )
        self._conn.commit()

    def registrar_egreso(self, lista_id: int, fecha: date, concepto: str, monto: Money, categoria_id: int, descripcion: str) -> None:
        """Registra la compra como un egreso (efectivo, debito, transferencia)."""
        concepto = self._validar_registro(monto, concepto)
        mov = self._movimientos.registrar(TipoMovimiento.EGRESO, fecha, concepto, "Compra mensual", monto, categoria_id)
        self._guardar_registro(lista_id, "egreso", mov.id, monto, fecha, descripcion)

    def registrar_en_tarjeta(
        self, lista_id: int, tarjeta_id: int, fecha: date, concepto: str, monto: Money, categoria_id: int,
        cuotas: int = 1, tarjeta_cerrada: bool = False,
    ) -> None:
        """Registra la compra en una tarjeta de credito (en pesos), en 1 pago o en cuotas."""
        concepto = self._validar_registro(monto, concepto)
        tarjeta = self._tarjetas.obtener_tarjeta(tarjeta_id)
        if tarjeta is None:
            raise ValueError("La tarjeta elegida no existe")
        if tarjeta.moneda != Moneda.ARS:
            raise ValueError(f"La tarjeta {tarjeta.nombre} es en {tarjeta.moneda.value}: la compra mensual es en pesos")
        if cuotas < 1:
            raise ValueError("Las cuotas tienen que ser 1 o más")
        compra = self._tarjetas.registrar_compra(
            tarjeta_id, fecha, concepto, "Compra mensual", monto, categoria_id, cuotas, tarjeta_cerrada=tarjeta_cerrada,
        )
        descripcion = f"{tarjeta.nombre} · " + ("1 pago" if cuotas == 1 else f"{cuotas} cuotas")
        self._guardar_registro(lista_id, "tarjeta", compra.id, monto, fecha, descripcion)

    def registros(self, lista_id: int) -> list[RegistroCompra]:
        return [
            RegistroCompra(r["id"], r["tipo"], r["referencia_id"], Money(r["monto_centavos"], Moneda.ARS),
                           date.fromisoformat(r["fecha"]), r["descripcion"])
            for r in self._conn.execute("SELECT * FROM compra_registros WHERE lista_id = ? ORDER BY fecha, id", (lista_id,))
        ]

    def deshacer_registro(self, registro_id: int) -> None:
        """Borra el registro y el egreso o la compra de tarjeta que genero."""
        r = self._conn.execute("SELECT tipo, referencia_id FROM compra_registros WHERE id = ?", (registro_id,)).fetchone()
        if r is None:
            return
        if r["tipo"] == "egreso":
            if self._movimientos.obtener(r["referencia_id"]) is not None:
                self._movimientos.eliminar(r["referencia_id"])
        elif self._tarjetas.obtener_compra(r["referencia_id"]) is not None:
            self._tarjetas.eliminar_compra(r["referencia_id"])
        self._conn.execute("DELETE FROM compra_registros WHERE id = ?", (registro_id,))
        self._conn.commit()
