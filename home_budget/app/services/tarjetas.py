from __future__ import annotations

import sqlite3
from datetime import date

from ..domain.dates import add_months
from ..domain.models import Compra, CuotaCompra, Tarjeta
from ..domain.money import Money, Moneda, split_in_installments
from ..repositories.tarjetas import CompraRepository, TarjetaRepository


class TarjetaService:
    def __init__(self, conn: sqlite3.Connection):
        self._tarjetas = TarjetaRepository(conn)
        self._compras = CompraRepository(conn)

    # Tarjetas
    def crear_tarjeta(self, nombre: str, banco: str, ultimos_digitos: str, moneda, color: str = "#D6467E") -> Tarjeta:
        tarjeta = Tarjeta(id=None, nombre=nombre, banco=banco, ultimos_digitos=ultimos_digitos, moneda=Moneda(moneda), color=color)
        tarjeta.id = self._tarjetas.crear(tarjeta)
        return tarjeta

    def listar_tarjetas(self, solo_activas: bool = False) -> list[Tarjeta]:
        return self._tarjetas.listar(solo_activas)

    def editar_tarjeta(self, tarjeta_id: int, nombre: str, banco: str, ultimos_digitos: str, moneda, color: str) -> Tarjeta:
        actual = next((t for t in self._tarjetas.listar() if t.id == tarjeta_id), None)
        if actual is None:
            raise ValueError("Tarjeta inexistente")
        actual.nombre = nombre
        actual.banco = banco
        actual.ultimos_digitos = ultimos_digitos
        actual.moneda = Moneda(moneda)
        actual.color = color
        self._tarjetas.actualizar(actual)
        return actual

    def eliminar_tarjeta(self, tarjeta_id: int) -> None:
        self._tarjetas.eliminar(tarjeta_id)

    # Compras y cuotas
    def registrar_compra(
        self,
        tarjeta_id: int,
        fecha: date,
        concepto: str,
        detalle: str,
        monto_total: Money,
        categoria_id: int,
        cantidad_cuotas: int = 1,
        cuota_inicial: int = 1,
    ) -> Compra:
        if not (1 <= cuota_inicial <= cantidad_cuotas):
            raise ValueError("La cuota actual debe estar entre 1 y la cantidad total de cuotas")
        montos_cuota = split_in_installments(monto_total, cantidad_cuotas)
        cuotas = []
        for i, monto in enumerate(montos_cuota):
            numero = i + 1
            vencimiento = add_months(fecha, numero) if cantidad_cuotas > 1 else fecha
            ya_pagada = numero < cuota_inicial
            cuotas.append(
                CuotaCompra(
                    id=None,
                    compra_id=0,
                    numero_cuota=numero,
                    monto=monto,
                    fecha_vencimiento=vencimiento,
                    pagada=ya_pagada,
                    fecha_pago=vencimiento if ya_pagada else None,
                )
            )
        compra = Compra(
            id=None,
            tarjeta_id=tarjeta_id,
            fecha=fecha,
            concepto=concepto,
            detalle=detalle,
            monto_total=monto_total,
            categoria_id=categoria_id,
            cantidad_cuotas=cantidad_cuotas,
            cuotas=cuotas,
        )
        compra.id = self._compras.crear_con_cuotas(compra)
        return self._compras.obtener(compra.id)

    def pagar_cuota(self, cuota_id: int, fecha_pago: date | None = None) -> None:
        self._compras.marcar_cuota_pagada(cuota_id, fecha_pago or date.today())

    def editar_datos_compra(self, compra_id: int, concepto: str, detalle: str, categoria_id: int) -> Compra:
        """Edita los datos descriptivos de una compra (concepto, detalle, categoria).
        No permite cambiar el monto ni la cantidad de cuotas para no romper el
        esquema de cuotas ya generado (algunas pueden estar pagadas)."""
        if not concepto.strip():
            raise ValueError("El concepto no puede estar vacio")
        self._compras.actualizar_datos(compra_id, concepto.strip(), detalle, categoria_id)
        return self._compras.obtener(compra_id)

    def eliminar_compra(self, compra_id: int) -> None:
        self._compras.eliminar(compra_id)

    def listar_compras(self, tarjeta_id: int) -> list[Compra]:
        return self._compras.listar_por_tarjeta(tarjeta_id)

    def obtener_compra(self, compra_id: int) -> Compra | None:
        return self._compras.obtener(compra_id)
