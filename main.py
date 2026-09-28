"""Punto de entrada de Kakeibo (version escritorio)."""
from __future__ import annotations

import asyncio

import flet as ft

from home_budget.app.auth.service import AuthService
from home_budget.app.database import DEFAULT_DB_PATH, get_connection, init_db
from home_budget.app.services.config import CLAVE_TEMA, ConfigService
from home_budget.ui import theme
from home_budget.ui.desktop.app_shell import build_app_shell
from home_budget.ui.desktop.login_view import build_lock_view, build_login_view

INACTIVITY_CHECK_INTERVAL_SECONDS = 10


def main(page: ft.Page) -> None:
    page.title = "Kakeibo — Gestión de gastos del hogar"

    conn = get_connection(DEFAULT_DB_PATH)
    init_db(conn)
    auth = AuthService(conn)

    oscuro = ConfigService(conn).obtener(CLAVE_TEMA) == "oscuro"
    theme.aplicar_modo(oscuro)
    page.theme = theme.app_theme()
    page.dark_theme = theme.app_theme()
    page.theme_mode = ft.ThemeMode.DARK if oscuro else ft.ThemeMode.LIGHT
    page.bgcolor = theme.PAGE_BG
    page.padding = 0
    page.window.width = 1180
    page.window.height = 780
    page.window.min_width = 900
    page.window.min_height = 600

    # Sin bgcolor propio: toma el de la pagina, que se actualiza al cambiar de tema.
    root = ft.Container(expand=True)
    page.add(root)

    monitor_task_started = {"value": False}
    aviso_vencimientos_mostrado = {"value": False}

    def _log_error(etiqueta: str) -> None:
        import traceback
        with open("kakeibo_debug.log", "a", encoding="utf-8") as f:
            f.write(f"--- error en {etiqueta} ---\n")
            f.write(traceback.format_exc())
            f.write("\n")

    def mostrar_login(usuario: str | None = None):
        page.overlay.clear()
        try:
            root.content = build_login_view(page, auth, on_success=lambda session: mostrar_app(), usuario_inicial=usuario)
        except Exception:
            _log_error("mostrar_login")
            raise
        page.update()

    def mostrar_lock():
        try:
            root.content = build_lock_view(page, auth, on_unlock=mostrar_app)
        except Exception:
            _log_error("mostrar_lock")
            raise
        page.update()

    def mostrar_app():
        try:
            # El aviso de vencimientos sale una sola vez por apertura de la app,
            # no cada vez que se desbloquea o se vuelve a iniciar sesion.
            root.content = build_app_shell(
                page, conn, auth, on_logout=mostrar_login,
                mostrar_aviso_vencimientos=not aviso_vencimientos_mostrado["value"],
            )
            aviso_vencimientos_mostrado["value"] = True
        except Exception:
            _log_error("mostrar_app")
            raise
        page.update()
        if not monitor_task_started["value"]:
            monitor_task_started["value"] = True
            page.run_task(monitor_inactividad)

    async def monitor_inactividad():
        while True:
            await asyncio.sleep(INACTIVITY_CHECK_INTERVAL_SECONDS)
            if auth.session is not None and auth.session.check_inactivity():
                mostrar_lock()

    def registrar_actividad(_e=None):
        if auth.session is not None and not auth.session.locked:
            auth.session.touch()

    page.on_keyboard_event = registrar_actividad

    mostrar_login()


if __name__ == "__main__":
    ft.run(main)
