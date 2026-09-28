from __future__ import annotations

import os
from typing import Callable

import flet as ft

from ...app.services.config import ConfigService
from ...app.services.logs import ruta_log, ultimo_error
from .. import theme


def build_configuracion_view(
    page: ft.Page,
    config_service: ConfigService,
    on_cambiar_tema: Callable[[bool], None],
) -> ft.Control:
    # config_service queda disponible para las proximas opciones de configuracion.
    return ft.Column(
        [
            ft.Text("Configuración", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=8),
            _apariencia_card(on_cambiar_tema),
            ft.Container(height=14),
            _registro_errores_card(page),
        ],
        expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
    )


def _apariencia_card(on_cambiar_tema: Callable[[bool], None]) -> ft.Control:
    return theme.card(
        ft.Column(
            [
                theme.section_pill("Apariencia", theme.CONFIG_COLOR, theme.CONFIG_BG, icon="palette_outlined"),
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Modo oscuro", size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                                ft.Text("Cambia los colores de toda la app a un tema oscuro.", size=12, color=theme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                        ),
                        ft.Switch(
                            value=theme.MODO_OSCURO,
                            active_color=theme.CONFIG_COLOR,
                            on_change=lambda e: on_cambiar_tema(e.control.value),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
        )
    )


def _registro_errores_card(page: ft.Page) -> ft.Control:
    icono = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=14)
    estado_texto = ft.Text("", size=12, selectable=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS, expand=True)

    def refrescar(_e=None):
        error = ultimo_error()
        if error:
            icono.icon, icono.color = ft.Icons.ERROR_OUTLINE_ROUNDED, theme.EXPENSE_RED
            estado_texto.value, estado_texto.color = f"Último error: {error}", theme.EXPENSE_RED
        else:
            icono.icon, icono.color = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, theme.INCOME_GREEN
            estado_texto.value, estado_texto.color = "Sin errores registrados.", theme.TEXT_MUTED
        if _e is not None:
            page.update()

    def abrir_carpeta(_e=None):
        try:
            os.startfile(ruta_log().parent)  # noqa: S606 (accion explicita del usuario, solo Windows)
        except OSError as exc:
            estado_texto.value = f"No se pudo abrir la carpeta: {exc}"
            page.update()

    refrescar()

    return theme.card(
        ft.Column(
            [
                ft.Row(
                    [
                        theme.section_pill("Registro de errores", theme.CONFIG_COLOR, theme.CONFIG_BG, icon="description_outlined"),
                        ft.Row(
                            [
                                theme.secondary_button("Actualizar", refrescar, icon=ft.Icons.REFRESH_ROUNDED),
                                theme.secondary_button("Abrir carpeta", abrir_carpeta, icon=ft.Icons.FOLDER_OPEN_ROUNDED),
                            ],
                            spacing=8,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(
                    "Si algo falló, en la carpeta está el archivo con el detalle técnico para pasarle a un "
                    "administrador o soporte. Se guarda solo en tu PC, no se envía a ningún lado.",
                    size=12, color=theme.TEXT_SECONDARY,
                ),
                ft.Row([icono, estado_texto], spacing=6),
            ],
            spacing=10,
        )
    )
