"""Pantallas de carga de Tarjetas en el celular: la tarjeta, una compra y el
pago del resumen. Piden los mismos datos y en el mismo orden que los
dialogos de escritorio."""
from __future__ import annotations

from datetime import date
from typing import Callable

import flet as ft

from ...app.domain.dates import add_months
from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.services.tarjetas import monto_total_desde_cuota
from .. import theme
from ..desktop import components
from ..desktop.tarjetas_view import SelectorResumen
from . import componentes as mc

_FORMAS = [("un_pago", "1 pago"), ("cuotas", "En cuotas")]


def _mes_y_anio(fecha: date) -> str:
    return f"{mc.MESES[fecha.month - 1]} {fecha.year}"


def _selector_resumen(page: ft.Page, servicios) -> SelectorResumen:
    return SelectorResumen(page, servicios.tarjetas, filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM,
                           border_color=theme.BORDER, expand=True)


def partes_pendientes(resumen, debitos) -> list[tuple[str, list[Money]]]:
    """Lo que falta pagar del mes separado en cuotas, compras en 1 pago y
    debitos automaticos (solo los grupos que tienen algo)."""
    cuotas = [cu.monto for co, cu in resumen.pendientes if co.cantidad_cuotas > 1]
    un_pago = [cu.monto for co, cu in resumen.pendientes if co.cantidad_cuotas == 1]
    automaticos = [o.gasto.monto for o in debitos]
    partes = [
        (f"{len(cuotas)} cuota(s)", cuotas),
        (f"{len(un_pago)} compra(s) en 1 pago", un_pago),
        (f"{len(automaticos)} débito(s) automático(s)", automaticos),
    ]
    return [(titulo, montos) for titulo, montos in partes if montos]


def _totales(montos) -> str:
    return " + ".join(m.formatted() for m in mc.totales_por_moneda(montos)) or Money.zero(Moneda.ARS).formatted()


def formulario_tarjeta(page: ft.Page, nav: mc.Navegacion, servicios, tarjeta=None) -> ft.Control:
    """Alta o edicion de una tarjeta. Al editar suma eliminarla."""
    es_edicion = tarjeta is not None
    nombre_f = mc.campo("Nombre (ej: Visa Galicia)", value=tarjeta.nombre if es_edicion else "", autofocus=not es_edicion)
    banco_f = mc.campo("Banco", value=tarjeta.banco if es_edicion else "")
    digitos_f = mc.campo("Últimos 4 dígitos (opcional)", value=tarjeta.ultimos_digitos if es_edicion else "", max_length=4,
                         keyboard_type=ft.KeyboardType.NUMBER)
    # La tarjeta opera en pesos y en dolares: la moneda se elige en cada compra.
    moneda_tarjeta = tarjeta.moneda if es_edicion else Moneda.ARS

    def campo_dia(label: str, valor) -> ft.TextField:
        return mc.campo(label, value=str(valor) if valor else "", keyboard_type=ft.KeyboardType.NUMBER, max_length=2, expand=True)

    cierre_f = campo_dia("Día de cierre", tarjeta.dia_cierre if es_edicion else None)
    vencimiento_f = campo_dia("Día de vencimiento", tarjeta.dia_vencimiento if es_edicion else None)
    colores, color_elegido = mc.muestras_color(page, theme.TARJETA_COLORES, tarjeta.color if es_edicion else theme.TARJETA_COLORES[0])
    error, mostrar_error = mc.texto_error(page)

    def leer_dia(campo: ft.TextField, que: str) -> int | None:
        texto = (campo.value or "").strip()
        if not texto:
            return None
        if not texto.isdigit():
            raise ValueError(f"El día de {que} debe ser un número entre 1 y 31")
        return int(texto)

    def guardar(_e):
        try:
            nombre = (nombre_f.value or "").strip()
            if not nombre:
                raise ValueError("El nombre de la tarjeta es obligatorio")
            datos = dict(dia_cierre=leer_dia(cierre_f, "cierre"), dia_vencimiento=leer_dia(vencimiento_f, "vencimiento"))
            if es_edicion:
                servicios.tarjetas.editar_tarjeta(tarjeta.id, nombre, banco_f.value or "", digitos_f.value or "", moneda_tarjeta,
                                                  color_elegido(), **datos)
            else:
                servicios.tarjetas.crear_tarjeta(nombre, banco_f.value or "", digitos_f.value or "", moneda_tarjeta,
                                                 color_elegido(), **datos)
        except ValueError as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar("Tarjeta guardada" if es_edicion else "Tarjeta creada")

    def eliminar(_e):
        cantidad = len(servicios.tarjetas.listar_compras(tarjeta.id))
        hoy = date.today()
        debitos = servicios.gastos_fijos.debitos_del_mes(tarjeta.id, hoy.year, hoy.month)
        detalle = [f'¿Seguro que querés eliminar la tarjeta "{tarjeta.nombre}"?']
        if cantidad:
            detalle.append(f"Se borran también sus {cantidad} compra(s) con todas sus cuotas, incluidas las ya pagadas.")
        if debitos:
            detalle.append(f"Sus {len(debitos)} débito(s) automático(s) no se pierden: pasan a ser gastos fijos comunes.")
        detalle.append("No se puede deshacer.")

        def aceptar():
            servicios.tarjetas.eliminar_tarjeta(tarjeta.id)
            nav.volver()
            nav.avisar("Tarjeta eliminada")

        mc.confirmar(page, "Eliminar tarjeta", ft.Column([ft.Text(t, color=theme.TEXT_PRIMARY) for t in detalle], spacing=8, tight=True),
                     "Eliminar", theme.EXPENSE_RED, "delete_outline_rounded", aceptar)

    return mc.pantalla([
        nombre_f,
        banco_f,
        digitos_f,
        mc.nota("Opera en pesos y en dólares: la moneda se elige en cada compra."),
        ft.Row([cierre_f, vencimiento_f], spacing=8),
        mc.nota("Opcionales. Con los dos días cargados, cada compra entra sola en el resumen que corresponde; "
                "el de vencimiento lo usan además los gastos fijos con débito automático."),
        ft.Text("Color para identificarla", size=12, color=theme.TEXT_SECONDARY),
        colores,
        error,
        mc.boton_ancho("Guardar" if es_edicion else "Crear", guardar, theme.TARJETAS_COLOR, ft.Icons.CHECK_ROUNDED),
        *([mc.boton_eliminar("Eliminar tarjeta", eliminar)] if es_edicion else []),
    ])


