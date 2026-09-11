from __future__ import annotations

from datetime import date, datetime

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.tarjetas import TarjetaService
from .. import theme
from . import components


def build_tarjetas_view(page: ft.Page, tarjeta_service: TarjetaService, categoria_repo: CategoriaRepository) -> ft.Control:
    categorias = categoria_repo.listar(TipoMovimiento.EGRESO)
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
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color="#FFFFFF", size=22),
                    ft.Text(t.nombre, color="#FFFFFF", weight=ft.FontWeight.BOLD, size=15),
                    ft.Text(f"{t.banco}  ••{t.ultimos_digitos}", color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=11),
                    ft.Text(t.moneda.value, color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=11),
                ],
                spacing=4,
            ),
            width=200,
            height=110,
            padding=16,
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
        if not compras:
            detalle_col.controls.append(components.empty_state("Esta tarjeta todavía no tiene compras.", "shopping_bag_rounded"))
        for c in compras:
            detalle_col.controls.append(_compra_card(c))

    def _compra_card(c):
        proxima = next((cu for cu in c.cuotas if not cu.pagada), None)
        acciones = []
        if proxima:
            acciones.append(
                theme.primary_button(
                    f"Pagar cuota {proxima.numero_cuota}",
                    lambda e, cid=proxima.id: pagar_cuota(cid),
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
                            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=theme.EXPENSE_RED, icon_size=16, on_click=lambda e, cid=c.id: eliminar_compra(cid)),
                        ]
                    ),
                    ft.Row(
                        [
                            ft.Text(f"Cuota {c.cuota_actual} de {c.cantidad_cuotas}", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(f"Restantes: {c.cuotas_restantes}", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(f"Cuota: {c.monto_cuota.formatted()}", size=12, color=theme.TEXT_SECONDARY),
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

    def pagar_cuota(cuota_id: int):
        tarjeta_service.pagar_cuota(cuota_id)
        refrescar_tarjetas()

    def eliminar_compra(compra_id: int):
        tarjeta_service.eliminar_compra(compra_id)
        refrescar_tarjetas()

    def nueva_tarjeta(_e=None):
        nombre_f = ft.TextField(label="Nombre (ej: Visa Galicia)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        banco_f = ft.TextField(label="Banco", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        digitos_f = ft.TextField(label="Últimos 4 dígitos (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, max_length=4)
        moneda_dd = ft.Dropdown(label="Moneda", value=Moneda.ARS.value, options=[ft.dropdown.Option(m.value) for m in Moneda], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        color_elegido = {"value": theme.TARJETA_COLORES[0]}
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
            title=ft.Text("Nueva tarjeta"),
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
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Crear", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
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
        concepto_f = ft.TextField(label="Concepto", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        monto_f = ft.TextField(label="Monto total", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value="1", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cuota_inicial_f = ft.TextField(
            label="¿En qué cuota empezás?", value="1", filled=True, bgcolor=theme.SURFACE_ALT,
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER,
            helper="Si ya veniás pagando (ej: compraste hace 3 meses), poné en qué cuota estás ahora.",
        )
        categoria_dd = ft.Dropdown(label="Categoría", value=str(categorias[0].id) if categorias else None, options=[ft.dropdown.Option(str(c.id), c.nombre) for c in categorias], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                tarjeta_id = int(tarjeta_dd.value)
                tarjeta = next(t for t in tarjetas_disponibles if t.id == tarjeta_id)
                monto = Money.from_decimal((monto_f.value or "0").replace(",", "."), tarjeta.moneda)
                cantidad = int(cuotas_f.value or "1")
                cuota_inicial = int(cuota_inicial_f.value or "1")
                tarjeta_service.registrar_compra(
                    tarjeta_id, fecha_holder["value"], concepto_f.value or "", detalle_f.value or "",
                    monto, int(categoria_dd.value), cantidad, cuota_inicial,
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
                        concepto_f, detalle_f, monto_f, cuotas_f, cuota_inicial_f, categoria_dd, error_text,
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
            ft.Row([theme.secondary_button("Nueva tarjeta", nueva_tarjeta, icon=ft.Icons.ADD_CARD_ROUNDED), theme.primary_button("Nueva compra", nueva_compra, color=theme.TARJETAS_COLOR, icon=ft.Icons.ADD_SHOPPING_CART_ROUNDED)]),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar_tarjetas()

    return ft.Column(
        [header, ft.Container(height=12), tarjetas_row, ft.Container(height=16), ft.Divider(color=theme.BORDER), ft.Container(height=8), detalle_col],
        expand=True, spacing=0,
    )
