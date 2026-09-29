from __future__ import annotations

import os
from typing import Callable

import flet as ft

from ...app.auth.service import AuthService
from ...app.services import inicio_windows
from ...app.services.config import ConfigService
from ...app.services.logs import ruta_log, ultimo_error
from .. import theme
from .usuario_config import build_usuario_seccion

# Secciones desplegadas. Vive a nivel de modulo para que sobreviva a las
# reconstrucciones de la vista (ej: al cambiar el nombre o el tema).
_expandidas: set[str] = set()


def build_configuracion_view(
    page: ft.Page,
    config_service: ConfigService,
    auth: AuthService,
    on_cambiar_tema: Callable[[bool], None],
    on_perfil_cambiado: Callable[[str], None],
) -> ft.Control:
    # config_service queda disponible para las proximas opciones de configuracion.
    return ft.Column(
        [
            ft.Text("Configuración", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=8),
            _seccion(page, "usuario", "Usuario", "person_rounded", build_usuario_seccion(page, auth, on_perfil_cambiado)),
            ft.Container(height=14),
            _seccion(page, "apariencia", "Apariencia", "palette_outlined", _apariencia(on_cambiar_tema)),
            ft.Container(height=14),
            _seccion(page, "general", "General", "settings_outlined", _general(page)),
            ft.Container(height=14),
            _seccion(page, "errores", "Registro de errores", "description_outlined", _registro_errores(page)),
        ],
        expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
    )


def _seccion(page: ft.Page, clave: str, titulo: str, icono: str, cuerpo: ft.Control) -> ft.Control:
    """Tarjeta plegable: arranca minimizada (solo el titulo) y se despliega
    o pliega tocando el encabezado."""
    abierta = clave in _expandidas
    cuerpo.visible = abierta
    flecha = ft.Icon(ft.Icons.EXPAND_LESS_ROUNDED if abierta else ft.Icons.EXPAND_MORE_ROUNDED, color=theme.TEXT_SECONDARY)

    def alternar(_e):
        if clave in _expandidas:
            _expandidas.discard(clave)
        else:
            _expandidas.add(clave)
        cuerpo.visible = clave in _expandidas
        flecha.icon = ft.Icons.EXPAND_LESS_ROUNDED if cuerpo.visible else ft.Icons.EXPAND_MORE_ROUNDED
        page.update()

    encabezado = ft.Container(
        content=ft.Row(
            [theme.section_pill(titulo, theme.CONFIG_COLOR, theme.CONFIG_BG, icon=icono), flecha],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        on_click=alternar,
        border_radius=theme.RADIUS_SM,
        tooltip="Mostrar u ocultar",
    )
    return theme.card(ft.Column([encabezado, cuerpo], spacing=14))


def _apariencia(on_cambiar_tema: Callable[[bool], None]) -> ft.Control:
    return ft.Row(
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
    )


def _general(page: ft.Page) -> ft.Control:
    exe = inicio_windows.ruta_ejecutable()
    error_texto = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

    def cambiar(e):
        try:
            if e.control.value:
                inicio_windows.activar(exe)
            else:
                inicio_windows.desactivar()
            error_texto.visible = False
        except (OSError, ValueError) as exc:
            e.control.value = inicio_windows.esta_activado()
            error_texto.value = f"No se pudo cambiar: {exc}"
            error_texto.visible = True
        page.update()

    descripcion = (
        "Kakeibo se abre solo al prender la computadora e iniciar sesión en Windows."
        if exe is not None
        else "Disponible solo en la app instalada (ahora se está ejecutando desde el código)."
    )
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Iniciar con Windows", size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                            ft.Text(descripcion, size=12, color=theme.TEXT_SECONDARY),
                        ],
                        spacing=2, expand=True,
                    ),
                    ft.Switch(
                        value=exe is not None and inicio_windows.esta_activado(),
                        active_color=theme.CONFIG_COLOR,
                        disabled=exe is None,
                        on_change=cambiar,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            error_texto,
        ],
        spacing=6,
    )


def _registro_errores(page: ft.Page) -> ft.Control:
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

    return ft.Column(
        [
            ft.Text(
                "Si algo falló, en la carpeta está el archivo con el detalle técnico para pasarle a un "
                "administrador o soporte. Se guarda solo en tu PC, no se envía a ningún lado.",
                size=12, color=theme.TEXT_SECONDARY,
            ),
            ft.Row([icono, estado_texto], spacing=6),
            ft.Row(
                [
                    theme.secondary_button("Actualizar", refrescar, icon=ft.Icons.REFRESH_ROUNDED),
                    theme.secondary_button("Abrir carpeta", abrir_carpeta, icon=ft.Icons.FOLDER_OPEN_ROUNDED),
                ],
                spacing=8,
            ),
        ],
        spacing=10,
    )
