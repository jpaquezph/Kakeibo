"""Punto de entrada de Kakeibo movil (Android).

En la computadora abre una ventana del tamano de un telefono, para ver y
probar las pantallas sin instalar nada en el celular."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import flet as ft

from home_budget.app import database
from home_budget.app.auth.service import AuthService
from home_budget.app.services.config import CLAVE_TEMA, ConfigService
from home_budget.app.services.logs import registrar_error
from home_budget.ui import theme
from home_budget.ui.mobile.acceso_view import build_acceso_view, build_bloqueo_view
from home_budget.ui.mobile.app_shell import build_mobile_shell
from home_budget.ui.mobile.huella import Huella

INACTIVITY_CHECK_INTERVAL_SECONDS = 10
# Ventana de prueba en la computadora: un telefono mediano en vertical.
ANCHO_PREVIA = 400
ALTO_PREVIA = 820


def _ruta_base(page: ft.Page) -> Path:
    # En el telefono la carpeta de la app es de solo lectura: la base va en
    # la carpeta de datos que el sistema le reserva a la app.
    datos = os.environ.get("FLET_APP_STORAGE_DATA")
    if datos and page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
        return Path(datos) / "kakeibo.db"
    return database.DEFAULT_DB_PATH


async def main(page: ft.Page) -> None:
    page.title = "Kakeibo"
    en_telefono = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    ruta_base = _ruta_base(page)
    if en_telefono:
        # El log de errores se escribe en la carpeta de trabajo: que sea la de datos, donde se puede escribir.
        os.chdir(ruta_base.parent)

    conn = database.get_connection(ruta_base)
    database.init_db(conn)
    auth = AuthService(conn)

    oscuro = ConfigService(conn).obtener(CLAVE_TEMA) == "oscuro"
    theme.aplicar_modo(oscuro)
    page.theme = theme.app_theme()
    page.dark_theme = theme.app_theme()
    page.theme_mode = ft.ThemeMode.DARK if oscuro else ft.ThemeMode.LIGHT
    page.bgcolor = theme.PAGE_BG
    page.padding = 0
    if not en_telefono:
        page.window.width = ANCHO_PREVIA
        page.window.height = ALTO_PREVIA
        page.window.resizable = False

    # SafeArea: deja libre la barra de estado y la de gestos del telefono.
    root = ft.Container(expand=True)
    page.add(ft.SafeArea(root, expand=True))

    huella = Huella()
    await huella.preparar(page)

    monitor_iniciado = {"value": False}

    def mostrar_login(usuario: str | None = None):
        page.overlay.clear()
        try:
            root.content = build_acceso_view(page, auth, huella, on_success=lambda session: mostrar_app(), usuario_inicial=usuario)
        except Exception:
            registrar_error("mostrar_login")
            raise
        page.update()

    def mostrar_lock():
        try:
            root.content = build_bloqueo_view(page, auth, huella, on_unlock=mostrar_app)
        except Exception:
            registrar_error("mostrar_lock")
            raise
        page.update()

    def mostrar_app():
        # Si algo falla se vuelve a la pantalla anterior (login o bloqueo),
        # que registra el error y lo muestra.
        anterior = root.content
        try:
            root.content = build_mobile_shell(page, conn, auth, huella, on_logout=mostrar_login)
            page.update()
        except Exception:
            root.content = anterior
            raise
        if not monitor_iniciado["value"]:
            monitor_iniciado["value"] = True
            page.run_task(monitor_inactividad)

    async def monitor_inactividad():
        while True:
            await asyncio.sleep(INACTIVITY_CHECK_INTERVAL_SECONDS)
            if auth.session is not None and auth.session.check_inactivity():
                mostrar_lock()

    mostrar_login()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
