"""Punto de entrada de Kakeibo (version escritorio)."""
from __future__ import annotations

import asyncio

import flet as ft

from home_budget.app.auth.service import AuthService
from home_budget.app.database import DEFAULT_DB_PATH, get_connection, init_db
from home_budget.ui import theme
from home_budget.ui.desktop.app_shell import build_app_shell
from home_budget.ui.desktop.login_view import build_lock_view, build_login_view

INACTIVITY_CHECK_INTERVAL_SECONDS = 10


def main(page: ft.Page) -> None:
    page.title = "Kakeibo — Gestión de gastos del hogar"
    page.theme = theme.app_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = theme.PAGE_BG
    page.padding = 0
    page.window.width = 1180
    page.window.height = 780
    page.window.min_width = 900
    page.window.min_height = 600

    conn = get_connection(DEFAULT_DB_PATH)
    init_db(conn)
    auth = AuthService(conn)

    root = ft.Container(expand=True, bgcolor=theme.PAGE_BG)
    page.add(root)

    monitor_task_started = {"value": False}

    def mostrar_login():
        root.content = build_login_view(page, auth, on_success=lambda session: mostrar_app())
        page.update()

    def mostrar_lock():
        root.content = build_lock_view(page, auth, on_unlock=mostrar_app)
        page.update()

    def mostrar_app():
        root.content = build_app_shell(page, conn, auth, on_logout=mostrar_login)
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
