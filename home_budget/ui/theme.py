"""Paleta y helpers visuales compartidos por toda la interfaz de escritorio.

Filosofia: fondo calido (no blanco/gris puro), cada seccion con un color de
identidad propio, verde para ingresos, rojo para egresos, esquinas redondeadas
en todos los contenedores interactivos.
"""
from __future__ import annotations

import flet as ft

# Los colores que cambian entre modo claro y oscuro se definen en las dos
# paletas de abajo y se vuelcan como variables del modulo con aplicar_modo().
# Las vistas los leen como theme.X al construirse, asi que alcanza con
# reconstruir la interfaz despues de cambiar de modo.
_PALETA_CLARA = {
    # Fondo y superficies (calidos, no grises fríos)
    "PAGE_BG": "#FAF6EF",
    "SURFACE": "#FFFFFF",
    "SURFACE_ALT": "#F3EEE3",
    "BORDER": "#E7E0D2",
    # Tinta / texto
    "TEXT_PRIMARY": "#2B2620",
    "TEXT_SECONDARY": "#6F6656",
    "TEXT_MUTED": "#9C927E",
    # Semantica financiera (siempre acompanada de icono/texto, nunca solo color)
    "INCOME_GREEN": "#1E9E5A",
    "INCOME_GREEN_BG": "#E4F7EC",
    "EXPENSE_RED": "#E4483F",
    "EXPENSE_RED_BG": "#FCEAE8",
    # Identidad por seccion
    "DASHBOARD_COLOR": "#4A3AA7",    # violeta
    "DASHBOARD_BG": "#EFEAFB",
    "MOVIMIENTOS_COLOR": "#EB6834",  # naranja
    "MOVIMIENTOS_BG": "#FDEEE5",
    "TARJETAS_COLOR": "#D6467E",     # magenta
    "TARJETAS_BG": "#FBE7EF",
    "PRESTAMOS_COLOR": "#1BAF7A",    # verde azulado
    "PRESTAMOS_BG": "#E3F6EE",
    "HISTORIAL_COLOR": "#C98500",    # ambar
    "HISTORIAL_BG": "#FBF0DC",
    "CALENDARIO_COLOR": "#2A78D6",   # azul
    "CALENDARIO_BG": "#E8F1FC",
    "CAMBIO_COLOR": "#0E7C86",       # teal (compra/venta de dólares)
    "CAMBIO_BG": "#E3F5F6",
    "CONFIG_COLOR": "#546E7A",       # gris azulado (configuracion)
    "CONFIG_BG": "#ECEFF1",
    "INVERSIONES_COLOR": "#3F51B5",  # indigo
    "INVERSIONES_BG": "#E8EAF6",
    "COMPRAS_COLOR": "#00897B",      # verde azulado (compra mensual)
    "COMPRAS_BG": "#E0F2F1",
}

# Mismo criterio calido que el modo claro: marrones muy oscuros en vez de
# negro/gris puro, y los fondos de seccion como tintes oscuros de su color.
_PALETA_OSCURA = {
    "PAGE_BG": "#1C1A17",
    "SURFACE": "#26231F",
    "SURFACE_ALT": "#312D27",
    "BORDER": "#3D382F",
    "TEXT_PRIMARY": "#F2EDE4",
    "TEXT_SECONDARY": "#C2B8A6",
    "TEXT_MUTED": "#8F8574",
    "INCOME_GREEN": "#34B870",
    "INCOME_GREEN_BG": "#1B3326",
    "EXPENSE_RED": "#EF5F56",
    "EXPENSE_RED_BG": "#3A1F1D",
    "DASHBOARD_COLOR": "#7B6BE0",
    "DASHBOARD_BG": "#2C2744",
    "MOVIMIENTOS_COLOR": "#EB6834",
    "MOVIMIENTOS_BG": "#3A2A20",
    "TARJETAS_COLOR": "#E0588E",
    "TARJETAS_BG": "#3A2230",
    "PRESTAMOS_COLOR": "#1BAF7A",
    "PRESTAMOS_BG": "#1D3329",
    "HISTORIAL_COLOR": "#D99A1E",
    "HISTORIAL_BG": "#3A2F18",
    "CALENDARIO_COLOR": "#4A90E2",
    "CALENDARIO_BG": "#1E2C3F",
    "CAMBIO_COLOR": "#1A9AA5",
    "CAMBIO_BG": "#193234",
    "CONFIG_COLOR": "#90A4AE",
    "CONFIG_BG": "#2A3236",
    "INVERSIONES_COLOR": "#7986CB",
    "INVERSIONES_BG": "#252A45",
    "COMPRAS_COLOR": "#26A69A",
    "COMPRAS_BG": "#1B3330",
}

