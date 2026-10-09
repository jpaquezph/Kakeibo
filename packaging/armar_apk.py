"""Arma el APK de Kakeibo movil.

    .venv-movil\\Scripts\\python packaging\\armar_apk.py

Copia a build/movil_src solo lo que la app necesita (codigo, migraciones y
assets) y compila desde ahi con `flet build apk`. Asi el APK nunca lleva una
base de datos, logs ni backups: cada instalacion arranca vacia.

Requiere el entorno .venv-movil (Flet 1.0 + flet-local-auth). La primera
corrida descarga el JDK, el SDK de Android y la version de Flutter que pide
Flet; tarda bastante. El APK queda en dist/android/.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARMADO = RAIZ / "build" / "movil_src"
SALIDA = RAIZ / "dist" / "android"

# Nada de esto puede terminar adentro del APK.
PROHIBIDOS = ("*.db", "*.log", "__pycache__", "*.pyc")


def preparar() -> None:
    if ARMADO.exists():
        shutil.rmtree(ARMADO)
    ARMADO.mkdir(parents=True)
    ignorar = shutil.ignore_patterns(*PROHIBIDOS)
    for carpeta in ("home_budget", "migrations", "assets"):
        shutil.copytree(RAIZ / carpeta, ARMADO / carpeta, ignore=ignorar)
    # Flet busca main.py: el punto de entrada movil se copia con ese nombre.
    shutil.copy(RAIZ / "main_movil.py", ARMADO / "main.py")
    shutil.copy(RAIZ / "packaging" / "movil" / "pyproject.toml", ARMADO / "pyproject.toml")

    colados = [p for patron in ("*.db", "*.log") for p in ARMADO.rglob(patron)]
    if colados:
        raise SystemExit(f"Hay archivos que no pueden ir en el APK: {colados}")


def compilar() -> int:
    flet = Path(sys.executable).with_name("flet.exe")
    return subprocess.call([str(flet), "build", "apk", str(ARMADO), "-o", str(SALIDA), "--yes", "--no-rich-output"])


if __name__ == "__main__":
    preparar()
    codigo = compilar()
    if codigo == 0:
        print(f"APK listo en {SALIDA}")
    sys.exit(codigo)
