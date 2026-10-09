"""Armazon de la version movil: encabezado con el menu hamburguesa, que
despliega todas las secciones, y debajo el contenido de la seccion elegida.

Las pantallas que se abren desde otra (un formulario) se apilan encima: el
encabezado pasa a mostrar la flecha de volver en lugar del menu."""
from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from ...app.auth.service import AuthService
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.cambio import CambioDivisaService
from ...app.services.config import CLAVE_TEMA, ConfigService
from ...app.services.dashboard import DashboardService
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.inversiones import InversionService
from ...app.services.movimientos import MovimientoService
from ...app.services.prestamos import PrestamoService
from ...app.services.tarjetas import TarjetaService
from ...app.services.vencimientos import VencimientoService
from .. import theme
from ..desktop import components
from . import componentes as mc
from .configuracion_view import build_configuracion_view
from .consultas_view import build_calendario_view
from .gastos_fijos_view import build_gastos_fijos_view
from .inversiones_view import build_inversiones_view
from .movimientos_view import build_movimientos_view
from .prestamos_view import build_prestamos_view
from .resumen_view import build_resumen_view
from .sincronizacion_view import build_sincronizacion_view
from .tarjetas_view import build_tarjetas_view

ANCHO_MENU = 290
# Secciones que no figuran en el menu: a Configuracion se entra tocando la foto de perfil.
FUERA_DEL_MENU = {"configuracion"}


@dataclass
class Servicios:
    """Los servicios de la capa app/, los mismos que usa la version de escritorio."""
    categorias: CategoriaRepository
    movimientos: MovimientoService
    tarjetas: TarjetaService
    prestamos: PrestamoService
    dashboard: DashboardService
    cambio: CambioDivisaService
    gastos_fijos: GastoFijoService
    config: ConfigService
    inversiones: InversionService
    vencimientos: VencimientoService


def _secciones():
    # Se arma al momento (no a nivel de modulo) para tomar la paleta activa.
    # Compra mensual e Historial no estan: son exclusivas de la version de escritorio.
    return [
        ("resumen", "space_dashboard_rounded", "Resumen", theme.DASHBOARD_COLOR, theme.DASHBOARD_BG),
        ("movimientos", "swap_vert_rounded", "Movimientos", theme.MOVIMIENTOS_COLOR, theme.MOVIMIENTOS_BG),
        ("gastos_fijos", "event_repeat_rounded", "Gastos fijos", theme.MOVIMIENTOS_COLOR, theme.MOVIMIENTOS_BG),
        ("tarjetas", "credit_card_rounded", "Tarjetas", theme.TARJETAS_COLOR, theme.TARJETAS_BG),
        ("prestamos", "account_balance_rounded", "Préstamos", theme.PRESTAMOS_COLOR, theme.PRESTAMOS_BG),
        ("inversiones", "trending_up_rounded", "Inversiones", theme.INVERSIONES_COLOR, theme.INVERSIONES_BG),
        ("calendario", "calendar_month_rounded", "Calendario", theme.CALENDARIO_COLOR, theme.CALENDARIO_BG),
        ("sincronizacion", "sync_rounded", "Sincronización", theme.CALENDARIO_COLOR, theme.CALENDARIO_BG),
        ("configuracion", "settings_rounded", "Configuración", theme.CONFIG_COLOR, theme.CONFIG_BG),
    ]


