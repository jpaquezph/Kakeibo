"""Configuración en el celular (se entra tocando la foto de perfil): el
usuario, el ingreso con huella, la apariencia, las categorías y el registro
de errores.

No estan "Iniciar con Windows" (es de la computadora) ni subir una imagen de
perfil: la imagen se sigue cargando desde la computadora; aca se elige el
color."""
from __future__ import annotations

from typing import Callable

import flet as ft

from ...app.auth.service import AuthError, AuthService
from ...app.domain.models import TipoMovimiento
from ...app.services.logs import leer_log, ultimo_error
from .. import theme
from ..desktop import components
from ..desktop.movimientos_view import _COLORES_CATEGORIA_NUEVA
from . import componentes as mc
from .huella import Huella


def build_configuracion_view(page: ft.Page, nav: mc.Navegacion, servicios, auth: AuthService, huella: Huella,
                             cambiar_tema: Callable[[bool], None], perfil_cambiado: Callable[[str], None]) -> ft.Control:
    """`perfil_cambiado(mensaje)` vuelve a armar la app (el encabezado
    muestra la foto y el menu el nombre) y avisa el resultado."""
    return mc.pantalla([
        _tarjeta("Usuario", "person_rounded", _usuario(page, nav, auth, perfil_cambiado)),
        _tarjeta("Seguridad", "lock_outline_rounded", _seguridad(page, nav, auth, huella)),
        _tarjeta("Apariencia", "palette_outlined", [
            _interruptor("Modo oscuro", "Cambia los colores de toda la app a un tema oscuro.", theme.MODO_OSCURO,
                         lambda e: cambiar_tema(e.control.value)),
        ]),
        _tarjeta("Categorías", "sell_outlined", [_categorias(page, servicios.categorias)]),
        _tarjeta("Registro de errores", "description_outlined", _registro_errores(page, nav)),
    ])


def _tarjeta(titulo: str, icono: str, cuerpo: list[ft.Control]) -> ft.Control:
    return theme.card(
        ft.Column([ft.Row([theme.section_pill(titulo, theme.CONFIG_COLOR, theme.CONFIG_BG, icon=icono)]), *cuerpo], spacing=14),
        padding=16,
    )


def _titulo(texto: str) -> ft.Text:
    return ft.Text(texto, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)


def _detalle(texto: str) -> ft.Text:
    return ft.Text(texto, size=12, color=theme.TEXT_SECONDARY)


def _interruptor(titulo: str, detalle: str, valor: bool, al_cambiar, visible: bool = True) -> ft.Row:
    return ft.Row(
        [ft.Column([_titulo(titulo), _detalle(detalle)], spacing=2, expand=True),
         ft.Switch(value=valor, active_color=theme.CONFIG_COLOR, on_change=al_cambiar)],
        spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, visible=visible,
    )


def _fila_accion(titulo: str, detalle: str, botones: list[ft.Control]) -> ft.Column:
    """Un dato con su explicacion y, debajo, los botones para cambiarlo."""
    return ft.Column([_titulo(titulo), _detalle(detalle), ft.Row(botones, spacing=8, wrap=True)], spacing=6)


