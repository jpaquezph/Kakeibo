from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from ..domain.models import Movimiento, TipoMovimiento
from ..domain.money import Money, Moneda
from ..repositories.categorias import CategoriaRepository
from ..repositories.movimientos import MovimientoRepository

CATEGORIA_EGRESO = "Cambio de moneda (entregado)"
CATEGORIA_INGRESO = "Cambio de moneda (recibido)"


class CambioDivisaService:
    """Registra operaciones de compra/venta de dolares como dos movimientos
    vinculados (lo que sale de una moneda y lo que entra en la otra), para
    que impacten en el resumen e historial como cualquier otro movimiento."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._movimientos = MovimientoRepository(conn)
        self._categorias = CategoriaRepository(conn)

    def _categoria_id(self, nombre: str) -> int:
        categoria = next((c for c in self._categorias.listar() if c.nombre == nombre), None)
        if categoria is None:
            raise ValueError(f"Falta la categoria base '{nombre}'")
        return categoria.id

    def _crear_movimiento(self, tipo: TipoMovimiento, fecha: date, concepto: str, detalle: str, monto: Money) -> Movimiento:
        categoria_id = self._categoria_id(CATEGORIA_EGRESO if tipo == TipoMovimiento.EGRESO else CATEGORIA_INGRESO)
        movimiento = Movimiento(
            id=None, tipo=tipo, fecha=fecha, concepto=concepto, detalle=detalle,
            monto=monto, categoria_id=categoria_id,
        )
        movimiento.id = self._movimientos.crear(movimiento)
        return movimiento

    def _detalle_cotizacion(self, cotizacion: Decimal) -> str:
        return f"Cotización usada: {Money.from_decimal(cotizacion, Moneda.ARS).formatted()} por USD 1"

    def comprar_dolares(self, fecha: date, cantidad_usd: Money, cotizacion: Decimal) -> tuple[Movimiento, Movimiento]:
        """El usuario entrega pesos y recibe dolares."""
        if cantidad_usd.moneda != Moneda.USD:
            raise ValueError("La cantidad debe estar en USD")
        if cantidad_usd.cents <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if cotizacion <= 0:
            raise ValueError("La cotización debe ser mayor a cero")
        total_ars = Money.from_decimal(cantidad_usd.amount * cotizacion, Moneda.ARS)
        detalle = self._detalle_cotizacion(cotizacion)
        egreso = self._crear_movimiento(TipoMovimiento.EGRESO, fecha, "Compra de dólares", detalle, total_ars)
        ingreso = self._crear_movimiento(TipoMovimiento.INGRESO, fecha, "Compra de dólares", detalle, cantidad_usd)
        return egreso, ingreso

    def vender_dolares(self, fecha: date, cantidad_usd: Money, cotizacion: Decimal) -> tuple[Movimiento, Movimiento]:
        """El usuario entrega dolares y recibe pesos."""
        if cantidad_usd.moneda != Moneda.USD:
            raise ValueError("La cantidad debe estar en USD")
        if cantidad_usd.cents <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if cotizacion <= 0:
            raise ValueError("La cotización debe ser mayor a cero")
        total_ars = Money.from_decimal(cantidad_usd.amount * cotizacion, Moneda.ARS)
        detalle = self._detalle_cotizacion(cotizacion)
        egreso = self._crear_movimiento(TipoMovimiento.EGRESO, fecha, "Venta de dólares", detalle, cantidad_usd)
        ingreso = self._crear_movimiento(TipoMovimiento.INGRESO, fecha, "Venta de dólares", detalle, total_ars)
        return egreso, ingreso
