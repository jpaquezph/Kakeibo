from __future__ import annotations

import flet as ft

from ...app.auth.service import AuthService
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.dashboard import DashboardService
from ...app.services.movimientos import MovimientoService
from ...app.services.prestamos import PrestamoService
from ...app.services.tarjetas import TarjetaService
from .. import theme
from .dashboard_view import build_dashboard_view
from .historial_view import build_historial_view
from .movimientos_view import build_movimientos_view
from .prestamos_view import build_prestamos_view
from .tarjetas_view import build_tarjetas_view

_SECTIONS = [
    ("dashboard", "space_dashboard_rounded", "Resumen", theme.DASHBOARD_COLOR, theme.DASHBOARD_BG),
    ("movimientos", "swap_vert_rounded", "Movimientos", theme.MOVIMIENTOS_COLOR, theme.MOVIMIENTOS_BG),
    ("tarjetas", "credit_card_rounded", "Tarjetas", theme.TARJETAS_COLOR, theme.TARJETAS_BG),
    ("prestamos", "account_balance_rounded", "Préstamos", theme.PRESTAMOS_COLOR, theme.PRESTAMOS_BG),
    ("historial", "history_rounded", "Historial", theme.HISTORIAL_COLOR, theme.HISTORIAL_BG),
]


def build_app_shell(page: ft.Page, conn, auth: AuthService, on_logout) -> ft.Control:
    categoria_repo = CategoriaRepository(conn)
    movimiento_service = MovimientoService(conn)
    tarjeta_service = TarjetaService(conn)
    prestamo_service = PrestamoService(conn)
    dashboard_service = DashboardService(conn)

    shell_container = ft.Container(expand=True)
    estado = {"seccion": "dashboard"}

    def contenido_para(seccion: str) -> ft.Control:
        if seccion == "movimientos":
            return build_movimientos_view(page, movimiento_service, categoria_repo)
        if seccion == "tarjetas":
            return build_tarjetas_view(page, tarjeta_service, categoria_repo)
        if seccion == "prestamos":
            return build_prestamos_view(page, prestamo_service)
        if seccion == "historial":
            return build_historial_view(page, movimiento_service, categoria_repo)
        return build_dashboard_view(page, dashboard_service)

    def cambiar_seccion(key: str):
        if auth.session is not None:
            auth.session.touch()
        estado["seccion"] = key
        shell_container.content = _build_layout(estado, cambiar_seccion, contenido_para, auth, salir)
        page.update()

    def salir(_e=None):
        auth.logout()
        on_logout()

    shell_container.content = _build_layout(estado, cambiar_seccion, contenido_para, auth, salir)
    return shell_container


def _build_layout(estado, cambiar_seccion, contenido_para, auth, salir) -> ft.Control:
    nav_items = [_nav_button(key, icon, label, color, bg, estado["seccion"] == key, cambiar_seccion) for key, icon, label, color, bg in _SECTIONS]

    sidebar = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon("savings_rounded", color=theme.DASHBOARD_COLOR, size=26),
                            ft.Text("Kakeibo", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                        ],
                        spacing=8,
                    ),
                    padding=theme.pad_only(left=20, top=24, bottom=24),
                ),
                *nav_items,
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([ft.Icon("account_circle_rounded", color=theme.TEXT_SECONDARY, size=18), ft.Text(auth.session.username, size=13, color=theme.TEXT_SECONDARY)], spacing=6),
                            ft.TextButton("Cerrar sesión", icon="logout_rounded", on_click=salir, style=ft.ButtonStyle(color=theme.EXPENSE_RED)),
                        ],
                        spacing=8,
                    ),
                    padding=theme.pad_only(left=20, bottom=20, right=8),
                ),
            ],
            spacing=2,
        ),
        width=230,
        bgcolor=theme.SURFACE,
        border=theme.border_right(1, theme.BORDER),
    )

    content_area = ft.Container(content=contenido_para(estado["seccion"]), expand=True, padding=28, bgcolor=theme.PAGE_BG)

    return ft.Row([sidebar, content_area], expand=True, spacing=0)


def _nav_button(key, icon, label, color, bg, is_active, on_click):
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=color if is_active else theme.TEXT_MUTED, size=18),
                ft.Text(label, size=14, color=color if is_active else theme.TEXT_SECONDARY, weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL),
            ],
            spacing=12,
        ),
        bgcolor=bg if is_active else None,
        padding=theme.pad(horizontal=20, vertical=12),
        margin=theme.margin_h(10),
        border_radius=theme.RADIUS_SM,
        on_click=lambda e, k=key: on_click(k),
        ink=True,
    )
