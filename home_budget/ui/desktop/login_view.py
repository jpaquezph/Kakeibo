from __future__ import annotations

import flet as ft

from ...app.auth.service import AuthError, AuthService
from .. import theme


def build_login_view(page: ft.Page, auth: AuthService, on_success) -> ft.Control:
    primer_uso = not auth.hay_usuarios()

    titulo = ft.Text(
        "Bienvenido a Kakeibo" if primer_uso else "Hola de nuevo",
        size=26,
        weight=ft.FontWeight.BOLD,
        color=theme.TEXT_PRIMARY,
    )
    subtitulo = ft.Text(
        "Creá tu usuario para empezar a llevar tus cuentas." if primer_uso
        else "Ingresá tus credenciales para ver tus finanzas.",
        size=14,
        color=theme.TEXT_SECONDARY,
    )

    username_field = ft.TextField(
        label="Usuario",
        autofocus=True,
        border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER,
        focused_border_color=theme.DASHBOARD_COLOR,
        filled=True,
        bgcolor=theme.SURFACE_ALT,
    )
    password_field = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER,
        focused_border_color=theme.DASHBOARD_COLOR,
        filled=True,
        bgcolor=theme.SURFACE_ALT,
    )
    confirm_field = ft.TextField(
        label="Confirmar contraseña",
        password=True,
        can_reveal_password=True,
        border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER,
        focused_border_color=theme.DASHBOARD_COLOR,
        filled=True,
        bgcolor=theme.SURFACE_ALT,
        visible=primer_uso,
    )
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def mostrar_error(mensaje: str) -> None:
        error_text.value = mensaje
        error_text.visible = True
        page.update()

    def submit(_e=None):
        error_text.visible = False
        username = username_field.value or ""
        password = password_field.value or ""

        try:
            if primer_uso:
                if password != (confirm_field.value or ""):
                    mostrar_error("Las contraseñas no coinciden")
                    return
                auth.crear_usuario(username, password)
                session = auth.login(username, password)
            else:
                session = auth.login(username, password)
        except (AuthError, ValueError) as exc:
            mostrar_error(str(exc))
            return

        on_success(session)

    password_field.on_submit = submit
    confirm_field.on_submit = submit

    submit_btn = theme.primary_button(
        "Crear cuenta e ingresar" if primer_uso else "Ingresar",
        submit,
        color=theme.DASHBOARD_COLOR,
        icon=ft.Icons.LOCK_OPEN_ROUNDED,
        width=320,
    )

    card_content = ft.Column(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
                bgcolor=theme.DASHBOARD_BG,
                padding=16,
                border_radius=theme.RADIUS_LG,
            ),
            ft.Container(height=8),
            titulo,
            subtitulo,
            ft.Container(height=16),
            username_field,
            password_field,
            confirm_field,
            error_text,
            ft.Container(height=8),
            submit_btn,
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Container(
        content=ft.Row(
            [theme.card(card_content, padding=36)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
        bgcolor=theme.PAGE_BG,
    )


def build_lock_view(page: ft.Page, auth: AuthService, on_unlock) -> ft.Control:
    session = auth.session
    password_field = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        autofocus=True,
        border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER,
        focused_border_color=theme.DASHBOARD_COLOR,
        filled=True,
        bgcolor=theme.SURFACE_ALT,
        width=320,
    )
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def submit(_e=None):
        try:
            auth.login(session.username, password_field.value or "")
        except AuthError:
            error_text.value = "Contraseña incorrecta"
            error_text.visible = True
            page.update()
            return
        on_unlock()

    password_field.on_submit = submit

    card_content = ft.Column(
        [
            ft.Icon(ft.Icons.LOCK_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
            ft.Text("Sesión bloqueada por inactividad", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text(f"Ingresá tu contraseña para continuar, {session.username}.", size=13, color=theme.TEXT_SECONDARY),
            ft.Container(height=8),
            password_field,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Desbloquear", submit, color=theme.DASHBOARD_COLOR, icon=ft.Icons.LOCK_OPEN_ROUNDED, width=320),
        ],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        width=360,
    )

    return ft.Container(
        content=ft.Row([theme.card(card_content, padding=36)], alignment=ft.MainAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        expand=True,
        bgcolor=theme.PAGE_BG,
    )