# Declarados para que el editor los reconozca; el valor lo pone aplicar_modo().
PAGE_BG: str
SURFACE: str
SURFACE_ALT: str
BORDER: str
TEXT_PRIMARY: str
TEXT_SECONDARY: str
TEXT_MUTED: str
INCOME_GREEN: str
INCOME_GREEN_BG: str
EXPENSE_RED: str
EXPENSE_RED_BG: str
DASHBOARD_COLOR: str
DASHBOARD_BG: str
MOVIMIENTOS_COLOR: str
MOVIMIENTOS_BG: str
TARJETAS_COLOR: str
TARJETAS_BG: str
PRESTAMOS_COLOR: str
PRESTAMOS_BG: str
HISTORIAL_COLOR: str
HISTORIAL_BG: str
CALENDARIO_COLOR: str
CALENDARIO_BG: str
CAMBIO_COLOR: str
CAMBIO_BG: str
CONFIG_COLOR: str
CONFIG_BG: str
INVERSIONES_COLOR: str
INVERSIONES_BG: str
COMPRAS_COLOR: str
COMPRAS_BG: str

MODO_OSCURO = False


def aplicar_modo(oscuro: bool) -> None:
    """Cambia la paleta activa. Hay que reconstruir las vistas despues."""
    global MODO_OSCURO
    MODO_OSCURO = oscuro
    globals().update(_PALETA_OSCURA if oscuro else _PALETA_CLARA)


aplicar_modo(False)

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
        color_scheme_seed=_PALETA_CLARA["DASHBOARD_COLOR"],
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


def card(content: ft.Control, color: str | None = None, bg: str | None = None, padding: int = 20) -> ft.Container:
    bg = bg or SURFACE
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


def primary_button(text: str, on_click, color: str | None = None, icon: str | None = None, width: int | None = None) -> ft.Button:
    color = color or DASHBOARD_COLOR
    return ft.Button(
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


def secondary_button(text: str, on_click, color: str | None = None, icon: str | None = None) -> ft.OutlinedButton:
    color = color or TEXT_SECONDARY
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


def dialogo(titulo: str, contenido: ft.Control, acciones: list, icono: str | None = None,
            color: str | None = None, ancho: int = 400) -> ft.AlertDialog:
    """Dialogo con la estetica de la app: titulo mediano con un icono de color,
    fondo de tarjeta y bordes redondeados (el AlertDialog por defecto de Flet
    trae un titulo grande y fondo tintado)."""
    color = color or DASHBOARD_COLOR
    cabecera = [ft.Text(titulo, size=17, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)]
    if icono:
        cabecera.insert(0, ft.Container(
            ft.Icon(to_icon(icono), size=18, color=color),
            bgcolor=ft.Colors.with_opacity(0.12, color), padding=8, border_radius=RADIUS_SM,
        ))
    return ft.AlertDialog(
        modal=True,
        title=ft.Row(cabecera, spacing=10),
        content=ft.Container(contenido, width=ancho),
        actions=acciones,
        bgcolor=SURFACE,
        shape=ft.RoundedRectangleBorder(radius=RADIUS),
        title_padding=ft.padding.Padding(left=24, top=22, right=24, bottom=4),
        content_padding=ft.padding.Padding(left=24, top=12, right=24, bottom=8),
        actions_padding=ft.padding.Padding(left=24, top=8, right=24, bottom=20),
    )
