"""Compra mensual: lista de compras por mes para comparar precios entre locales.

Los productos se cargan una vez (con su cantidad, igual para todos los locales)
y los locales una vez; despues solo se completa el precio de cada producto en
cada local. Para cada producto se marca el local mas barato y se calculan dos
totales: el de comprar todo en cada local y el de comprar cada producto donde
sale mas barato. Todo en pesos.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..domain.models import TipoMovimiento
from ..domain.money import Money, Moneda
from .movimientos import MovimientoService
from .tarjetas import TarjetaService

# Locales por lista: con mas la tabla se vuelve dificil de recorrer y lenta de abrir.
MAX_LOCALES = 5
MENSAJE_MAX_LOCALES = (f"Podés tener hasta {MAX_LOCALES} locales por mes. "
                       "Para agregar otro, eliminá uno (tocá su nombre en la tabla).")

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


@dataclass
class InfoLista:
    """Datos livianos de una lista (sin productos ni precios): para mostrar
    una compra cerrada como resumen y para elegir de que mes copiar."""
    id: int
    anio: int
    mes: int
    cerrada: bool
    cantidad_productos: int
    cantidad_locales: int
    cerrada_at: date | None = None
    total_optimo: Money | None = None      # guardados al cerrar
    total_registrado: Money | None = None

    @property
    def titulo(self) -> str:
        return f"{MESES[self.mes - 1]} {self.anio}"

    @property
    def total(self) -> Money | None:
        """Lo registrado en las cuentas si se registro algo; si no, el total
        comprando lo mas barato de cada local."""
        if self.total_registrado is not None and self.total_registrado.cents > 0:
            return self.total_registrado
        return self.total_optimo


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


# Orden de los productos en la tabla. "Barato"/"caro" usan el mejor precio de
# cada producto (el total del local mas barato); los que no tienen precio en
# ningun local van al final.
ORDENES_PRODUCTOS: dict[str, str] = {
    "carga": "Como los cargaste",
    "az": "Nombre (A-Z)",
    "za": "Nombre (Z-A)",
    "barato": "Más barato primero",
    "caro": "Más caro primero",
    "sin_precio": "Sin precio primero",
}


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn")


def coincide_busqueda(nombre: str, busqueda: str) -> bool:
    """Busqueda de productos: sin distinguir mayusculas ni acentos, y todas
    las palabras buscadas tienen que aparecer ("leche desc" encuentra
    "Leche descremada")."""
    nombre_n = _sin_acentos(nombre)
    return all(p in nombre_n for p in _sin_acentos(busqueda).split())


def ordenar_productos(resumen: ResumenCompra, orden: str) -> list[ProductoCompra]:
    filas = list(resumen.filas)
    if orden in ("az", "za"):
        filas.sort(key=lambda f: _sin_acentos(f.producto.nombre), reverse=orden == "za")
    elif orden in ("barato", "caro"):
        con = sorted((f for f in filas if f.mejor_total is not None), key=lambda f: f.mejor_total.cents, reverse=orden == "caro")
        filas = con + [f for f in filas if f.mejor_total is None]
    elif orden == "sin_precio":
        filas = [f for f in filas if f.sin_precio] + [f for f in filas if not f.sin_precio]
    return [f.producto for f in filas]


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

    # --- resumen liviano, cierre y reapertura ---

    _SQL_INFO = """
        SELECT l.*,
               (SELECT COUNT(*) FROM compra_productos WHERE lista_id = l.id) AS n_productos,
               (SELECT COUNT(*) FROM compra_locales WHERE lista_id = l.id) AS n_locales
        FROM compra_listas l"""

    @staticmethod
    def _info(r: sqlite3.Row) -> InfoLista:
        cerrada = r["estado"] == "cerrada"
        centavos = lambda c: Money(c, Moneda.ARS) if c is not None else None  # noqa: E731
        return InfoLista(
            r["id"], r["anio"], r["mes"], cerrada,
            # Cerrada: lo que tenia al cerrarla (queda como resumen historico).
            r["cantidad_productos"] if cerrada and r["cantidad_productos"] is not None else r["n_productos"],
            r["cantidad_locales"] if cerrada and r["cantidad_locales"] is not None else r["n_locales"],
            date.fromisoformat(r["cerrada_at"][:10]) if cerrada and r["cerrada_at"] else None,
            centavos(r["total_optimo_centavos"]) if cerrada else None,
            centavos(r["total_registrado_centavos"]) if cerrada else None,
        )

    def info_del_mes(self, anio: int, mes: int) -> InfoLista | None:
        r = self._conn.execute(self._SQL_INFO + " WHERE l.anio = ? AND l.mes = ?", (anio, mes)).fetchone()
        return self._info(r) if r else None

    def listas(self, solo_cerradas: bool = False) -> list[InfoLista]:
        """Todas las listas (o solo las cerradas), de la mas nueva a la mas vieja, sin cargar su detalle."""
        filtro = " WHERE l.estado = 'cerrada'" if solo_cerradas else ""
        return [self._info(r) for r in self._conn.execute(self._SQL_INFO + filtro + " ORDER BY l.anio DESC, l.mes DESC")]

    def esta_cerrada(self, lista_id: int) -> bool:
        r = self._conn.execute("SELECT estado FROM compra_listas WHERE id = ?", (lista_id,)).fetchone()
        return r is not None and r["estado"] == "cerrada"

    def _verificar_abierta(self, lista_id: int) -> None:
        if self.esta_cerrada(lista_id):
            raise ValueError("Esta compra mensual está cerrada. Reabrila para modificarla.")

    def _lista_de(self, tabla: str, id_: int) -> int:
        r = self._conn.execute(f"SELECT lista_id FROM {tabla} WHERE id = ?", (id_,)).fetchone()
        if r is None:
            raise ValueError("Ese dato ya no existe")
        return r["lista_id"]

    def cerrar_lista(self, lista_id: int, hoy: date | None = None) -> InfoLista:
        """Cierra la compra: guarda su resumen (totales y cantidades) para
        mostrarla sin cargar la tabla. El detalle queda guardado para
        consultarlo o reabrirla."""
        self._verificar_abierta(lista_id)
        lista = self._cargar(lista_id)
        resumen = calcular(lista)
        registrado = sum(r.monto.cents for r in self.registros(lista_id))
        self._conn.execute(
            """UPDATE compra_listas SET estado = 'cerrada', cerrada_at = ?, total_optimo_centavos = ?,
                 total_registrado_centavos = ?, cantidad_productos = ?, cantidad_locales = ? WHERE id = ?""",
            ((hoy or date.today()).isoformat(), resumen.total_optimo.cents, registrado,
             len(lista.productos), len(lista.locales), lista_id),
        )
        self._conn.commit()
        return self.info_del_mes(lista.anio, lista.mes)

    def reabrir_lista(self, lista_id: int) -> None:
        """Vuelve a abrir la compra con sus datos de siempre (no se copia nada).
        El resumen se vuelve a calcular la proxima vez que se cierre."""
        self._conn.execute(
            """UPDATE compra_listas SET estado = 'abierta', cerrada_at = NULL, total_optimo_centavos = NULL,
                 total_registrado_centavos = NULL, cantidad_productos = NULL, cantidad_locales = NULL WHERE id = ?""",
            (lista_id,),
        )
        self._conn.commit()

    def detalle(self, lista_id: int) -> ListaCompra:
        """Detalle completo de una lista (por ejemplo, una cerrada para consultarla)."""
        return self._cargar(lista_id)

    # --- copiar de otro mes ---

    def copiar_de(self, lista_id: int, origen_id: int, locales: bool = True, productos: bool = True) -> tuple[int, int]:
        """Copia a la lista los locales y/o productos (con cantidades) de otra.
        No copia precios ni descuentos; si el producto y el local quedan en las
        dos listas, copia el detalle (marca) a las casillas que aca no tienen nada cargado.
        Lo que ya esta (mismo nombre, sin importar mayusculas) no se duplica y
        se respeta el maximo de locales. Devuelve (locales, productos) copiados."""
        self._verificar_abierta(lista_id)
        if lista_id == origen_id:
            raise ValueError("Elegí otro mes para copiar")
        if not (locales or productos):
            raise ValueError("Elegí qué querés copiar")
        origen, destino = self._cargar(origen_id), self._cargar(lista_id)
        clave = lambda nombre: nombre.strip().lower()  # noqa: E731
        copiados_l = copiados_p = 0
        if locales:
            existentes = {clave(l.nombre) for l in destino.locales}
            orden = self._siguiente_orden("compra_locales", lista_id)
            for l in origen.locales:
                if clave(l.nombre) in existentes:
                    continue
                if len(existentes) >= MAX_LOCALES:
                    break
                self._conn.execute("INSERT INTO compra_locales (lista_id, nombre, orden) VALUES (?, ?, ?)",
                                   (lista_id, l.nombre, orden))
                existentes.add(clave(l.nombre))
                orden += 1
                copiados_l += 1
        if productos:
            existentes = {clave(p.nombre) for p in destino.productos}
            orden = self._siguiente_orden("compra_productos", lista_id)
            for p in origen.productos:
                if clave(p.nombre) in existentes:
                    continue
                self._conn.execute("INSERT INTO compra_productos (lista_id, nombre, cantidad, orden) VALUES (?, ?, ?, ?)",
                                   (lista_id, p.nombre, str(p.cantidad), orden))
                existentes.add(clave(p.nombre))
                orden += 1
                copiados_p += 1
        # Detalles (marca, tamaño) de las casillas que coinciden por nombre.
        locales_dest = {clave(r["nombre"]): r["id"] for r in self._conn.execute(
            "SELECT id, nombre FROM compra_locales WHERE lista_id = ?", (lista_id,))}
        productos_dest = {clave(r["nombre"]): r["id"] for r in self._conn.execute(
            "SELECT id, nombre FROM compra_productos WHERE lista_id = ?", (lista_id,))}
        for p in origen.productos:
            for l in origen.locales:
                detalle = origen.precio(p.id, l.id).detalle
                pid, lid = productos_dest.get(clave(p.nombre)), locales_dest.get(clave(l.nombre))
                if detalle and pid and lid:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO compra_precios (producto_id, local_id, detalle) VALUES (?, ?, ?)",
                        (pid, lid, detalle),
                    )
        self._conn.commit()
        return copiados_l, copiados_p

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
        self._verificar_abierta(lista_id)
        cantidad = self._conn.execute("SELECT COUNT(*) FROM compra_locales WHERE lista_id = ?", (lista_id,)).fetchone()[0]
        if cantidad >= MAX_LOCALES:
            raise ValueError(MENSAJE_MAX_LOCALES)
        nombre = self._validar_nombre_local(lista_id, nombre)
        self._conn.execute(
            "INSERT INTO compra_locales (lista_id, nombre, orden) VALUES (?, ?, ?)",
            (lista_id, nombre, self._siguiente_orden("compra_locales", lista_id)),
        )
        self._conn.commit()

    def renombrar_local(self, local_id: int, nombre: str) -> None:
        lista_id = self._lista_de("compra_locales", local_id)
        self._verificar_abierta(lista_id)
        nombre = self._validar_nombre_local(lista_id, nombre, excepto=local_id)
        self._conn.execute("UPDATE compra_locales SET nombre = ? WHERE id = ?", (nombre, local_id))
        self._conn.commit()

    def eliminar_local(self, local_id: int) -> None:
        self._verificar_abierta(self._lista_de("compra_locales", local_id))
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
        self._verificar_abierta(lista_id)
        nombre = self._validar_producto(nombre, cantidad)
        self._conn.execute(
            "INSERT INTO compra_productos (lista_id, nombre, cantidad, orden) VALUES (?, ?, ?, ?)",
            (lista_id, nombre, str(cantidad), self._siguiente_orden("compra_productos", lista_id)),
        )
        self._conn.commit()

    def editar_producto(self, producto_id: int, nombre: str, cantidad: Decimal) -> None:
        self._verificar_abierta(self._lista_de("compra_productos", producto_id))
        nombre = self._validar_producto(nombre, cantidad)
        self._conn.execute("UPDATE compra_productos SET nombre = ?, cantidad = ? WHERE id = ?", (nombre, str(cantidad), producto_id))
        self._conn.commit()

    def eliminar_producto(self, producto_id: int) -> None:
        self._verificar_abierta(self._lista_de("compra_productos", producto_id))
        self._conn.execute("DELETE FROM compra_productos WHERE id = ?", (producto_id,))
        self._conn.commit()

    # --- precios ---

    def guardar_precio(self, producto_id: int, local_id: int, precio: Money | None, descuento: Decimal | None, detalle: str) -> None:
        self._verificar_abierta(self._lista_de("compra_productos", producto_id))
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
        self._verificar_abierta(lista_id)
        concepto = self._validar_registro(monto, concepto)
        mov = self._movimientos.registrar(TipoMovimiento.EGRESO, fecha, concepto, "Compra mensual", monto, categoria_id)
        self._guardar_registro(lista_id, "egreso", mov.id, monto, fecha, descripcion)

    def registrar_en_tarjeta(
        self, lista_id: int, tarjeta_id: int, fecha: date, concepto: str, monto: Money, categoria_id: int,
        cuotas: int = 1, tarjeta_cerrada: bool = False,
    ) -> None:
        """Registra la compra en una tarjeta de credito (en pesos), en 1 pago o en cuotas."""
        self._verificar_abierta(lista_id)
        concepto = self._validar_registro(monto, concepto)
        tarjeta = self._tarjetas.obtener_tarjeta(tarjeta_id)
        if tarjeta is None:
            raise ValueError("La tarjeta elegida no existe")
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
        r = self._conn.execute("SELECT lista_id, tipo, referencia_id FROM compra_registros WHERE id = ?", (registro_id,)).fetchone()
        if r is None:
            return
        self._verificar_abierta(r["lista_id"])
        if r["tipo"] == "egreso":
            if self._movimientos.obtener(r["referencia_id"]) is not None:
                self._movimientos.eliminar(r["referencia_id"])
        elif self._tarjetas.obtener_compra(r["referencia_id"]) is not None:
            self._tarjetas.eliminar_compra(r["referencia_id"])
        self._conn.execute("DELETE FROM compra_registros WHERE id = ?", (registro_id,))
        self._conn.commit()
