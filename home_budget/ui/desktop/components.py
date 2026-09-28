from __future__ import annotations

import flet as ft

from ...app.domain.money import Money
from .. import theme


def stat_card(title: str, value: Money, icon: str, is_income: bool | None = None) -> ft.Container:
    if is_income is None:
        color = theme.DASHBOARD_COLOR
        bg = theme.DASHBOARD_BG
    else:
        color = theme.INCOME_GREEN if is_income else theme.EXPENSE_RED
        bg = theme.INCOME_GREEN_BG if is_income else theme.EXPENSE_RED_BG

    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(theme.to_icon(icon), color=color, size=18),
                        bgcolor=bg,
                        padding=8,
                        border_radius=theme.RADIUS_SM,
                    ),
                    ft.Text(title, size=12, color=theme.TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                ],
                spacing=8,
            ),
            ft.Text(value.formatted(), size=20, weight=ft.FontWeight.BOLD, color=color),
        ],
        spacing=10,
    )
    return theme.card(content, padding=16)


def category_chip(nombre: str, color: str, icono: str) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [ft.Icon(theme.to_icon(icono), size=13, color=color), ft.Text(nombre, size=11, color=color, weight=ft.FontWeight.W_600)],
            spacing=4,
            tight=True,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        padding=theme.pad(horizontal=9, vertical=4),
        border_radius=theme.RADIUS_LG,
    )


def empty_state(mensaje: str, icon: str = "inbox_rounded") -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(theme.to_icon(icon), size=40, color=theme.TEXT_MUTED),
                ft.Text(mensaje, color=theme.TEXT_MUTED, size=13),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=40,
        alignment=ft.Alignment.CENTER,
    )


def movimiento_row(movimiento, on_edit=None, on_delete=None) -> ft.Container:
    es_ingreso = movimiento.tipo.value == "ingreso"
    signo = "+" if es_ingreso else "-"
    color = theme.INCOME_GREEN if es_ingreso else theme.EXPENSE_RED
    bg = theme.INCOME_GREEN_BG if es_ingreso else theme.EXPENSE_RED_BG

    fila = ft.Row(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED if es_ingreso else ft.Icons.ARROW_DOWNWARD_ROUNDED, color=color, size=16),
                bgcolor=bg,
                padding=10,
                border_radius=theme.RADIUS_SM,
            ),
            ft.Column(
                [
                    ft.Text(movimiento.concepto, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                    ft.Row(
                        [
                            category_chip(movimiento.categoria_nombre or "", movimiento.categoria_color or theme.TEXT_MUTED, movimiento.categoria_icono or "category"),
                            ft.Text(movimiento.fecha.strftime("%d/%m/%Y"), size=11, color=theme.TEXT_MUTED),
                            ft.Text("Fijo", size=10, color=theme.TEXT_MUTED, italic=True) if movimiento.fijo else ft.Container(),
                            ft.Text("Pendiente", size=10, color=theme.HISTORIAL_COLOR, italic=True) if movimiento.estado.value == "pendiente" else ft.Container(),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=4,
                expand=True,
            ),
            ft.Text(f"{signo} {movimiento.monto.formatted()}", size=15, weight=ft.FontWeight.BOLD, color=color),
            *([ft.IconButton(icon=ft.Icons.EDIT_ROUNDED, icon_size=16, icon_color=theme.TEXT_MUTED, on_click=lambda e: on_edit(movimiento))] if on_edit else []),
            *([ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=theme.EXPENSE_RED, on_click=lambda e: on_delete(movimiento))] if on_delete else []),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return ft.Container(
        content=fila,
        bgcolor=theme.SURFACE,
        padding=theme.pad(horizontal=16, vertical=10),
        border_radius=theme.RADIUS_SM,
        border=theme.border_all(1, theme.BORDER),
        margin=theme.margin_only(bottom=8),
    )


AVATAR_COLOR_DEFECTO = "#898781"  # gris
AVATAR_COLORES = [AVATAR_COLOR_DEFECTO, "#4A3AA7", "#2A78D6", "#0E7C86", "#1BAF7A", "#C98500", "#EB6834", "#D6467E"]


def avatar(perfil, radio: int = 14) -> ft.CircleAvatar:
    """Imagen de perfil del usuario, o su inicial sobre su color si no subio una."""
    inicial = (perfil.username[:1] or "?").upper()
    return ft.CircleAvatar(
        content=ft.Text(inicial, size=radio * 0.9, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
        foreground_image_src=perfil.avatar_imagen,
        bgcolor=perfil.avatar_color or AVATAR_COLOR_DEFECTO,
        radius=radio,
    )
