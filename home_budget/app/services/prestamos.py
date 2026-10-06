from __future__ import annotations

import calendar
import sqlite3
from datetime import date

from ..domain.dates import add_months
from ..domain.models import CuotaPrestamo, Movimiento, Prestamo, TipoMovimiento
from ..domain.money import Money, split_in_installments
from ..repositories.movimientos import MovimientoRepository
from ..repositories.prestamos import PrestamoRepository


def vencimiento_cuota_prestamo(fecha_inicio: date, numero_cuota: int, dia_vencimiento: int | None = None) -> date:
    """La cuota N vence N meses despues del inicio, el dia elegido (si el mes
    no tiene ese dia, el ultimo del mes: ej. 31 -> 30 de abril)."""
    mes = add_months(fecha_inicio.replace(day=1), numero_cuota)
    dia = dia_vencimiento or fecha_inicio.day
    return mes.replace(day=min(dia, calendar.monthrange(mes.year, mes.month)[1]))


class PrestamoService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._repo = PrestamoRepository(conn)
        self._movimientos = MovimientoRepository(conn)

    def registrar_prestamo(
        self,
        nombre: str,
        detalle: str,
        monto_original: Money,
        cantidad_cuotas: int,
        fecha_inicio: date,
        cuota_inicial: int = 1,
        dia_vencimiento: int | None = None,
    ) -> Prestamo:
        """`cuota_inicial`: en que cuota se esta (para prestamos que se venian
        pagando antes de usar la app); las anteriores quedan pagadas.
        `dia_vencimiento`: dia del mes en que vence cada cuota (por defecto, el
        de la fecha de inicio). La 1ra cuota vence el mes siguiente al inicio."""
        if cantidad_cuotas < 1:
            raise ValueError("La cantidad de cuotas tiene que ser 1 o más")
        if not (1 <= cuota_inicial <= cantidad_cuotas):
            raise ValueError("La cuota actual debe estar entre 1 y la cantidad total de cuotas")
        if dia_vencimiento is not None and not (1 <= dia_vencimiento <= 31):
            raise ValueError("El día de vencimiento debe estar entre 1 y 31")
        montos_cuota = split_in_installments(monto_original, cantidad_cuotas)
        cuotas = []
        for i, monto in enumerate(montos_cuota):
            numero = i + 1
            vencimiento = vencimiento_cuota_prestamo(fecha_inicio, numero, dia_vencimiento)
            pagada = numero < cuota_inicial
            cuotas.append(CuotaPrestamo(
                id=None, prestamo_id=0, numero_cuota=numero, monto=monto, fecha_vencimiento=vencimiento,
                pagada=pagada, fecha_pago=vencimiento if pagada else None,
            ))
        prestamo = Prestamo(
            id=None,
            nombre=nombre,
            detalle=detalle,
            monto_original=monto_original,
            cantidad_cuotas=cantidad_cuotas,
            fecha_inicio=fecha_inicio,
            cuotas=cuotas,
            dia_vencimiento=dia_vencimiento,
        )
        prestamo.id = self._repo.crear_con_cuotas(prestamo)
        return self._repo.obtener(prestamo.id)

    @staticmethod
    def dia_vencimiento_de(prestamo: Prestamo) -> int:
        """El dia en que vencen sus cuotas. Los prestamos cargados antes de
        guardar ese dato lo toman de sus cuotas (el mayor dia, por si algun
        mes lo recorto: 31 -> 30 de abril)."""
        if prestamo.dia_vencimiento:
            return prestamo.dia_vencimiento
        if prestamo.cuotas:
            return max(c.fecha_vencimiento.day for c in prestamo.cuotas)
        return prestamo.fecha_inicio.day

    @staticmethod
    def cuotas_que_se_conservan(prestamo: Prestamo, cuotas_pagadas: int) -> list[CuotaPrestamo]:
        """Las cuotas pagadas que quedan intactas al editar el prestamo."""
        return [c for c in prestamo.cuotas if c.pagada and c.numero_cuota <= cuotas_pagadas]

    def editar_prestamo(
        self,
        prestamo_id: int,
        nombre: str,
        detalle: str,
        monto_total: Money,
        cantidad_cuotas: int,
        cuotas_pagadas: int,
        fecha_inicio: date,
        dia_vencimiento: int,
    ) -> Prestamo:
        """Corrige cualquier dato del prestamo. Las cuotas ya pagadas no se
        modifican; lo que falta del monto total se reparte entre las demas,
        que se recalculan con el nuevo dia de vencimiento."""
        actual = self._repo.obtener(prestamo_id)
        if actual is None:
            raise ValueError("El préstamo no existe")
        if not nombre.strip():
            raise ValueError("El nombre no puede estar vacío")
        if cantidad_cuotas < 1:
            raise ValueError("La cantidad de cuotas tiene que ser 1 o más")
        if not (0 <= cuotas_pagadas <= cantidad_cuotas):
            raise ValueError("Las cuotas pagadas tienen que estar entre 0 y la cantidad de cuotas")
        if not (1 <= dia_vencimiento <= 31):
            raise ValueError("El día de vencimiento debe estar entre 1 y 31")

        conservadas = self.cuotas_que_se_conservan(actual, cuotas_pagadas)
        if conservadas and monto_total.moneda != actual.monto_original.moneda:
            raise ValueError("No se puede cambiar la moneda de un préstamo con cuotas pagadas")
        ya_pagado = sum(c.monto.cents for c in conservadas)
        restantes = cantidad_cuotas - len(conservadas)
        falta = monto_total.cents - ya_pagado
        if restantes == 0 and falta != 0:
            raise ValueError(
                f"Las {len(conservadas)} cuotas ya pagadas suman {Money(ya_pagado, monto_total.moneda).formatted()}: con esa "
                "cantidad de cuotas el monto total tiene que ser ese. Si querés cambiarlo, indicá menos cuotas pagadas."
            )
        if restantes > 0 and falta <= 0:
            raise ValueError(f"El monto total tiene que ser mayor a lo ya pagado ({Money(ya_pagado, monto_total.moneda).formatted()})")

        cuotas = [
            CuotaPrestamo(id=None, prestamo_id=prestamo_id, numero_cuota=c.numero_cuota, monto=c.monto,
                          fecha_vencimiento=c.fecha_vencimiento, pagada=True, fecha_pago=c.fecha_pago)
            for c in conservadas
        ]
        if restantes:
            montos = split_in_installments(Money(falta, monto_total.moneda), restantes)
            for numero, monto in zip(range(len(conservadas) + 1, cantidad_cuotas + 1), montos):
                vencimiento = vencimiento_cuota_prestamo(fecha_inicio, numero, dia_vencimiento)
                pagada = numero <= cuotas_pagadas
                cuotas.append(CuotaPrestamo(id=None, prestamo_id=prestamo_id, numero_cuota=numero, monto=monto,
                                            fecha_vencimiento=vencimiento, pagada=pagada, fecha_pago=vencimiento if pagada else None))
        prestamo = Prestamo(id=prestamo_id, nombre=nombre.strip(), detalle=detalle, monto_original=monto_total,
                            cantidad_cuotas=cantidad_cuotas, fecha_inicio=fecha_inicio, cuotas=cuotas, dia_vencimiento=dia_vencimiento)
        self._repo.reemplazar(prestamo)
        return self._repo.obtener(prestamo_id)

    def cambiar_monto_cuota(self, cuota_id: int, monto: Money, tambien_las_siguientes: bool = False) -> Prestamo:
        """Cambia el monto de una cuota pendiente (prestamos con cuota variable:
        UVA, sistema aleman, ajustes). Con `tambien_las_siguientes`, el mismo
        monto se aplica a las cuotas pendientes que vienen despues. El monto
        total del prestamo pasa a ser la suma de sus cuotas."""
        if monto.cents <= 0:
            raise ValueError("El monto de la cuota tiene que ser mayor a cero")
        prestamo = self._repo.obtener_por_cuota(cuota_id)
        if prestamo is None:
            raise ValueError("Cuota inexistente")
        cuota = next(c for c in prestamo.cuotas if c.id == cuota_id)
        if cuota.pagada:
            raise ValueError("Esa cuota ya está pagada: no se puede cambiar su monto")
        if monto.moneda != prestamo.monto_original.moneda:
            raise ValueError("El monto tiene que estar en la moneda del préstamo")
        a_cambiar = [c.id for c in prestamo.cuotas
                     if c.id == cuota_id or (tambien_las_siguientes and not c.pagada and c.numero_cuota > cuota.numero_cuota)]
        self._repo.cambiar_monto_cuotas(prestamo.id, a_cambiar, monto)
        return self._repo.obtener(prestamo.id)

    def pagar_cuota(self, cuota_id: int, fecha_pago: date | None = None, monto: Money | None = None) -> None:
        """Paga la cuota. Si se indica `monto` distinto (la cuota vino con otro
        valor ese mes), primero se corrige el monto de esa cuota. El pago se
        registra como un movimiento de egreso (categoria "Préstamos"), que es
        lo que cuenta en el Resumen."""
        fecha_pago = fecha_pago or date.today()
        if monto is not None:
            self.cambiar_monto_cuota(cuota_id, monto)
        self._repo.marcar_cuota_pagada(cuota_id, fecha_pago)
        prestamo = self._repo.obtener_por_cuota(cuota_id)
        categoria = self._conn.execute("SELECT id FROM categorias WHERE nombre = 'Préstamos' AND tipo = 'egreso'").fetchone()
        if prestamo is None or categoria is None:
            return
        cuota = next(c for c in prestamo.cuotas if c.id == cuota_id)
        self._movimientos.crear(Movimiento(
            id=None, tipo=TipoMovimiento.EGRESO, fecha=fecha_pago, concepto=prestamo.nombre,
            detalle=f"Préstamo · cuota {cuota.numero_cuota} de {prestamo.cantidad_cuotas}", monto=cuota.monto,
            categoria_id=categoria["id"],
        ))

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
