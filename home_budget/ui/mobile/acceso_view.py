"""Ingreso, alta de usuario y bloqueo en el celular. Con la huella activada,
al abrir la app (y al bloquearse por inactividad) se pide la huella; la
contrasena queda siempre como alternativa.

Recuperar la contrasena y eliminar usuarios todavia se hacen desde la
computadora."""
from __future__ import annotations

import flet as ft

from ...app.auth.service import PREGUNTAS_SECRETAS, AuthError, AuthService
from ...app.services.logs import registrar_error
from .. import theme
from ..desktop import components
from . import componentes as mc
from .huella import Huella

MOTIVO_INGRESO = "Poné tu huella para entrar a Kakeibo"
MOTIVO_DESBLOQUEO = "Poné tu huella para seguir en Kakeibo"


def _pantalla(controles: list[ft.Control]) -> ft.Control:
    """Pantalla de acceso: una columna centrada, con scroll por si el teclado tapa."""
    return ft.Container(
        ft.Column(
            [ft.Container(ft.Column(controles, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                          padding=theme.pad_only(left=24, top=32, right=24, bottom=24))],
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=0,
        ),
        bgcolor=theme.PAGE_BG, expand=True,
    )


def _encabezado(titulo: str, texto: str, icono: ft.Control) -> list[ft.Control]:
    return [
        ft.Row([icono], alignment=ft.MainAxisAlignment.CENTER),
        ft.Text(titulo, size=24, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
        ft.Text(texto, size=14, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
        ft.Container(height=8),
    ]


def _boton_huella(texto: str, al_tocar) -> ft.Control:
    boton = theme.secondary_button(texto, al_tocar, color=theme.DASHBOARD_COLOR, icon=ft.Icons.FINGERPRINT_ROUNDED)
    boton.expand = True
    return ft.Row([boton])


def _entrar(abrir_app, mostrar_error) -> None:
    """Abre la app despues de un ingreso correcto; si falla, lo muestra y lo deja en el registro de errores."""
    try:
        abrir_app()
    except Exception as exc:
        registrar_error("abrir la app despues de ingresar")
        mostrar_error(f"No se pudo abrir la aplicación ({type(exc).__name__}: {exc}).")


def build_acceso_view(page: ft.Page, auth: AuthService, huella: Huella, on_success, usuario_inicial: str | None = None) -> ft.Control:
    raiz = ft.Container(expand=True)

    def mostrar(vista: ft.Control):
        raiz.content = vista
        page.update()

    def ingreso():
        return _vista_ingreso(page, auth, huella, on_success, lambda: mostrar(alta(permitir_volver=True)), usuario_inicial)

    def alta(permitir_volver: bool):
        return _vista_alta(page, auth, huella, on_success, (lambda: mostrar(ingreso())) if permitir_volver else None)

    raiz.content = ingreso() if auth.hay_usuarios() else alta(permitir_volver=False)
    return raiz


def _ofrecer_huella(page: ft.Page, auth: AuthService, huella: Huella, seguir) -> None:
    """Despues de entrar con contrasena, si el telefono tiene huella y este
    usuario todavia no la usa, se le ofrece activarla. Despues sigue a la app."""
    if not huella.disponible or auth.usuario_con_huella() == auth.session.username:
        seguir()
        return

    def responder(activar: bool):
        page.pop_dialog()
        if activar:
            auth.activar_huella()
        seguir()

    page.show_dialog(theme.dialogo(
        "Entrar con tu huella",
        ft.Text("¿Querés entrar a Kakeibo con tu huella en este celular? La contraseña sigue sirviendo, "
                "y lo podés cambiar cuando quieras desde el menú.", color=theme.TEXT_PRIMARY),
        [theme.secondary_button("Ahora no", lambda e: responder(False)),
         theme.primary_button("Activar huella", lambda e: responder(True), icon=ft.Icons.FINGERPRINT_ROUNDED)],
        icono="fingerprint_rounded", ancho=300,
    ))


def _vista_ingreso(page, auth: AuthService, huella: Huella, on_success, ir_a_alta, usuario_inicial: str | None) -> ft.Control:
    con_huella = auth.usuario_con_huella() if huella.disponible else None
    usuario_f = mc.campo("Usuario", value=usuario_inicial or con_huella or "", autofocus=not (usuario_inicial or con_huella))
    password_f = mc.campo("Contraseña", password=True, can_reveal_password=True)
    error = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False, text_align=ft.TextAlign.CENTER)

    def mostrar_error(mensaje: str):
        error.value, error.visible = mensaje, True
        page.update()

    def ingresar(_e=None):
        error.visible = False
        try:
            session = auth.login(usuario_f.value or "", password_f.value or "")
        except (AuthError, ValueError) as exc:
            mostrar_error(str(exc))
            return
        _ofrecer_huella(page, auth, huella, lambda: _entrar(lambda: on_success(session), mostrar_error))

    async def ingresar_con_huella(_e=None):
        if await huella.pedir(MOTIVO_INGRESO):
            try:
                session = auth.login_con_huella()
            except AuthError as exc:
                mostrar_error(str(exc))
                return
            _entrar(lambda: on_success(session), mostrar_error)

    password_f.on_submit = ingresar
    if con_huella:
        # Al abrir la app se pide la huella directamente, sin tener que tocar el boton.
        page.run_task(ingresar_con_huella)

    return _pantalla([
        *_encabezado("Hola de nuevo", "Ingresá para ver tus finanzas.", components.logo(72)),
        *([_boton_huella(f"Entrar con la huella de {con_huella}", ingresar_con_huella)] if con_huella else []),
        usuario_f,
        password_f,
        error,
        mc.boton_ancho("Ingresar", ingresar, theme.DASHBOARD_COLOR, ft.Icons.LOCK_OPEN_ROUNDED),
        ft.Row([ft.TextButton("Crear usuario nuevo", on_click=lambda e: ir_a_alta(), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))],
               alignment=ft.MainAxisAlignment.CENTER),
    ])


def _vista_alta(page, auth: AuthService, huella: Huella, on_success, volver) -> ft.Control:
    """Mismos datos que el alta de escritorio: usuario, contrasena dos veces y la pregunta de seguridad."""
    usuario_f = mc.campo("Usuario", autofocus=True)
    password_f = mc.campo("Contraseña", password=True, can_reveal_password=True)
    confirmar_f = mc.campo("Confirmar contraseña", password=True, can_reveal_password=True)
    pregunta_dd = mc.desplegable("Pregunta de seguridad", PREGUNTAS_SECRETAS[0], [ft.dropdown.Option(p) for p in PREGUNTAS_SECRETAS], expand=True)
    respuesta_f = mc.campo("Respuesta")
    error = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False, text_align=ft.TextAlign.CENTER)

    def mostrar_error(mensaje: str):
        error.value, error.visible = mensaje, True
        page.update()

    def crear(_e=None):
        error.visible = False
        password = password_f.value or ""
        if password != (confirmar_f.value or ""):
            mostrar_error("Las contraseñas no coinciden")
            return
        if not (respuesta_f.value or "").strip():
            mostrar_error("Completá la respuesta de seguridad, la vas a necesitar si olvidás tu contraseña")
            return
        try:
            auth.crear_usuario(usuario_f.value or "", password, pregunta_dd.value, respuesta_f.value or "")
            session = auth.login(usuario_f.value or "", password)
        except (AuthError, ValueError) as exc:
            mostrar_error(str(exc))
            return
        _ofrecer_huella(page, auth, huella, lambda: _entrar(lambda: on_success(session), mostrar_error))

    return _pantalla([
        *_encabezado("Bienvenido a Kakeibo" if volver is None else "Crear un usuario nuevo",
                     "Creá tu usuario para empezar a llevar tus cuentas.", components.logo(72)),
        usuario_f,
        password_f,
        confirmar_f,
        ft.Text("Para poder recuperar tu contraseña si la olvidás:", size=12, color=theme.TEXT_SECONDARY),
        ft.Row([pregunta_dd]),
        respuesta_f,
        error,
        mc.boton_ancho("Crear cuenta e ingresar", crear, theme.DASHBOARD_COLOR, ft.Icons.LOCK_OPEN_ROUNDED),
        *([ft.Row([ft.TextButton("Volver a iniciar sesión", on_click=lambda e: volver(), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))],
                  alignment=ft.MainAxisAlignment.CENTER)] if volver else []),
    ])


