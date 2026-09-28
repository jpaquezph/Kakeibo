from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
from datetime import date
from pathlib import Path

import flet as ft

from ...app.auth.service import AuthService
from ...app.database import DEFAULT_DB_PATH
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.backup import crear_backup
from ...app.services.cambio import CambioDivisaService
from ...app.services.config import CLAVE_TEMA, ConfigService
from ...app.services.dashboard import DashboardService
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.movimientos import MovimientoService
from ...app.services.prestamos import PrestamoService
from ...app.services.tarjetas import TarjetaService
from ...app.services.vencimientos import VencimientoService
from .. import theme
from . import components
from .calendario_view import build_calendario_view
from .configuracion_view import build_configuracion_view
from .dashboard_view import build_dashboard_view
from .gastos_fijos_view import build_gastos_fijos_view
from .historial_view import build_historial_view
from .movimientos_view import build_movimientos_view
from .prestamos_view import build_prestamos_view
from .tarjetas_view import build_tarjetas_view
from .vencimientos_aviso import build_aviso_minimizado, build_aviso_vencimientos


class _BrowseInfo(ctypes.Structure):
    _fields_ = [
        ("hwndOwner", wintypes.HWND),
        ("pidlRoot", ctypes.c_void_p),
        ("pszDisplayName", wintypes.LPWSTR),
        ("lpszTitle", wintypes.LPCWSTR),
        ("ulFlags", wintypes.UINT),
        ("lpfn", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("iImage", ctypes.c_int),
    ]


# En ctypes hay que declarar restype/argtypes explicitamente: sin eso asume
# que todo devuelve un int de 32 bits, lo que trunca el puntero de 64 bits
# que devuelve SHBrowseForFolderW y termina en "access violation" al usarlo.
_SHBrowseForFolderW = ctypes.windll.shell32.SHBrowseForFolderW
_SHBrowseForFolderW.restype = ctypes.c_void_p
_SHBrowseForFolderW.argtypes = [ctypes.POINTER(_BrowseInfo)]

_SHGetPathFromIDListW = ctypes.windll.shell32.SHGetPathFromIDListW
_SHGetPathFromIDListW.restype = wintypes.BOOL
_SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]

_CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
_CoTaskMemFree.restype = None
_CoTaskMemFree.argtypes = [ctypes.c_void_p]


def _elegir_carpeta_backup() -> str | None:
    """Abre el selector nativo de carpetas de Windows via Shell32 (ctypes).

    No se usa Tkinter porque el runtime de Python embebido por
    'flet build windows' no incluye el modulo _tkinter, ni ft.FilePicker
    porque en esta version de Flet (0.86.5) ese control no se registra en
    el cliente de Windows ("Unknown control: FilePicker"). La API de Shell32
    via ctypes no depende de ninguno de los dos.
    """
    BIF_RETURNONLYFSDIRS = 0x0001

    display_name = ctypes.create_unicode_buffer(260)
    info = _BrowseInfo()
    info.pszDisplayName = ctypes.cast(display_name, wintypes.LPWSTR)
    info.lpszTitle = "Elegí dónde guardar el backup"
    info.ulFlags = BIF_RETURNONLYFSDIRS

    pidl = _SHBrowseForFolderW(ctypes.byref(info))
    if not pidl:
        return None
    try:
        path_buf = ctypes.create_unicode_buffer(260)
        _SHGetPathFromIDListW(pidl, path_buf)
        return path_buf.value or None
    finally:
        _CoTaskMemFree(pidl)


def _secciones():
    # Se arma al momento (no a nivel de modulo) para tomar la paleta activa.
    return [
        ("dashboard", "space_dashboard_rounded", "Resumen", theme.DASHBOARD_COLOR, theme.DASHBOARD_BG),
        ("movimientos", "swap_vert_rounded", "Movimientos", theme.MOVIMIENTOS_COLOR, theme.MOVIMIENTOS_BG),
        ("gastos_fijos", "event_repeat_rounded", "Gastos fijos", theme.MOVIMIENTOS_COLOR, theme.MOVIMIENTOS_BG),
        ("tarjetas", "credit_card_rounded", "Tarjetas", theme.TARJETAS_COLOR, theme.TARJETAS_BG),
        ("prestamos", "account_balance_rounded", "Préstamos", theme.PRESTAMOS_COLOR, theme.PRESTAMOS_BG),
        ("calendario", "calendar_month_rounded", "Calendario", theme.CALENDARIO_COLOR, theme.CALENDARIO_BG),
        ("historial", "history_rounded", "Historial", theme.HISTORIAL_COLOR, theme.HISTORIAL_BG),
        ("configuracion", "settings_rounded", "Configuración", theme.CONFIG_COLOR, theme.CONFIG_BG),
    ]


