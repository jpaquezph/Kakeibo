"""Aviso (abajo a la derecha) con los vencimientos pendientes del mes en
curso. Aparece al abrir la app y solo se cierra con la cruz. Minimizado
queda solo el titulo, en una franja propia que no tapa el contenido."""
from __future__ import annotations

from datetime import date
from typing import Callable

import flet as ft

from ...app.services.vencimientos import Vencimiento
from .. import theme

_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_ICONO_ORIGEN = {
    "tarjeta": "credit_card_rounded",
    "prestamo": "account_balance_rounded",
    "fijo": "receipt_long_rounded",
}
_ANCHO = 360
_ALTO_MAXIMO_LISTA = 320


def _fila(v: Vencimiento, hoy: date) -> ft.Control:
    vencido = v.fecha < hoy
    es_hoy = v.fecha == hoy
    color_fecha = theme.EXPENSE_RED if vencido else (theme.HISTORIAL_COLOR if es_hoy else theme.TEXT_SECONDARY)
    etiqueta = v.etiqueta + (" · vencido" if vencido else " · vence hoy" if es_hoy else "")
    return ft.Row(
        [
            ft.Container(
                ft.Text(v.fecha.strftime("%d/%m"), size=12, weight=ft.FontWeight.BOLD, color=color_fecha),
                bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=theme.pad(horizontal=8, vertical=4),
            ),
            ft.Icon(theme.to_icon(_ICONO_ORIGEN.get(v.origen, "event_rounded")), size=16, color=theme.TEXT_MUTED),
            ft.Column(
                [
                    ft.Text(v.titulo, size=13, color=theme.TEXT_PRIMARY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(etiqueta, size=11, color=theme.EXPENSE_RED if vencido else theme.TEXT_MUTED),
                ],
                spacing=0, expand=True,
            ),
            ft.Text(f"{v.monto.formatted()} {v.monto.moneda.value}", size=12, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _titulo(hoy: date) -> str:
    return f"Vencimientos de {_MESES[hoy.month - 1]}"


def _boton(icono, tooltip: str, on_click: Callable[[], None]) -> ft.IconButton:
    return ft.IconButton(icon=icono, icon_size=18, icon_color=theme.TEXT_SECONDARY, tooltip=tooltip, on_click=lambda e: on_click())


def build_aviso_vencimientos(
    vencimientos: list[Vencimiento], hoy: date, on_cerrar: Callable[[], None], on_minimizar: Callable[[], None]
) -> ft.Control:
    lista = ft.Column([_fila(v, hoy) for v in vencimientos], spacing=10, scroll=ft.ScrollMode.AUTO)
    # Alto fijo solo si la lista no entra: asi con pocos vencimientos el aviso queda compacto.
    alto_estimado = len(vencimientos) * 44
    contenedor_lista = ft.Container(lista, height=_ALTO_MAXIMO_LISTA if alto_estimado > _ALTO_MAXIMO_LISTA else None)

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, size=18, color=theme.CALENDARIO_COLOR),
                        ft.Text(_titulo(hoy), size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                        _boton(ft.Icons.REMOVE_ROUNDED, "Minimizar", on_minimizar),
                        _boton(ft.Icons.CLOSE_ROUNDED, "Cerrar", on_cerrar),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(f"{len(vencimientos)} pendiente(s) de pago este mes", size=12, color=theme.TEXT_SECONDARY),
                ft.Divider(height=1, color=theme.BORDER),
                contenedor_lista,
            ],
            spacing=8,
            tight=True,
        ),
        width=_ANCHO,
        bgcolor=theme.SURFACE,
        border=theme.border_all(1, theme.BORDER),
        border_radius=theme.RADIUS,
        padding=theme.pad_only(left=16, top=8, right=8, bottom=16),
        shadow=ft.BoxShadow(blur_radius=24, color=ft.Colors.with_opacity(0.18, "#000000"), offset=ft.Offset(0, 6)),
        right=24,
        bottom=24,
    )


def build_aviso_minimizado(
    cantidad: int, hoy: date, on_expandir: Callable[[], None], on_cerrar: Callable[[], None]
) -> ft.Control:
    """Solo el titulo; tocandolo se vuelve a expandir."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, size=16, color=theme.CALENDARIO_COLOR),
                ft.Text(f"{_titulo(hoy)} ({cantidad})", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                _boton(ft.Icons.OPEN_IN_FULL_ROUNDED, "Expandir", on_expandir),
                _boton(ft.Icons.CLOSE_ROUNDED, "Cerrar", on_cerrar),
            ],
            spacing=4, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE,
        border=theme.border_all(1, theme.BORDER),
        border_radius=theme.RADIUS_SM,
        padding=theme.pad_only(left=12, right=4),
        on_click=lambda e: on_expandir(),
    )