def build_bloqueo_view(page: ft.Page, auth: AuthService, huella: Huella, on_unlock) -> ft.Control:
    """Bloqueo por inactividad. Con la huella activada se pide la huella; si
    no, el PIN (si el usuario tiene uno) o la contrasena, como en escritorio."""
    session = auth.session
    con_huella = huella.disponible and auth.usuario_con_huella() == session.username
    raiz = ft.Container(expand=True)

    def mostrar(usar_pin: bool):
        raiz.content = contenido(usar_pin)
        page.update()

    def contenido(usar_pin: bool) -> ft.Control:
        error = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False, text_align=ft.TextAlign.CENTER)

        def mostrar_error(mensaje: str):
            error.value, error.visible = mensaje, True
            page.update()

        async def desbloquear_con_huella(_e=None):
            if await huella.pedir(MOTIVO_DESBLOQUEO):
                try:
                    auth.desbloquear_con_huella()
                except AuthError as exc:
                    mostrar_error(str(exc))
                    return
                _entrar(on_unlock, mostrar_error)

        if usar_pin:
            campo = mc.campo("PIN", password=True, max_length=4, input_filter=ft.NumbersOnlyInputFilter(),
                             keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER, text_size=22)

            def desbloquear(_e=None):
                try:
                    auth.desbloquear_con_pin(campo.value or "")
                except AuthError as exc:
                    campo.value = ""
                    if not auth.puede_desbloquear_con_pin():
                        mostrar(False)  # demasiados intentos: pasa a contrasena
                        return
                    mostrar_error(str(exc))
                    return
                _entrar(on_unlock, mostrar_error)

            campo.on_change = lambda e: desbloquear() if len(campo.value or "") == 4 else None
            instruccion = f"Ingresá tu PIN para continuar, {session.username}."
            alternativa = ("Usar contraseña", lambda e: mostrar(False))
        else:
            campo = mc.campo("Contraseña", password=True, can_reveal_password=True)

            def desbloquear(_e=None):
                try:
                    auth.login(session.username, campo.value or "")
                except AuthError:
                    mostrar_error("Contraseña incorrecta")
                    return
                _entrar(on_unlock, mostrar_error)

            instruccion = f"Ingresá tu contraseña para continuar, {session.username}."
            alternativa = ("Usar PIN", lambda e: mostrar(True)) if auth.puede_desbloquear_con_pin() else None
            if auth.obtener_perfil(session.usuario_id).tiene_pin and not auth.puede_desbloquear_con_pin():
                instruccion = "Demasiados intentos con el PIN. Ingresá tu contraseña para continuar."

        campo.on_submit = desbloquear
        return _pantalla([
            *_encabezado("Sesión bloqueada", instruccion, ft.Icon(ft.Icons.LOCK_ROUNDED, size=44, color=theme.DASHBOARD_COLOR)),
            *([_boton_huella("Desbloquear con huella", desbloquear_con_huella)] if con_huella else []),
            campo,
            error,
            mc.boton_ancho("Desbloquear", desbloquear, theme.DASHBOARD_COLOR, ft.Icons.LOCK_OPEN_ROUNDED),
            *([ft.Row([ft.TextButton(alternativa[0], on_click=alternativa[1], style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))],
                      alignment=ft.MainAxisAlignment.CENTER)] if alternativa else []),
        ])

    raiz.content = contenido(auth.puede_desbloquear_con_pin())
    if con_huella:
        async def pedir_al_bloquearse():
            if await huella.pedir(MOTIVO_DESBLOQUEO):
                auth.desbloquear_con_huella()
                on_unlock()

        page.run_task(pedir_al_bloquearse)
    return raiz
