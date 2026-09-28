from __future__ import annotations

import flet as ft

from ...app.auth.service import PREGUNTAS_SECRETAS, AuthError, AuthService
from .. import theme
from . import components


def build_login_view(page: ft.Page, auth: AuthService, on_success, usuario_inicial: str | None = None) -> ft.Control:
    """`usuario_inicial` precarga el usuario (al cambiar de usuario desde la app)."""
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
        mostrar(_vista_login(page, auth, on_success, mostrar, usuario_inicial))

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


def _vista_signup(page, auth, on_success, mostrar, permitir_volver: bool = False) -> ft.Control:
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

    def volver(_e=None):
        mostrar(_vista_login(page, auth, on_success, mostrar))

    return ft.Column(
        [
            components.logo(72),
            ft.Container(height=8),
            ft.Text("Bienvenido a Kakeibo" if not permitir_volver else "Crear un usuario nuevo", size=26, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
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
            *([ft.TextButton("Volver a iniciar sesión", on_click=volver, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))] if permitir_volver else []),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )


def _vista_login(page, auth, on_success, mostrar, usuario_inicial: str | None = None) -> ft.Control:
    username_field = _campo("Usuario", value=usuario_inicial or "", autofocus=not usuario_inicial)
    password_field = _campo("Contraseña", password=True, can_reveal_password=True, autofocus=bool(usuario_inicial))
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

    def ir_a_crear_usuario(_e=None):
        mostrar(_vista_signup(page, auth, on_success, mostrar, permitir_volver=True))

    def ir_a_eliminar_usuario(_e=None):
        mostrar(_vista_eliminar_usuario(page, auth, mostrar))

    return ft.Column(
        [
            components.logo(72),
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
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("Gestionar usuarios", size=11, color=theme.TEXT_MUTED),
            ft.Row(
                [
                    ft.TextButton("Crear usuario nuevo", on_click=ir_a_crear_usuario, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
                    ft.TextButton("Eliminar un usuario", on_click=ir_a_eliminar_usuario, style=ft.ButtonStyle(color=theme.EXPENSE_RED)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            ),
        ],
        width=360,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _vista_eliminar_usuario(page, auth, mostrar) -> ft.Control:
    usuarios = auth.listar_usernames()
    usuario_dd = ft.Dropdown(
        label="Usuario a eliminar",
        options=[ft.dropdown.Option(u) for u in usuarios],
        value=usuarios[0] if usuarios else None,
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
    )
    password_field = _campo("Contraseña de ese usuario", password=True, can_reveal_password=True)
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def volver(_e=None):
        mostrar(_vista_login(page, auth, lambda s: None, mostrar))

    def confirmar_eliminar(_e=None):
        def confirmar(_e2):
            try:
                auth.eliminar_usuario(usuario_dd.value or "", password_field.value or "")
            except AuthError as exc:
                page.pop_dialog()
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            mostrar(_vista_login(page, auth, lambda s: None, mostrar))

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar usuario"),
            content=ft.Text(f'¿Seguro que querés eliminar el usuario "{usuario_dd.value}"? Esta acción no se puede deshacer.'),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    password_field.on_submit = confirmar_eliminar

    if not usuarios:
        contenido = [
            ft.Icon(ft.Icons.PERSON_OFF_ROUNDED, size=40, color=theme.TEXT_MUTED),
            ft.Text("No hay usuarios para eliminar.", size=14, color=theme.TEXT_SECONDARY),
            ft.Container(height=8),
            ft.TextButton("Volver a iniciar sesión", on_click=volver, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ]
    else:
        contenido = [
            ft.Icon(ft.Icons.PERSON_OFF_ROUNDED, size=40, color=theme.EXPENSE_RED),
            ft.Text("Eliminar usuario", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text("Se necesita la contraseña de ese usuario para confirmar.", size=13, color=theme.TEXT_SECONDARY),
            ft.Container(height=8),
            usuario_dd,
            password_field,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Eliminar usuario", confirmar_eliminar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED, width=320),
            ft.TextButton("Cancelar", on_click=volver, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ]

    return ft.Column(
        contenido,
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
    """Bloqueo por inactividad. Si el usuario configuro un PIN se pide el PIN
    (con opcion de usar la contrasena); tras varios PIN errados, solo contrasena."""
    session = auth.session
    tarjeta = ft.Container()

    def mostrar(usar_pin: bool):
        tarjeta.content = theme.card(_contenido_lock(page, auth, session, on_unlock, usar_pin, mostrar), padding=36)
        page.update()

    tarjeta.content = theme.card(
        _contenido_lock(page, auth, session, on_unlock, auth.puede_desbloquear_con_pin(), mostrar), padding=36
    )
    return ft.Container(
        content=ft.Row([tarjeta], alignment=ft.MainAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        expand=True,
        bgcolor=theme.PAGE_BG,
    )


def _contenido_lock(page, auth: AuthService, session, on_unlock, usar_pin: bool, mostrar) -> ft.Control:
    error_text = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def mostrar_error(mensaje: str):
        error_text.value = mensaje
        error_text.visible = True
        page.update()

    if usar_pin:
        campo = ft.TextField(
            label="PIN", password=True, autofocus=True, max_length=4, width=200,
            input_filter=ft.NumbersOnlyInputFilter(), keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER, text_size=22,
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, focused_border_color=theme.DASHBOARD_COLOR,
            filled=True, bgcolor=theme.SURFACE_ALT,
        )

        def submit(_e=None):
            try:
                auth.desbloquear_con_pin(campo.value or "")
            except AuthError as exc:
                campo.value = ""
                if not auth.puede_desbloquear_con_pin():
                    mostrar(False)  # demasiados intentos: pasa a contrasena
                    return
                mostrar_error(str(exc))
                return
            on_unlock()

        def on_change(_e):
            if len(campo.value or "") == 4:
                submit()

        campo.on_change = on_change
        campo.on_submit = submit
        instruccion = f"Ingresá tu PIN para continuar, {session.username}."
        alternativa = ft.TextButton("Usar contraseña", on_click=lambda e: mostrar(False), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))
    else:
        campo = ft.TextField(
            label="Contraseña", password=True, can_reveal_password=True, autofocus=True, width=320,
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, focused_border_color=theme.DASHBOARD_COLOR,
            filled=True, bgcolor=theme.SURFACE_ALT,
        )

        def submit(_e=None):
            try:
                auth.login(session.username, campo.value or "")
            except AuthError:
                mostrar_error("Contraseña incorrecta")
                return
            on_unlock()

        campo.on_submit = submit
        instruccion = f"Ingresá tu contraseña para continuar, {session.username}."
        alternativa = (
            ft.TextButton("Usar PIN", on_click=lambda e: mostrar(True), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))
            if auth.puede_desbloquear_con_pin() else ft.Container()
        )
        if auth.obtener_perfil(session.usuario_id).tiene_pin and not auth.puede_desbloquear_con_pin():
            instruccion = "Demasiados intentos con el PIN. Ingresá tu contraseña para continuar."

    return ft.Column(
        [
            ft.Icon(ft.Icons.LOCK_ROUNDED, size=40, color=theme.DASHBOARD_COLOR),
            ft.Text("Sesión bloqueada por inactividad", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Text(instruccion, size=13, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
            ft.Container(height=8),
            campo,
            error_text,
            ft.Container(height=8),
            theme.primary_button("Desbloquear", submit, color=theme.DASHBOARD_COLOR, icon=ft.Icons.LOCK_OPEN_ROUNDED, width=320),
            alternativa,
        ],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        width=360,
    )
