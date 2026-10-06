from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from ..domain.dates import add_months
from ..domain.models import Compra, CuotaCompra, Movimiento, PagoTarjeta, Tarjeta, TipoMovimiento
from ..domain.money import Money, Moneda, split_in_installments
from ..repositories.movimientos import MovimientoRepository
from ..repositories.tarjetas import CompraRepository, TarjetaRepository


def vencimiento_cuota(
    fecha_compra: date, numero_cuota: int, cantidad_cuotas: int, tarjeta_cerrada: bool = False, cuota_inicial: int = 1,
) -> date:
    """En cuotas, la 1ra vence el mes siguiente a la compra; en 1 pago, el
    mismo mes. Si la tarjeta ya cerro el resumen del mes, todo se corre un
    mes mas (ej: compra en enero en cuotas con la tarjeta cerrada -> 1ra
    cuota en marzo). Si la compra se cargo ya empezada (`cuota_inicial` > 1),
    esa cuota es la que vence el mes siguiente a la fecha de carga y las
    anteriores quedan en los meses de atras."""
    desfase = 1 if tarjeta_cerrada else 0
    meses = (numero_cuota - (cuota_inicial - 1) if cantidad_cuotas > 1 else 0) + desfase
    return add_months(fecha_compra, meses) if meses else fecha_compra


@dataclass
class ResumenMesTarjeta:
    """Lo que entra en el resumen de una tarjeta en un mes. `pendientes`: las
    cuotas (y compras en 1 pago) sin pagar que vencen ese mes o quedaron sin
    pagar de meses anteriores. `pagadas`: las de ese mes que ya se pagaron.
    Cada una va con su compra. `pagos`: los pagos del resumen registrados."""
    pendientes: list[tuple[Compra, CuotaCompra]] = field(default_factory=list)
    pagadas: list[tuple[Compra, CuotaCompra]] = field(default_factory=list)
    pagos: list[PagoTarjeta] = field(default_factory=list)


def monto_total_desde_cuota(valor_cuota: Money, cantidad_cuotas: int) -> Money:
    """Total de una compra cargada por el valor de la cuota: cuota x cantidad.
    Al dividirlo de nuevo en cuotas, cada una queda exactamente en ese valor."""
    if cantidad_cuotas < 1:
        raise ValueError("La cantidad de cuotas tiene que ser 1 o más")
    return Money(valor_cuota.cents * cantidad_cuotas, valor_cuota.moneda)