def formulario_compra(page: ft.Page, nav: mc.Navegacion, servicios, tarjeta_id: int,
                      ver_mes: Callable[[int, int], None]) -> ft.Control:
    """Compra nueva. `ver_mes`: para que, al volver, Tarjetas muestre el mes
    en el que entra la compra recien cargada."""
    tarjetas = servicios.tarjetas.listar_tarjetas()
    categoria = next((c for c in servicios.categorias.listar(TipoMovimiento.EGRESO) if c.nombre == "Tarjeta de crédito"), None)

    tarjeta_dd = mc.desplegable("Tarjeta", str(tarjeta_id), [ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas], expand=True)
    # El mes del resumen sale del dia de cierre y de vencimiento de la
    # tarjeta; se puede cambiar porque el cierre se corre de un mes a otro.
    resumen_sel = _selector_resumen(page, servicios)
    tipo_sel = mc.selector(_FORMAS, "un_pago")
    concepto_f = mc.campo("Concepto", autofocus=True)
    detalle_f = mc.campo("Detalle (opcional)")
    monto_f = mc.campo("Monto total", keyboard_type=ft.KeyboardType.NUMBER)
    moneda_dd = mc.desplegable("Moneda", Moneda.ARS.value, [ft.dropdown.Option(m.value) for m in Moneda])
    cuotas_f = mc.campo("Cantidad de cuotas", value="2", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    cuota_inicial_f = mc.campo("¿En qué cuota empezás?", value="1", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    # En cuotas se puede cargar el total de la compra o el valor de cada
    # cuota (el total se calcula: valor de cuota x cantidad de cuotas).
    modo_monto = mc.selector([("total", "Cargo el total"), ("cuota", "Cargo la cuota")], "total")
    calculo = ft.Text("", size=12, weight=ft.FontWeight.W_600, color=theme.TARJETAS_COLOR, visible=False)
    en_cuotas = ft.Column(
        [
            ft.Row([modo_monto]),
            ft.Row([cuotas_f, cuota_inicial_f], spacing=8),
            mc.nota("Si ya venías pagando (ej: compraste hace 3 meses), dejá la fecha de hoy y poné la cuota que te toca pagar ahora."),
            calculo,
        ],
        spacing=12, visible=False,
    )
    error, mostrar_error = mc.texto_error(page)

    def es_en_cuotas() -> bool:
        return mc.elegido(tipo_sel) == "cuotas"

    def por_cuota() -> bool:
        return es_en_cuotas() and mc.elegido(modo_monto) == "cuota"

    def actualizar_calculo(_e=None):
        """Muestra la cuenta: total a partir de la cuota, o cuota a partir del total."""
        monto_f.label = "Valor de cada cuota" if por_cuota() else "Monto total"
        try:
            monto = components.parse_monto(monto_f.value, moneda_dd.value)
            cantidad = components.parse_entero(cuotas_f.value, "Cuotas", minimo=2)
        except ValueError:
            calculo.value = ""
        else:
            if por_cuota():
                calculo.value = f"Total de la compra: {monto_total_desde_cuota(monto, cantidad).formatted()} ({cantidad} cuotas de {monto.formatted()})"
            else:
                calculo.value = f"{cantidad} cuotas de {Money.from_decimal(monto.amount / cantidad, monto.moneda).formatted()} aprox."
        calculo.visible = bool(calculo.value)
        if _e is not None:
            page.update()

    def que_se_paga() -> str:
        if not es_en_cuotas():
            return "Se paga"
        # Cargada ya empezada, la cuota en la que se esta es la primera que se paga.
        inicial = (cuota_inicial_f.value or "").strip()
        return f"La cuota {inicial} se paga" if inicial.isdigit() and int(inicial) > 1 else "La primera cuota se paga"

    def proponer_resumen(_e=None):
        resumen_sel.proponer(int(tarjeta_dd.value), fecha_elegida(), 2 if es_en_cuotas() else 1, que_se_paga())
        if _e is not None:
            page.update()

    def al_cambiar_tipo(_e):
        en_cuotas.visible = es_en_cuotas()
        proponer_resumen()
        actualizar_calculo()
        page.update()

    def al_cambiar_cuota_inicial(_e):
        resumen_sel.describir(que_se_paga())
        page.update()

    fila_fecha, fecha_elegida = mc.selector_fecha(page, "Fecha de la compra", date.today(), al_elegir=lambda: proponer_resumen())
    monto_f.on_change = cuotas_f.on_change = modo_monto.on_change = actualizar_calculo
    moneda_dd.on_select = actualizar_calculo
    tipo_sel.on_change = al_cambiar_tipo
    tarjeta_dd.on_select = proponer_resumen
    cuota_inicial_f.on_change = al_cambiar_cuota_inicial
    proponer_resumen()

    def guardar(_e):
        try:
            if categoria is None:
                raise ValueError("Falta la categoría base 'Tarjeta de crédito'")
            cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas", minimo=2) if es_en_cuotas() else 1
            cuota_inicial = components.parse_entero(cuota_inicial_f.value, "¿En qué cuota empezás?", maximo=cantidad) if es_en_cuotas() else 1
            if por_cuota():
                monto = monto_total_desde_cuota(components.parse_monto(monto_f.value, moneda_dd.value, "Valor de cada cuota"), cantidad)
            else:
                monto = components.parse_monto(monto_f.value, moneda_dd.value, "Monto total")
            if not (concepto_f.value or "").strip():
                raise ValueError("El concepto no puede estar vacío")
            servicios.tarjetas.registrar_compra(
                int(tarjeta_dd.value), fecha_elegida(), concepto_f.value.strip(), detalle_f.value or "", monto, categoria.id,
                cantidad, cuota_inicial, meses_al_resumen=resumen_sel.meses,
            )
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        ver_mes(resumen_sel.mes.year, resumen_sel.mes.month)
        nav.volver()
        nav.avisar(f"Compra registrada: entra en el resumen de {_mes_y_anio(resumen_sel.mes)}")

    return mc.pantalla([
        ft.Row([tarjeta_dd]),
        fila_fecha,
        concepto_f,
        detalle_f,
        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
        ft.Row([tipo_sel]),
        en_cuotas,
        ft.Row([resumen_sel.dropdown]),
        resumen_sel.aviso,
        error,
        mc.boton_ancho("Registrar compra", guardar, theme.TARJETAS_COLOR, ft.Icons.CHECK_ROUNDED),
    ])


def pantalla_compra(page: ft.Page, nav: mc.Navegacion, servicios, compra, cuota) -> ft.Control:
    """Una compra ya cargada: pagar la cuota que entra en el resumen que se
    esta viendo, corregir cualquier dato o eliminarla. Antes de guardar
    muestra que cambia y pide confirmacion, porque las cuotas se recalculan."""
    tarjetas = servicios.tarjetas.listar_tarjetas()
    en_cuotas_antes = compra.cantidad_cuotas > 1
    meses_antes = servicios.tarjetas.meses_al_resumen_de(compra)

    tarjeta_dd = mc.desplegable("Tarjeta", str(compra.tarjeta_id), [ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas], expand=True)
    resumen_sel = _selector_resumen(page, servicios)
    concepto_f = mc.campo("Concepto", value=compra.concepto)
    detalle_f = mc.campo("Detalle (opcional)", value=compra.detalle)
    monto_f = mc.campo("Monto total", value=components.monto_editable(compra.monto_total), keyboard_type=ft.KeyboardType.NUMBER)
    moneda_dd = mc.desplegable("Moneda", compra.monto_total.moneda.value, [ft.dropdown.Option(m.value) for m in Moneda])
    tipo_sel = mc.selector(_FORMAS, "cuotas" if en_cuotas_antes else "un_pago")
    cuotas_f = mc.campo("Cantidad de cuotas", value=str(compra.cantidad_cuotas if en_cuotas_antes else 2),
                        keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    pagadas_f = mc.campo("Cuotas ya pagadas", value=str(compra.cuotas_pagadas if en_cuotas_antes else 0),
                         keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    en_cuotas = ft.Column(
        [ft.Row([cuotas_f, pagadas_f], spacing=8), mc.nota("Las cuotas ya pagadas no se modifican: se recalculan solo las que faltan.")],
        spacing=12, visible=en_cuotas_antes,
    )
    pagada_check = ft.Checkbox(label="Ya está pagada", value=not en_cuotas_antes and compra.cuotas_pagadas > 0,
                               active_color=theme.TARJETAS_COLOR, visible=not en_cuotas_antes)
    error, mostrar_error = mc.texto_error(page)

    def proponer_resumen(_e=None, meses=None):
        """Al cambiar la fecha o la tarjeta se vuelve a proponer el mes."""
        que = "Se paga"
        if compra.cantidad_cuotas > 1:
            que = f"La cuota {compra.cuota_inicial} se paga" if compra.cuota_inicial > 1 else "La primera cuota se paga"
        resumen_sel.proponer(int(tarjeta_dd.value), fecha_elegida(), compra.cantidad_cuotas, que, meses)
        if _e is not None:
            page.update()

    def al_cambiar_tipo(_e):
        en_cuotas.visible = mc.elegido(tipo_sel) == "cuotas"
        pagada_check.visible = not en_cuotas.visible
        page.update()

    fila_fecha, fecha_elegida = mc.selector_fecha(page, "Fecha de la compra", compra.fecha, al_elegir=lambda: proponer_resumen())
    tarjeta_dd.on_select = proponer_resumen
    tipo_sel.on_change = al_cambiar_tipo
    proponer_resumen(meses=meses_antes)

    def leer() -> dict:
        monto = components.parse_monto(monto_f.value, moneda_dd.value)
        if mc.elegido(tipo_sel) == "cuotas":
            cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas", minimo=2)
            pagadas = components.parse_entero(pagadas_f.value, "Cuotas ya pagadas", minimo=0, maximo=cantidad)
        else:
            cantidad, pagadas = 1, 1 if pagada_check.value else 0
        concepto = (concepto_f.value or "").strip()
        if not concepto:
            raise ValueError("El concepto no puede estar vacío")
        return dict(tarjeta_id=int(tarjeta_dd.value), fecha=fecha_elegida(), concepto=concepto, detalle=detalle_f.value or "",
                    monto_total=monto, cantidad_cuotas=cantidad, cuotas_pagadas=pagadas, meses_al_resumen=resumen_sel.meses)

    def cambios(nuevo: dict) -> list[str]:
        nombre = {t.id: t.nombre for t in tarjetas}

        def cuotas_txt(n: int) -> str:
            return "1 pago" if n == 1 else f"{n} cuotas"

        pares = [
            ("Tarjeta", nombre.get(compra.tarjeta_id, "?"), nombre.get(nuevo["tarjeta_id"], "?")),
            ("Fecha", compra.fecha.strftime("%d/%m/%Y"), nuevo["fecha"].strftime("%d/%m/%Y")),
            ("Concepto", compra.concepto, nuevo["concepto"]),
            ("Detalle", compra.detalle or "(vacío)", nuevo["detalle"] or "(vacío)"),
            ("Monto", compra.monto_total.formatted(), nuevo["monto_total"].formatted()),
            ("Forma de pago", cuotas_txt(compra.cantidad_cuotas), cuotas_txt(nuevo["cantidad_cuotas"])),
            ("Cuotas pagadas", str(compra.cuotas_pagadas), str(nuevo["cuotas_pagadas"])),
            ("Entra en el resumen de", _mes_y_anio(add_months(compra.fecha, meses_antes)),
             _mes_y_anio(add_months(nuevo["fecha"], nuevo["meses_al_resumen"]))),
        ]
        return [f"{que}: {antes}  →  {despues}" for que, antes, despues in pares if antes != despues]

    def guardar(_e):
        try:
            nuevo = leer()
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        lista = cambios(nuevo)
        if not lista:
            nav.volver()
            return

        def aplicar():
            try:
                servicios.tarjetas.editar_compra(compra.id, **nuevo)
            except (ValueError, ArithmeticError) as exc:
                mostrar_error(exc)
                return
            nav.volver()
            nav.avisar("Compra guardada")

        lineas = [ft.Text("Se van a hacer estos cambios:", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)]
        lineas += [ft.Text(f"•  {c}", size=13, color=theme.TEXT_PRIMARY) for c in lista]
        if any(not c.startswith(("Concepto", "Detalle")) for c in lista):
            conservadas = servicios.tarjetas.cuotas_que_se_conservan(compra, nuevo["cuotas_pagadas"])
            moneda = nuevo["monto_total"].moneda
            ya_pagado = sum((c.monto.amount for c in conservadas), 0)
            restantes = nuevo["cantidad_cuotas"] - len(conservadas)
            if conservadas:
                lineas.append(ft.Text(f"Las {len(conservadas)} cuota(s) ya pagada(s) no se modifican "
                                      f"({Money.from_decimal(ya_pagado, moneda).formatted()} en total).",
                                      size=12, weight=ft.FontWeight.W_600, color=theme.INCOME_GREEN))
            if restantes:
                falta = nuevo["monto_total"].amount - ya_pagado
                lineas.append(ft.Text(f"{'Lo que falta' if conservadas else 'El monto'} ({Money.from_decimal(falta, moneda).formatted()}) "
                                      f"se reparte en {restantes} cuota(s) de {Money.from_decimal(falta / restantes, moneda).formatted()} aprox.",
                                      size=12, color=theme.TEXT_SECONDARY))
        mc.confirmar(page, "¿Confirmás los cambios?", ft.Column(lineas, spacing=6, tight=True, scroll=ft.ScrollMode.AUTO), "Sí, guardar",
                     theme.TARJETAS_COLOR, "check_rounded", aplicar, cancelar="Volver")

    def pagar(_e):
        def aceptar():
            servicios.tarjetas.pagar_cuota(cuota.id)
            nav.volver()
            nav.avisar("Pago registrado")

        que = f"la cuota {cuota.numero_cuota} de" if compra.cantidad_cuotas > 1 else ""
        mc.confirmar(page, "Confirmar pago", f'¿Seguro que querés pagar {que} "{compra.concepto}" ({cuota.monto.formatted()})?'.replace("  ", " "),
                     "Sí, pagar", theme.TARJETAS_COLOR, "check_rounded", aceptar)

    def eliminar(_e):
        def aceptar():
            servicios.tarjetas.eliminar_compra(compra.id)
            nav.volver()
            nav.avisar("Compra eliminada")

        mc.confirmar(page, "Eliminar compra",
                     f'¿Seguro que querés eliminar la compra "{compra.concepto}" ({compra.monto_total.formatted()})? Se borran también '
                     "todas sus cuotas, incluidas las ya pagadas. No se puede deshacer.",
                     "Eliminar", theme.EXPENSE_RED, "delete_outline_rounded", aceptar)

    forma = f"Cuota {cuota.numero_cuota} de {compra.cantidad_cuotas}" if en_cuotas_antes else "1 pago"
    if cuota.pagada:
        cuando = f" el {cuota.fecha_pago.strftime('%d/%m/%Y')}" if cuota.fecha_pago else ""
        cabecera = [ft.Row([components.category_chip(f"{forma} · pagada{cuando}", theme.INCOME_GREEN, "check_circle_rounded")])]
    else:
        cabecera = [mc.boton_ancho(f"Pagar cuota {cuota.numero_cuota} ({cuota.monto.formatted()})" if en_cuotas_antes
                                   else f"Pagar ({cuota.monto.formatted()})", pagar, theme.INCOME_GREEN,
                                   ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED)]
    if en_cuotas_antes:
        cabecera.append(ft.Text(f"Cuota {compra.monto_cuota.formatted()} · restan {compra.cuotas_restantes} · "
                                f"pendiente {compra.monto_pendiente.formatted()}", size=12, color=theme.TEXT_SECONDARY))

    return mc.pantalla([
        *cabecera,
        mc.separador(),
        ft.Row([tarjeta_dd]),
        fila_fecha,
        concepto_f,
        detalle_f,
        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
        ft.Row([tipo_sel]),
        en_cuotas,
        pagada_check,
        ft.Row([resumen_sel.dropdown]),
        resumen_sel.aviso,
        error,
        mc.boton_ancho("Guardar", guardar, theme.TARJETAS_COLOR, ft.Icons.CHECK_ROUNDED),
        mc.boton_eliminar("Eliminar compra", eliminar),
    ])


def pantalla_pagar_mes(page: ft.Page, nav: mc.Navegacion, servicios, tarjeta, anio: int, mes: int) -> ft.Control:
    """Pagar el resumen del mes: marca como pagado todo lo que entra en ese
    resumen. El saldo se puede corregir, porque el resumen de la tarjeta
    puede venir con otro importe (impuestos, intereses, ajustes)."""
    resumen = servicios.tarjetas.resumen_del_mes(tarjeta.id, anio, mes)
    debitos = [o for o in servicios.gastos_fijos.debitos_del_mes(tarjeta.id, anio, mes) if not o.ya_registrado]
    partes = partes_pendientes(resumen, debitos)
    calculado = {m.moneda: m for m in mc.totales_por_moneda(monto for _titulo, montos in partes for monto in montos)}
    campos = {
        moneda: mc.campo(f"Saldo a pagar ({moneda.value})", value=components.monto_editable(total), keyboard_type=ft.KeyboardType.NUMBER)
        for moneda, total in calculado.items()
    }
    error, mostrar_error = mc.texto_error(page)
    nombre_mes = _mes_y_anio(date(anio, mes, 1))

    def pagar(_e):
        try:
            pagado = {moneda: components.parse_monto(campo.value, moneda, f"Saldo a pagar ({moneda.value})")
                      for moneda, campo in campos.items()}
            servicios.tarjetas.pagar_mes(tarjeta.id, anio, mes, [o.gasto.monto for o in debitos], pagado)
            servicios.gastos_fijos.registrar_debitos_del_mes(tarjeta.id, anio, mes)
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar(f"{tarjeta.nombre}: {nombre_mes} pagado")

    return mc.pantalla([
        ft.Text(f"{tarjeta.nombre} · {nombre_mes}", size=16, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
        theme.card(
            ft.Column(
                [
                    ft.Text("Se marca como pagado:", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    *[mc.fila_dato("check_rounded", theme.TARJETAS_COLOR, titulo, "", _totales(montos), theme.TEXT_PRIMARY)
                      for titulo, montos in partes],
                ],
                spacing=10,
            ),
            padding=14,
        ),
        *campos.values(),
        mc.nota("Si el resumen vino con otro importe (impuestos, intereses, ajustes), corregí el saldo antes de pagar."),
        mc.nota("Si compraste algo en cuotas hace poco, su 1ra cuota recién vence el mes que viene, por eso puede no estar incluida todavía."),
        error,
        mc.boton_ancho("Sí, pagar todo", pagar, theme.TARJETAS_COLOR, ft.Icons.CHECK_ROUNDED),
    ])
