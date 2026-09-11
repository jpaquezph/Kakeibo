from __future__ import annotations

import sqlite3
from datetime import date

from ..domain.models import EstadoMovimiento, GastoFijo, Movimiento, TipoMovimiento
from ..repositories.gastos_fijos import GastoFijoRepository
from ..repositories.movimientos import MovimientoRepository


class GastoFijoService:
    def __init__(self, conn: sqlite3.Connection):
        self._repo = GastoFijoRepository(conn)
        self._movimientos = MovimientoRepository(conn)

    def crear(self, gasto: GastoFijo) -> GastoFijo:
        gasto.id = self._repo.crear(gasto)
        return gasto

    def eliminar(self, gasto_fijo_id: int) -> None:
        self._repo.eliminar(gasto_fijo_id)

    def listar(self, solo_activos: bool = True) -> list[GastoFijo]:
        return self._repo.listar(solo_activos)

    def generar_movimiento_del_mes(self, gasto_fijo_id: int, hoy: date | None = None) -> Movimiento:
        """Crea el movimiento de egreso correspondiente al mes actual para un gasto fijo."""
        hoy = hoy or date.today()
        gastos = {g.id: g for g in self._repo.listar(solo_activos=False)}
        gasto = gastos.get(gasto_fijo_id)
        if gasto is None:
            raise ValueError("Gasto fijo inexistente")

        import calendar

        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        fecha = date(hoy.year, hoy.month, min(gasto.dia_mes, ultimo_dia))

        movimiento = Movimiento(
            id=None,
            tipo=TipoMovimiento.EGRESO,
            fecha=fecha,
            concepto=gasto.concepto,
            detalle=gasto.detalle,
            monto=gasto.monto,
            categoria_id=gasto.categoria_id,
            estado=EstadoMovimiento.CONFIRMADO,
            fijo=True,
        )
        movimiento.id = self._movimientos.crear(movimiento)
        return movimiento