class TarjetaService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._tarjetas = TarjetaRepository(conn)
        self._compras = CompraRepository(conn)
        self._movimientos = MovimientoRepository(conn)

    # Tarjetas
    @staticmethod
    def _validar_dia(dia: int | None, que: str) -> None:
        if dia is not None and not (1 <= dia <= 31):
            raise ValueError(f"El día de {que} debe estar entre 1 y 31")

    def crear_tarjeta(
        self, nombre: str, banco: str, ultimos_digitos: str, moneda=Moneda.ARS, color: str = "#D6467E",
        dia_cierre: int | None = None, dia_vencimiento: int | None = None,
    ) -> Tarjeta:
        self._validar_dia(dia_cierre, "cierre")
        self._validar_dia(dia_vencimiento, "vencimiento")
        tarjeta = Tarjeta(id=None, nombre=nombre, banco=banco, ultimos_digitos=ultimos_digitos, moneda=Moneda(moneda), color=color,
                          dia_cierre=dia_cierre, dia_vencimiento=dia_vencimiento)
        tarjeta.id = self._tarjetas.crear(tarjeta)
        return tarjeta

    def listar_tarjetas(self, solo_activas: bool = False) -> list[Tarjeta]:
        return self._tarjetas.listar(solo_activas)

    def editar_tarjeta(
        self, tarjeta_id: int, nombre: str, banco: str, ultimos_digitos: str, moneda, color: str,
        dia_cierre: int | None | object = ..., dia_vencimiento: int | None | object = ...,
    ) -> Tarjeta:
        """Los dias de cierre/vencimiento, si no se pasan, se mantienen."""
        actual = next((t for t in self._tarjetas.listar() if t.id == tarjeta_id), None)
        if actual is None:
            raise ValueError("Tarjeta inexistente")
        if dia_cierre is not ...:
            self._validar_dia(dia_cierre, "cierre")
            actual.dia_cierre = dia_cierre
        if dia_vencimiento is not ...:
            self._validar_dia(dia_vencimiento, "vencimiento")
            actual.dia_vencimiento = dia_vencimiento
        actual.nombre = nombre
        actual.banco = banco
        actual.ultimos_digitos = ultimos_digitos
        actual.moneda = Moneda(moneda)
        actual.color = color
        self._tarjetas.actualizar(actual)
        return actual

    def eliminar_tarjeta(self, tarjeta_id: int) -> None:
        self._tarjetas.eliminar(tarjeta_id)

    def obtener_tarjeta(self, tarjeta_id: int) -> Tarjeta | None:
        return self._tarjetas.obtener(tarjeta_id)

    def total_pendiente(self, tarjeta_id: int, moneda=Moneda.ARS) -> Money:
        """Lo que falta pagar de las compras de la tarjeta en esa moneda."""
        moneda = Moneda(moneda)
        return Money(self._compras.total_pendiente_centavos(tarjeta_id, moneda), moneda)

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
        tarjeta_cerrada: bool = False,
    ) -> Compra:
        if not (1 <= cuota_inicial <= cantidad_cuotas):
            raise ValueError("La cuota actual debe estar entre 1 y la cantidad total de cuotas")
        cuotas = self._armar_cuotas(fecha, monto_total, cantidad_cuotas, cuota_inicial - 1, tarjeta_cerrada, cuota_inicial)
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
            cuota_inicial=cuota_inicial,
        )
        compra.id = self._compras.crear_con_cuotas(compra)
        return self._compras.obtener(compra.id)

    @staticmethod
    def _armar_cuotas(
        fecha: date, monto_total: Money, cantidad_cuotas: int, cuotas_pagadas: int, tarjeta_cerrada: bool,
        cuota_inicial: int = 1,
    ) -> list[CuotaCompra]:
        """Divide el monto en cuotas con su vencimiento. Las primeras
        `cuotas_pagadas` quedan pagadas, con su vencimiento como fecha de pago."""
        if cantidad_cuotas < 1:
            raise ValueError("La cantidad de cuotas tiene que ser 1 o más")
        if monto_total.cents <= 0:
            raise ValueError("El monto tiene que ser mayor a cero")
        cuotas = []
        for i, monto in enumerate(split_in_installments(monto_total, cantidad_cuotas)):
            numero = i + 1
            vencimiento = vencimiento_cuota(fecha, numero, cantidad_cuotas, tarjeta_cerrada, cuota_inicial)
            pagada = numero <= cuotas_pagadas
            cuotas.append(CuotaCompra(
                id=None, compra_id=0, numero_cuota=numero, monto=monto, fecha_vencimiento=vencimiento, pagada=pagada,
                fecha_pago=vencimiento if pagada else None,
            ))
        return cuotas

    @staticmethod
    def cuotas_que_se_conservan(compra: Compra, cuotas_pagadas: int) -> list[CuotaCompra]:
        """Las cuotas pagadas que quedan intactas al editar la compra: las que
        ya estaban pagadas, hasta la cantidad de pagadas que se indique."""
        return [c for c in compra.cuotas if c.pagada and c.numero_cuota <= cuotas_pagadas]

    def _cuotas_editadas(
        self, actual: Compra, fecha: date, monto_total: Money, cantidad_cuotas: int, cuotas_pagadas: int, tarjeta_cerrada: bool,
        cuota_inicial: int = 1,
    ) -> list[CuotaCompra]:
        conservadas = self.cuotas_que_se_conservan(actual, min(cuotas_pagadas, cantidad_cuotas))
        if not conservadas:
            return self._armar_cuotas(fecha, monto_total, cantidad_cuotas, cuotas_pagadas, tarjeta_cerrada, cuota_inicial)
        if any(c.monto.moneda != monto_total.moneda for c in conservadas):
            raise ValueError("No se puede cambiar la moneda de una compra con cuotas pagadas")
        ya_pagado = Money.zero(monto_total.moneda)
        for c in conservadas:
            ya_pagado = ya_pagado + c.monto
        restantes = cantidad_cuotas - len(conservadas)
        falta = monto_total.cents - ya_pagado.cents
        if restantes == 0 and falta != 0:
            raise ValueError(
                f"Las {len(conservadas)} cuotas ya pagadas suman {ya_pagado.formatted()}: con esa cantidad de cuotas "
                "el monto total tiene que ser ese. Si querés cambiarlo, indicá menos cuotas pagadas."
            )
        if restantes > 0 and falta <= 0:
            raise ValueError(f"El monto total tiene que ser mayor a lo ya pagado ({ya_pagado.formatted()})")
        cuotas = [
            CuotaCompra(id=None, compra_id=0, numero_cuota=c.numero_cuota, monto=c.monto, fecha_vencimiento=c.fecha_vencimiento,
                        pagada=True, fecha_pago=c.fecha_pago)
            for c in conservadas
        ]
        if restantes:
            montos = split_in_installments(Money(falta, monto_total.moneda), restantes)
            for numero, monto in zip(range(len(conservadas) + 1, cantidad_cuotas + 1), montos):
                vencimiento = vencimiento_cuota(fecha, numero, cantidad_cuotas, tarjeta_cerrada, cuota_inicial)
                pagada = numero <= cuotas_pagadas
                cuotas.append(CuotaCompra(id=None, compra_id=0, numero_cuota=numero, monto=monto, fecha_vencimiento=vencimiento,
                                          pagada=pagada, fecha_pago=vencimiento if pagada else None))
        return cuotas

    @staticmethod
    def tarjeta_estaba_cerrada(compra: Compra) -> bool:
        """Si la compra se cargo con "la tarjeta ya cerro el resumen" (sus
        cuotas vencen un mes despues de lo normal)."""
        if not compra.cuotas:
            return False
        primera = compra.cuotas[0]
        return primera.fecha_vencimiento != vencimiento_cuota(compra.fecha, 1, compra.cantidad_cuotas, False, compra.cuota_inicial)

    def editar_compra(
        self,
        compra_id: int,
        tarjeta_id: int,
        fecha: date,
        concepto: str,
        detalle: str,
        monto_total: Money,
        cantidad_cuotas: int,
        cuotas_pagadas: int,
        tarjeta_cerrada: bool = False,
    ) -> Compra:
        """Corrige cualquier dato de una compra (por si se cargo mal). Las cuotas
        que ya estaban pagadas no se modifican (monto, vencimiento y fecha de
        pago); lo que falta del monto total se reparte entre las demas, que se
        recalculan. Quedan pagadas las primeras `cuotas_pagadas`."""
        actual = self._compras.obtener(compra_id)
        if actual is None:
            raise ValueError("La compra no existe")
        if not concepto.strip():
            raise ValueError("El concepto no puede estar vacío")
        if self._tarjetas.obtener(tarjeta_id) is None:
            raise ValueError("La tarjeta elegida no existe")
        if not (0 <= cuotas_pagadas <= cantidad_cuotas):
            raise ValueError("Las cuotas pagadas tienen que estar entre 0 y la cantidad de cuotas")
        # La cuota en la que se empezo se mantiene (si sigue entrando en la cantidad de cuotas).
        cuota_inicial = min(actual.cuota_inicial, cantidad_cuotas)
        cuotas = self._cuotas_editadas(actual, fecha, monto_total, cantidad_cuotas, cuotas_pagadas, tarjeta_cerrada, cuota_inicial)
        compra = Compra(
            id=compra_id, tarjeta_id=tarjeta_id, fecha=fecha, concepto=concepto.strip(), detalle=detalle,
            monto_total=monto_total, categoria_id=actual.categoria_id, cantidad_cuotas=cantidad_cuotas, cuotas=cuotas,
            cuota_inicial=cuota_inicial,
        )
        self._compras.reemplazar(compra)
        return self._compras.obtener(compra_id)

    # Una compra con tarjeta no es un egreso al hacerla: la plata sale cuando se
    # paga. Por eso cada pago (una cuota suelta o el resumen del mes) registra
    # un movimiento de egreso, que es lo que cuenta en el Resumen.

    def _categoria_tarjeta_id(self) -> int | None:
        row = self._conn.execute(
            "SELECT id FROM categorias WHERE nombre = 'Tarjeta de crédito' AND tipo = 'egreso'"
        ).fetchone()
        return row["id"] if row else None

    def _registrar_egreso(
        self, tarjeta_id: int, fecha: date, concepto: str, detalle: str, monto: Money, categoria_id: int | None,
    ) -> int | None:
        if categoria_id is None or monto.cents <= 0:
            return None
        return self._movimientos.crear(Movimiento(
            id=None, tipo=TipoMovimiento.EGRESO, fecha=fecha, concepto=concepto, detalle=detalle, monto=monto,
            categoria_id=categoria_id, tarjeta_id=tarjeta_id,
        ))

    def pagar_cuota(self, cuota_id: int, fecha_pago: date | None = None) -> None:
        """Marca la cuota como pagada y registra el egreso."""
        fecha_pago = fecha_pago or date.today()
        compra = self._compras.obtener_por_cuota(cuota_id)
        self._compras.marcar_cuota_pagada(cuota_id, fecha_pago)
        cuota = next(c for c in compra.cuotas if c.id == cuota_id)
        tarjeta = self._tarjetas.obtener(compra.tarjeta_id)
        detalle = f"Cuota {cuota.numero_cuota} de {compra.cantidad_cuotas}" if compra.cantidad_cuotas > 1 else "1 pago"
        self._registrar_egreso(compra.tarjeta_id, fecha_pago, f"{tarjeta.nombre}: {compra.concepto}", detalle, cuota.monto,
                               compra.categoria_id)

    def resumen_del_mes(self, tarjeta_id: int, anio: int, mes: int) -> ResumenMesTarjeta:
        """Lo que entra en el resumen de la tarjeta ese mes: cuotas y compras en
        1 pago que vencen en el mes, mas lo que quedo sin pagar de meses
        anteriores (si no se pago, se sigue debiendo)."""
        desde = date(anio, mes, 1)
        hasta = date(anio, mes, calendar.monthrange(anio, mes)[1])
        resumen = ResumenMesTarjeta(pagos=self._tarjetas.pagos_del_mes(tarjeta_id, anio, mes))
        for compra in self._compras.listar_por_tarjeta(tarjeta_id):
            for cuota in compra.cuotas:
                if not cuota.pagada and cuota.fecha_vencimiento <= hasta:
                    resumen.pendientes.append((compra, cuota))
                elif cuota.pagada and desde <= cuota.fecha_vencimiento <= hasta:
                    resumen.pagadas.append((compra, cuota))
        return resumen

    def cuotas_pendientes_del_mes(self, tarjeta_id: int, anio: int, mes: int) -> list[CuotaCompra]:
        """Cuotas sin pagar de esta tarjeta (de cualquier compra) que vencen en
        ese mes o quedaron sin pagar de meses anteriores."""
        return [cuota for _compra, cuota in self.resumen_del_mes(tarjeta_id, anio, mes).pendientes]

    def pagar_cuotas_del_mes(self, tarjeta_id: int, anio: int, mes: int, fecha_pago: date | None = None) -> int:
        """Marca como pagadas todas las cuotas de esta tarjeta que entran en el
        resumen de ese mes, cada una con su egreso. Devuelve la cantidad de
        cuotas pagadas."""
        fecha_pago = fecha_pago or date.today()
        cuotas = self.cuotas_pendientes_del_mes(tarjeta_id, anio, mes)
        for cuota in cuotas:
            self.pagar_cuota(cuota.id, fecha_pago)
        return len(cuotas)

    def pagar_mes(
        self, tarjeta_id: int, anio: int, mes: int, debitos: list[Money] | None = None,
        pagado: dict[Moneda, Money] | None = None, fecha_pago: date | None = None,
    ) -> list[PagoTarjeta]:
        """Paga el resumen del mes: marca como pagadas las cuotas y compras en 1
        pago que entran en el mes y deja registrado el pago, uno por moneda.
        `debitos`: los debitos automaticos que se pagan junto con la tarjeta
        (su pago lo registra Gastos fijos; aca solo suman al saldo).
        `pagado`: el saldo que se pago de verdad en cada moneda, si se corrigio
        (el resumen puede traer impuestos, intereses o ajustes); si no, vale
        lo que daba la cuenta.
        Registra un egreso por moneda con lo pagado menos los debitos
        automaticos, que ya tienen su propio egreso como gastos fijos."""
        fecha_pago = fecha_pago or date.today()
        pendientes = self.cuotas_pendientes_del_mes(tarjeta_id, anio, mes)
        calculado: dict[Moneda, Money] = {}
        for monto in [c.monto for c in pendientes] + list(debitos or []):
            calculado[monto.moneda] = calculado[monto.moneda] + monto if monto.moneda in calculado else monto
        pagado = {Moneda(m): monto for m, monto in (pagado or {}).items()}
        for moneda, monto in pagado.items():
            if monto.moneda != moneda:
                raise ValueError("El saldo pagado no coincide con su moneda")
            if monto.cents < 0:
                raise ValueError("El saldo a pagar no puede ser negativo")
        for cuota in pendientes:
            self._compras.marcar_cuota_pagada(cuota.id, fecha_pago)
        tarjeta = self._tarjetas.obtener(tarjeta_id)
        categoria_id = self._categoria_tarjeta_id()
        pagos = []
        for moneda in Moneda:
            if moneda not in calculado and moneda not in pagado:
                continue
            total = calculado.get(moneda, Money.zero(moneda))
            pago = PagoTarjeta(id=None, tarjeta_id=tarjeta_id, anio=anio, mes=mes, monto=pagado.get(moneda, total),
                               calculado=total, fecha_pago=fecha_pago)
            en_debitos = sum(d.cents for d in debitos or [] if d.moneda == moneda)
            pago.movimiento_id = self._registrar_egreso(
                tarjeta_id, fecha_pago, f"Pago tarjeta {tarjeta.nombre}", f"Resumen {mes:02d}/{anio}",
                Money(pago.monto.cents - en_debitos, moneda), categoria_id,
            )
            pago.id = self._tarjetas.registrar_pago(pago)
            pagos.append(pago)
        return pagos

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
