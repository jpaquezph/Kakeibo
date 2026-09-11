from __future__ import annotations

import flet as ft

from ...app.auth.service import PREGUNTAS_SECRETAS, AuthError, AuthService
from .. import theme


def build_login_view(page: ft.Page, auth: AuthService, on_success) -> ft.Control:
    primer_uso = not auth.hay_usuarios()
    tarjeta = ft.Container()
    shell = ft.Container(
        content=ft.Row([tarjeta], alignment=ft.MainAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        expand=True,
        bgcolor=theme.PAGE_BG,
    )

    def mostrar(contenido: ft.Control):
        tarjeta.content = theme.card(contenido, padding=36)
        page.update()

    if primer_uso:
        mostrar(_vista_signup(page, auth, on_success, mostrar))
    else:
        mostrar(_vista_login(page, auth, on_success, mostrar))

    return shell


def _campo(label, **kwargs) -> ft.TextField:
    return ft.TextField(
        label=label,
        border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER,
        focused_border_color=theme.DASHBOARD_COLOR,
        filled=True,
        bgcolor=theme.SURFACE_ALT,
        **kwargs,
    )


def _vista_signup(page, auth, on_success, mostrar) -> ft.Control:
    username_field = _campo("Usuario", autofocus=True)
    password_field = _campo("Contraseña", password=True, can_reveal_password=True)
    confirm_field = _campo("Confirmar contraseña", password=True, can_reveal_password=True)
    pregunta_dd = ft.Dropdown(
        label="Pregunta de seguridad",
        options=[ft.dropdown.Option(p) for p in PREGUNTAS_SECRETAS],
        value=PREGUNTAS_SECRETAS[0],
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
    )
    respuesta_field = _campo("Respuesta")
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def mostrar_error(mensaje: str) -> None:
        error_text.value = mensaje
        error_text.visible = True
        page.update()

    def submit(_e=None):
        error_text.visible = False
        username = username_field.value or ""
        password = password_field.value or ""
        respuesta = respuesta_field.value or ""

        if password != (confirm_field.value or ""):
            mostrar_error("Las contraseñas no coinciden")
            return
        if not respuesta.strip():
            mostrar_error("Completá la respuesta de seguridad, la vas a necesitar si olvidás tu contraseña")
            return

        try:
            auth.crear_usuario(username, password, pregunta_dd.value, respuesta)
            session = auth.login(username, password)
        except (AuthError, ValueError) as exc:
            mostrar_error(str(exc))
            return

        on_success(session)

    for campo in (password_field, confirm_field, respuesta_field):
        campo.on_submit = submit

    return ft.Column(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
                bgcolor=theme.DASHBOARD_BG, padding=16, border_radius=theme.RADIUS_LG,
            ),
            ft.Container(height=8),
            ft.Text("Bienvenido a Kakeibo", size=26, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text("Creá tu usuario para empezar a llevar tus cuentas.", size=14, color=theme.TEXT_SECONDARY),
            ft.Container(height=16),
            username_field,
            password_field,
            confirm_field,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("Para poder recuperar tu contraseña si la olvidás:", size=12, color=theme.TEXT_SECONDARY),
            pregunta_dd,
            respuesta_field,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Crear cuenta e ingresar", submit, color=theme.DASHBOARD_COLOR, icon=ft.Icons.LOCK_OPEN_ROUNDED, width=320),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )


def _vista_login(page, auth, on_success, mostrar) -> ft.Control:
    username_field = _campo("Usuario", autofocus=True)
    password_field = _campo("Contraseña", password=True, can_reveal_password=True)
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def mostrar_error(mensaje: str) -> None:
        error_text.value = mensaje
        error_text.visible = True
        page.update()

    def submit(_e=None):
        error_text.visible = False
        try:
            session = auth.login(username_field.value or "", password_field.value or "")
        except (AuthError, ValueError) as exc:
            mostrar_error(str(exc))
            return
        on_success(session)

    password_field.on_submit = submit

    def ir_a_recuperar(_e=None):
        mostrar(_vista_recuperar_paso1(page, auth, mostrar))

    return ft.Column(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
                bgcolor=theme.DASHBOARD_BG, padding=16, border_radius=theme.RADIUS_LG,
            ),
            ft.Container(height=8),
            ft.Text("Hola de nuevo", size=26, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text("Ingresá tus credenciales para ver tus finanzas.", size=14, color=theme.TEXT_SECONDARY),
            ft.Container(height=16),
            username_field,
            password_field,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Ingresar", submit, color=theme.DASHBOARD_COLOR, icon=ft.Icons.LOCK_OPEN_ROUNDED, width=320),
            ft.TextButton("¿Olvidaste tu contraseña?", on_click=ir_a_recuperar, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _vista_recuperar_paso1(page, auth, mostrar) -> ft.Control:
    username_field = _campo("Tu usuario", autofocus=True)
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def continuar(_e=None):
        username = (username_field.value or "").strip()
        pregunta = auth.obtener_pregunta_secreta(username)
        if pregunta is None:
            error_text.value = "No encontramos ese usuario o no tiene una pregunta de seguridad configurada"
            error_text.visible = True
            page.update()
            return
        mostrar(_vista_recuperar_paso2(page, auth, mostrar, username, pregunta))

    username_field.on_submit = continuar

    def volver(_e=None):
        mostrar(_vista_login(page, auth, lambda s: None, mostrar))

    return ft.Column(
        [
            ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
            ft.Text("Recuperar contraseña", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text("Ingresá tu usuario para ver tu pregunta de seguridad.", size=13, color=theme.TEXT_SECONDARY),
            ft.Container(height=8),
            username_field,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Continuar", continuar, color=theme.DASHBOARD_COLOR, icon=ft.Icons.ARROW_FORWARD_ROUNDED, width=320),
            ft.TextButton("Volver a iniciar sesión", on_click=volver, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _vista_recuperar_paso2(page, auth, mostrar, username: str, pregunta: str) -> ft.Control:
    respuesta_field = _campo("Tu respuesta", autofocus=True)
    nueva_field = _campo("Nueva contraseña", password=True, can_reveal_password=True)
    confirmar_field = _campo("Confirmar nueva contraseña", password=True, can_reveal_password=True)
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def restablecer(_e=None):
        if (nueva_field.value or "") != (confirmar_field.value or ""):
            error_text.value = "Las contraseñas no coinciden"
            error_text.visible = True
            page.update()
            return
        try:
            auth.restablecer_password(username, respuesta_field.value or "", nueva_field.value or "")
        except (AuthError, ValueError) as exc:
            error_text.value = str(exc)
            error_text.visible = True
            page.update()
            return
        mostrar(_vista_recuperar_exito(page, auth, mostrar))

    confirmar_field.on_submit = restablecer

    def volver(_e=None):
        mostrar(_vista_login(page, auth, lambda s: None, mostrar))

    return ft.Column(
        [
            ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
            ft.Text("Recuperar contraseña", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text(pregunta, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
            respuesta_field,
            ft.Divider(height=1, color=theme.BORDER),
            nueva_field,
            confirmar_field,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Restablecer contraseña", restablecer, color=theme.DASHBOARD_COLOR, icon=ft.Icons.CHECK_ROUNDED, width=320),
            ft.TextButton("Volver a iniciar sesión", on_click=volver, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )


def _vista_recuperar_exito(page, auth, mostrar) -> ft.Control:
    def volver(_e=None):
        mostrar(_vista_login(page, auth, lambda s: None, mostrar))

    return ft.Column(
        [
            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=40, color=theme.INCOME_GREEN),
            ft.Text("¡Contraseña actualizada!", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text("Ya podés iniciar sesión con tu nueva contraseña.", size=13, color=theme.TEXT_SECONDARY),
            ft.Container(height=8),
            theme.primary_button("Ir a iniciar sesión", volver, color=theme.DASHBOARD_COLOR, icon=ft.Icons.LOGIN_ROUNDED, width=320),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
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