def build_mobile_shell(page: ft.Page, conn, auth: AuthService, huella, on_logout) -> ft.Control:
    tarjetas = TarjetaService(conn)
    prestamos = PrestamoService(conn)
    gastos_fijos = GastoFijoService(conn)
    servicios = Servicios(
        categorias=CategoriaRepository(conn),
        movimientos=MovimientoService(conn),
        tarjetas=tarjetas,
        prestamos=prestamos,
        dashboard=DashboardService(conn),
        cambio=CambioDivisaService(conn),
        gastos_fijos=gastos_fijos,
        config=ConfigService(conn),
        inversiones=InversionService(conn),
        vencimientos=VencimientoService(tarjetas, prestamos, gastos_fijos),
    )

    raiz = ft.Container(expand=True)
    # pila: pantallas abiertas encima de la seccion, cada una (titulo, color, contenido).
    # contenido: la vista de la seccion actual; se conserva al abrir y cerrar el menu.
    estado = {"seccion": "resumen", "pila": [], "menu": False, "contenido": None}

    def tocar():
        if auth.session is not None:
            auth.session.touch()

    def contenido_seccion() -> ft.Control:
        clave = estado["seccion"]
        if clave == "resumen":
            return build_resumen_view(page, nav, servicios)
        if clave == "movimientos":
            return build_movimientos_view(page, nav, servicios)
        if clave == "tarjetas":
            return build_tarjetas_view(page, nav, servicios)
        if clave == "gastos_fijos":
            return build_gastos_fijos_view(page, nav, servicios)
        if clave == "prestamos":
            return build_prestamos_view(page, nav, servicios)
        if clave == "inversiones":
            return build_inversiones_view(page, nav, servicios)
        if clave == "calendario":
            return build_calendario_view(page, servicios)
        if clave == "sincronizacion":
            return build_sincronizacion_view(page, nav)
        return build_configuracion_view(page, nav, servicios, auth, huella, cambiar_tema, perfil_cambiado)

    def redibujar(rearmar: bool = True):
        tocar()
        if estado["pila"]:
            titulo, color, contenido = estado["pila"][-1]
            raiz.content = ft.Column([_encabezado_interno(titulo, color, volver), ft.Container(contenido, expand=True)],
                                     spacing=0, expand=True)
        else:
            if rearmar or estado["contenido"] is None:
                estado["contenido"] = contenido_seccion()
            capas = [ft.Column(
                [
                    _encabezado(estado["seccion"], auth, lambda e: alternar_menu(True), cambiar_seccion),
                    ft.Container(estado["contenido"], expand=True),
                ],
                spacing=0, expand=True,
            )]
            if estado["menu"]:
                capas += _menu(estado["seccion"], auth, huella, cambiar_seccion, lambda e: alternar_menu(False), cambiar_tema, salir)
            raiz.content = ft.Stack(capas, expand=True)
        page.update()

    def alternar_menu(abierto: bool):
        estado["menu"] = abierto
        redibujar(rearmar=False)

    def cambiar_seccion(clave: str):
        estado["seccion"] = clave
        estado["menu"] = False
        estado["pila"].clear()
        page.overlay.clear()
        redibujar()

    def abrir(titulo: str, constructor, color: str | None = None):
        estado["pila"].append((titulo, color or theme.DASHBOARD_COLOR, constructor()))
        redibujar(rearmar=False)

    def volver():
        # La pantalla de abajo se vuelve a armar: asi muestra lo que se acaba de cargar.
        if estado["pila"]:
            estado["pila"].pop()
        page.overlay.clear()
        redibujar()

    def avisar(mensaje: str):
        page.show_dialog(ft.SnackBar(ft.Text(mensaje)))

    def cambiar_tema(oscuro: bool):
        servicios.config.guardar(CLAVE_TEMA, "oscuro" if oscuro else "claro")
        theme.aplicar_modo(oscuro)
        page.theme_mode = ft.ThemeMode.DARK if oscuro else ft.ThemeMode.LIGHT
        page.bgcolor = theme.PAGE_BG
        redibujar()

    def perfil_cambiado(mensaje: str):
        # Se vuelve a armar todo: el encabezado muestra la foto y el menu, el nombre.
        redibujar()
        avisar(mensaje)

    def salir(_e=None):
        auth.logout()
        on_logout()

    nav = mc.Navegacion(abrir=abrir, volver=volver, avisar=avisar)
    redibujar()
    return raiz


