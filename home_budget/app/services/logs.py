"""Acceso al archivo de log de errores de la app (kakeibo_debug.log).

Los distintos puntos de la app que atrapan excepciones inesperadas (main.py,
app_shell.py, asistente_view.py) escriben ahi con la misma ruta relativa: al
correr empaquetada con flet build windows, el proceso queda con el
directorio de trabajo puesto en la carpeta del ejecutable, junto a la base."""
from __future__ import annotations

from pathlib import Path

NOMBRE_ARCHIVO = "kakeibo_debug.log"


def ruta_log() -> Path:
    return Path(NOMBRE_ARCHIVO).resolve()


def leer_log(max_caracteres: int = 20000) -> str:
    """Contenido del log, recortado a los ultimos `max_caracteres` si es muy
    largo (para no tildar la UI con un archivo gigante). Devuelve "" si
    todavia no hay ningun error registrado."""
    ruta = ruta_log()
    if not ruta.exists():
        return ""
    contenido = ruta.read_text(encoding="utf-8", errors="replace")
    if len(contenido) > max_caracteres:
        contenido = (
            f"[... se omitió el principio del log, mostrando los últimos {max_caracteres} caracteres ...]\n\n"
            + contenido[-max_caracteres:]
        )
    return contenido
