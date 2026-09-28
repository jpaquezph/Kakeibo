from __future__ import annotations

from datetime import date, datetime

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.tarjetas import TarjetaService, vencimiento_cuota
from .. import theme
from . import components

_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def build_tarjetas_view(
    page: ft.Page, tarjeta_service: TarjetaService, categoria_repo: CategoriaRepository, gasto_fijo_service: GastoFijoService,
) -> ft.Control:
    categoria_tarjeta = next((c for c in categoria_repo.listar(TipoMovimiento.EGRESO) if c.nombre == "Tarjeta de crédito"), None)
    categoria_tarjeta_id = categoria_tarjeta.id if categoria_tarjeta else None
    estado = {"tarjeta_id": None}

    tarjetas_row = ft.Row(spacing=12, wrap=True)
    detalle_col = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def refrescar_tarjetas():
        tarjetas = tarjeta_service.listar_tarjetas()
        tarjetas_row.controls.clear()
        if not tarjetas:
            tarjetas_row.controls.append(components.empty_state("Todavía no cargaste tarjetas.", "credit_card_rounded"))
        for t in tarjetas:
            seleccionada = t.id == estado["tarjeta_id"]
            tarjetas_row.controls.append(_tarjeta_card(t, seleccionada, lambda e, tid=t.id: seleccionar(tid)))
        if estado["tarjeta_id"] is None and tarjetas:
            estado["tarjeta_id"] = tarjetas[0].id
        refrescar_detalle()
        page.update()

    def _tarjeta_card(t, seleccionada, on_click):
        hoy = date.today()
        # Cuotas pendientes + debitos automaticos del mes: todo lo que hay que pagar.
        pendiente = tarjeta_service.total_pendiente(t.id) + gasto_fijo_service.total_debitos_pendientes(t.id, hoy.year, hoy.month, t.moneda)
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color="#FFFFFF", size=22),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_ROUNDED, icon_color=ft.Colors.with_opacity(0.85, "#FFFFFF"), icon_size=16,
                                on_click=lambda e, tarjeta=t: dialogo_tarjeta(tarjeta),
                                style=ft.ButtonStyle(padding=0),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(t.nombre, color="#FFFFFF", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        [
                            ft.Text(f"{t.banco}  ••{t.ultimos_digitos}" if t.ultimos_digitos else t.banco, color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=11, expand=True),
                            ft.Text(t.moneda.value, color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=11, weight=ft.FontWeight.W_600),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(f"Pendiente: {pendiente.formatted()}", color="#FFFFFF", size=12, weight=ft.FontWeight.BOLD),
                ],
                spacing=2,
            ),
            width=200,
            height=128,
            padding=12,
            border_radius=theme.RADIUS,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[t.color, theme.darken(t.color)],
            ),
            border=theme.border_all(3, theme.TEXT_PRIMARY) if seleccionada else None,
            on_click=on_click,
            ink=True,
        )

    def seleccionar(tarjeta_id: int):
        estado["tarjeta_id"] = tarjeta_id
        refrescar_tarjetas()

    def refrescar_detalle():
        detalle_col.controls.clear()
        if estado["tarjeta_id"] is None:
            detalle_col.controls.append(components.empty_state("Elegí o creá una tarjeta para ver sus compras."))
            return
        compras = tarjeta_service.listar_compras(estado["tarjeta_id"])
        tarjeta_actual = tarjeta_service.obtener_tarjeta(estado["tarjeta_id"])
        banner = _banner_pagar_mes(estado["tarjeta_id"])
        if banner:
            detalle_col.controls.append(banner)
        debitos = _debitos_card(estado["tarjeta_id"])
        if debitos:
            detalle_col.controls.append(debitos)
        if not compras:
            detalle_col.controls.append(components.empty_state("Esta tarjeta todavía no tiene compras.", "shopping_bag_rounded"))
        for c in compras:
            detalle_col.controls.append(_compra_card(c, tarjeta_actual))

    def _pendiente_del_mes(tarjeta_id: int):
        """Cuotas y debitos automaticos sin pagar de este mes, y el total."""
        hoy = date.today()
        cuotas = tarjeta_service.cuotas_pendientes_del_mes(tarjeta_id, hoy.year, hoy.month)
        debitos = [o for o in gasto_fijo_service.debitos_del_mes(tarjeta_id, hoy.year, hoy.month) if not o.ya_registrado]
        montos = [c.monto for c in cuotas] + [o.gasto.monto for o in debitos]
        total = None
        for m in montos:
            total = m if total is None else total + m
        return cuotas, debitos, total

    def _descripcion_pendiente(cuotas, debitos) -> str:
        partes = []
        if cuotas:
            partes.append(f"{len(cuotas)} cuota(s)")
        if debitos:
            partes.append(f"{len(debitos)} débito(s) automático(s)")
        return " y ".join(partes)

    def _debitos_card(tarjeta_id: int):
        hoy = date.today()
        debitos = gasto_fijo_service.debitos_del_mes(tarjeta_id, hoy.year, hoy.month)
        if not debitos:
            return None
        filas = []
        for o in debitos:
            estado_chip = (
                components.category_chip("Pagado este mes", theme.INCOME_GREEN, "check_circle_rounded") if o.ya_registrado
                else ft.Text(f"Vence el {o.fecha.strftime('%d/%m')}", size=12, color=theme.TEXT_SECONDARY)
            )
            filas.append(ft.Row(
                [
                    ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=16, color=theme.MOVIMIENTOS_COLOR),
                    ft.Text(o.gasto.concepto, size=13, color=theme.TEXT_PRIMARY, expand=True),
                    estado_chip,
                    ft.Text(o.gasto.monto.formatted(), size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY, width=120, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=10,
            ))
        return theme.card(
            ft.Column(
                [
                    ft.Text("Débitos automáticos de este mes", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Text("Son gastos fijos: se cuentan una sola vez, en Gastos fijos. Pagar la tarjeta también registra su pago.",
                            size=11, color=theme.TEXT_MUTED),
                    *filas,
                ],
                spacing=8,
            ),
            padding=14,
        )

    def _banner_pagar_mes(tarjeta_id: int):
        cuotas, debitos, total = _pendiente_del_mes(tarjeta_id)
        if total is None:
            return None
        return theme.card(
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(f"{_descripcion_pendiente(cuotas, debitos)} vencen este mes", size=13, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                            ft.Text(f"Total: {total.formatted()}", size=12, color=theme.TEXT_SECONDARY),
                        ],
                        spacing=2, expand=True,
                    ),
                    theme.primary_button("Pagar tarjeta (mes)", lambda e, tid=tarjeta_id: confirmar_pagar_mes(tid), color=theme.TARJETAS_COLOR, icon=ft.Icons.PAYMENTS_ROUNDED),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=14,
        )

    def confirmar_pagar_mes(tarjeta_id: int):
        hoy = date.today()
        cuotas, debitos, total = _pendiente_del_mes(tarjeta_id)

        def confirmar(_e):
            tarjeta_service.pagar_cuotas_del_mes(tarjeta_id, hoy.year, hoy.month)
            gasto_fijo_service.registrar_debitos_del_mes(tarjeta_id, hoy.year, hoy.month)
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Pagar tarjeta del mes"),
            content=ft.Column(
                [
                    ft.Text(f"¿Marcar como pagados {_descripcion_pendiente(cuotas, debitos)} que vencen este mes, por un total de {total.formatted()}?"),
                    ft.Text(
                        "Nota: si compraste algo en cuotas hace poco, su 1ra cuota recién vence el mes que viene, "
                        "por eso puede no estar incluida todavía.",
                        size=11, color=theme.TEXT_MUTED, italic=True,
                    ),
                ],
                spacing=10, tight=True,
            ),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, pagar todo", confirmar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def _compra_card(c, tarjeta_actual):
        proxima = next((cu for cu in c.cuotas if not cu.pagada), None)
        acciones = []
        if proxima:
            acciones.append(
                theme.primary_button(
                    f"Pagar cuota {proxima.numero_cuota}",
                    lambda e, cid=proxima.id, num=proxima.numero_cuota, concepto=c.concepto: confirmar_pago_compra(cid, num, concepto),
                    color=theme.TARJETAS_COLOR,
                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                )
            )
        else:
            acciones.append(components.category_chip("Compra saldada", theme.INCOME_GREEN, "check_circle_rounded"))

        return theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(c.concepto, size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                            ft.Text(c.monto_total.formatted(), size=15, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                            ft.IconButton(icon=ft.Icons.EDIT_ROUNDED, icon_color=theme.TEXT_MUTED, icon_size=16, on_click=lambda e, compra=c: dialogo_editar_compra(compra)),
                            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=theme.EXPENSE_RED, icon_size=16, on_click=lambda e, cid=c.id: eliminar_compra(cid)),
                        ]
                    ),
                    ft.Row(
                        [
                            components.category_chip("1 pago" if c.cantidad_cuotas == 1 else f"Cuota {c.cuota_actual} de {c.cantidad_cuotas}", theme.TARJETAS_COLOR, "payments_rounded" if c.cantidad_cuotas == 1 else "calendar_view_month_rounded"),
                            components.category_chip(tarjeta_actual.nombre, tarjeta_actual.color, "credit_card_rounded") if tarjeta_actual else ft.Container(),
                            ft.Text(f"Restantes: {c.cuotas_restantes}", size=12, color=theme.TEXT_SECONDARY) if c.cantidad_cuotas > 1 else ft.Container(),
                            ft.Text(f"Cuota: {c.monto_cuota.formatted()}", size=12, color=theme.TEXT_SECONDARY) if c.cantidad_cuotas > 1 else ft.Container(),
                            ft.Text(f"Pendiente: {c.monto_pendiente.formatted()}", size=12, weight=ft.FontWeight.W_600, color=theme.EXPENSE_RED),
                        ],
                        spacing=14,
                        wrap=True,
                    ),
                    ft.Row(acciones),
                ],
                spacing=8,
            ),
            padding=16,
        )

    def confirmar_pago_compra(cuota_id: int, numero_cuota: int, concepto: str):
        def confirmar(_e):
            tarjeta_service.pagar_cuota(cuota_id)
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar pago"),
            content=ft.Text(f'¿Seguro que querés pagar la cuota {numero_cuota} de "{concepto}"?'),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, pagar", confirmar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def eliminar_compra(compra_id: int):
        compra = next((c for c in tarjeta_service.listar_compras(estado["tarjeta_id"]) if c.id == compra_id), None)
        descripcion = f'"{compra.concepto}" ({compra.monto_total.formatted()})' if compra else "esta compra"

        def confirmar(_e):
            tarjeta_service.eliminar_compra(compra_id)
            page.pop_dialog()
            refrescar_tarjetas()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar compra"),
            content=ft.Text(f"¿Seguro que querés eliminar la compra {descripcion}? Se borran también todas sus cuotas, "
                            "incluidas las ya pagadas. No se puede deshacer."),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        ))

    def eliminar_tarjeta(tarjeta):
        cantidad = len(tarjeta_service.listar_compras(tarjeta.id))
        hoy = date.today()
        debitos = gasto_fijo_service.debitos_del_mes(tarjeta.id, hoy.year, hoy.month)
        detalle = [f'¿Seguro que querés eliminar la tarjeta "{tarjeta.nombre}"?']
        if cantidad:
            detalle.append(f"Se borran también sus {cantidad} compra(s) con todas sus cuotas, incluidas las ya pagadas.")
        if debitos:
            detalle.append(f"Sus {len(debitos)} débito(s) automático(s) no se pierden: pasan a ser gastos fijos comunes.")
        detalle.append("No se puede deshacer.")

        def confirmar(_e):
            tarjeta_service.eliminar_tarjeta(tarjeta.id)
            if estado["tarjeta_id"] == tarjeta.id:
                estado["tarjeta_id"] = None
            page.pop_dialog()
            refrescar_tarjetas()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar tarjeta"),
            content=ft.Container(ft.Column([ft.Text(t) for t in detalle], spacing=8, tight=True), width=380),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Eliminar tarjeta", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        ))

    def dialogo_tarjeta(tarjeta=None):
        es_edicion = tarjeta is not None
        nombre_f = ft.TextField(label="Nombre (ej: Visa Galicia)", value=tarjeta.nombre if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        banco_f = ft.TextField(label="Banco", value=tarjeta.banco if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        digitos_f = ft.TextField(label="Últimos 4 dígitos (opcional)", value=tarjeta.ultimos_digitos if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, max_length=4)
        moneda_dd = ft.Dropdown(label="Moneda", value=(tarjeta.moneda.value if es_edicion else Moneda.ARS.value), options=[ft.dropdown.Option(m.value) for m in Moneda], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        color_elegido = {"value": tarjeta.color if es_edicion else theme.TARJETA_COLORES[0]}
        swatches_row = ft.Row(spacing=10)

        def elegir_color(color):
            color_elegido["value"] = color
            _redibujar_swatches()
            page.update()

        def _swatch(color):
            seleccionado = color == color_elegido["value"]
            return ft.Container(
                width=30, height=30, bgcolor=color, border_radius=15,
                border=theme.border_all(3, theme.TEXT_PRIMARY) if seleccionado else theme.border_all(1, theme.BORDER),
                on_click=lambda e, c=color: elegir_color(c),
                ink=True,
            )

        def _redibujar_swatches():
            swatches_row.controls = [_swatch(c) for c in theme.TARJETA_COLORES]

        _redibujar_swatches()

        def guardar(_e):
            try:
                if not (nombre_f.value or "").strip():
                    raise ValueError("El nombre de la tarjeta es obligatorio")
                if es_edicion:
                    tarjeta_service.editar_tarjeta(
                        tarjeta.id, nombre_f.value.strip(), banco_f.value or "", digitos_f.value or "",
                        moneda_dd.value, color_elegido["value"],
                    )
                else:
                    t = tarjeta_service.crear_tarjeta(
                        nombre_f.value.strip(), banco_f.value or "", digitos_f.value or "",
                        moneda_dd.value, color_elegido["value"],
                    )
                    estado["tarjeta_id"] = t.id
            except ValueError as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar tarjeta" if es_edicion else "Nueva tarjeta"),
            content=ft.Container(
                ft.Column(
                    [
                        nombre_f, banco_f, digitos_f, moneda_dd,
                        ft.Text("Color para identificarla", size=12, color=theme.TEXT_SECONDARY),
                        swatches_row,
                        error_text,
                    ],
                    spacing=12, tight=True,
                ),
                width=360,
            ),
            actions=[
                # Eliminar se ofrece desde la edicion; primero se cierra este dialogo para mostrar la confirmacion.
                *([ft.TextButton("Eliminar tarjeta", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, style=ft.ButtonStyle(color=theme.EXPENSE_RED),
                                 on_click=lambda e: (page.pop_dialog(), eliminar_tarjeta(tarjeta)))] if es_edicion else []),
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Guardar" if es_edicion else "Crear", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def dialogo_editar_compra(compra):
        concepto_f = ft.TextField(label="Concepto", value=compra.concepto, filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", value=compra.detalle, filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                tarjeta_service.editar_datos_compra(compra.id, concepto_f.value or "", detalle_f.value or "", categoria_tarjeta_id)
            except ValueError as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar compra"),
            content=ft.Container(
                ft.Column(
                    [
                        concepto_f, detalle_f, error_text,
                        ft.Text("El monto y la cantidad de cuotas no se pueden editar.", size=11, color=theme.TEXT_MUTED, italic=True),
                    ],
                    spacing=12, tight=True,
                ),
                width=380,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Guardar", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    def nueva_compra(_e=None):
        tarjetas_disponibles = tarjeta_service.listar_tarjetas()
        if not tarjetas_disponibles:
            return
        fecha_holder = {"value": date.today()}
        fecha_text = ft.Text(fecha_holder["value"].strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                actualizar_primer_vencimiento()
                page.update()

        date_picker = ft.DatePicker(value=fecha_holder["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        tarjeta_id_inicial = estado["tarjeta_id"] if estado["tarjeta_id"] is not None else tarjetas_disponibles[0].id
        tarjeta_dd = ft.Dropdown(
            label="Tarjeta",
            value=str(tarjeta_id_inicial),
            options=[ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas_disponibles],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )

        tipo_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="un_pago", label=ft.Text("1 pago"), icon=ft.Icons.PAYMENTS_ROUNDED),
                ft.Segment(value="cuotas", label=ft.Text("En cuotas"), icon=ft.Icons.CALENDAR_VIEW_MONTH_ROUNDED),
            ],
            selected=["un_pago"],
            allow_multiple_selection=False,
            allow_empty_selection=False,
        )

        concepto_f = ft.TextField(label="Concepto", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        monto_f = ft.TextField(label="Monto total", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value="2", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cuota_inicial_f = ft.TextField(
            label="¿En qué cuota empezás?", value="1", filled=True, bgcolor=theme.SURFACE_ALT,
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER,
            helper="Si ya veniás pagando (ej: compraste hace 3 meses), poné en qué cuota estás ahora.",
        )
        cuotas_container = ft.Column([cuotas_f, cuota_inicial_f], spacing=12, visible=False)

        # Se pregunta en cada compra (no es un dato fijo de la tarjeta) porque
        # el dia de cierre del resumen cambia mes a mes.
        cerrada_check = ft.Checkbox(
            label="La tarjeta ya cerró el resumen de este mes", value=False, active_color=theme.TARJETAS_COLOR,
        )
        primer_vencimiento_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY, italic=True)

        def actualizar_primer_vencimiento(_e=None):
            es_en_cuotas = "cuotas" in tipo_selector.selected
            vence = vencimiento_cuota(fecha_holder["value"], 1, 2 if es_en_cuotas else 1, bool(cerrada_check.value))
            que = "La primera cuota se paga" if es_en_cuotas else "Se paga"
            primer_vencimiento_text.value = f"{que} en {_MESES[vence.month - 1].lower()} {vence.year}."

        def on_tipo_change(_e):
            cuotas_container.visible = "cuotas" in tipo_selector.selected
            actualizar_primer_vencimiento()
            page.update()

        def on_cerrada_change(_e):
            actualizar_primer_vencimiento()
            page.update()

        tipo_selector.on_change = on_tipo_change
        cerrada_check.on_change = on_cerrada_change
        actualizar_primer_vencimiento()

        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                if categoria_tarjeta_id is None:
                    raise ValueError("Falta la categoría base 'Tarjeta de crédito'")
                tarjeta_id = int(tarjeta_dd.value)
                tarjeta = next(t for t in tarjetas_disponibles if t.id == tarjeta_id)
                monto = Money.from_decimal((monto_f.value or "0").replace(",", "."), tarjeta.moneda)
                es_en_cuotas = "cuotas" in tipo_selector.selected
                cantidad = int(cuotas_f.value or "1") if es_en_cuotas else 1
                cuota_inicial = int(cuota_inicial_f.value or "1") if es_en_cuotas else 1
                tarjeta_service.registrar_compra(
                    tarjeta_id, fecha_holder["value"], concepto_f.value or "", detalle_f.value or "",
                    monto, categoria_tarjeta_id, cantidad, cuota_inicial, tarjeta_cerrada=bool(cerrada_check.value),
                )
                estado["tarjeta_id"] = tarjeta_id
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nueva compra"),
            content=ft.Container(
                ft.Column(
                    [
                        tarjeta_dd,
                        ft.Row([ft.Text("Fecha:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        concepto_f, detalle_f, monto_f,
                        tipo_selector,
                        cuotas_container,
                        cerrada_check,
                        primer_vencimiento_text,
                        error_text,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Registrar compra", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    header = ft.Row(
        [
            ft.Text("Tarjetas", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Row([theme.secondary_button("Nueva tarjeta", lambda e: dialogo_tarjeta(None), icon=ft.Icons.ADD_CARD_ROUNDED), theme.primary_button("Nueva compra", nueva_compra, color=theme.TARJETAS_COLOR, icon=ft.Icons.ADD_SHOPPING_CART_ROUNDED)]),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar_tarjetas()

    return ft.Column(
        [header, ft.Container(height=12), tarjetas_row, ft.Container(height=16), ft.Divider(color=theme.BORDER), ft.Container(height=8), detalle_col],
        expand=True, spacing=0,
    )