def _encabezado(seccion: str, auth: AuthService, abrir_menu, cambiar_seccion) -> ft.Control:
    titulo = next(label for clave, _icono, label, _color, _bg in _secciones() if clave == seccion)
    return ft.Container(
        ft.Row(
            [
                ft.IconButton(icon=ft.Icons.MENU_ROUNDED, icon_color=theme.TEXT_PRIMARY, tooltip="Menú", on_click=abrir_menu),
                ft.Text(titulo, size=19, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                ft.IconButton(icon=ft.Icons.SYNC_ROUNDED, icon_color=theme.TEXT_SECONDARY, tooltip="Sincronizar con la computadora",
                              on_click=lambda e: cambiar_seccion("sincronizacion")),
                ft.Container(components.avatar(auth.obtener_perfil(auth.session.usuario_id), radio=15), border_radius=20, padding=3,
                             on_click=lambda e: cambiar_seccion("configuracion"), ink=True, tooltip="Configuración"),
            ],
            spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE, padding=theme.pad_only(left=4, top=6, right=12, bottom=6),
        border=ft.border.Border(bottom=ft.border.BorderSide(1, theme.BORDER)),
    )


def _encabezado_interno(titulo: str, color: str, volver) -> ft.Control:
    return ft.Container(
        ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, icon_color=color, tooltip="Volver", on_click=lambda e: volver()),
                ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True, no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE, padding=theme.pad_only(left=4, top=6, right=12, bottom=6),
        border=ft.border.Border(bottom=ft.border.BorderSide(1, theme.BORDER)),
    )


def _menu(seccion: str, auth: AuthService, huella, cambiar_seccion, cerrar, cambiar_tema, salir) -> list[ft.Control]:
    """El menu desplegado: un fondo oscuro que lo cierra al tocarlo y, encima,
    el panel con las secciones, el tema y la sesion."""
    def item(clave, icono, label, color, bg):
        activa = clave == seccion
        return ft.Container(
            ft.Row(
                [
                    ft.Icon(theme.to_icon(icono), size=20, color=color if activa else theme.TEXT_MUTED),
                    ft.Text(label, size=15, color=color if activa else theme.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_600 if activa else ft.FontWeight.NORMAL),
                ],
                spacing=14,
            ),
            bgcolor=bg if activa else None, padding=theme.pad(horizontal=16, vertical=12), border_radius=theme.RADIUS_SM,
            on_click=lambda e: cambiar_seccion(clave), ink=True,
        )

    def al_cambiar_huella(e):
        if e.control.value:
            auth.activar_huella()
        else:
            auth.desactivar_huella()

    perfil = auth.obtener_perfil(auth.session.usuario_id)
    # Solo en telefonos con huella cargada: en el resto la opcion no aparece.
    fila_huella = ft.Container(
        ft.Row(
            [
                ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, size=20, color=theme.TEXT_SECONDARY),
                ft.Text("Entrar con huella", size=14, color=theme.TEXT_PRIMARY, expand=True),
                ft.Switch(value=auth.usuario_con_huella() == auth.session.username, on_change=al_cambiar_huella),
            ],
            spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=theme.pad(horizontal=16), visible=huella.disponible,
    )
    panel = ft.Container(
        ft.Column(
            [
                ft.Container(
                    ft.Row(
                        [
                            components.logo(28),
                            ft.Text("Kakeibo", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                            ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_color=theme.TEXT_SECONDARY, tooltip="Cerrar menú", on_click=cerrar),
                        ],
                        spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=theme.pad_only(left=16, top=10, right=4, bottom=6),
                ),
                ft.Column([item(*s) for s in _secciones() if s[0] not in FUERA_DEL_MENU], spacing=2, scroll=ft.ScrollMode.AUTO, expand=True),
                mc.separador(),
                fila_huella,
                ft.Container(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.DARK_MODE_ROUNDED, size=20, color=theme.TEXT_SECONDARY),
                            ft.Text("Modo oscuro", size=14, color=theme.TEXT_PRIMARY, expand=True),
                            ft.Switch(value=theme.MODO_OSCURO, on_change=lambda e: cambiar_tema(e.control.value)),
                        ],
                        spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=theme.pad(horizontal=16),
                ),
                ft.Container(
                    ft.Row(
                        [
                            ft.Container(
                                ft.Row(
                                    [
                                        components.avatar(perfil, radio=15),
                                        ft.Text(perfil.username, size=14, color=theme.TEXT_SECONDARY, expand=True, no_wrap=True,
                                                overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                    spacing=10,
                                ),
                                expand=True, on_click=lambda e: cambiar_seccion("configuracion"), tooltip="Configuración",
                            ),
                            ft.TextButton("Cerrar sesión", icon=ft.Icons.LOGOUT_ROUNDED, on_click=salir,
                                          style=ft.ButtonStyle(color=theme.EXPENSE_RED)),
                        ],
                        spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=theme.pad_only(left=16, right=8, bottom=10),
                ),
            ],
            spacing=4,
        ),
        width=ANCHO_MENU, top=0, bottom=0, left=0, bgcolor=theme.SURFACE, padding=theme.pad(horizontal=6),
        border=theme.border_right(1, theme.BORDER),
        shadow=ft.BoxShadow(blur_radius=24, color=ft.Colors.with_opacity(0.3, "#000000")),
    )
    fondo = ft.Container(bgcolor=ft.Colors.with_opacity(0.45, "#000000"), left=0, top=0, right=0, bottom=0, on_click=cerrar)
    return [fondo, panel]
