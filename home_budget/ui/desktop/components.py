from __future__ import annotations

import math
from pathlib import Path

import flet as ft
import flet.canvas as cv

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


# Logo de la app (assets/ en la raiz del proyecto). Se pasa como bytes para no
# depender de como resuelve rutas de assets cada modo (flet run / flet build).
RUTA_ASSETS = Path(__file__).resolve().parents[3] / "assets"
_LOGO_OSCURO = (RUTA_ASSETS / "logo.png").read_bytes()        # ambar, para el tema oscuro
_LOGO_CLARO = (RUTA_ASSETS / "logo_claro.png").read_bytes()   # azul, para el tema claro


def logo(tamano: int = 32) -> ft.Image:
    # Se elige al construir: al cambiar de tema la interfaz se reconstruye y toma el otro.
    src = _LOGO_OSCURO if theme.MODO_OSCURO else _LOGO_CLARO
    return ft.Image(src=src, width=tamano, height=tamano, fit=ft.BoxFit.CONTAIN)


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


_DIAMETRO_TORTA = 170


def torta(porciones) -> ft.Control:
    """Torta dibujada en un canvas (esta version de Flet no trae PieChart).
    `porciones`: objetos con nombre, color, total (Money) y porcentaje (0-100).
    Las porciones arrancan arriba y siguen en sentido horario, de mayor a
    menor; una linea del color de la tarjeta separa cada porcion."""
    radio = _DIAMETRO_TORTA / 2
    formas = []
    angulo = -math.pi / 2
    limites = []
    for p in porciones:
        barrido = 2 * math.pi * p.porcentaje / 100
        formas.append(cv.Arc(
            0, 0, _DIAMETRO_TORTA, _DIAMETRO_TORTA, start_angle=angulo, sweep_angle=barrido,
            use_center=True, paint=ft.Paint(color=p.color, style=ft.PaintingStyle.FILL),
        ))
        limites.append(angulo)
        angulo += barrido
    if len(porciones) > 1:
        separador = ft.Paint(color=theme.SURFACE, stroke_width=2, style=ft.PaintingStyle.STROKE)
        for a in limites:
            formas.append(cv.Line(radio, radio, radio + radio * math.cos(a), radio + radio * math.sin(a), paint=separador))
    return cv.Canvas(formas, width=_DIAMETRO_TORTA, height=_DIAMETRO_TORTA)


def leyenda_torta(porciones) -> ft.Control:
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=p.color, border_radius=5),
                    ft.Text(p.nombre, size=13, color=theme.TEXT_PRIMARY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{p.porcentaje:.1f}%", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, width=52, text_align=ft.TextAlign.RIGHT),
                    ft.Text(p.total.formatted(), size=12, color=theme.TEXT_SECONDARY, width=110, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=10,
            )
            for p in porciones
        ],
        spacing=8,
        expand=True,
    )