def build_app_shell(page: ft.Page, conn, auth: AuthService, on_logout, mostrar_aviso_vencimientos: bool = False) -> ft.Control:
    categoria_repo = CategoriaRepository(conn)
    movimiento_service = MovimientoService(conn)
    tarjeta_service = TarjetaService(conn)
    prestamo_service = PrestamoService(conn)
    dashboard_service = DashboardService(conn)
    cambio_service = CambioDivisaService(conn)
    gasto_fijo_service = GastoFijoService(conn)
    config_service = ConfigService(conn)

    vencimiento_service = VencimientoService(tarjeta_service, prestamo_service, gasto_fijo_service)

    shell_container = ft.Container(expand=True)
    # aviso: "abierto" | "minimizado" | "cerrado". "contenido" es la vista de
    # la seccion actual: se reutiliza al minimizar/expandir el aviso para no
    # perder lo que el usuario estaba cargando.
    estado = {"seccion": "dashboard", "aviso": "abierto" if mostrar_aviso_vencimientos else "cerrado", "contenido": None}

    def contenido_para(seccion: str) -> ft.Control:
        if seccion == "movimientos":
            return build_movimientos_view(page, movimiento_service, categoria_repo)
        if seccion == "gastos_fijos":
            return build_gastos_fijos_view(page, gasto_fijo_service, categoria_repo)
        if seccion == "tarjetas":
            return build_tarjetas_view(page, tarjeta_service, categoria_repo)
        if seccion == "prestamos":
            return build_prestamos_view(page, prestamo_service)
        if seccion == "calendario":
            return build_calendario_view(page, tarjeta_service, prestamo_service, gasto_fijo_service)
        if seccion == "historial":
            return build_historial_view(page, movimiento_service, categoria_repo)
        if seccion == "configuracion":
            return build_configuracion_view(page, config_service, auth, cambiar_tema, perfil_cambiado)
        return build_dashboard_view(page, dashboard_service, cambio_service)

    def cambiar_seccion(key: str):
        if auth.session is not None:
            auth.session.touch()
        estado["seccion"] = key
        page.overlay.clear()
        try:
            estado["contenido"] = contenido_para(key)
            shell_container.content = montar()
        except Exception:
            import traceback
            with open("kakeibo_debug.log", "a", encoding="utf-8") as f:
                f.write(f"--- error al cambiar a seccion {key!r} ---\n")
                f.write(traceback.format_exc())
                f.write("\n")
            raise
        page.update()

    def cambiar_tema(oscuro: bool):
        config_service.guardar(CLAVE_TEMA, "oscuro" if oscuro else "claro")
        theme.aplicar_modo(oscuro)
        page.theme_mode = ft.ThemeMode.DARK if oscuro else ft.ThemeMode.LIGHT
        page.bgcolor = theme.PAGE_BG
        cambiar_seccion(estado["seccion"])

    def perfil_cambiado(mensaje: str):
        # Se reconstruye todo porque la barra lateral muestra nombre y avatar.
        cambiar_seccion(estado["seccion"])
        page.show_dialog(ft.SnackBar(ft.Text(mensaje)))

    def salir(_e=None, usuario_siguiente: str | None = None):
        auth.logout()
        on_logout(usuario_siguiente)

    def cambiar_usuario(username: str):
        def confirmar(_e):
            page.pop_dialog()
            salir(usuario_siguiente=username)

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Cambiar de usuario"),
            content=ft.Text(f'¿Querés cambiar al usuario "{username}"? Se va a cerrar tu sesión y vas a tener que ingresar su contraseña.'),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Cambiar", confirmar, color=theme.DASHBOARD_COLOR, icon=ft.Icons.SWITCH_ACCOUNT_ROUNDED),
            ],
        ))

    async def hacer_backup(_e=None):
        loop = asyncio.get_event_loop()
        destino_dir = await loop.run_in_executor(None, _elegir_carpeta_backup)

        if not destino_dir:
            return  # el usuario cancelo el dialogo

        try:
            destino = crear_backup(DEFAULT_DB_PATH, Path(destino_dir))
            icono, color, mensaje = ft.Icons.CHECK_CIRCLE_ROUNDED, theme.INCOME_GREEN, f"Backup creado con éxito en:\n{destino}"
        except Exception as exc:
            icono, color, mensaje = ft.Icons.ERROR_ROUNDED, theme.EXPENSE_RED, f"No se pudo crear el backup:\n{exc}"

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(icono, color=color), ft.Text("Backup")], spacing=8),
            content=ft.Text(mensaje, size=13, selectable=True),
            actions=[theme.primary_button("Aceptar", lambda e: page.pop_dialog(), color=theme.DASHBOARD_COLOR)],
        )
        page.show_dialog(dialog)

    def montar() -> ft.Control:
        """Layout de la seccion actual mas el aviso de vencimientos, que
        sobrevive a los cambios de seccion. Abierto flota encima del
        contenido; minimizado va en una franja propia debajo, sin taparlo."""
        hoy = date.today()
        pendientes = []
        if estado["aviso"] != "cerrado":
            pendientes = vencimiento_service.pendientes_del_mes(hoy.year, hoy.month)
            if not pendientes:
                estado["aviso"] = "cerrado"

        pie = None
        if estado["aviso"] == "minimizado":
            pie = build_aviso_minimizado(len(pendientes), hoy, lambda: cambiar_aviso("abierto"), lambda: cambiar_aviso("cerrado"))
        capas = [_build_layout(estado, cambiar_seccion, estado["contenido"], auth, salir, hacer_backup, cambiar_usuario, pie)]
        if estado["aviso"] == "abierto":
            capas.append(build_aviso_vencimientos(pendientes, hoy, lambda: cambiar_aviso("cerrado"), lambda: cambiar_aviso("minimizado")))
        return ft.Stack(capas, expand=True)

    def cambiar_aviso(nuevo: str):
        estado["aviso"] = nuevo
        shell_container.content = montar()
        shell_container.update()

    estado["contenido"] = contenido_para(estado["seccion"])
    shell_container.content = montar()
    return shell_container


