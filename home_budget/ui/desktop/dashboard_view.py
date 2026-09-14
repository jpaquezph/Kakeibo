from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.cambio import CambioDivisaService
from ...app.services.dashboard import DashboardService
from .. import theme
from . import components


_ICONO_ORIGEN = {
    "fijo": ("receipt_long_rounded", theme.MOVIMIENTOS_COLOR),
    "tarjeta": ("credit_card_rounded", theme.TARJETAS_COLOR),
    "prestamo": ("account_balance_rounded", theme.PRESTAMOS_COLOR),
}


def _construir_pagado_card(pagos) -> ft.Container:
    totales: dict[Moneda, Money] = {}
    for p in pagos:
        totales[p.monto.moneda] = totales.get(p.monto.moneda, Money.zero(p.monto.moneda)) + p.monto

    items = []
    for p in pagos[:10]:
        icono, color = _ICONO_ORIGEN.get(p.origen, ("check_circle_rounded", theme.TEXT_MUTED))
        items.append(
            ft.Row(
                [
                    ft.Icon(theme.to_icon(icono), size=15, color=color),
                    ft.Text(p.concepto, size=12, color=theme.TEXT_PRIMARY, expand=True),
                    ft.Text(p.monto.formatted(), size=12, weight=ft.FontWeight.W_600, color=color),
                ],
                spacing=8,
            )
        )

    totales_row = ft.Row(
        [ft.Text(f"Total {moneda.value}: {total.formatted()}", size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY) for moneda, total in totales.items()],
        spacing=16,
    ) if totales else ft.Container()

    return theme.card(
        ft.Column(
            [
                ft.Text("Pagado este mes", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                ft.Divider(height=1, color=theme.BORDER),
                *(items or [components.empty_state("Todavía no pagaste nada este mes.", "task_alt_rounded")]),
                totales_row,
            ],
            spacing=8,
        )
    )


def build_dashboard_view(page: ft.Page, dashboard_service: DashboardService, cambio_service: CambioDivisaService) -> ft.Control:
    root = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar():
        root.controls = _construir(dashboard_service.resumen())
        page.update()

    def _construir(resumen) -> list[ft.Control]:
        moneda_rows = []
        for r in resumen.por_moneda:
            if r.ingresos.cents == 0 and r.egresos.cents == 0:
                continue
            moneda_rows.append(
                ft.Column(
                    [
                        ft.Text(r.moneda.value, size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY),
                        ft.ResponsiveRow(
                            [
                                ft.Container(components.stat_card("Ingresos", r.ingresos, "trending_up_rounded", is_income=True), col=4),
                                ft.Container(components.stat_card("Egresos", r.egresos, "trending_down_rounded", is_income=False), col=4),
                                ft.Container(components.stat_card("Balance", r.balance, "account_balance_wallet_rounded", is_income=not r.balance.is_negative()), col=4),
                            ],
                            spacing=12,
                        ),
                    ],
                    spacing=8,
                )
            )

        if not moneda_rows:
            moneda_rows = [components.empty_state("Todavía no registraste movimientos.", "savings_rounded")]

        categoria_items = []
        for tc in resumen.por_categoria[:8]:
            categoria_items.append(
                ft.Row(
                    [
                        ft.Container(width=10, height=10, bgcolor=tc.color, border_radius=5),
                        ft.Text(tc.nombre, size=13, color=theme.TEXT_PRIMARY, expand=True),
                        ft.Text(f"{tc.total.formatted()} {tc.moneda.value}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ],
                    spacing=10,
                )
            )
        categoria_card = theme.card(
            ft.Column(
                [
                    ft.Text("Gastos por categoría", size=15, weight=ft.FontWeight.BOLD, color=theme.MOVIMIENTOS_COLOR),
                    ft.Divider(height=1, color=theme.BORDER),
                    *(categoria_items or [components.empty_state("Sin gastos registrados todavía.")]),
                ],
                spacing=10,
            )
        )

        tarjeta_items = []
        for tt in resumen.por_tarjeta:
            detalle_partes = []
            if tt.total_pendiente_un_pago.cents > 0:
                detalle_partes.append(f"1 pago: {tt.total_pendiente_un_pago.formatted()}")
            if tt.total_pendiente_cuotas.cents > 0:
                detalle_partes.append(f"cuotas: {tt.total_pendiente_cuotas.formatted()}")
            tarjeta_items.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=16, color=theme.TARJETAS_COLOR),
                                ft.Text(tt.nombre, size=13, color=theme.TEXT_PRIMARY, expand=True),
                                ft.Text(tt.total_pendiente.formatted(), size=13, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                            ],
                            spacing=10,
                        ),
                        ft.Column(
                            [ft.Text(parte, size=11, color=theme.TEXT_SECONDARY) for parte in detalle_partes],
                            spacing=1,
                        ),
                    ],
                    spacing=2,
                )
            )
        tarjetas_card = theme.card(
            ft.Column(
                [
                    ft.Text("Pendiente en tarjetas", size=15, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                    ft.Divider(height=1, color=theme.BORDER),
                    *(tarjeta_items or [components.empty_state("Sin cuotas pendientes.", "credit_card_rounded")]),
                ],
                spacing=10,
            )
        )

        prestamos_card = theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Préstamos pendientes", size=15, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR, expand=True),
                            components.category_chip(f"{resumen.prestamos_pendientes_cantidad} activo(s)", theme.PRESTAMOS_COLOR, "hourglass_top_rounded"),
                        ],
                    ),
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Row([ft.Text("ARS", size=13, color=theme.TEXT_SECONDARY, expand=True), ft.Text(resumen.prestamos_pendientes_ars.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)]),
                    ft.Row([ft.Text("USD", size=13, color=theme.TEXT_SECONDARY, expand=True), ft.Text(resumen.prestamos_pendientes_usd.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)]),
                ],
                spacing=10,
            )
        )

        cambio_card = theme.card(
            ft.Column(
                [
                    ft.Text("Compra / venta de dólares", size=15, weight=ft.FontWeight.BOLD, color=theme.CAMBIO_COLOR),
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Text("Registrá una operación de cambio: se descuenta de una moneda y se acredita en la otra.", size=12, color=theme.TEXT_SECONDARY),
                    theme.primary_button("Nueva operación", nueva_operacion_cambio, color=theme.CAMBIO_COLOR, icon=ft.Icons.CURRENCY_EXCHANGE_ROUNDED),
                ],
                spacing=10,
            )
        )

        pagado_card = _construir_pagado_card(resumen.pagado_este_mes)

        return [
            ft.Text("Resumen general", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=4),
            *moneda_rows,
            ft.Container(height=8),
            ft.ResponsiveRow(
                [
                    ft.Container(ft.Column([categoria_card, cambio_card], spacing=16), col=6),
                    ft.Container(
                        ft.Column([tarjetas_card, prestamos_card, pagado_card], spacing=16),
                        col=6,
                    ),
                ],
                spacing=16,
            ),
        ]

    def nueva_operacion_cambio(_e=None):
        operacion_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="comprar", label=ft.Text("Comprar USD"), icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED),
                ft.Segment(value="vender", label=ft.Text("Vender USD"), icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED),
            ],
            selected=["comprar"],
            allow_multiple_selection=False,
            allow_empty_selection=False,
        )

        fecha_holder = {"value": date.today()}
        fecha_text = ft.Text(fecha_holder["value"].strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                page.update()

        date_picker = ft.DatePicker(value=fecha_holder["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        cantidad_f = ft.TextField(label="Cantidad de USD", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cotizacion_f = ft.TextField(label="Cotización (ARS por USD 1)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def operacion_actual() -> str:
            return next(iter(operacion_selector.selected))

        def continuar(_e):
            try:
                cantidad_usd = Money.from_decimal((cantidad_f.value or "0").replace(",", "."), Moneda.USD)
                cotizacion = Decimal((cotizacion_f.value or "0").replace(",", "."))
                if cantidad_usd.cents <= 0:
                    raise ValueError("La cantidad debe ser mayor a cero")
                if cotizacion <= 0:
                    raise ValueError("La cotización debe ser mayor a cero")
            except (InvalidOperation, ValueError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return

            page.pop_dialog()
            confirmar_operacion(operacion_actual(), fecha_holder["value"], cantidad_usd, cotizacion)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Compra / venta de dólares"),
            content=ft.Container(
                ft.Column(
                    [
                        operacion_selector,
                        ft.Row([ft.Text("Fecha:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        cantidad_f, cotizacion_f, error_text,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Continuar", continuar, color=theme.CAMBIO_COLOR, icon=ft.Icons.ARROW_FORWARD_ROUNDED)],
        )
        page.show_dialog(dialog)

    def confirmar_operacion(operacion: str, fecha: date, cantidad_usd: Money, cotizacion: Decimal):
        total_ars = Money.from_decimal(cantidad_usd.amount * cotizacion, Moneda.ARS)
        if operacion == "comprar":
            mensaje = f"¿Confirmás comprar {cantidad_usd.formatted()} a {Money.from_decimal(cotizacion, Moneda.ARS).formatted()} cada uno?\n\nSe van a descontar {total_ars.formatted()} y se van a sumar {cantidad_usd.formatted()}."
        else:
            mensaje = f"¿Confirmás vender {cantidad_usd.formatted()} a {Money.from_decimal(cotizacion, Moneda.ARS).formatted()} cada uno?\n\nSe van a descontar {cantidad_usd.formatted()} y se van a sumar {total_ars.formatted()}."

        def confirmar(_e):
            if operacion == "comprar":
                cambio_service.comprar_dolares(fecha, cantidad_usd, cotizacion)
            else:
                cambio_service.vender_dolares(fecha, cantidad_usd, cotizacion)
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar operación"),
            content=ft.Text(mensaje),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, confirmar", confirmar, color=theme.CAMBIO_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    refrescar()
    return root
