"""Validacion de la imagen de perfil: solo PNG o JPEG, con limite de peso y
de dimensiones. Se leen las dimensiones del encabezado del archivo a mano
para no sumar Pillow como dependencia solo para esto."""
from __future__ import annotations

import struct

MAX_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_LADO_PX = 2048


class ImagenInvalidaError(ValueError):
    pass


def _dimensiones_png(datos: bytes) -> tuple[int, int]:
    # Firma de 8 bytes + chunk IHDR: largo(4) tipo(4) ancho(4) alto(4)
    if len(datos) < 24 or datos[12:16] != b"IHDR":
        raise ImagenInvalidaError("El archivo PNG está dañado")
    return struct.unpack(">II", datos[16:24])


def _dimensiones_jpeg(datos: bytes) -> tuple[int, int]:
    # Se recorren los segmentos hasta el marcador SOF (Start Of Frame), que
    # trae alto y ancho. Los marcadores SOF son C0-CF salvo C4, C8 y CC.
    i = 2
    while i + 9 < len(datos):
        if datos[i] != 0xFF:
            i += 1
            continue
        marcador = datos[i + 1]
        if marcador in (0xD8, 0x01) or 0xD0 <= marcador <= 0xD7:
            i += 2
            continue
        largo = struct.unpack(">H", datos[i + 2:i + 4])[0]
        if 0xC0 <= marcador <= 0xCF and marcador not in (0xC4, 0xC8, 0xCC):
            alto, ancho = struct.unpack(">HH", datos[i + 5:i + 9])
            return ancho, alto
        i += 2 + largo
    raise ImagenInvalidaError("No se pudo leer el tamaño de la imagen JPEG")


def validar_imagen(datos: bytes) -> None:
    """Lanza ImagenInvalidaError si la imagen no es PNG/JPEG o supera los limites."""
    if len(datos) > MAX_BYTES:
        raise ImagenInvalidaError(f"La imagen pesa {len(datos) / 1024 / 1024:.1f} MB; el máximo es {MAX_BYTES // 1024 // 1024} MB")
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        ancho, alto = _dimensiones_png(datos)
    elif datos.startswith(b"\xff\xd8"):
        ancho, alto = _dimensiones_jpeg(datos)
    else:
        raise ImagenInvalidaError("Formato no soportado: usá una imagen PNG o JPG")
    if ancho > MAX_LADO_PX or alto > MAX_LADO_PX:
        raise ImagenInvalidaError(f"La imagen mide {ancho}x{alto} px; el máximo es {MAX_LADO_PX}x{MAX_LADO_PX} px")
