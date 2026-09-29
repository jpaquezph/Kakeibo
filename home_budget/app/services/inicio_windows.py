"""Iniciar Kakeibo junto con Windows.

Se usa la clave Run del usuario (HKCU), que no pide permisos de
administrador y es la que muestra el Administrador de tareas en "Inicio".
Solo tiene sentido en la app instalada: en desarrollo no hay Kakeibo.exe.
"""
from __future__ import annotations

import sys
from pathlib import Path

CLAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE_VALOR = "Kakeibo"
NOMBRE_EXE = "Kakeibo.exe"


def ruta_ejecutable() -> Path | None:
    """El Kakeibo.exe de la instalacion, o None si la app no corre instalada.

    Con `flet build windows` el codigo vive en <instalacion>\\app y el
    ejecutable en <instalacion>, asi que se busca subiendo desde este archivo.
    """
    exe = Path(sys.executable)
    if exe.name.lower() == NOMBRE_EXE.lower():
        return exe
    for carpeta in Path(__file__).resolve().parents:
        candidato = carpeta / NOMBRE_EXE
        if candidato.is_file():
            return candidato
    return None


def _comando(exe: Path) -> str:
    return f'"{exe}"'


def esta_activado(clave: str = CLAVE_RUN) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            winreg.QueryValueEx(k, NOMBRE_VALOR)
            return True
    except FileNotFoundError:
        return False


def activar(exe: Path | None = None, clave: str = CLAVE_RUN) -> None:
    import winreg

    exe = exe or ruta_ejecutable()
    if exe is None:
        raise ValueError("Esta opción solo está disponible en la app instalada.")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, clave) as k:
        winreg.SetValueEx(k, NOMBRE_VALOR, 0, winreg.REG_SZ, _comando(exe))


def desactivar(clave: str = CLAVE_RUN) -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, NOMBRE_VALOR)
    except FileNotFoundError:
        pass
