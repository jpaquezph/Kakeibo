"""Vencimientos pendientes de un mes: cuotas de tarjeta, cuotas de prestamos
y gastos fijos. Lo usan el calendario y el aviso que aparece al abrir la app."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..domain.money import Money
from .gastos_fijos import GastoFijoService
from .prestamos import PrestamoService
from .tarjetas import TarjetaService


@dataclass
class Vencimiento:
    fecha: date
    origen: str  # "tarjeta" | "prestamo" | "fijo"
    titulo: str
    monto: Money
    referencia_id: int  # cuota_id (tarjeta/prestamo) o gasto_fijo_id (fijo)
    etiqueta: str  # texto secundario ("cuota N" o "gasto fijo")
    color: str | None = None  # color propio de la tarjeta; None para prestamos y gastos fijos


class VencimientoService:
    def __init__(self, tarjeta_service: TarjetaService, prestamo_service: PrestamoService, gasto_fijo_service: GastoFijoService):
        self._tarjetas = tarjeta_service
        self._prestamos = prestamo_service
        self._gastos_fijos = gasto_fijo_service

    def pendientes_del_mes(self, anio: int, mes: int) -> list[Vencimiento]:
        """Todo lo que vence en el mes y todavia no se pago, ordenado por fecha."""
        def en_el_mes(fecha: date) -> bool:
            return fecha.year == anio and fecha.month == mes

        vencimientos = []
        for t in self._tarjetas.listar_tarjetas():
            for compra in self._tarjetas.listar_compras(t.id):
                for cuota in compra.cuotas:
                    if not cuota.pagada and en_el_mes(cuota.fecha_vencimiento):
                        vencimientos.append(Vencimiento(
                            cuota.fecha_vencimiento, "tarjeta", f"{t.nombre}: {compra.concepto}",
                            cuota.monto, cuota.id, f"cuota {cuota.numero_cuota}", t.color,
                        ))
        for p in self._prestamos.listar():
            for cuota in p.cuotas:
                if not cuota.pagada and en_el_mes(cuota.fecha_vencimiento):
                    vencimientos.append(Vencimiento(
                        cuota.fecha_vencimiento, "prestamo", p.nombre, cuota.monto, cuota.id, f"cuota {cuota.numero_cuota}",
                    ))
        for ocurrencia in self._gastos_fijos.proximas_ocurrencias(anio, mes):
            if not ocurrencia.ya_registrado:
                vencimientos.append(Vencimiento(
                    ocurrencia.fecha, "fijo", ocurrencia.gasto.concepto, ocurrencia.gasto.monto, ocurrencia.gasto.id, "gasto fijo",
                ))
        return sorted(vencimientos, key=lambda v: v.fecha)
