from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date

from ..domain.dates import add_months
from ..domain.models import EstadoMovimiento, GastoFijo, Movimiento, TipoMovimiento
from ..domain.money import Money
from ..repositories.gastos_fijos import GastoFijoRepository
from ..repositories.movimientos import MovimientoRepository


@dataclass
class OcurrenciaGastoFijo:
    gasto: GastoFijo
    fecha: date
    ya_registrado: bool


class GastoFijoService:
    def __init__(self, conn: sqlite3.Connection):
        self._repo = GastoFijoRepository(conn)
        self._movimientos = MovimientoRepository(conn)

    def registrar(self, concepto: str, detalle: str, monto: Money, categoria_id: int, dia_mes: int) -> GastoFijo:
        if not concepto.strip():
            raise ValueError("El concepto no puede estar vacio")
        if not (1 <= dia_mes <= 28):
            raise ValueError("El dia del mes debe estar entre 1 y 28")
        gasto = GastoFijo(id=None, concepto=concepto.strip(), detalle=detalle, monto=monto, categoria_id=categoria_id, dia_mes=dia_mes)
        gasto.id = self._repo.crear(gasto)
        return gasto

    def editar(self, gasto_fijo_id: int, nuevo_monto: Money, nuevo_dia_mes: int) -> GastoFijo:
        """Cambia el monto y/o el dia de vencimiento a partir de ahora. Los
        movimientos ya registrados en meses anteriores no se modifican."""
        gasto = self.obtener(gasto_fijo_id)
        if gasto is None:
            raise ValueError("Gasto fijo inexistente")
        if nuevo_monto.cents <= 0:
            raise ValueError("El monto debe ser mayor a cero")
        if not (1 <= nuevo_dia_mes <= 28):
            raise ValueError("El día de vencimiento debe estar entre 1 y 28")
        gasto.monto = nuevo_monto
        gasto.dia_mes = nuevo_dia_mes
        self._repo.actualizar(gasto)
        return gasto

    def eliminar(self, gasto_fijo_id: int) -> None:
        self._repo.eliminar(gasto_fijo_id)

    def obtener(self, gasto_fijo_id: int) -> GastoFijo | None:
        return next((g for g in self._repo.listar(solo_activos=False) if g.id == gasto_fijo_id), None)

    def listar(self, solo_activos: bool = True) -> list[GastoFijo]:
        return self._repo.listar(solo_activos)

    def ya_registrado_este_mes(self, gasto_fijo_id: int, anio: int, mes: int) -> bool:
        return self._movimientos.existe_para_gasto_fijo(gasto_fijo_id, anio, mes)

    def _fecha_del_mes(self, gasto: GastoFijo, anio: int, mes: int) -> date:
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return date(anio, mes, min(gasto.dia_mes, ultimo_dia))

    def proximas_ocurrencias(self, anio: int, mes: int) -> list[OcurrenciaGastoFijo]:
        """Ocurrencia de cada gasto fijo activo para el mes dado (pagada o no)."""
        ocurrencias = []
        for gasto in self._repo.listar(solo_activos=True):
            fecha = self._fecha_del_mes(gasto, anio, mes)
            ya = self.ya_registrado_este_mes(gasto.id, anio, mes)
            ocurrencias.append(OcurrenciaGastoFijo(gasto=gasto, fecha=fecha, ya_registrado=ya))
        return ocurrencias

    def generar_movimiento_del_mes(self, gasto_fijo_id: int, hoy: date | None = None) -> Movimiento:
        """Crea el movimiento de egreso correspondiente al mes actual para un gasto fijo."""
        hoy = hoy or date.today()
        gasto = self.obtener(gasto_fijo_id)
        if gasto is None:
            raise ValueError("Gasto fijo inexistente")
        if self.ya_registrado_este_mes(gasto_fijo_id, hoy.year, hoy.month):
            raise ValueError("Este gasto fijo ya tiene un pago registrado este mes")

        fecha = self._fecha_del_mes(gasto, hoy.year, hoy.month)
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
            gasto_fijo_id=gasto.id,
        )
        movimiento.id = self._movimientos.crear(movimiento)
        return movimiento

    def proximo_vencimiento(self, gasto: GastoFijo, desde: date | None = None) -> date:
        """La proxima fecha (hoy o futura) en la que vence este gasto fijo."""
        desde = desde or date.today()
        fecha_este_mes = self._fecha_del_mes(gasto, desde.year, desde.month)
        if fecha_este_mes >= desde:
            return fecha_este_mes
        siguiente = add_months(desde.replace(day=1), 1)
        return self._fecha_del_mes(gasto, siguiente.year, siguiente.month)
