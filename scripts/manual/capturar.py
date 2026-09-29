"""Abre Kakeibo con la base de ejemplo y recorre las pantallas sacando las
capturas del manual. Uso: python capturar.py [nombre_de_escena ...]"""
from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROYECTO))
sys.path.insert(0, str(AQUI))
os.chdir(AQUI)

import datos_demo  # noqa: E402
import home_budget.app.database as database  # noqa: E402

DB = AQUI / "demo.db"
datos_demo.crear(DB)
database.DEFAULT_DB_PATH = DB

import flet as ft  # noqa: E402

from home_budget.app.services import inicio_windows  # noqa: E402

# Como en la app instalada: el interruptor "Iniciar con Windows" habilitado y
# apagado. Nunca se activa en las capturas (no se toca el registro de Windows).
inicio_windows.ruta_ejecutable = lambda: Path(r"C:\Users\Usuario\AppData\Local\Kakeibo\Kakeibo.exe")
inicio_windows.esta_activado = lambda clave=inicio_windows.CLAVE_RUN: False
inicio_windows.activar = lambda *a, **k: None
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")

import main as kakeibo_main  # noqa: E402
from escenas import ESCENAS  # noqa: E402
from motor import TITULO_VENTANA, Motor  # noqa: E402

SOLO = set(sys.argv[1:])


def app(page: ft.Page):
    kakeibo_main.main(page)
    page.title = TITULO_VENTANA  # titulo unico: asi se captura esta ventana y no la app real
    page.window.width, page.window.height = 1240, 800
    page.update()

    async def recorrido():
        m = Motor(page, AQUI / "capturas")
        await asyncio.sleep(3)
        try:
            if SOLO and "acceso" not in SOLO and "todo" not in SOLO:
                import escenas
                await escenas.entrar_rapido(m, cerrar_aviso="principal" not in SOLO)
            for nombre, escena in ESCENAS:
                if SOLO and nombre not in SOLO and "todo" not in SOLO:
                    continue
                print(f"== {nombre}")
                await escena(m)
        except Exception:
            traceback.print_exc()
        finally:
            print("FIN")
            try:
                await page.window.destroy()
            except Exception:
                pass
            await asyncio.sleep(1)
            os._exit(0)

    page.run_task(recorrido)


ft.run(app, assets_dir=str(PROYECTO / "assets"))
