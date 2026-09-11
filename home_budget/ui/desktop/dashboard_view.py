from __future__ import annotations

import flet as ft

from ...app.domain.money import Moneda
from ...app.services.dashboard import DashboardService
from .. import theme
from . import components


def build_dashboard_view(page: ft.Page, dashboard_service: DashboardService) -> ft.Control:
    resumen = dashboard_service.resumen()

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
            ft.Row(
                [
                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=16, color=theme.TARJETAS_COLOR),
                    ft.Text(tt.nombre, size=13, color=theme.TEXT_PRIMARY, expand=True),
                    ft.Text("  •  ".join(detalle_partes), size=12, weight=ft.FontWeight.W_600, color=theme.TARJETAS_COLOR),
                ],
                spacing=10,
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
                ft.Text("Préstamos pendientes", size=15, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR),
                ft.Divider(height=1, color=theme.BORDER),
                ft.Row([ft.Text("ARS", size=13, color=theme.TEXT_SECONDARY, expand=True), ft.Text(resumen.prestamos_pendientes_ars.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)]),
                ft.Row([ft.Text("USD", size=13, color=theme.TEXT_SECONDARY, expand=True), ft.Text(resumen.prestamos_pendientes_usd.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)]),
            ],
            spacing=10,
        )
    )

    return ft.Column(
        [
            ft.Text("Resumen general", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=4),
            *moneda_rows,
            ft.Container(height=8),
            ft.ResponsiveRow(
                [
                    ft.Container(categoria_card, col=6),
                    ft.Container(
                        ft.Column([tarjetas_card, prestamos_card], spacing=16),
                        col=6,
                    ),
                ],
                spacing=16,
            ),
        ],
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
