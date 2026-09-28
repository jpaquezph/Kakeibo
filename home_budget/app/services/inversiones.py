"""Inversiones: ahorro, acciones, bonos/Lecap, FCI y crypto.

Cada inversion puede, si el usuario lo elige, operar con la plata de la
app: al invertir se registra un egreso (categoria "Inversiones") y al
finalizar/rescatar/retirar/vender un ingreso ("Retiro de inversiones").
Esos movimientos quedan vinculados y se borran junto con la inversion.

Los totales nunca mezclan monedas: todo se calcula por ARS y USD por separado.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from ..domain.models import TipoMovimiento
from ..domain.money import Money, Moneda
from ..repositories.categorias import CategoriaRepository
from .movimientos import MovimientoService

CATEGORIA_INVERSION = "Inversiones"
CATEGORIA_RETIRO = "Retiro de inversiones"


class EstadoInversion(str, Enum):
    VIGENTE = "vigente"
    FINALIZADA = "finalizada"


class TipoTitulo(str, Enum):
    ACCION = "accion"
    BONO = "bono"


class Plazo(str, Enum):
    CORTO = "corto"
    MEDIANO = "mediano"
    LARGO = "largo"


class OperacionCrypto(str, Enum):
    COMPRA = "compra"
    VENTA = "venta"


def _fecha(valor: str | None) -> date | None:
    return date.fromisoformat(valor) if valor else None


def fmt_cantidad(d: Decimal) -> str:
    """Cantidad sin ceros de mas y con coma decimal (1,5 / 0,00012)."""
    return f"{d.normalize():f}".replace(".", ",")


def _costo(precio: Money, cantidad: Decimal) -> Money:
    return Money.from_decimal(precio.amount * cantidad, precio.moneda)


@dataclass
class Ahorro:
    id: int | None
    monto: Money
    fecha: date
    ubicacion: str = ""
    observaciones: str = ""
    estado: EstadoInversion = EstadoInversion.VIGENTE
    fecha_salida: date | None = None
    monto_salida: Money | None = None
    entrada_mov_id: int | None = None
    salida_mov_id: int | None = None

    @property
    def costo(self) -> Money:
        return self.monto


@dataclass
class Titulo:
    """Una compra de una accion o de un bono/Lecap."""
    id: int | None
    tipo: TipoTitulo
    simbolo: str
    fecha_suscripcion: date
    cantidad: Decimal
    precio_compra: Money  # por unidad
    nombre: str = ""
    tipo_empresa: str = ""
    plazo: Plazo = Plazo.LARGO
    broker: str = ""
    transaccion: str = ""
    meses_pago: list[int] = field(default_factory=list)  # dividendos (acciones) / renta (bonos)
    observaciones: str = ""
    estado: EstadoInversion = EstadoInversion.VIGENTE
    fecha_salida: date | None = None
    monto_salida: Money | None = None
    entrada_mov_id: int | None = None
    salida_mov_id: int | None = None

    @property
    def costo(self) -> Money:
        return _costo(self.precio_compra, self.cantidad)


@dataclass
class Fci:
    id: int | None
    nombre: str
    fecha_suscripcion: date
    monto: Money
    simbolo: str = ""
    plazo: Plazo = Plazo.CORTO
    broker: str = ""
    transaccion: str = ""
    fecha_rescate: date | None = None
    tna: Decimal | None = None
    observaciones: str = ""
    estado: EstadoInversion = EstadoInversion.VIGENTE
    fecha_salida: date | None = None
    monto_salida: Money | None = None
    entrada_mov_id: int | None = None
    salida_mov_id: int | None = None

    @property
    def costo(self) -> Money:
        return self.monto


@dataclass
class OperacionCryptoRegistro:
    id: int | None
    fecha: date
    operacion: OperacionCrypto
    activo: str
    monto: Money
    precio_unitario: Decimal
    cantidad: Decimal
    observaciones: str = ""
    mov_id: int | None = None


@dataclass
class Totales:
    """Totales de un apartado en una moneda.
    invertido: todo lo que se invirtio alguna vez (vigente o no).
    vigente: el costo de lo que se tiene hoy.
    recibido: lo cobrado al finalizar/rescatar/retirar/vender.
    resultado: recibido menos el costo de lo finalizado (ganancia o perdida)."""
    moneda: Moneda
    invertido: Money
    vigente: Money
    recibido: Money
    resultado: Money
    cantidad_vigentes: int = 0

    @classmethod
    def vacio(cls, moneda: Moneda) -> "Totales":
        cero = Money.zero(moneda)
        return cls(moneda, cero, cero, cero, cero)


@dataclass
class Tenencia:
    """Suma de todas las compras vigentes de un mismo simbolo."""
    simbolo: str
    nombre: str
    moneda: Moneda
    cantidad: Decimal
    costo: Money
    transacciones: int

    @property
    def precio_promedio(self) -> Money:
        if self.cantidad == 0:
            return Money.zero(self.moneda)
        return Money.from_decimal(self.costo.amount / self.cantidad, self.moneda)


@dataclass
class TenenciaCrypto:
    activo: str
    moneda: Moneda
    cantidad: Decimal  # neta: compras - ventas
    invertido: Money   # suma de compras
    recibido: Money    # suma de ventas
    vigente: Money     # cantidad neta valuada a costo promedio de compra


def totales_de(items: list, moneda: Moneda) -> Totales:
    """Totales para ahorros, titulos o FCIs (todos exponen costo/estado/monto_salida)."""
    t = Totales.vacio(moneda)
    for it in items:
        if it.costo.moneda != moneda:
            continue
        t.invertido = t.invertido + it.costo
        if it.estado == EstadoInversion.VIGENTE:
            t.vigente = t.vigente + it.costo
            t.cantidad_vigentes += 1
        elif it.monto_salida is not None:
            t.recibido = t.recibido + it.monto_salida
            t.resultado = t.resultado + (it.monto_salida - it.costo)
    return t


def tenencias_por_simbolo(titulos: list[Titulo], moneda: Moneda) -> list[Tenencia]:
    por_simbolo: dict[str, Tenencia] = {}
    for t in titulos:
        if t.estado != EstadoInversion.VIGENTE or t.precio_compra.moneda != moneda:
            continue
        clave = t.simbolo.upper()
        ten = por_simbolo.get(clave)
        if ten is None:
            por_simbolo[clave] = Tenencia(clave, t.nombre, moneda, t.cantidad, t.costo, 1)
        else:
            ten.cantidad += t.cantidad
            ten.costo = ten.costo + t.costo
            ten.transacciones += 1
            ten.nombre = ten.nombre or t.nombre
    return sorted(por_simbolo.values(), key=lambda x: x.costo.cents, reverse=True)


def tenencias_crypto(operaciones: list[OperacionCryptoRegistro], moneda: Moneda) -> list[TenenciaCrypto]:
    datos: dict[str, dict] = {}
    for op in operaciones:
        if op.monto.moneda != moneda:
            continue
        d = datos.setdefault(op.activo.upper(), {
            "comprado": Decimal(0), "vendido": Decimal(0),
            "invertido": Money.zero(moneda), "recibido": Money.zero(moneda),
        })
        if op.operacion == OperacionCrypto.COMPRA:
            d["comprado"] += op.cantidad
            d["invertido"] = d["invertido"] + op.monto
        else:
            d["vendido"] += op.cantidad
            d["recibido"] = d["recibido"] + op.monto

    tenencias = []
    for activo, d in datos.items():
        neta = d["comprado"] - d["vendido"]
        if d["comprado"] > 0 and neta > 0:
            vigente = Money.from_decimal(d["invertido"].amount / d["comprado"] * neta, moneda)
        else:
            vigente = Money.zero(moneda)
        tenencias.append(TenenciaCrypto(activo, moneda, neta, d["invertido"], d["recibido"], vigente))
    return sorted(tenencias, key=lambda x: x.vigente.cents, reverse=True)


def totales_crypto(operaciones: list[OperacionCryptoRegistro], moneda: Moneda) -> Totales:
    t = Totales.vacio(moneda)
    for ten in tenencias_crypto(operaciones, moneda):
        t.invertido = t.invertido + ten.invertido
        t.vigente = t.vigente + ten.vigente
        t.recibido = t.recibido + ten.recibido
        if ten.cantidad > 0:
            t.cantidad_vigentes += 1
    # Resultado de lo ya vendido: lo cobrado menos el costo de lo que salio.
    t.resultado = t.recibido - (t.invertido - t.vigente)
    return t


@dataclass
class EventoInversion:
    """Algo que paso (o esta previsto) en una fecha, para el calendario."""
    fecha: date
    apartado: str  # "ahorro" | "acciones" | "bonos" | "fci" | "crypto"
    titulo: str
    detalle: str
    monto: Money | None = None
    previsto: bool = False  # ej: fecha de rescate de un FCI que todavia no se rescato


class InversionService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._movimientos = MovimientoService(conn)
        self._categorias = CategoriaRepository(conn)

    # --- movimientos vinculados ---

    def _categoria_id(self, nombre: str) -> int:
        for c in self._categorias.listar():
            if c.nombre == nombre:
                return c.id
        raise ValueError(f"Falta la categoria {nombre!r}")

    def _registrar_mov(self, tipo: TipoMovimiento, fecha: date, concepto: str, monto: Money) -> int:
        categoria = CATEGORIA_INVERSION if tipo == TipoMovimiento.EGRESO else CATEGORIA_RETIRO
        mov = self._movimientos.registrar(tipo, fecha, concepto, "Generado desde Inversiones", monto, self._categoria_id(categoria))
        return mov.id

    def _borrar_movs(self, *mov_ids: int | None) -> None:
        for mov_id in mov_ids:
            if mov_id is not None and self._movimientos.obtener(mov_id) is not None:
                self._movimientos.eliminar(mov_id)

    def _actualizar_mov(self, mov_id: int | None, fecha: date, monto: Money) -> None:
        """Al editar una inversion, el egreso vinculado acompana el nuevo monto y fecha."""
        if mov_id is None:
            return
        mov = self._movimientos.obtener(mov_id)
        if mov is not None:
            mov.fecha, mov.monto = fecha, monto
            self._movimientos.editar(mov)

    # --- Ahorro ---

    def _map_ahorro(self, r) -> Ahorro:
        return Ahorro(
            id=r["id"], monto=Money(r["monto_centavos"], r["moneda"]), fecha=date.fromisoformat(r["fecha"]),
            ubicacion=r["ubicacion"], observaciones=r["observaciones"], estado=EstadoInversion(r["estado"]),
            fecha_salida=_fecha(r["fecha_salida"]),
            monto_salida=Money(r["monto_salida_centavos"], r["moneda"]) if r["monto_salida_centavos"] is not None else None,
            entrada_mov_id=r["entrada_mov_id"], salida_mov_id=r["salida_mov_id"],
        )

    def listar_ahorros(self) -> list[Ahorro]:
        rows = self._conn.execute("SELECT * FROM ahorros ORDER BY fecha DESC, id DESC").fetchall()
        return [self._map_ahorro(r) for r in rows]

    def obtener_ahorro(self, ahorro_id: int) -> Ahorro | None:
        r = self._conn.execute("SELECT * FROM ahorros WHERE id = ?", (ahorro_id,)).fetchone()
        return self._map_ahorro(r) if r else None

    def registrar_ahorro(self, a: Ahorro, debitar: bool) -> Ahorro:
        if a.monto.cents <= 0:
            raise ValueError("El monto tiene que ser mayor a cero")
        a.entrada_mov_id = self._registrar_mov(TipoMovimiento.EGRESO, a.fecha, f"Ahorro: {a.ubicacion or 'sin ubicación'}", a.monto) if debitar else None
        cur = self._conn.execute(
            """INSERT INTO ahorros (monto_centavos, moneda, fecha, ubicacion, observaciones, entrada_mov_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (a.monto.cents, a.monto.moneda.value, a.fecha.isoformat(), a.ubicacion.strip(), a.observaciones.strip(), a.entrada_mov_id),
        )
        self._conn.commit()
        a.id = cur.lastrowid
        return a

    def editar_ahorro(self, a: Ahorro) -> None:
        if a.monto.cents <= 0:
            raise ValueError("El monto tiene que ser mayor a cero")
        self._conn.execute(
            "UPDATE ahorros SET monto_centavos = ?, moneda = ?, fecha = ?, ubicacion = ?, observaciones = ? WHERE id = ?",
            (a.monto.cents, a.monto.moneda.value, a.fecha.isoformat(), a.ubicacion.strip(), a.observaciones.strip(), a.id),
        )
        self._conn.commit()
        self._actualizar_mov(a.entrada_mov_id, a.fecha, a.monto)

    def retirar_ahorro(self, ahorro_id: int, fecha: date, monto: Money, acreditar: bool) -> None:
        a = self.obtener_ahorro(ahorro_id)
        mov_id = self._registrar_mov(TipoMovimiento.INGRESO, fecha, f"Retiro de ahorro: {a.ubicacion or 'sin ubicación'}", monto) if acreditar else None
        self._conn.execute(
            "UPDATE ahorros SET estado = 'finalizada', fecha_salida = ?, monto_salida_centavos = ?, salida_mov_id = ? WHERE id = ?",
            (fecha.isoformat(), monto.cents, mov_id, ahorro_id),
        )
        self._conn.commit()

    def eliminar_ahorro(self, ahorro_id: int) -> None:
        a = self.obtener_ahorro(ahorro_id)
        self._conn.execute("DELETE FROM ahorros WHERE id = ?", (ahorro_id,))
        self._conn.commit()
        self._borrar_movs(a.entrada_mov_id, a.salida_mov_id)

    # --- Acciones y Bonos/Lecap ---

    def _map_titulo(self, r) -> Titulo:
        return Titulo(
            id=r["id"], tipo=TipoTitulo(r["tipo"]), simbolo=r["simbolo"], nombre=r["nombre"],
            tipo_empresa=r["tipo_empresa"], plazo=Plazo(r["plazo"]), broker=r["broker"], transaccion=r["transaccion"],
            fecha_suscripcion=date.fromisoformat(r["fecha_suscripcion"]), cantidad=Decimal(r["cantidad"]),
            precio_compra=Money(r["precio_compra_centavos"], r["moneda"]),
            meses_pago=[int(m) for m in r["meses_pago"].split(",") if m],
            observaciones=r["observaciones"], estado=EstadoInversion(r["estado"]), fecha_salida=_fecha(r["fecha_salida"]),
            monto_salida=Money(r["monto_salida_centavos"], r["moneda"]) if r["monto_salida_centavos"] is not None else None,
            entrada_mov_id=r["entrada_mov_id"], salida_mov_id=r["salida_mov_id"],
        )

    def listar_titulos(self, tipo: TipoTitulo) -> list[Titulo]:
        rows = self._conn.execute(
            "SELECT * FROM titulos WHERE tipo = ? ORDER BY fecha_suscripcion DESC, id DESC", (tipo.value,)
        ).fetchall()
        return [self._map_titulo(r) for r in rows]

    def obtener_titulo(self, titulo_id: int) -> Titulo | None:
        r = self._conn.execute("SELECT * FROM titulos WHERE id = ?", (titulo_id,)).fetchone()
        return self._map_titulo(r) if r else None

    @staticmethod
    def _validar_titulo(t: Titulo) -> None:
        if not t.simbolo.strip():
            raise ValueError("Completá el símbolo")
        if t.cantidad <= 0:
            raise ValueError("La cantidad tiene que ser mayor a cero")
        if t.precio_compra.cents <= 0:
            raise ValueError("El precio de compra tiene que ser mayor a cero")

    def _valores_titulo(self, t: Titulo) -> tuple:
        return (
            t.estado.value, t.simbolo.strip().upper(), t.nombre.strip(), t.tipo_empresa.strip(), t.plazo.value,
            t.broker.strip(), t.transaccion.strip(), t.fecha_suscripcion.isoformat(), str(t.cantidad),
            t.precio_compra.cents, t.precio_compra.moneda.value, ",".join(str(m) for m in sorted(t.meses_pago)),
            t.observaciones.strip(),
        )

    def registrar_titulo(self, t: Titulo, debitar: bool) -> Titulo:
        self._validar_titulo(t)
        etiqueta = "Acción" if t.tipo == TipoTitulo.ACCION else "Bono"
        t.entrada_mov_id = self._registrar_mov(TipoMovimiento.EGRESO, t.fecha_suscripcion, f"{etiqueta}: {t.simbolo.upper()}", t.costo) if debitar else None
        cur = self._conn.execute(
            """INSERT INTO titulos (estado, simbolo, nombre, tipo_empresa, plazo, broker, transaccion, fecha_suscripcion,
                                    cantidad, precio_compra_centavos, moneda, meses_pago, observaciones, tipo, entrada_mov_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*self._valores_titulo(t), t.tipo.value, t.entrada_mov_id),
        )
        self._conn.commit()
        t.id = cur.lastrowid
        return t

    def editar_titulo(self, t: Titulo) -> None:
        self._validar_titulo(t)
        self._conn.execute(
            """UPDATE titulos SET estado = ?, simbolo = ?, nombre = ?, tipo_empresa = ?, plazo = ?, broker = ?, transaccion = ?,
                                  fecha_suscripcion = ?, cantidad = ?, precio_compra_centavos = ?, moneda = ?, meses_pago = ?,
                                  observaciones = ?
               WHERE id = ?""",
            (*self._valores_titulo(t), t.id),
        )
        self._conn.commit()
        self._actualizar_mov(t.entrada_mov_id, t.fecha_suscripcion, t.costo)

    def finalizar_titulo(self, titulo_id: int, fecha: date, monto: Money, acreditar: bool) -> None:
        """Venta: `monto` es el total cobrado."""
        t = self.obtener_titulo(titulo_id)
        mov_id = self._registrar_mov(TipoMovimiento.INGRESO, fecha, f"Venta: {t.simbolo}", monto) if acreditar else None
        self._conn.execute(
            "UPDATE titulos SET estado = 'finalizada', fecha_salida = ?, monto_salida_centavos = ?, salida_mov_id = ? WHERE id = ?",
            (fecha.isoformat(), monto.cents, mov_id, titulo_id),
        )
        self._conn.commit()

    def eliminar_titulo(self, titulo_id: int) -> None:
        t = self.obtener_titulo(titulo_id)
        self._conn.execute("DELETE FROM titulos WHERE id = ?", (titulo_id,))
        self._conn.commit()
        self._borrar_movs(t.entrada_mov_id, t.salida_mov_id)

    # --- FCI ---

    def _map_fci(self, r) -> Fci:
        return Fci(
            id=r["id"], estado=EstadoInversion(r["estado"]), simbolo=r["simbolo"], nombre=r["nombre"], plazo=Plazo(r["plazo"]),
            broker=r["broker"], transaccion=r["transaccion"], fecha_suscripcion=date.fromisoformat(r["fecha_suscripcion"]),
            monto=Money(r["monto_centavos"], r["moneda"]), fecha_rescate=_fecha(r["fecha_rescate"]),
            tna=Decimal(r["tna"]) if r["tna"] else None, observaciones=r["observaciones"], fecha_salida=_fecha(r["fecha_salida"]),
            monto_salida=Money(r["monto_salida_centavos"], r["moneda"]) if r["monto_salida_centavos"] is not None else None,
            entrada_mov_id=r["entrada_mov_id"], salida_mov_id=r["salida_mov_id"],
        )

    def listar_fcis(self) -> list[Fci]:
        rows = self._conn.execute("SELECT * FROM fcis ORDER BY fecha_suscripcion DESC, id DESC").fetchall()
        return [self._map_fci(r) for r in rows]

    def obtener_fci(self, fci_id: int) -> Fci | None:
        r = self._conn.execute("SELECT * FROM fcis WHERE id = ?", (fci_id,)).fetchone()
        return self._map_fci(r) if r else None

    @staticmethod
    def _validar_fci(f: Fci) -> None:
        if not f.nombre.strip():
            raise ValueError("Completá el nombre del fondo")
        if f.monto.cents <= 0:
            raise ValueError("El monto tiene que ser mayor a cero")

    def _valores_fci(self, f: Fci) -> tuple:
        return (
            f.estado.value, f.simbolo.strip().upper(), f.nombre.strip(), f.plazo.value, f.broker.strip(), f.transaccion.strip(),
            f.fecha_suscripcion.isoformat(), f.monto.cents, f.monto.moneda.value,
            f.fecha_rescate.isoformat() if f.fecha_rescate else None, str(f.tna) if f.tna is not None else None,
            f.observaciones.strip(),
        )

    def registrar_fci(self, f: Fci, debitar: bool) -> Fci:
        self._validar_fci(f)
        f.entrada_mov_id = self._registrar_mov(TipoMovimiento.EGRESO, f.fecha_suscripcion, f"FCI: {f.nombre.strip()}", f.monto) if debitar else None
        cur = self._conn.execute(
            """INSERT INTO fcis (estado, simbolo, nombre, plazo, broker, transaccion, fecha_suscripcion, monto_centavos, moneda,
                                 fecha_rescate, tna, observaciones, entrada_mov_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*self._valores_fci(f), f.entrada_mov_id),
        )
        self._conn.commit()
        f.id = cur.lastrowid
        return f

    def editar_fci(self, f: Fci) -> None:
        self._validar_fci(f)
        self._conn.execute(
            """UPDATE fcis SET estado = ?, simbolo = ?, nombre = ?, plazo = ?, broker = ?, transaccion = ?, fecha_suscripcion = ?,
                               monto_centavos = ?, moneda = ?, fecha_rescate = ?, tna = ?, observaciones = ?
               WHERE id = ?""",
            (*self._valores_fci(f), f.id),
        )
        self._conn.commit()
        self._actualizar_mov(f.entrada_mov_id, f.fecha_suscripcion, f.monto)

    def rescatar_fci(self, fci_id: int, fecha: date, monto: Money, acreditar: bool) -> None:
        f = self.obtener_fci(fci_id)
        mov_id = self._registrar_mov(TipoMovimiento.INGRESO, fecha, f"Rescate FCI: {f.nombre}", monto) if acreditar else None
        self._conn.execute(
            """UPDATE fcis SET estado = 'finalizada', fecha_salida = ?, fecha_rescate = ?, monto_salida_centavos = ?, salida_mov_id = ?
               WHERE id = ?""",
            (fecha.isoformat(), fecha.isoformat(), monto.cents, mov_id, fci_id),
        )
        self._conn.commit()

    def eliminar_fci(self, fci_id: int) -> None:
        f = self.obtener_fci(fci_id)
        self._conn.execute("DELETE FROM fcis WHERE id = ?", (fci_id,))
        self._conn.commit()
        self._borrar_movs(f.entrada_mov_id, f.salida_mov_id)

    # --- Crypto ---

    def _map_crypto(self, r) -> OperacionCryptoRegistro:
        return OperacionCryptoRegistro(
            id=r["id"], fecha=date.fromisoformat(r["fecha"]), operacion=OperacionCrypto(r["operacion"]), activo=r["activo"],
            monto=Money(r["monto_centavos"], r["moneda"]), precio_unitario=Decimal(r["precio_unitario"]),
            cantidad=Decimal(r["cantidad"]), observaciones=r["observaciones"], mov_id=r["mov_id"],
        )

    def listar_crypto(self) -> list[OperacionCryptoRegistro]:
        rows = self._conn.execute("SELECT * FROM crypto_operaciones ORDER BY fecha DESC, id DESC").fetchall()
        return [self._map_crypto(r) for r in rows]

    def obtener_crypto(self, op_id: int) -> OperacionCryptoRegistro | None:
        r = self._conn.execute("SELECT * FROM crypto_operaciones WHERE id = ?", (op_id,)).fetchone()
        return self._map_crypto(r) if r else None

    @staticmethod
    def _validar_crypto(op: OperacionCryptoRegistro) -> None:
        if not op.activo.strip():
            raise ValueError("Completá la moneda (ej: USDT)")
        if op.monto.cents <= 0 or op.cantidad <= 0 or op.precio_unitario <= 0:
            raise ValueError("Monto, precio unitario y cantidad tienen que ser mayores a cero")

    def _valores_crypto(self, op: OperacionCryptoRegistro) -> tuple:
        return (
            op.fecha.isoformat(), op.operacion.value, op.activo.strip().upper(), op.monto.cents, op.monto.moneda.value,
            str(op.precio_unitario), str(op.cantidad), op.observaciones.strip(),
        )

    def registrar_crypto(self, op: OperacionCryptoRegistro, operar_con_cuenta: bool) -> OperacionCryptoRegistro:
        """Compra: si `operar_con_cuenta`, descuenta el monto de la app. Venta: lo suma."""
        self._validar_crypto(op)
        if op.operacion == OperacionCrypto.VENTA:
            tenencia = next((t for t in tenencias_crypto(self.listar_crypto(), op.monto.moneda) if t.activo == op.activo.strip().upper()), None)
            disponible = tenencia.cantidad if tenencia else Decimal(0)
            if op.cantidad > disponible:
                raise ValueError(f"No podés vender {op.cantidad} {op.activo.upper()}: tenés {disponible}")
        op.mov_id = None
        if operar_con_cuenta:
            es_compra = op.operacion == OperacionCrypto.COMPRA
            op.mov_id = self._registrar_mov(
                TipoMovimiento.EGRESO if es_compra else TipoMovimiento.INGRESO, op.fecha,
                f"{'Compra' if es_compra else 'Venta'} crypto: {op.activo.strip().upper()}", op.monto,
            )
        cur = self._conn.execute(
            """INSERT INTO crypto_operaciones (fecha, operacion, activo, monto_centavos, moneda, precio_unitario, cantidad,
                                               observaciones, mov_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*self._valores_crypto(op), op.mov_id),
        )
        self._conn.commit()
        op.id = cur.lastrowid
        return op

    def editar_crypto(self, op: OperacionCryptoRegistro) -> None:
        self._validar_crypto(op)
        self._conn.execute(
            """UPDATE crypto_operaciones SET fecha = ?, operacion = ?, activo = ?, monto_centavos = ?, moneda = ?,
                                             precio_unitario = ?, cantidad = ?, observaciones = ?
               WHERE id = ?""",
            (*self._valores_crypto(op), op.id),
        )
        self._conn.commit()
        self._actualizar_mov(op.mov_id, op.fecha, op.monto)

    def eliminar_crypto(self, op_id: int) -> None:
        op = self.obtener_crypto(op_id)
        self._conn.execute("DELETE FROM crypto_operaciones WHERE id = ?", (op_id,))
        self._conn.commit()
        self._borrar_movs(op.mov_id)

    # --- Resumen ---

    def totales_por_apartado(self, moneda: Moneda) -> dict[str, Totales]:
        return {
            "ahorro": totales_de(self.listar_ahorros(), moneda),
            "acciones": totales_de(self.listar_titulos(TipoTitulo.ACCION), moneda),
            "bonos": totales_de(self.listar_titulos(TipoTitulo.BONO), moneda),
            "fci": totales_de(self.listar_fcis(), moneda),
            "crypto": totales_crypto(self.listar_crypto(), moneda),
        }

    # --- Calendario ---

    def pagos_por_mes(self) -> dict[int, list[Titulo]]:
        """Acciones y bonos en posesion agrupados por mes en que pagan
        dividendos o renta (1-12). Un simbolo con varias compras aparece una vez."""
        por_mes: dict[int, list[Titulo]] = {m: [] for m in range(1, 13)}
        vistos: set[tuple[int, str, str]] = set()
        for tipo in TipoTitulo:
            for t in self.listar_titulos(tipo):
                if t.estado != EstadoInversion.VIGENTE:
                    continue
                for mes in t.meses_pago:
                    clave = (mes, t.tipo.value, t.simbolo.upper())
                    if clave not in vistos:
                        vistos.add(clave)
                        por_mes[mes].append(t)
        for lista in por_mes.values():
            lista.sort(key=lambda t: t.simbolo)
        return por_mes

    def eventos_del_mes(self, anio: int, mes: int) -> list[EventoInversion]:
        """Suscripciones, ventas, rescates, retiros y operaciones crypto del mes, por fecha."""
        def en_mes(d: date | None) -> bool:
            return d is not None and d.year == anio and d.month == mes

        eventos: list[EventoInversion] = []
        for a in self.listar_ahorros():
            nombre = a.ubicacion or "Ahorro"
            if en_mes(a.fecha):
                eventos.append(EventoInversion(a.fecha, "ahorro", nombre, "Ahorro cargado", a.monto))
            if en_mes(a.fecha_salida):
                eventos.append(EventoInversion(a.fecha_salida, "ahorro", nombre, "Retiro", a.monto_salida))
        for tipo in TipoTitulo:
            apartado = "acciones" if tipo == TipoTitulo.ACCION else "bonos"
            for t in self.listar_titulos(tipo):
                if en_mes(t.fecha_suscripcion):
                    eventos.append(EventoInversion(t.fecha_suscripcion, apartado, t.simbolo, f"Compra de {fmt_cantidad(t.cantidad)} u.", t.costo))
                if en_mes(t.fecha_salida):
                    eventos.append(EventoInversion(t.fecha_salida, apartado, t.simbolo, "Venta", t.monto_salida))
        for f in self.listar_fcis():
            if en_mes(f.fecha_suscripcion):
                eventos.append(EventoInversion(f.fecha_suscripcion, "fci", f.nombre, "Suscripción", f.monto))
            if f.estado == EstadoInversion.FINALIZADA and en_mes(f.fecha_salida):
                eventos.append(EventoInversion(f.fecha_salida, "fci", f.nombre, "Rescate", f.monto_salida))
            elif f.estado == EstadoInversion.VIGENTE and en_mes(f.fecha_rescate):
                eventos.append(EventoInversion(f.fecha_rescate, "fci", f.nombre, "Rescate previsto", f.monto, previsto=True))
        for op in self.listar_crypto():
            if en_mes(op.fecha):
                es_compra = op.operacion == OperacionCrypto.COMPRA
                eventos.append(EventoInversion(op.fecha, "crypto", op.activo, f"{'Compra' if es_compra else 'Venta'} de {fmt_cantidad(op.cantidad)} u.", op.monto))
        return sorted(eventos, key=lambda e: e.fecha)
