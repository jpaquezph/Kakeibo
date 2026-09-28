from __future__ import annotations

import os

import flet as ft

from ...app.services.config import ConfigService
from ...app.services.logs import leer_log, ruta_log
from .. import theme


def build_configuracion_view(page: ft.Page, config_service: ConfigService) -> ft.Control:
    # config_service queda disponible para las proximas opciones de configuracion.
    return ft.Column(
        [
            ft.Text("Configuración", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=8),
            _registro_errores_card(page),
        ],
        expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
    )


def _registro_errores_card(page: ft.Page) -> ft.Control:
    contenido_f = ft.TextField(
        value="", read_only=True, multiline=True, min_lines=16, max_lines=16,
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        text_style=ft.TextStyle(font_family="monospace", size=11),
    )
    estado_texto = ft.Text("", size=11, color=theme.TEXT_MUTED, selectable=True)

    def refrescar_log(_e=None):
        contenido = leer_log()
        if contenido:
            contenido_f.value = contenido
            estado_texto.value = f"Archivo: {ruta_log()}"
        else:
            contenido_f.value = ""
            estado_texto.value = "Todavía no se registró ningún error. Buenas noticias."
        if _e is not None:
            page.update()

    def abrir_carpeta(_e=None):
        try:
            os.startfile(ruta_log().parent)  # noqa: S606 (accion explicita del usuario, solo Windows)
        except OSError as exc:
            estado_texto.value = f"No se pudo abrir la carpeta: {exc}"
            page.update()

    refrescar_log()

    return theme.card(
        ft.Column(
            [
                ft.Row(
                    [
                        theme.section_pill("Registro de errores", theme.CONFIG_COLOR, theme.CONFIG_BG, icon="description_outlined"),
                        ft.Row(
                            [
                                theme.secondary_button("Actualizar", refrescar_log, icon=ft.Icons.REFRESH_ROUNDED),
                                theme.secondary_button("Abrir carpeta", abrir_carpeta, icon=ft.Icons.FOLDER_OPEN_ROUNDED),
                            ],
                            spacing=8,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(
                    "Si algo falló, acá vas a encontrar el detalle técnico para pasarle a un "
                    "administrador o soporte. Se guarda solo en tu PC, no se envía a ningún lado.",
                    size=12, color=theme.TEXT_SECONDARY,
                ),
                contenido_f,
                estado_texto,
            ],
            spacing=10,
        )
    )