def _usuario(page: ft.Page, nav: mc.Navegacion, auth: AuthService, perfil_cambiado) -> list[ft.Control]:
    usuario_id = auth.session.usuario_id
    perfil = auth.obtener_perfil(usuario_id)

    def elegir_color(color: str):
        auth.cambiar_avatar_color(usuario_id, "" if color == components.AVATAR_COLOR_DEFECTO else color)
        perfil_cambiado("Color de perfil actualizado")

    colores, _color = mc.muestras_color(page, components.AVATAR_COLORES, perfil.avatar_color or components.AVATAR_COLOR_DEFECTO,
                                        elegir_color)
    nombre_f = mc.campo("Nombre de usuario", value=perfil.username, expand=True)
    error, mostrar_error = mc.texto_error(page)

    def guardar_nombre(_e=None):
        try:
            auth.cambiar_nombre(usuario_id, nombre_f.value or "")
        except ValueError as exc:
            mostrar_error(exc)
            return
        perfil_cambiado("Nombre actualizado")

    nombre_f.on_submit = guardar_nombre
    return [
        ft.Row(
            [components.avatar(perfil, radio=30),
             ft.Column([_titulo("Color de perfil"),
                        _detalle("Se usa si no hay imagen. La imagen de perfil se carga desde la computadora."
                                 if perfil.avatar_imagen else "La imagen de perfil se carga desde la computadora.")],
                       spacing=2, expand=True)],
            spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        colores,
        mc.separador(),
        _titulo("Nombre"),
        ft.Row([nombre_f, theme.primary_button("Guardar", guardar_nombre, color=theme.CONFIG_COLOR)], spacing=8,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        error,
    ]


def _seguridad(page: ft.Page, nav: mc.Navegacion, auth: AuthService, huella: Huella) -> list[ft.Control]:
    usuario_id = auth.session.usuario_id
    perfil = auth.obtener_perfil(usuario_id)

    def abrir(titulo: str, constructor):
        nav.abrir(titulo, constructor, theme.CONFIG_COLOR)

    def al_cambiar_huella(e):
        if e.control.value:
            auth.activar_huella()
        else:
            auth.desactivar_huella()

    botones_pin = [theme.secondary_button("Cambiar PIN" if perfil.tiene_pin else "Configurar PIN",
                                          lambda e: abrir("PIN de desbloqueo", lambda: _formulario_pin(page, nav, auth, perfil.tiene_pin)),
                                          icon=ft.Icons.PIN_ROUNDED)]
    if perfil.tiene_pin:
        botones_pin.append(theme.secondary_button("Quitar PIN", lambda e: abrir("Quitar PIN", lambda: _formulario_quitar_pin(page, nav, auth)),
                                                  icon=ft.Icons.CLOSE_ROUNDED))
    return [
        # Solo en telefonos con huella cargada: en el resto la opcion no aparece.
        _interruptor("Entrar con huella", "Al abrir la app y al volver de la inactividad se pide la huella. La contraseña sigue sirviendo.",
                     auth.usuario_con_huella() == auth.session.username, al_cambiar_huella, visible=huella.disponible),
        *([mc.separador()] if huella.disponible else []),
        _fila_accion("Contraseña", "Mínimo 6 caracteres.", [
            theme.secondary_button("Cambiar contraseña", lambda e: abrir("Cambiar contraseña", lambda: _formulario_password(page, nav, auth)),
                                   icon=ft.Icons.KEY_ROUNDED),
        ]),
        mc.separador(),
        _fila_accion("PIN de desbloqueo",
                     "Activado: al volver de la inactividad se pide el PIN." if perfil.tiene_pin
                     else "Desactivado: al volver de la inactividad se pide la contraseña.", botones_pin),
    ]


def _campo_password(label: str, **kwargs) -> ft.TextField:
    return mc.campo(label, password=True, can_reveal_password=True, **kwargs)


def _campo_pin(label: str) -> ft.TextField:
    return _campo_password(label, max_length=4, input_filter=ft.NumbersOnlyInputFilter(), keyboard_type=ft.KeyboardType.NUMBER)


def _formulario_password(page: ft.Page, nav: mc.Navegacion, auth: AuthService) -> ft.Control:
    actual_f = _campo_password("Contraseña actual", autofocus=True)
    nueva_f = _campo_password("Nueva contraseña")
    confirmar_f = _campo_password("Confirmar nueva contraseña")
    error, mostrar_error = mc.texto_error(page)

    def guardar(_e=None):
        if (nueva_f.value or "") != (confirmar_f.value or ""):
            mostrar_error("Las contraseñas no coinciden")
            return
        try:
            auth.cambiar_password(auth.session.usuario_id, actual_f.value or "", nueva_f.value or "")
        except (AuthError, ValueError) as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar("Contraseña actualizada")

    confirmar_f.on_submit = guardar
    return mc.pantalla([actual_f, nueva_f, confirmar_f, mc.nota("Mínimo 6 caracteres."), error,
                        mc.boton_ancho("Guardar", guardar, theme.CONFIG_COLOR, ft.Icons.CHECK_ROUNDED)])


def _formulario_pin(page: ft.Page, nav: mc.Navegacion, auth: AuthService, tiene_pin: bool) -> ft.Control:
    password_f = _campo_password("Contraseña actual", autofocus=True)
    pin_f = _campo_pin("PIN (4 números)")
    confirmar_f = _campo_pin("Confirmar PIN")
    error, mostrar_error = mc.texto_error(page)

    def guardar(_e=None):
        if (pin_f.value or "") != (confirmar_f.value or ""):
            mostrar_error("Los PIN no coinciden")
            return
        try:
            auth.establecer_pin(auth.session.usuario_id, password_f.value or "", pin_f.value or "")
        except (AuthError, ValueError) as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar("PIN guardado")

    confirmar_f.on_submit = guardar
    return mc.pantalla([
        _detalle("Con el PIN desbloqueás la app cuando se bloquea por inactividad. Para iniciar sesión se sigue usando la contraseña."),
        password_f, pin_f, confirmar_f, error,
        mc.boton_ancho("Cambiar PIN" if tiene_pin else "Guardar PIN", guardar, theme.CONFIG_COLOR, ft.Icons.CHECK_ROUNDED),
    ])


def _formulario_quitar_pin(page: ft.Page, nav: mc.Navegacion, auth: AuthService) -> ft.Control:
    password_f = _campo_password("Contraseña actual", autofocus=True)
    error, mostrar_error = mc.texto_error(page)

    def quitar(_e=None):
        try:
            auth.quitar_pin(auth.session.usuario_id, password_f.value or "")
        except AuthError as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar("PIN quitado: el desbloqueo vuelve a pedir la contraseña")

    password_f.on_submit = quitar
    return mc.pantalla([
        _detalle("Ingresá tu contraseña para quitar el PIN. Después, el desbloqueo por inactividad va a pedir la contraseña."),
        password_f, error,
        mc.boton_ancho("Quitar PIN", quitar, theme.EXPENSE_RED, ft.Icons.CLOSE_ROUNDED),
    ])


def _categorias(page: ft.Page, categorias) -> ft.Control:
    """Ver, agregar, quitar y volver a agregar categorias. Quitar una no
    borra nada: lo ya cargado con ella la conserva."""
    cuerpo = ft.Column(spacing=16)
    error, mostrar_error = mc.texto_error(page)

    def refrescar(actualizar: bool = True):
        cuerpo.controls = [
            _detalle("Quitar una categoría no borra nada: lo que ya cargaste con ella la conserva. Solo deja de aparecer para elegir."),
            error,
            _bloque(TipoMovimiento.EGRESO, "De egreso"),
            _bloque(TipoMovimiento.INGRESO, "De ingreso"),
        ]
        if actualizar:
            page.update()

    def _chip(c) -> ft.Control:
        fija = categorias.puede_quitarse(c)  # el motivo por el que no se puede quitar, si lo hay
        return ft.Container(
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=c.color, border_radius=5),
                    ft.Text(c.nombre, size=13, color=theme.TEXT_PRIMARY),
                    ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, size=14, color=theme.TEXT_MUTED, tooltip=fija) if fija
                    else ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16, color=theme.EXPENSE_RED),
                ],
                spacing=6, tight=True,
            ),
            padding=theme.pad(horizontal=10, vertical=7), border_radius=16, bgcolor=theme.SURFACE_ALT,
            border=theme.border_all(1, theme.BORDER), on_click=None if fija else (lambda e: confirmar_quitar(c)),
        )

    def _bloque(tipo: TipoMovimiento, titulo: str) -> ft.Control:
        quitadas = [c for c in categorias.listar(tipo, incluir_quitadas=True) if not c.activa]
        nombre_f = mc.campo("Nueva categoría", dense=True, expand=True)

        def agregar(_e=None):
            nombre = (nombre_f.value or "").strip()
            if not nombre:
                return
            color = _COLORES_CATEGORIA_NUEVA[len(categorias.listar(incluir_quitadas=True)) % len(_COLORES_CATEGORIA_NUEVA)]
            try:
                categorias.crear(nombre, color, "label_rounded", tipo)
            except ValueError as exc:
                mostrar_error(exc)
                return
            error.visible = False
            refrescar()

        nombre_f.on_submit = agregar
        controles = [
            _titulo(titulo),
            ft.Row([_chip(c) for c in categorias.listar(tipo)], wrap=True, spacing=8, run_spacing=8),
            ft.Row([nombre_f, ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, icon_color=theme.CONFIG_COLOR,
                                            tooltip="Agregar categoría", on_click=agregar)], spacing=4),
        ]
        if quitadas:
            controles.append(ft.Row(
                [ft.Text("Quitadas:", size=12, color=theme.TEXT_MUTED)] + [
                    ft.TextButton(c.nombre, icon=ft.Icons.UNDO_ROUNDED, tooltip="Volver a agregarla",
                                  style=ft.ButtonStyle(color=theme.TEXT_SECONDARY), on_click=lambda e, c=c: restaurar(c))
                    for c in quitadas
                ],
                wrap=True, spacing=4, run_spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ))
        return ft.Column(controles, spacing=8)

    def restaurar(c):
        categorias.crear(c.nombre, c.color, c.icono, c.tipo)
        error.visible = False
        refrescar()

    def confirmar_quitar(c):
        detalle = ("Lo que ya está cargado con esta categoría la conserva: no queda sin categoría."
                   if categorias.usos(c.id) else "No tiene nada cargado todavía.")

        def quitar():
            try:
                categorias.quitar(c.id)
            except ValueError as exc:
                mostrar_error(exc)
                return
            error.visible = False
            refrescar()

        mc.confirmar(page, "Quitar categoría", f'¿Quitar "{c.nombre}"? Ya no va a aparecer para elegir.\n\n{detalle}', "Quitar",
                     theme.EXPENSE_RED, "delete_outline_rounded", quitar)

    refrescar(actualizar=False)
    return cuerpo


