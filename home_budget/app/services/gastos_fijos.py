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
from ..repositories.tarjetas import TarjetaRepository


@dataclass
class FiltroGastosFijos:
    """Filtros y orden de la lista de Gastos fijos. `estado`: "todos",
    "finalizados" (pago del mes ya registrado) o "en_curso" (falta pagar este
    mes). `debito`: "todos", "con" o "sin" debito automatico. `orden`:
    "vencimiento", "monto_mayor", "monto_menor" o "alfabetico"."""
    estado: str = "todos"
    debito: str = "todos"
    categoria_id: int | None = None
    orden: str = "vencimiento"

    @property
    def activo(self) -> bool:
        return (self.estado, self.debito, self.categoria_id) != ("todos", "todos", None)


@dataclass
class OcurrenciaGastoFijo:
    gasto: GastoFijo
    fecha: date
    ya_registrado: bool


class GastoFijoService:
    def __init__(self, conn: sqlite3.Connection):
        self._repo = GastoFijoRepository(conn)
        self._movimientos = MovimientoRepository(conn)
        self._tarjetas = TarjetaRepository(conn)

    def _validar_tarjeta(self, tarjeta_id: int | None, monto: Money):
        """Devuelve la tarjeta del debito automatico (o None si no tiene)."""
        if tarjeta_id is None:
            return None
        tarjeta = self._tarjetas.obtener(tarjeta_id)
        if tarjeta is None:
            raise ValueError("La tarjeta elegida no existe")
        if tarjeta.dia_vencimiento is None:
            raise ValueError(
                f"La tarjeta {tarjeta.nombre} no tiene cargado el día de vencimiento. "
                "Cargalo en la sección Tarjetas (editar tarjeta) para usar débito automático."
            )
        return tarjeta

    @staticmethod
    def _dia_guardado(tarjeta) -> int:
        """Con debito automatico el vencimiento es el de la tarjeta; se guarda
        igual un dia valido (1-28) por si la tarjeta se borra."""
        return min(tarjeta.dia_vencimiento, 28)

    def registrar(
        self, concepto: str, detalle: str, monto: Money, categoria_id: int, dia_mes: int | None, tarjeta_id: int | None = None,
    ) -> GastoFijo:
        """`tarjeta_id`: si se paga por debito automatico, la tarjeta a la que se
        debita. En ese caso `dia_mes` se ignora: vence cuando vence la tarjeta."""
        if not concepto.strip():
            raise ValueError("El concepto no puede estar vacio")
        tarjeta = self._validar_tarjeta(tarjeta_id, monto)
        if tarjeta is not None:
            dia_mes = self._dia_guardado(tarjeta)
        elif dia_mes is None or not (1 <= dia_mes <= 28):
            raise ValueError("El dia del mes debe estar entre 1 y 28")
        gasto = GastoFijo(id=None, concepto=concepto.strip(), detalle=detalle, monto=monto, categoria_id=categoria_id,
                          dia_mes=dia_mes, tarjeta_id=tarjeta_id)
        gasto.id = self._repo.crear(gasto)
        return gasto

    def editar(self, gasto_fijo_id: int, nuevo_monto: Money, nuevo_dia_mes: int | None, tarjeta_id: int | None | object = ...) -> GastoFijo:
        """Cambia el monto y/o el dia de vencimiento a partir de ahora. Los
        movimientos ya registrados en meses anteriores no se modifican. Con
        debito automatico el dia se ignora: vence cuando vence la tarjeta."""
        gasto = self.obtener(gasto_fijo_id)
        if gasto is None:
            raise ValueError("Gasto fijo inexistente")
        if nuevo_monto.cents <= 0:
            raise ValueError("El monto debe ser mayor a cero")
        if tarjeta_id is not ...:  # sin pasarlo, se mantiene el debito que tenia
            gasto.tarjeta_id = tarjeta_id
        tarjeta = self._validar_tarjeta(gasto.tarjeta_id, nuevo_monto)
        if tarjeta is not None:
            nuevo_dia_mes = self._dia_guardado(tarjeta)
        elif nuevo_dia_mes is None or not (1 <= nuevo_dia_mes <= 28):
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

    def filtrar_y_ordenar(self, gastos: list[GastoFijo], filtro: FiltroGastosFijos, hoy: date | None = None) -> list[GastoFijo]:
        hoy = hoy or date.today()
        resultado = []
        for g in gastos:
            if filtro.categoria_id is not None and g.categoria_id != filtro.categoria_id:
                continue
            if filtro.debito == "con" and g.tarjeta_id is None or filtro.debito == "sin" and g.tarjeta_id is not None:
                continue
            if filtro.estado != "todos":
                pagado = self.ya_registrado_este_mes(g.id, hoy.year, hoy.month)
                if (filtro.estado == "finalizados") != pagado:
                    continue
            resultado.append(g)

        if filtro.orden == "alfabetico":
            resultado.sort(key=lambda g: g.concepto.casefold())
        elif filtro.orden in ("monto_mayor", "monto_menor"):
            # Pesos y dolares no se comparan entre si: primero ARS, despues USD.
            signo = -1 if filtro.orden == "monto_mayor" else 1
            resultado.sort(key=lambda g: (g.monto.moneda.value, signo * g.monto.cents))
        else:
            resultado.sort(key=lambda g: (self.proximo_vencimiento(g, hoy), g.concepto.casefold()))
        return resultado

    def ya_registrado_este_mes(self, gasto_fijo_id: int, anio: int, mes: int) -> bool:
        return self._movimientos.existe_para_gasto_fijo(gasto_fijo_id, anio, mes)

    def dia_vencimiento(self, gasto: GastoFijo) -> int:
        """Con debito automatico vence el dia en que vence la tarjeta (asi, si
        se cambia el dia de la tarjeta, sus debitos lo siguen); si no, el dia
        propio del gasto."""
        if gasto.tarjeta_id is not None:
            tarjeta = self._tarjetas.obtener(gasto.tarjeta_id)
            if tarjeta is not None and tarjeta.dia_vencimiento is not None:
                return tarjeta.dia_vencimiento
        return gasto.dia_mes

    def _fecha_del_mes(self, gasto: GastoFijo, anio: int, mes: int) -> date:
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return date(anio, mes, min(self.dia_vencimiento(gasto), ultimo_dia))

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

    # --- Debito automatico ---
    # El gasto se registra una sola vez, como gasto fijo (un movimiento con
    # fijo=1). La tarjeta solo lo muestra dentro de su resumen del mes y, al
    # pagar la tarjeta, registra ese mismo pago: no se crea una compra aparte,
    # para no contarlo dos veces.

    def debitos_del_mes(self, tarjeta_id: int, anio: int, mes: int) -> list[OcurrenciaGastoFijo]:
        return [o for o in self.proximas_ocurrencias(anio, mes) if o.gasto.tarjeta_id == tarjeta_id]

    def total_debitos_pendientes(self, tarjeta_id: int, anio: int, mes: int, moneda) -> Money:
        """Lo que falta pagar de los debitos de esta tarjeta en el mes, en esa
        moneda: suma al total a pagar de la tarjeta (el consumo ya cuenta en
        Gastos fijos)."""
        total = Money.zero(moneda)
        for o in self.debitos_del_mes(tarjeta_id, anio, mes):
            if not o.ya_registrado and o.gasto.monto.moneda == total.moneda:
                total = total + o.gasto.monto
        return total

    def registrar_debitos_del_mes(self, tarjeta_id: int, anio: int, mes: int) -> int:
        """Registra el pago de los debitos de esta tarjeta que faltan en el mes.
        Devuelve cuantos se registraron."""
        pendientes = [o for o in self.debitos_del_mes(tarjeta_id, anio, mes) if not o.ya_registrado]
        for o in pendientes:
            self.generar_movimiento_del_mes(o.gasto.id, date(anio, mes, 1))
        return len(pendientes)

    def proximo_vencimiento(self, gasto: GastoFijo, desde: date | None = None) -> date:
        """La proxima fecha (hoy o futura) en la que vence este gasto fijo."""
        desde = desde or date.today()
        fecha_este_mes = self._fecha_del_mes(gasto, desde.year, desde.month)
        if fecha_este_mes >= desde:
            return fecha_este_mes
        siguiente = add_months(desde.replace(day=1), 1)
        return self._fecha_del_mes(gasto, siguiente.year, siguiente.month)
