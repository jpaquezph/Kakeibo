"""Entidades de dominio. Sin dependencias de UI ni de la base de datos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from .money import Money, Moneda


class TipoMovimiento(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"


class EstadoMovimiento(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"


class EstadoPrestamo(str, Enum):
    ACTIVO = "activo"
    PAGADO = "pagado"
    CANCELADO = "cancelado"


CATEGORIAS_BASE: list[dict] = [
    {"nombre": "Préstamos", "color": "#9C3D63", "icono": "account_balance", "tipo": "egreso"},
    {"nombre": "Comida", "color": "#EB6834", "icono": "restaurant", "tipo": "egreso"},
    {"nombre": "Farmacia", "color": "#E87BA4", "icono": "local_pharmacy", "tipo": "egreso"},
    {"nombre": "Mascotas", "color": "#C98500", "icono": "pets", "tipo": "egreso"},
    {"nombre": "Salidas", "color": "#4A3AA7", "icono": "celebration", "tipo": "egreso"},
    {"nombre": "Casa", "color": "#1BAF7A", "icono": "home", "tipo": "egreso"},
    {"nombre": "Otros", "color": "#898781", "icono": "category", "tipo": "egreso"},
    {"nombre": "Servicios esenciales", "color": "#2A78D6", "icono": "bolt", "tipo": "egreso"},
    {"nombre": "Servicios no esenciales", "color": "#6DA7EC", "icono": "tv", "tipo": "egreso"},
    {"nombre": "Auto", "color": "#EDA100", "icono": "directions_car", "tipo": "egreso"},
    {"nombre": "Tarjeta de crédito", "color": "#E34948", "icono": "credit_card", "tipo": "egreso"},
    {"nombre": "Sueldo", "color": "#1E8E4A", "icono": "payments", "tipo": "ingreso"},
    {"nombre": "Venta", "color": "#16A34A", "icono": "sell", "tipo": "ingreso"},
    {"nombre": "Extra", "color": "#4CAF50", "icono": "add_circle", "tipo": "ingreso"},
    {"nombre": "Regalo", "color": "#2E7D32", "icono": "card_giftcard", "tipo": "ingreso"},
    {"nombre": "Otros ingresos", "color": "#66BB6A", "icono": "more_horiz", "tipo": "ingreso"},
    {"nombre": "Cambio de moneda (entregado)", "color": "#0E7C86", "icono": "currency_exchange", "tipo": "egreso"},
    {"nombre": "Cambio de moneda (recibido)", "color": "#0E7C86", "icono": "currency_exchange", "tipo": "ingreso"},
    {"nombre": "Inversiones", "color": "#5C6BC0", "icono": "trending_up", "tipo": "egreso"},
    {"nombre": "Retiro de inversiones", "color": "#5C6BC0", "icono": "savings", "tipo": "ingreso"},
]

# Categorias que la app usa por su nombre (pagos de tarjeta y de prestamos,
# compra/venta de dolares, inversiones): no se pueden quitar.
CATEGORIAS_DEL_SISTEMA = frozenset({
    "Tarjeta de crédito",
    "Préstamos",
    "Cambio de moneda (entregado)",
    "Cambio de moneda (recibido)",
    "Inversiones",
    "Retiro de inversiones",
})


@dataclass(slots=True)
class Usuario:
    id: int | None
    username: str
    password_hash: str
    salt: str
    created_at: datetime | None = None


@dataclass(slots=True)
class Categoria:
    id: int | None
    nombre: str
    color: str
    icono: str
    tipo: TipoMovimiento = TipoMovimiento.EGRESO
    activa: bool = True  # False = quitada: no se ofrece mas, pero lo ya cargado la conserva


@dataclass(slots=True)
class Movimiento:
    id: int | None
    tipo: TipoMovimiento
    fecha: date
    concepto: str
    detalle: str
    monto: Money
    categoria_id: int
    estado: EstadoMovimiento = EstadoMovimiento.CONFIRMADO
    fijo: bool = False
    tarjeta_id: int | None = None
    gasto_fijo_id: int | None = None
    categoria_nombre: str | None = None
    categoria_color: str | None = None
    categoria_icono: str | None = None
    metodo_pago: str = ""  # clave de METODOS_PAGO; "" = sin especificar

    def __post_init__(self):
        if not self.concepto.strip():
            raise ValueError("El concepto no puede estar vacio")
        if self.monto.cents <= 0:
            raise ValueError("El monto debe ser mayor a cero")


@dataclass(slots=True)
class GastoFijo:
    id: int | None
    concepto: str
    detalle: str
    monto: Money
    categoria_id: int
    dia_mes: int
    activo: bool = True
    tarjeta_id: int | None = None  # debito automatico en esta tarjeta
    metodo_pago: str = ""  # clave de METODOS_PAGO; "" = sin especificar. Con debito automatico no se usa


# Como se paga un gasto fijo. El debito automatico no esta aca: se indica con
# la tarjeta del gasto (tarjeta_id), porque ademas suma al resumen de esa tarjeta.
METODOS_PAGO: dict[str, str] = {
    "efectivo": "Efectivo",
    "transferencia": "Transferencia",
    "tarjeta_debito": "Tarjeta de débito",
    "billetera": "Billetera virtual (Mercado Pago, etc.)",
    "otro": "Otro",
}


@dataclass(slots=True)
class Tarjeta:
    id: int | None
    nombre: str
    banco: str
    ultimos_digitos: str
    # Sin uso desde la 1.3: una tarjeta opera en ARS y en USD y cada compra
    # tiene su propia moneda. Se conserva por compatibilidad con la base.
    moneda: Moneda
    color: str = "#D6467E"
    activa: bool = True
    dia_cierre: int | None = None  # dia del mes en que cierra el resumen (opcional)
    dia_vencimiento: int | None = None  # dia del mes en que vence el resumen (opcional)


@dataclass(slots=True)
class CuotaCompra:
    id: int | None
    compra_id: int
    numero_cuota: int
    monto: Money
    fecha_vencimiento: date
    pagada: bool = False
    fecha_pago: date | None = None


@dataclass(slots=True)
class PagoTarjeta:
    """Pago del resumen de una tarjeta en un mes, en una moneda. `monto` es lo
    que se pago; `calculado`, lo que sumaban cuotas, compras en 1 pago y
    debitos automaticos (difieren si el saldo se corrigio al pagar)."""
    id: int | None
    tarjeta_id: int
    anio: int
    mes: int
    monto: Money
    calculado: Money
    fecha_pago: date
    movimiento_id: int | None = None  # el egreso que genero el pago (los debitos automaticos tienen el suyo)


@dataclass(slots=True)
class Compra:
    id: int | None
    tarjeta_id: int
    fecha: date
    concepto: str
    detalle: str
    monto_total: Money
    categoria_id: int
    cantidad_cuotas: int
    cuotas: list[CuotaCompra] = field(default_factory=list)
    # En que cuota se estaba al cargar la compra (1 = compra nueva). Esa cuota
    # es la primera que se paga despues de `fecha`; las anteriores ya vencieron.
    cuota_inicial: int = 1

    def __post_init__(self):
        if not self.concepto.strip():
            raise ValueError("El concepto no puede estar vacio")
        if self.monto_total.cents <= 0:
            raise ValueError("El monto debe ser mayor a cero")
        if self.cantidad_cuotas <= 0:
            raise ValueError("La cantidad de cuotas debe ser mayor a cero")

    @property
    def cuotas_pagadas(self) -> int:
        return sum(1 for c in self.cuotas if c.pagada)

    @property
    def cuotas_restantes(self) -> int:
        return self.cantidad_cuotas - self.cuotas_pagadas

    @property
    def cuota_actual(self) -> int:
        return min(self.cuotas_pagadas + 1, self.cantidad_cuotas)

    @property
    def monto_cuota(self) -> Money:
        return self.cuotas[0].monto if self.cuotas else Money.zero(self.monto_total.moneda)

    @property
    def monto_pendiente(self) -> Money:
        total = Money.zero(self.monto_total.moneda)
        for c in self.cuotas:
            if not c.pagada:
                total = total + c.monto
        return total


@dataclass(slots=True)
class CuotaPrestamo:
    id: int | None
    prestamo_id: int
    numero_cuota: int
    monto: Money
    fecha_vencimiento: date
    pagada: bool = False
    fecha_pago: date | None = None


@dataclass(slots=True)
class Prestamo:
    id: int | None
    nombre: str
    detalle: str
    monto_original: Money
    cantidad_cuotas: int
    fecha_inicio: date
    estado: EstadoPrestamo = EstadoPrestamo.ACTIVO
    cuotas: list[CuotaPrestamo] = field(default_factory=list)
    dia_vencimiento: int | None = None  # dia del mes en que vencen las cuotas (None: el de fecha_inicio)

    def __post_init__(self):
        if not self.nombre.strip():
            raise ValueError("El nombre del prestamo no puede estar vacio")
        if self.monto_original.cents <= 0:
            raise ValueError("El monto total debe ser mayor a cero")
        if self.cantidad_cuotas <= 0:
            raise ValueError("La cantidad de cuotas debe ser mayor a cero")

    @property
    def cuotas_pagadas(self) -> int:
        return sum(1 for c in self.cuotas if c.pagada)

    @property
    def cuotas_restantes(self) -> int:
        return self.cantidad_cuotas - self.cuotas_pagadas

    @property
    def total_pagado(self) -> Money:
        total = Money.zero(self.monto_original.moneda)
        for c in self.cuotas:
            if c.pagada:
                total = total + c.monto
        return total

    @property
    def total_pendiente(self) -> Money:
        total = Money.zero(self.monto_original.moneda)
        for c in self.cuotas:
            if not c.pagada:
                total = total + c.monto
        return total
