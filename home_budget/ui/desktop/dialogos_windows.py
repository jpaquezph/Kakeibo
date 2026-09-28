"""Dialogos nativos de Windows via ctypes (ft.FilePicker no funciona en el
cliente de Windows de esta version de Flet, ver app_shell._elegir_carpeta_backup)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class _OpenFileNameW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", ctypes.c_void_p),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


_GetOpenFileNameW = ctypes.windll.comdlg32.GetOpenFileNameW
_GetOpenFileNameW.restype = wintypes.BOOL
_GetOpenFileNameW.argtypes = [ctypes.POINTER(_OpenFileNameW)]

_OFN_NOCHANGEDIR = 0x00000008  # sin esto el dialogo cambia el directorio de trabajo (y la ruta del log)
_OFN_PATHMUSTEXIST = 0x00000800
_OFN_FILEMUSTEXIST = 0x00001000


def elegir_imagen() -> str | None:
    """Abre el selector nativo de archivos filtrando PNG/JPG. None si se cancela."""
    # El filtro son pares "descripcion\0patron\0" terminados en un \0 extra;
    # se pasa como buffer porque un str con \0 intermedios no se convierte a LPCWSTR.
    filtro = ctypes.create_unicode_buffer("Imágenes (PNG, JPG)\0*.png;*.jpg;*.jpeg\0\0")
    archivo = ctypes.create_unicode_buffer(1024)

    ofn = _OpenFileNameW()
    ofn.lStructSize = ctypes.sizeof(_OpenFileNameW)
    ofn.lpstrFilter = ctypes.cast(filtro, wintypes.LPCWSTR)
    ofn.lpstrFile = ctypes.cast(archivo, wintypes.LPWSTR)
    ofn.nMaxFile = len(archivo)
    ofn.lpstrTitle = "Elegí tu imagen de perfil"
    ofn.Flags = _OFN_NOCHANGEDIR | _OFN_PATHMUSTEXIST | _OFN_FILEMUSTEXIST

    if not _GetOpenFileNameW(ctypes.byref(ofn)):
        return None
    return archivo.value or None
