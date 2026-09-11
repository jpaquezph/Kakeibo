from __future__ import annotations

import sqlite3
from datetime import date

from ..domain.dates import add_months
from ..domain.models import CuotaPrestamo, Prestamo
from ..domain.money import Money, split_in_installments
from ..repositories.prestamos import PrestamoRepository


class PrestamoService:
    def __init__(self, conn: sqlite3.Connection):
        self._repo = PrestamoRepository(conn)

    def registrar_prestamo(
        self,
        nombre: str,
        detalle: str,
        monto_original: Money,
        cantidad_cuotas: int,
        fecha_inicio: date,
    ) -> Prestamo:
        montos_cuota = split_in_installments(monto_original, cantidad_cuotas)
        cuotas = [
            CuotaPrestamo(
                id=None,
                prestamo_id=0,
                numero_cuota=i + 1,
                monto=monto,
                fecha_vencimiento=add_months(fecha_inicio, i + 1),
            )
            for i, monto in enumerate(montos_cuota)
        ]
        prestamo = Prestamo(
            id=None,
            nombre=nombre,
            detalle=detalle,
            monto_original=monto_original,
            cantidad_cuotas=cantidad_cuotas,
            fecha_inicio=fecha_inicio,
            cuotas=cuotas,
        )
        prestamo.id = self._repo.crear_con_cuotas(prestamo)
        return self._repo.obtener(prestamo.id)

    def pagar_cuota(self, cuota_id: int, fecha_pago: date | None = None) -> None:
        self._repo.marcar_cuota_pagada(cuota_id, fecha_pago or date.today())

    def editar_datos(self, prestamo_id: int, nombre: str, detalle: str) -> Prestamo:
        """Edita nombre y detalle de un prestamo existente. No permite cambiar el
        monto ni la cantidad de cuotas para no romper el esquema ya generado."""
        if not nombre.strip():
            raise ValueError("El nombre no puede estar vacio")
        self._repo.actualizar_datos(prestamo_id, nombre.strip(), detalle)
        return self._repo.obtener(prestamo_id)

    def eliminar_prestamo(self, prestamo_id: int) -> None:
        self._repo.eliminar(prestamo_id)

    def listar(self) -> list[Prestamo]:
        return self._repo.listar()

    def obtener(self, prestamo_id: int) -> Prestamo | None:
        return self._repo.obtener(prestamo_id)
