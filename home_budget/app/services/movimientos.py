from __future__ import annotations

import sqlite3
from datetime import date

from ..domain.models import EstadoMovimiento, Movimiento, TipoMovimiento
from ..domain.money import Money, Moneda
from ..repositories.movimientos import FiltroMovimientos, MovimientoRepository


class MovimientoService:
    def __init__(self, conn: sqlite3.Connection):
        self._repo = MovimientoRepository(conn)

    def registrar(
        self,
        tipo: TipoMovimiento,
        fecha: date,
        concepto: str,
        detalle: str,
        monto: Money,
        categoria_id: int,
        estado: EstadoMovimiento = EstadoMovimiento.CONFIRMADO,
        fijo: bool = False,
        tarjeta_id: int | None = None,
    ) -> Movimiento:
        movimiento = Movimiento(
            id=None,
            tipo=tipo,
            fecha=fecha,
            concepto=concepto,
            detalle=detalle,
            monto=monto,
            categoria_id=categoria_id,
            estado=estado,
            fijo=fijo,
            tarjeta_id=tarjeta_id,
        )
        movimiento.id = self._repo.crear(movimiento)
        return movimiento

    def editar(self, movimiento: Movimiento) -> None:
        self._repo.actualizar(movimiento)

    def eliminar(self, movimiento_id: int) -> None:
        self._repo.eliminar(movimiento_id)

    def obtener(self, movimiento_id: int) -> Movimiento | None:
        return self._repo.obtener(movimiento_id)

    def listar(self, filtro: FiltroMovimientos | None = None) -> list[Movimiento]:
        return self._repo.listar(filtro)

    def total_por_moneda(self, tipo: TipoMovimiento, moneda: Moneda, filtro: FiltroMovimientos | None = None) -> Money:
        filtro = filtro or FiltroMovimientos()
        filtro.tipo = tipo
        filtro.moneda = moneda
        total = Money.zero(moneda)
        for m in self._repo.listar(filtro):
            total = total + m.monto
        return total
