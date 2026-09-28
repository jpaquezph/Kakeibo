"""Tarjeta "Usuario" de Configuracion: imagen/color de perfil, nombre,
contrasena y PIN de desbloqueo por inactividad."""
from __future__ import annotations

import asyncio
import os
from typing import Callable

import flet as ft

from ...app.auth.avatar import MAX_BYTES, MAX_LADO_PX, ImagenInvalidaError
from ...app.auth.service import AuthError, AuthService
from .. import theme
from . import components
from .dialogos_windows import elegir_imagen


def _campo(label: str, **kwargs) -> ft.TextField:
    return ft.TextField(
        label=label, filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER, focused_border_color=theme.CONFIG_COLOR, **kwargs,
    )


def _campo_pin(label: str) -> ft.TextField:
    return _campo(
        label, password=True, can_reveal_password=True, max_length=4,
        input_filter=ft.NumbersOnlyInputFilter(), keyboard_type=ft.KeyboardType.NUMBER,
    )


def _titulo_bloque(texto: str) -> ft.Text:
    return ft.Text(texto, size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)


def build_usuario_card(page: ft.Page, auth: AuthService, on_perfil_cambiado: Callable[[str], None]) -> ft.Control:
    """`on_perfil_cambiado(mensaje)` reconstruye la app (la barra lateral
    muestra nombre y avatar) y avisa el resultado."""
    usuario_id = auth.session.usuario_id
    perfil = auth.obtener_perfil(usuario_id)

    # --- Imagen / color de perfil ---
    error_imagen = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

    def mostrar_error_imagen(mensaje: str):
        error_imagen.value = mensaje
        error_imagen.visible = True
        page.update()

    async def subir_imagen(_e=None):
        loop = asyncio.get_event_loop()
        ruta = await loop.run_in_executor(None, elegir_imagen)
        if not ruta:
            return
        try:
            # Se chequea el peso antes de leer, para no cargar en memoria un archivo enorme.
            if os.path.getsize(ruta) > MAX_BYTES:
                raise ImagenInvalidaError(f"La imagen pesa más de {MAX_BYTES // 1024 // 1024} MB")
            with open(ruta, "rb") as f:
                auth.cambiar_avatar_imagen(usuario_id, f.read())
        except (ImagenInvalidaError, OSError) as exc:
            mostrar_error_imagen(str(exc))
            return
        on_perfil_cambiado("Imagen de perfil actualizada")

    def quitar_imagen(_e=None):
        auth.cambiar_avatar_imagen(usuario_id, None)
        on_perfil_cambiado("Imagen de perfil quitada")

    def elegir_color(color: str):
        auth.cambiar_avatar_color(usuario_id, "" if color == components.AVATAR_COLOR_DEFECTO else color)
        on_perfil_cambiado("Color de perfil actualizado")

    color_actual = perfil.avatar_color or components.AVATAR_COLOR_DEFECTO
    muestras = ft.Row(
        [
            ft.Container(
                width=26, height=26, bgcolor=c, border_radius=13,
                border=theme.border_all(3, theme.TEXT_PRIMARY) if c == color_actual else None,
                on_click=lambda e, c=c: elegir_color(c), tooltip="Elegir este color",
            )
            for c in components.AVATAR_COLORES
        ],
        spacing=8, wrap=True,
    )

    bloque_imagen = ft.Row(
        [
            components.avatar(perfil, radio=36),
            ft.Column(
                [
                    _titulo_bloque("Imagen de perfil"),
                    ft.Row(
                        [
                            theme.secondary_button("Subir imagen", subir_imagen, icon=ft.Icons.UPLOAD_ROUNDED),
                            *([theme.secondary_button("Quitar imagen", quitar_imagen, icon=ft.Icons.DELETE_OUTLINE_ROUNDED)] if perfil.avatar_imagen else []),
                        ],
                        spacing=8, wrap=True,
                    ),
                    ft.Text(f"PNG o JPG, hasta {MAX_BYTES // 1024 // 1024} MB y {MAX_LADO_PX}x{MAX_LADO_PX} px.", size=11, color=theme.TEXT_MUTED),
                    error_imagen,
                    ft.Text("O elegí un color (se usa si no hay imagen):", size=12, color=theme.TEXT_SECONDARY),
                    muestras,
                ],
                spacing=8, expand=True,
            ),
        ],
        spacing=20, vertical_alignment=ft.CrossAxisAlignment.START,
    )

    # --- Nombre ---
    nombre_field = _campo("Nombre de usuario", value=perfil.username, expand=True)
    error_nombre = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

    def guardar_nombre(_e=None):
        try:
            auth.cambiar_nombre(usuario_id, nombre_field.value or "")
        except ValueError as exc:
            error_nombre.value = str(exc)
            error_nombre.visible = True
            page.update()
            return
        on_perfil_cambiado("Nombre actualizado")

    nombre_field.on_submit = guardar_nombre
    bloque_nombre = ft.Column(
        [
            _titulo_bloque("Nombre"),
            ft.Row([nombre_field, theme.primary_button("Guardar", guardar_nombre, color=theme.CONFIG_COLOR)], spacing=10),
            error_nombre,
        ],
        spacing=8,
    )

    # --- Contrasena ---
    def abrir_cambiar_password(_e=None):
        actual_f = _campo("Contraseña actual", password=True, can_reveal_password=True, autofocus=True)
        nueva_f = _campo("Nueva contraseña", password=True, can_reveal_password=True)
        confirmar_f = _campo("Confirmar nueva contraseña", password=True, can_reveal_password=True)
        error = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

        def guardar(_e2=None):
            if (nueva_f.value or "") != (confirmar_f.value or ""):
                error.value, error.visible = "Las contraseñas no coinciden", True
                page.update()
                return
            try:
                auth.cambiar_password(usuario_id, actual_f.value or "", nueva_f.value or "")
            except (AuthError, ValueError) as exc:
                error.value, error.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            on_perfil_cambiado("Contraseña actualizada")

        confirmar_f.on_submit = guardar
        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Cambiar contraseña"),
            content=ft.Container(ft.Column([actual_f, nueva_f, confirmar_f, error], spacing=12, tight=True), width=380),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Guardar", guardar, color=theme.CONFIG_COLOR),
            ],
        ))

    bloque_password = ft.Row(
        [
            ft.Column([_titulo_bloque("Contraseña"), ft.Text("Mínimo 6 caracteres.", size=12, color=theme.TEXT_SECONDARY)], spacing=2, expand=True),
            theme.secondary_button("Cambiar contraseña", abrir_cambiar_password, icon=ft.Icons.KEY_ROUNDED),
        ],
    )

    # --- PIN ---
    def abrir_configurar_pin(_e=None):
        password_f = _campo("Contraseña actual", password=True, can_reveal_password=True, autofocus=True)
        pin_f = _campo_pin("PIN (4 números)")
        confirmar_f = _campo_pin("Confirmar PIN")
        error = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

        def guardar(_e2=None):
            if (pin_f.value or "") != (confirmar_f.value or ""):
                error.value, error.visible = "Los PIN no coinciden", True
                page.update()
                return
            try:
                auth.establecer_pin(usuario_id, password_f.value or "", pin_f.value or "")
            except (AuthError, ValueError) as exc:
                error.value, error.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            on_perfil_cambiado("PIN guardado")

        confirmar_f.on_submit = guardar
        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Cambiar PIN" if perfil.tiene_pin else "Configurar PIN"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Con el PIN desbloqueás la app cuando se bloquea por inactividad. "
                                "Para iniciar sesión se sigue usando la contraseña.", size=12, color=theme.TEXT_SECONDARY),
                        password_f, pin_f, confirmar_f, error,
                    ],
                    spacing=12, tight=True,
                ),
                width=380,
            ),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Guardar", guardar, color=theme.CONFIG_COLOR),
            ],
        ))

    def quitar_pin(_e=None):
        password_f = _campo("Contraseña actual", password=True, can_reveal_password=True, autofocus=True)
        error = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

        def confirmar(_e2=None):
            try:
                auth.quitar_pin(usuario_id, password_f.value or "")
            except AuthError as exc:
                error.value, error.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            on_perfil_cambiado("PIN quitado: el desbloqueo vuelve a pedir la contraseña")

        password_f.on_submit = confirmar
        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Quitar PIN"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Ingresá tu contraseña para quitar el PIN. Después, el desbloqueo por inactividad "
                                "va a pedir la contraseña.", size=12, color=theme.TEXT_SECONDARY),
                        password_f, error,
                    ],
                    spacing=12, tight=True,
                ),
                width=380,
            ),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Quitar PIN", confirmar, color=theme.EXPENSE_RED),
            ],
        ))

    bloque_pin = ft.Row(
        [
            ft.Column(
                [
                    _titulo_bloque("PIN de desbloqueo"),
                    ft.Text(
                        "Activado: al volver de la inactividad se pide el PIN." if perfil.tiene_pin
                        else "Desactivado: al volver de la inactividad se pide la contraseña.",
                        size=12, color=theme.TEXT_SECONDARY,
                    ),
                ],
                spacing=2, expand=True,
            ),
            *([theme.secondary_button("Quitar PIN", quitar_pin, icon=ft.Icons.CLOSE_ROUNDED)] if perfil.tiene_pin else []),
            theme.secondary_button("Cambiar PIN" if perfil.tiene_pin else "Configurar PIN", abrir_configurar_pin, icon=ft.Icons.PIN_ROUNDED),
        ],
        spacing=8,
    )

    divisor = ft.Divider(height=1, color=theme.BORDER)
    return theme.card(
        ft.Column(
            [
                theme.section_pill("Usuario", theme.CONFIG_COLOR, theme.CONFIG_BG, icon="person_rounded"),
                bloque_imagen, divisor, bloque_nombre, divisor, bloque_password, divisor, bloque_pin,
            ],
            spacing=14,
        )
    )
