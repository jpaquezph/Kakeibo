"""Maqueta de la sincronizacion con la computadora. Todavia no cruza datos:
muestra como se va a ver el estado, el boton de sincronizar y el aviso que
sale cuando un cambio pisaria algo que se modifico en el otro dispositivo.
Los datos que se ven aca son de ejemplo."""
from __future__ import annotations

import flet as ft

from .. import theme
from . import componentes as mc


def build_sincronizacion_view(page: ft.Page, nav: mc.Navegacion) -> ft.Control:
    color = theme.CALENDARIO_COLOR

    def paso(numero: int, texto: str) -> ft.Row:
        return ft.Row(
            [
                ft.Container(ft.Text(str(numero), size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"), width=22, height=22,
                             bgcolor=color, border_radius=11, alignment=ft.Alignment.CENTER),
                ft.Text(texto, size=13, color=theme.TEXT_PRIMARY, expand=True),
            ],
            spacing=10, vertical_alignment=ft.CrossAxisAlignment.START,
        )

    return mc.pantalla([
        ft.Row([theme.section_pill("Maqueta: todavía no cruza datos", theme.HISTORIAL_COLOR, theme.HISTORIAL_BG, "construction_rounded")]),
        theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(ft.Icon(ft.Icons.COMPUTER_ROUNDED, size=22, color=color), bgcolor=theme.CALENDARIO_BG, padding=10,
                                         border_radius=theme.RADIUS_SM),
                            ft.Column(
                                [
                                    ft.Text("Computadora de casa", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                                    ft.Row([ft.Container(width=8, height=8, bgcolor=theme.INCOME_GREEN, border_radius=4),
                                            ft.Text("En la misma red Wi-Fi", size=12, color=theme.TEXT_SECONDARY)], spacing=6),
                                ],
                                spacing=2, expand=True,
                            ),
                        ],
                        spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    mc.separador(),
                    ft.Row([ft.Text("Última sincronización", size=13, color=theme.TEXT_SECONDARY, expand=True),
                            ft.Text("hoy, 10:42", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)]),
                    ft.Row([ft.Text("Cambios sin enviar", size=13, color=theme.TEXT_SECONDARY, expand=True),
                            ft.Text("3", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)]),
                    mc.boton_ancho("Sincronizar ahora", lambda e: nav.avisar("Maqueta: la sincronización todavía no está conectada."),
                                   color, ft.Icons.SYNC_ROUNDED),
                ],
                spacing=12,
            ),
            padding=16,
        ),
        theme.card(
            ft.Column(
                [
                    mc.titulo_tarjeta("Cómo va a funcionar", color),
                    paso(1, "Se vincula una sola vez: la computadora muestra un código y se carga acá."),
                    paso(2, "Cuando el celular y la computadora están en la misma red y con Kakeibo abierto, se cruzan los cambios solos."),
                    paso(3, "Lo que cargaste en uno aparece en el otro. Los datos no salen de tu red."),
                    paso(4, "Si un cambio pisaría algo que se modificó en el otro dispositivo, Kakeibo te avisa antes y vos decidís."),
                ],
                spacing=10,
            ),
            padding=16,
        ),
        ft.Row([theme.secondary_button("Ver el aviso de cambio pisado", lambda e: _aviso_de_ejemplo(page), color=color,
                                       icon=ft.Icons.WARNING_AMBER_ROUNDED)], alignment=ft.MainAxisAlignment.CENTER),
    ])


def _aviso_de_ejemplo(page: ft.Page) -> None:
    """El aviso que sale antes de pisar un dato que cambio en el otro
    dispositivo: que se modifico, cuando y con que informacion."""
    def version(titulo: str, cuando: str, datos: list[tuple[str, str, bool]], color: str, bg: str) -> ft.Container:
        return ft.Container(
            ft.Column(
                [
                    ft.Text(titulo, size=12, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(cuando, size=11, color=theme.TEXT_SECONDARY),
                    *[
                        ft.Row([ft.Text(campo, size=12, color=theme.TEXT_SECONDARY, width=64),
                                ft.Text(valor, size=13, color=theme.TEXT_PRIMARY, expand=True,
                                        weight=ft.FontWeight.BOLD if distinto else ft.FontWeight.NORMAL)], spacing=6)
                        for campo, valor, distinto in datos
                    ],
                ],
                spacing=3,
            ),
            bgcolor=bg, border_radius=theme.RADIUS_SM, padding=10,
        )

    contenido = ft.Column(
        [
            ft.Text("Estás por modificar un movimiento que ya se modificó en la computadora.", size=13, color=theme.TEXT_PRIMARY),
            version("En la computadora", "Modificado el 08/10/2026 a las 21:14",
                    [("Concepto", "Supermercado", False), ("Monto", "$ 45.200,00", True), ("Fecha", "05/10/2026", True)],
                    theme.CALENDARIO_COLOR, theme.CALENDARIO_BG),
            version("Tu cambio en este celular", "Modificado el 09/10/2026 a las 10:02",
                    [("Concepto", "Supermercado", False), ("Monto", "$ 48.900,00", True), ("Fecha", "06/10/2026", True)],
                    theme.MOVIMIENTOS_COLOR, theme.MOVIMIENTOS_BG),
            ft.Text("En negrita, lo que cambia. ¿Qué hacemos?", size=12, color=theme.TEXT_SECONDARY),
            mc.boton_ancho("Pisar con mi cambio", lambda e: page.pop_dialog(), theme.MOVIMIENTOS_COLOR, ft.Icons.EDIT_ROUNDED),
            mc.boton_ancho("Dejar el de la computadora", lambda e: page.pop_dialog(), theme.CALENDARIO_COLOR, ft.Icons.COMPUTER_ROUNDED),
        ],
        spacing=10, tight=True,
    )
    page.show_dialog(theme.dialogo(
        "Este dato ya cambió", contenido, [ft.TextButton("Decidir después", on_click=lambda e: page.pop_dialog())],
        icono="warning_amber_rounded", color=theme.HISTORIAL_COLOR, ancho=300,
    ))