def _build_layout(estado, cambiar_seccion, contenido: ft.Control, auth, salir, hacer_backup, cambiar_usuario, pie: ft.Control | None = None) -> ft.Control:
    nav_items = [_nav_button(key, icon, label, color, bg, estado["seccion"] == key, cambiar_seccion) for key, icon, label, color, bg in _secciones()]

    sidebar = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=theme.DASHBOARD_COLOR, size=26),
                            ft.Text("Kakeibo", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                        ],
                        spacing=8,
                    ),
                    padding=theme.pad_only(left=20, top=24, bottom=24),
                ),
                *nav_items,
                ft.Container(expand=True),
                ft.Container(
                    content=ft.TextButton(
                        "Hacer backup",
                        icon=ft.Icons.BACKUP_ROUNDED,
                        on_click=hacer_backup,
                        style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                    ),
                    padding=theme.pad_only(left=12, bottom=4, right=8),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            _selector_usuario(auth, cambiar_usuario),
                            ft.TextButton("Cerrar sesión", icon=ft.Icons.LOGOUT_ROUNDED, on_click=salir, style=ft.ButtonStyle(color=theme.EXPENSE_RED)),
                        ],
                        spacing=8,
                    ),
                    padding=theme.pad_only(left=20, bottom=20, right=8),
                ),
            ],
            spacing=2,
        ),
        width=230,
        bgcolor=theme.SURFACE,
        border=theme.border_right(1, theme.BORDER),
    )

    if pie is not None:
        contenido = ft.Column(
            [ft.Container(contenido, expand=True), ft.Row([pie], alignment=ft.MainAxisAlignment.END)],
            spacing=12, expand=True,
        )
    content_area = ft.Container(content=contenido, expand=True, padding=28, bgcolor=theme.PAGE_BG)

    return ft.Row([sidebar, content_area], expand=True, spacing=0)


def _selector_usuario(auth, cambiar_usuario) -> ft.Control:
    """Nombre del usuario en la barra lateral; al tocarlo despliega todos los
    usuarios para cambiar de cuenta (el actual aparece tildado)."""
    actual = auth.session.username
    items = [ft.PopupMenuItem(content=ft.Text("Cambiar de usuario", size=11, color=theme.TEXT_MUTED), height=32)]
    for username in auth.listar_usernames():
        es_actual = username == actual
        items.append(ft.PopupMenuItem(
            content=ft.Text(username, size=13, weight=ft.FontWeight.W_600 if es_actual else ft.FontWeight.NORMAL),
            icon=ft.Icons.CHECK_ROUNDED if es_actual else ft.Icons.PERSON_OUTLINE_ROUNDED,
            on_click=None if es_actual else (lambda e, u=username: cambiar_usuario(u)),
        ))
    return ft.PopupMenuButton(
        content=ft.Row(
            [
                components.avatar(auth.obtener_perfil(auth.session.usuario_id), radio=14),
                ft.Text(actual, size=13, color=theme.TEXT_SECONDARY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Icon(ft.Icons.UNFOLD_MORE_ROUNDED, size=16, color=theme.TEXT_MUTED),
            ],
            spacing=8,
        ),
        items=items,
        tooltip="Cambiar de usuario",
        menu_position=ft.PopupMenuPosition.OVER,
    )


def _nav_button(key, icon, label, color, bg, is_active, on_click):
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(theme.to_icon(icon), color=color if is_active else theme.TEXT_MUTED, size=18),
                ft.Text(label, size=14, color=color if is_active else theme.TEXT_SECONDARY, weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL),
            ],
            spacing=12,
        ),
        bgcolor=bg if is_active else None,
        padding=theme.pad(horizontal=20, vertical=12),
        margin=theme.margin_h(10),
        border_radius=theme.RADIUS_SM,
        on_click=lambda e, k=key: on_click(k),
        ink=True,
    )
