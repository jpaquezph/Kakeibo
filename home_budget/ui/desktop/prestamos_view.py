from __future__ import annotations

from datetime import date, datetime

import flet as ft

from ...app.domain.models import EstadoPrestamo
from ...app.domain.money import Money, Moneda
from ...app.services.prestamos import PrestamoService
from .. import theme
from . import components


def build_prestamos_view(page: ft.Page, prestamo_service: PrestamoService) -> ft.Control:
    lista_col = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar():
        prestamos = prestamo_service.listar()
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
                    lambda e, cid=proxima.id: pagar_cuota(cid),
                    color=theme.PRESTAMOS_COLOR,
                    icon="check_circle_outline_rounded",
                )
            )
        acciones.append(ft.IconButton(icon="delete_outline_rounded", icon_color=theme.EXPENSE_RED, icon_size=18, on_click=lambda e, pid=p.id: eliminar(pid)))

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
                            ft.Text(f"Cuotas: {p.cuotas_pagadas}/{p.cantidad_cuotas}", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(f"Pagado: {p.total_pagado.formatted()}", size=12, color=theme.INCOME_GREEN, weight=ft.FontWeight.W_600),
                            ft.Text(f"Pendiente: {p.total_pendiente.formatted()}", size=12, color=theme.EXPENSE_RED, weight=ft.FontWeight.W_600),
                        ],
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Row(acciones, alignment=ft.MainAxisAlignment.START),
                ],
                spacing=10,
            ),
            padding=18,
        )

    def pagar_cuota(cuota_id: int):
        prestamo_service.pagar_cuota(cuota_id)
        refrescar()

    def eliminar(prestamo_id: int):
        def confirmar(_e):
            prestamo_service.eliminar_prestamo(prestamo_id)
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar préstamo"),
            content=ft.Text("¿Seguro que querés eliminar este préstamo y todas sus cuotas?"),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon="delete_outline_rounded")],
        )
        page.show_dialog(dialog)

    def nuevo_prestamo(_e=None):
        fecha_holder = {"value": date.today()}
        fecha_text = ft.Text(fecha_holder["value"].strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                page.update()

        date_picker = ft.DatePicker(value=fecha_holder["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        nombre_f = ft.TextField(label="Nombre del préstamo", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        monto_f = ft.TextField(label="Monto original", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        moneda_dd = ft.Dropdown(label="Moneda", value=Moneda.ARS.value, options=[ft.dropdown.Option(m.value) for m in Moneda], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value="12", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                monto = Money.from_decimal((monto_f.value or "0").replace(",", "."), moneda_dd.value)
                cantidad = int(cuotas_f.value or "1")
                prestamo_service.registrar_prestamo(nombre_f.value or "", detalle_f.value or "", monto, cantidad, fecha_holder["value"])
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nuevo préstamo"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Row([ft.Text("Fecha de inicio:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon="calendar_month_rounded", on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        nombre_f, detalle_f, monto_f, moneda_dd, cuotas_f, error_text,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Registrar préstamo", guardar, color=theme.PRESTAMOS_COLOR, icon="check_rounded")],
        )
        page.show_dialog(dialog)

    header = ft.Row(
        [
            ft.Text("Préstamos", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            theme.primary_button("Nuevo préstamo", nuevo_prestamo, color=theme.PRESTAMOS_COLOR, icon="add_rounded"),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar()

    return ft.Column([header, ft.Container(height=12), lista_col], expand=True, spacing=0)
