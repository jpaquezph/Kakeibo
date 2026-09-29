from __future__ import annotations

from datetime import date, datetime

import flet as ft

from ...app.domain.models import EstadoPrestamo
from ...app.domain.money import Money, Moneda
from ...app.services.prestamos import PrestamoService, vencimiento_cuota_prestamo
from .. import theme
from . import components


def build_prestamos_view(page: ft.Page, prestamo_service: PrestamoService) -> ft.Control:
    lista_col = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    contador_text = ft.Text("", size=13, color=theme.TEXT_SECONDARY)

    def refrescar():
        prestamos = prestamo_service.listar()
        pendientes = [p for p in prestamos if p.estado == EstadoPrestamo.ACTIVO]
        contador_text.value = f"{len(pendientes)} préstamo(s) pendiente(s) de {len(prestamos)} en total"
        lista_col.controls.clear()
        if not prestamos:
            lista_col.controls.append(components.empty_state("Todavía no registraste préstamos.", "account_balance_rounded"))
        for p in prestamos:
            lista_col.controls.append(_prestamo_card(p))
        page.update()

    def _prestamo_card(p):
        proxima = next((c for c in p.cuotas if not c.pagada), None)
        progreso = p.cuotas_pagadas / p.cantidad_cuotas if p.cantidad_cuotas else 0
        pagado_badge = components.category_chip("Pagado", theme.INCOME_GREEN, "check_circle_rounded") if p.estado == EstadoPrestamo.PAGADO else components.category_chip("Activo", theme.PRESTAMOS_COLOR, "hourglass_top_rounded")

        acciones = []
        if proxima:
            acciones.append(
                theme.primary_button(
                    f"Pagar cuota {proxima.numero_cuota} ({proxima.monto.formatted()})",
                    lambda e, cuota=proxima, nombre=p.nombre: confirmar_pago(cuota, nombre),
                    color=theme.PRESTAMOS_COLOR,
                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                )
            )
        acciones.append(ft.TextButton("Ver cuotas", icon=ft.Icons.LIST_ALT_ROUNDED, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                                      tooltip="Ver todas las cuotas y cambiar el monto de las que faltan",
                                      on_click=lambda e, prestamo=p: dialogo_cuotas(prestamo)))
        acciones.append(ft.TextButton("Editar", icon=ft.Icons.EDIT_ROUNDED, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                                      tooltip="Cambiar monto, cuotas, fecha o día de vencimiento",
                                      on_click=lambda e, prestamo=p: dialogo_editar(prestamo)))
        acciones.append(ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=theme.EXPENSE_RED, icon_size=18, on_click=lambda e, pid=p.id: eliminar(pid)))

        return theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(p.nombre, size=16, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                            pagado_badge,
                        ]
                    ),
                    ft.Text(p.detalle, size=12, color=theme.TEXT_SECONDARY) if p.detalle else ft.Container(),
                    ft.ProgressBar(value=progreso, color=theme.PRESTAMOS_COLOR, bgcolor=theme.PRESTAMOS_BG, border_radius=8, height=8),
                    ft.Row(
                        [
                            ft.Text(f"Monto total: {p.monto_original.formatted()}", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(f"Cuotas: {p.cuotas_pagadas}/{p.cantidad_cuotas}", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(f"Pagado: {p.total_pagado.formatted()}", size=12, color=theme.INCOME_GREEN, weight=ft.FontWeight.W_600),
                            ft.Text(f"Pendiente: {p.total_pendiente.formatted()}", size=12, color=theme.EXPENSE_RED, weight=ft.FontWeight.W_600),
                        ],
                        spacing=16,
                        wrap=True,
                    ),
                    *([ft.Row(
                        [ft.Icon(ft.Icons.EVENT_ROUNDED, size=15, color=theme.PRESTAMOS_COLOR),
                         ft.Text(f"Próximo vencimiento: cuota {proxima.numero_cuota}, el {proxima.fecha_vencimiento.strftime('%d/%m/%Y')}",
                                 size=12, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)],
                        spacing=6,
                    )] if proxima else []),
                    ft.Row(acciones, alignment=ft.MainAxisAlignment.START),
                ],
                spacing=10,
            ),
            padding=18,
        )

    campo = dict(filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)

    def confirmar_pago(cuota, nombre_prestamo: str):
        """El monto de la cuota viene cargado y se puede corregir: hay prestamos
        cuya cuota cambia cada mes (UVA, sistema aleman, ajustes)."""
        monto_f = ft.TextField(label=f"Monto de la cuota ({cuota.monto.moneda.value})", value=components.monto_editable(cuota.monto),
                               keyboard_type=ft.KeyboardType.NUMBER, helper="Si este mes la cuota vino con otro monto, corregilo acá.", **campo)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def confirmar(_e):
            try:
                monto = components.parse_monto(monto_f.value, cuota.monto.moneda, "Monto de la cuota")
                prestamo_service.pagar_cuota(cuota.id, monto=monto if monto != cuota.monto else None)
            except (ValueError, ArithmeticError) as exc:
                error_text.value, error_text.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            refrescar()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error("Confirmar pago", error_text),
            content=ft.Container(ft.Column(
                [ft.Text(f'¿Pagar la cuota {cuota.numero_cuota} de "{nombre_prestamo}" (vence el {cuota.fecha_vencimiento.strftime("%d/%m/%Y")})?'),
                 monto_f],
                spacing=12, tight=True,
            ), width=400),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, pagar", confirmar, color=theme.PRESTAMOS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        ))

    def dialogo_cuotas(prestamo):
        """Todas las cuotas del prestamo; en las que faltan pagar se puede
        cambiar el monto (y aplicarlo tambien a las siguientes)."""
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)
        siguientes_check = ft.Checkbox(label="Al cambiar una cuota, aplicar el mismo monto a las siguientes", value=False,
                                       active_color=theme.PRESTAMOS_COLOR)
        filas = ft.Column(spacing=6, tight=True, scroll=ft.ScrollMode.AUTO)

        def armar_filas(p):
            filas.controls.clear()
            for c in p.cuotas:
                vence = ft.Text(f"Cuota {c.numero_cuota} · vence {c.fecha_vencimiento.strftime('%d/%m/%Y')}", size=12,
                                color=theme.TEXT_SECONDARY, expand=True)
                if c.pagada:
                    pagada_el = f"pagada el {c.fecha_pago.strftime('%d/%m/%Y')}" if c.fecha_pago else "pagada"
                    filas.controls.append(ft.Row([
                        vence,
                        ft.Text(f"{c.monto.formatted()} · {pagada_el}", size=12, color=theme.INCOME_GREEN),
                    ]))
                else:
                    monto_f = ft.TextField(value=components.monto_editable(c.monto), width=130, dense=True, text_size=13,
                                           keyboard_type=ft.KeyboardType.NUMBER, **campo)
                    filas.controls.append(ft.Row([
                        vence, monto_f,
                        ft.IconButton(icon=ft.Icons.CHECK_ROUNDED, icon_color=theme.PRESTAMOS_COLOR, icon_size=18,
                                      tooltip="Guardar este monto",
                                      on_click=lambda e, cuota=c, campo_monto=monto_f: guardar_cuota(cuota, campo_monto)),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def guardar_cuota(cuota, campo_monto):
            try:
                monto = components.parse_monto(campo_monto.value, cuota.monto.moneda, f"Cuota {cuota.numero_cuota}")
                actualizado = prestamo_service.cambiar_monto_cuota(cuota.id, monto, bool(siguientes_check.value))
            except (ValueError, ArithmeticError) as exc:
                error_text.value, error_text.visible = str(exc), True
                page.update()
                return
            error_text.visible = False
            total_text.value = f"Monto total: {actualizado.monto_original.formatted()}"
            armar_filas(actualizado)
            refrescar()

        total_text = ft.Text(f"Monto total: {prestamo.monto_original.formatted()}", size=13, weight=ft.FontWeight.W_600)
        armar_filas(prestamo)
        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error(f"Cuotas de {prestamo.nombre}", error_text),
            content=ft.Container(ft.Column(
                [
                    ft.Text("Cambiá el monto de una cuota pendiente y tocá ✓ para guardarlo. El monto total del préstamo "
                            "pasa a ser la suma de todas las cuotas. Las cuotas pagadas no se modifican.",
                            size=11, color=theme.TEXT_MUTED, italic=True),
                    siguientes_check, total_text, ft.Divider(height=1, color=theme.BORDER),
                    ft.Container(filas, height=340),
                ],
                spacing=10, tight=True,
            ), width=480),
            actions=[theme.primary_button("Listo", lambda e: page.pop_dialog(), color=theme.PRESTAMOS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        ))

    def dialogo_editar(prestamo):
        """Edicion completa del prestamo. Muestra que cambia y pide
        confirmacion; las cuotas pagadas no se modifican."""
        fecha_holder = {"value": prestamo.fecha_inicio}
        fecha_text = ft.Text(prestamo.fecha_inicio.strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                page.update()

        date_picker = ft.DatePicker(value=prestamo.fecha_inicio, on_change=on_fecha_change)
        page.overlay.append(date_picker)

        dia_actual = prestamo_service.dia_vencimiento_de(prestamo)
        nombre_f = ft.TextField(label="Nombre del préstamo", value=prestamo.nombre, **campo)
        detalle_f = ft.TextField(label="Detalle (opcional)", value=prestamo.detalle, **campo)
        monto_f = ft.TextField(label="Monto total", value=components.monto_editable(prestamo.monto_original),
                               keyboard_type=ft.KeyboardType.NUMBER, expand=2, **campo)
        moneda_dd = ft.Dropdown(label="Moneda", value=prestamo.monto_original.moneda.value,
                                options=[ft.dropdown.Option(m.value) for m in Moneda], expand=1, **campo)
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value=str(prestamo.cantidad_cuotas), keyboard_type=ft.KeyboardType.NUMBER, expand=True, **campo)
        pagadas_f = ft.TextField(label="Cuotas ya pagadas", value=str(prestamo.cuotas_pagadas), keyboard_type=ft.KeyboardType.NUMBER, expand=True, **campo)
        dia_f = ft.TextField(label="Día de vencimiento de cada cuota", value=str(dia_actual), keyboard_type=ft.KeyboardType.NUMBER, max_length=2, **campo)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def leer():
            nombre = (nombre_f.value or "").strip()
            if not nombre:
                raise ValueError("El nombre no puede estar vacío")
            cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas")
            return dict(
                nombre=nombre, detalle=detalle_f.value or "",
                monto_total=components.parse_monto(monto_f.value, moneda_dd.value, "Monto total"),
                cantidad_cuotas=cantidad,
                cuotas_pagadas=components.parse_entero(pagadas_f.value, "Cuotas ya pagadas", minimo=0, maximo=cantidad),
                fecha_inicio=fecha_holder["value"],
                dia_vencimiento=components.parse_entero(dia_f.value, "Día de vencimiento", maximo=31),
            )

        def _cambios(nuevo) -> list[str]:
            pares = [
                ("Nombre", prestamo.nombre, nuevo["nombre"]),
                ("Detalle", prestamo.detalle or "(vacío)", nuevo["detalle"] or "(vacío)"),
                ("Monto total", prestamo.monto_original.formatted(), nuevo["monto_total"].formatted()),
                ("Cantidad de cuotas", str(prestamo.cantidad_cuotas), str(nuevo["cantidad_cuotas"])),
                ("Cuotas pagadas", str(prestamo.cuotas_pagadas), str(nuevo["cuotas_pagadas"])),
                ("Fecha de inicio", prestamo.fecha_inicio.strftime("%d/%m/%Y"), nuevo["fecha_inicio"].strftime("%d/%m/%Y")),
                ("Día de vencimiento", str(dia_actual), str(nuevo["dia_vencimiento"])),
            ]
            return [f"{que}: {antes}  →  {despues}" for que, antes, despues in pares if antes != despues]

        def guardar(_e):
            try:
                nuevo = leer()
            except (ValueError, ArithmeticError) as exc:
                error_text.value, error_text.visible = str(exc), True
                page.update()
                return
            cambios = _cambios(nuevo)
            page.pop_dialog()
            if cambios:
                confirmar_edicion(nuevo, cambios)

        def confirmar_edicion(nuevo, cambios):
            conservadas = prestamo_service.cuotas_que_se_conservan(prestamo, nuevo["cuotas_pagadas"])
            moneda = nuevo["monto_total"].moneda
            ya_pagado = sum((c.monto.amount for c in conservadas), 0)
            restantes = nuevo["cantidad_cuotas"] - len(conservadas)
            solo_textos = all(c.startswith(("Nombre", "Detalle")) for c in cambios)

            def aplicar(_e):
                try:
                    prestamo_service.editar_prestamo(prestamo.id, **nuevo)
                except (ValueError, ArithmeticError) as exc:
                    page.pop_dialog()
                    error_text.value, error_text.visible = str(exc), True
                    page.show_dialog(dialog)
                    return
                page.pop_dialog()
                refrescar()

            def volver(_e):
                page.pop_dialog()
                page.show_dialog(dialog)

            lineas = [ft.Text("Se van a hacer estos cambios:", size=13, weight=ft.FontWeight.W_600)]
            lineas += [ft.Text(f"•  {c}", size=13) for c in cambios]
            if not solo_textos:
                if conservadas:
                    lineas.append(ft.Text(
                        f"Las {len(conservadas)} cuota(s) ya pagada(s) no se modifican ({Money.from_decimal(ya_pagado, moneda).formatted()} en total).",
                        size=12, weight=ft.FontWeight.W_600, color=theme.INCOME_GREEN,
                    ))
                if restantes:
                    falta = nuevo["monto_total"].amount - ya_pagado
                    lineas.append(ft.Text(
                        f"{'Lo que falta' if conservadas else 'El monto'} ({Money.from_decimal(falta, moneda).formatted()}) se reparte en "
                        f"{restantes} cuota(s) de {Money.from_decimal(falta / restantes, moneda).formatted()} aprox., "
                        f"que vencen el día {nuevo['dia_vencimiento']} de cada mes.",
                        size=12, color=theme.TEXT_SECONDARY,
                    ))
                    lineas.append(ft.Text("Si cambiaste montos de cuotas a mano (en \"Ver cuotas\"), las pendientes vuelven a quedar iguales.",
                                          size=11, color=theme.TEXT_MUTED, italic=True))
            page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("¿Confirmás los cambios?"),
                content=ft.Container(ft.Column(lineas, spacing=6, tight=True, scroll=ft.ScrollMode.AUTO), width=440),
                actions=[
                    theme.secondary_button("Volver a editar", volver),
                    theme.primary_button("Sí, guardar", aplicar, color=theme.PRESTAMOS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
                ],
            ))

        dialog = ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error("Editar préstamo", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Row([ft.Text("Fecha de inicio:", size=13, color=theme.TEXT_SECONDARY), fecha_text,
                                ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        nombre_f, detalle_f,
                        ft.Row([monto_f, moneda_dd], spacing=8),
                        ft.Row([cuotas_f, pagadas_f], spacing=8),
                        dia_f,
                        ft.Text("Las cuotas ya pagadas no se modifican: se recalculan solo las que faltan.",
                                size=11, color=theme.TEXT_MUTED, italic=True),
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                     theme.primary_button("Guardar", guardar, color=theme.PRESTAMOS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    def eliminar(prestamo_id: int):
        def confirmar(_e):
            prestamo_service.eliminar_prestamo(prestamo_id)
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar préstamo"),
            content=ft.Text("¿Seguro que querés eliminar este préstamo y todas sus cuotas?"),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED)],
        )
        page.show_dialog(dialog)

    def nuevo_prestamo(_e=None):
        fecha_holder = {"value": date.today()}
        fecha_text = ft.Text(fecha_holder["value"].strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                actualizar_vencimientos()
                page.update()

        date_picker = ft.DatePicker(value=fecha_holder["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        nombre_f = ft.TextField(label="Nombre del préstamo", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        campo = dict(filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        monto_f = ft.TextField(label="Monto total", **campo)
        moneda_dd = ft.Dropdown(label="Moneda", value=Moneda.ARS.value, options=[ft.dropdown.Option(m.value) for m in Moneda], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value="12", expand=True, **campo)
        cuota_inicial_f = ft.TextField(label="¿En qué cuota estás?", value="1", expand=True, **campo)
        dia_venc_f = ft.TextField(label="Día de vencimiento de cada cuota", value=str(fecha_holder["value"].day), max_length=2, **campo)
        vencimientos_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY, italic=True)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def actualizar_vencimientos(_e=None):
            """Muestra cuando vence la proxima cuota a pagar, segun lo cargado."""
            try:
                cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas")
                actual = components.parse_entero(cuota_inicial_f.value, "Cuota", maximo=cantidad)
                dia = components.parse_entero(dia_venc_f.value, "Día", maximo=31)
            except ValueError:
                vencimientos_text.value = ""
            else:
                vence = vencimiento_cuota_prestamo(fecha_holder["value"], actual, dia)
                previas = f" Las cuotas 1 a {actual - 1} quedan como pagadas." if actual > 1 else ""
                vencimientos_text.value = f"La cuota {actual} vence el {vence.strftime('%d/%m/%Y')}.{previas}"
            if _e is not None:
                page.update()

        for f in (cuotas_f, cuota_inicial_f, dia_venc_f):
            f.on_change = actualizar_vencimientos
        actualizar_vencimientos()

        def guardar(_e):
            try:
                monto = components.parse_monto(monto_f.value, moneda_dd.value, "Monto total")
                cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas")
                cuota_inicial = components.parse_entero(cuota_inicial_f.value, "¿En qué cuota estás?", maximo=cantidad)
                dia = components.parse_entero(dia_venc_f.value, "Día de vencimiento", maximo=31)
                prestamo_service.registrar_prestamo(nombre_f.value or "", detalle_f.value or "", monto, cantidad, fecha_holder["value"],
                                                    cuota_inicial=cuota_inicial, dia_vencimiento=dia)
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error("Nuevo préstamo", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Row([ft.Text("Fecha de inicio:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        nombre_f, detalle_f,
                        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
                        ft.Row([cuotas_f, cuota_inicial_f], spacing=8),
                        ft.Text("Si ya venías pagando, poné en qué cuota estás ahora: las anteriores quedan pagadas.",
                                size=11, color=theme.TEXT_MUTED, italic=True),
                        dia_venc_f,
                        vencimientos_text,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Registrar préstamo", guardar, color=theme.PRESTAMOS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text("Préstamos", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    contador_text,
                ],
                spacing=2,
            ),
            theme.primary_button("Nuevo préstamo", nuevo_prestamo, color=theme.PRESTAMOS_COLOR, icon=ft.Icons.ADD_ROUNDED),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar()

    return ft.Column([header, ft.Container(height=12), lista_col], expand=True, spacing=0)