def _registro_errores(page: ft.Page, nav: mc.Navegacion) -> list[ft.Control]:
    icono = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=16)
    estado = ft.Text("", size=12, selectable=True, expand=True)

    def refrescar(_e=None):
        error = ultimo_error()
        if error:
            icono.icon, icono.color = ft.Icons.ERROR_OUTLINE_ROUNDED, theme.EXPENSE_RED
            estado.value, estado.color = f"Último error: {error}", theme.EXPENSE_RED
        else:
            icono.icon, icono.color = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, theme.INCOME_GREEN
            estado.value, estado.color = "Sin errores registrados.", theme.TEXT_MUTED
        if _e is not None:
            page.update()

    def ver_detalle(_e=None):
        nav.abrir("Registro de errores", lambda: mc.pantalla([
            _detalle("El detalle técnico para pasarle a soporte. Se puede seleccionar y copiar."),
            ft.Text(leer_log() or "Sin errores registrados.", size=11, selectable=True, color=theme.TEXT_PRIMARY, font_family="monospace"),
        ]), theme.CONFIG_COLOR)

    refrescar()
    return [
        _detalle("Si algo falló, acá queda el detalle técnico para pasarle a soporte. Se guarda solo en este celular, no se envía a ningún lado."),
        ft.Row([icono, estado], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
        ft.Row([theme.secondary_button("Actualizar", refrescar, icon=ft.Icons.REFRESH_ROUNDED),
                theme.secondary_button("Ver detalle", ver_detalle, icon=ft.Icons.DESCRIPTION_OUTLINED)], spacing=8, wrap=True),
    ]
