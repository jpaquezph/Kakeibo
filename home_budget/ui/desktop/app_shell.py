from __future__ import annotations

import flet as ft

from ...app.auth.service import AuthService
from ...app.database import DEFAULT_DB_PATH
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.backup import crear_backup
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
        shell_container.content = _build_layout(estado, cambiar_seccion, contenido_para, auth, salir, hacer_backup)
        page.update()

    def salir(_e=None):
        auth.logout()
        on_logout()

    def hacer_backup(_e=None):
        try:
            destino = crear_backup(DEFAULT_DB_PATH, DEFAULT_DB_PATH.parent / "backups")
            icono, color, mensaje = "check_circle_rounded", theme.INCOME_GREEN, f"Backup creado con éxito en:\n{destino}"
        except Exception as exc:
            icono, color, mensaje = "error_rounded", theme.EXPENSE_RED, f"No se pudo crear el backup:\n{exc}"

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(theme.to_icon(icono), color=color), ft.Text("Backup")], spacing=8),
            content=ft.Text(mensaje, size=13, selectable=True),
            actions=[theme.primary_button("Aceptar", lambda e: page.pop_dialog(), color=theme.DASHBOARD_COLOR)],
        )
        page.show_dialog(dialog)

    shell_container.content = _build_layout(estado, cambiar_seccion, contenido_para, auth, salir, hacer_backup)
    return shell_container


def _build_layout(estado, cambiar_seccion, contenido_para, auth, salir, hacer_backup) -> ft.Control:
    nav_items = [_nav_button(key, icon, label, color, bg, estado["seccion"] == key, cambiar_seccion) for key, icon, label, color, bg in _SECTIONS]

    sidebar = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=theme.DASHBOARD_COLOR, size=26),
                            ft.Text("Kakeibo", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                        ],
                        spacing=8,
                    ),
                    padding=theme.pad_only(left=20, top=24, bottom=24),
                ),
                *nav_items,
                ft.Container(expand=True),
                ft.Container(
                    content=ft.TextButton(
                        "Hacer backup",
                        icon=ft.Icons.BACKUP_ROUNDED,
                        on_click=hacer_backup,
                        style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                    ),
                    padding=theme.pad_only(left=12, bottom=4, right=8),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, color=theme.TEXT_SECONDARY, size=18), ft.Text(auth.session.username, size=13, color=theme.TEXT_SECONDARY)], spacing=6),
                            ft.TextButton("Cerrar sesión", icon=ft.Icons.LOGOUT_ROUNDED, on_click=salir, style=ft.ButtonStyle(color=theme.EXPENSE_RED)),
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
                ft.Icon(theme.to_icon(icon), color=color if is_active else theme.TEXT_MUTED, size=18),
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
