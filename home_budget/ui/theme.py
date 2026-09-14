"""Paleta y helpers visuales compartidos por toda la interfaz de escritorio.

Filosofia: fondo calido (no blanco/gris puro), cada seccion con un color de
identidad propio, verde para ingresos, rojo para egresos, esquinas redondeadas
en todos los contenedores interactivos.
"""
from __future__ import annotations

import flet as ft

# Fondo y superficies (calidos, no grises fríos)
PAGE_BG = "#FAF6EF"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F3EEE3"
BORDER = "#E7E0D2"

# Tinta / texto
TEXT_PRIMARY = "#2B2620"
TEXT_SECONDARY = "#6F6656"
TEXT_MUTED = "#9C927E"

# Semantica financiera (siempre acompanada de icono/texto, nunca solo color)
INCOME_GREEN = "#1E9E5A"
INCOME_GREEN_BG = "#E4F7EC"
EXPENSE_RED = "#E4483F"
EXPENSE_RED_BG = "#FCEAE8"

# Identidad por seccion
DASHBOARD_COLOR = "#4A3AA7"   # violeta
DASHBOARD_BG = "#EFEAFB"
MOVIMIENTOS_COLOR = "#EB6834"  # naranja
MOVIMIENTOS_BG = "#FDEEE5"
TARJETAS_COLOR = "#D6467E"     # magenta
TARJETAS_BG = "#FBE7EF"
PRESTAMOS_COLOR = "#1BAF7A"    # verde azulado
PRESTAMOS_BG = "#E3F6EE"
HISTORIAL_COLOR = "#C98500"    # ambar
HISTORIAL_BG = "#FBF0DC"
CALENDARIO_COLOR = "#2A78D6"   # azul
CALENDARIO_BG = "#E8F1FC"
CAMBIO_COLOR = "#0E7C86"       # teal (compra/venta de dólares)
CAMBIO_BG = "#E3F5F6"

RADIUS = 16
RADIUS_SM = 10
RADIUS_LG = 24

# Paleta de colores a elegir para identificar tarjetas visualmente
TARJETA_COLORES = ["#D6467E", "#2A78D6", "#EB6834", "#16A34A", "#7C4DFF", "#E34948", "#1BAF7A", "#EDA100"]


def darken(hex_color: str, factor: float = 0.65) -> str:
    """Oscurece un color hexadecimal (0 < factor < 1) para usar como par en gradientes."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


def app_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=DASHBOARD_COLOR,
        font_family="Segoe UI",
        use_material3=True,
    )


def to_icon(name):
    """Convierte un nombre de icono en snake_case (ej: 'savings_rounded') al
    miembro real de ft.Icons. Los strings sueltos no se renderizan en esta
    version de Flet y rompen el layout completo del contenedor padre."""
    if not isinstance(name, str):
        return name
    return getattr(ft.Icons, name.upper(), ft.Icons.CIRCLE)


def pad(horizontal: int = 0, vertical: int = 0) -> ft.padding.Padding:
    return ft.padding.Padding(left=horizontal, right=horizontal, top=vertical, bottom=vertical)


def pad_only(left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> ft.padding.Padding:
    return ft.padding.Padding(left=left, top=top, right=right, bottom=bottom)


def margin_h(horizontal: int = 0) -> ft.margin.Margin:
    return ft.margin.Margin(left=horizontal, right=horizontal, top=0, bottom=0)


def margin_only(bottom: int = 0) -> ft.margin.Margin:
    return ft.margin.Margin(left=0, top=0, right=0, bottom=bottom)


def border_all(width: int, color: str) -> ft.border.Border:
    side = ft.border.BorderSide(width, color)
    return ft.border.Border(left=side, top=side, right=side, bottom=side)


def border_right(width: int, color: str) -> ft.border.Border:
    return ft.border.Border(right=ft.border.BorderSide(width, color))


def card(content: ft.Control, color: str | None = None, bg: str = SURFACE, padding: int = 20) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=bg,
        padding=padding,
        border_radius=RADIUS,
        border=border_all(1, BORDER) if bg == SURFACE else None,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=14,
            color=ft.Colors.with_opacity(0.06, "#000000"),
            offset=ft.Offset(0, 4),
        ) if bg == SURFACE else None,
    )


def section_pill(text: str, color: str, bg: str, icon: str | None = None) -> ft.Container:
    row_controls = []
    if icon:
        row_controls.append(ft.Icon(to_icon(icon), color=color, size=16))
    row_controls.append(ft.Text(text, color=color, weight=ft.FontWeight.W_600, size=12))
    return ft.Container(
        content=ft.Row(row_controls, spacing=4, tight=True),
        bgcolor=bg,
        padding=pad(horizontal=10, vertical=5),
        border_radius=RADIUS_LG,
    )


def primary_button(text: str, on_click, color: str = DASHBOARD_COLOR, icon: str | None = None, width: int | None = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        content=text,
        icon=to_icon(icon),
        icon_color="#FFFFFF",
        color="#FFFFFF",
        bgcolor=color,
        on_click=on_click,
        width=width,
        elevation=0,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=RADIUS_SM),
            padding=pad(horizontal=20, vertical=14),
        ),
    )


def secondary_button(text: str, on_click, color: str = TEXT_SECONDARY, icon: str | None = None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=text,
        icon=to_icon(icon),
        icon_color=color,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=color,
            side=ft.BorderSide(1, BORDER),
            shape=ft.RoundedRectangleBorder(radius=RADIUS_SM),
            padding=pad(horizontal=18, vertical=14),
        ),
    )


def money_text(formatted: str, is_income: bool, size: int = 22) -> ft.Text:
    return ft.Text(
        formatted,
        size=size,
        weight=ft.FontWeight.BOLD,
        color=INCOME_GREEN if is_income else EXPENSE_RED,
    )
