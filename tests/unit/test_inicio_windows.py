import sys
from pathlib import Path

import pytest

from home_budget.app.services import inicio_windows

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="usa el registro de Windows")

# Clave propia de los tests: nunca se toca la clave Run real del usuario.
CLAVE_TEST = r"Software\KakeiboTests\Run"


@pytest.fixture
def clave():
    import winreg

    yield CLAVE_TEST
    for sub in (CLAVE_TEST, r"Software\KakeiboTests"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except FileNotFoundError:
            pass


def test_activar_y_desactivar_inicio_con_windows(clave):
    import winreg

    exe = Path(r"C:\Programas\Kakeibo\Kakeibo.exe")
    assert not inicio_windows.esta_activado(clave)

    inicio_windows.activar(exe, clave)
    assert inicio_windows.esta_activado(clave)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
        valor, _ = winreg.QueryValueEx(k, "Kakeibo")
    assert valor == f'"{exe}"'  # entre comillas: la ruta puede tener espacios

    inicio_windows.desactivar(clave)
    assert not inicio_windows.esta_activado(clave)
    inicio_windows.desactivar(clave)  # desactivar dos veces no falla


def test_sin_app_instalada_no_se_puede_activar(clave, monkeypatch):
    monkeypatch.setattr(inicio_windows, "ruta_ejecutable", lambda: None)

    with pytest.raises(ValueError, match="app instalada"):
        inicio_windows.activar(clave=clave)
    assert not inicio_windows.esta_activado(clave)


def test_desde_el_codigo_no_hay_ejecutable():
    """Corriendo desde el proyecto (tests) no hay Kakeibo.exe en la cadena de carpetas."""
    assert inicio_windows.ruta_ejecutable() is None


def test_encuentra_el_ejecutable_de_la_instalacion(tmp_path, monkeypatch):
    """Instalada con flet build: <instalacion>\\Kakeibo.exe y el codigo en <instalacion>\\app\\..."""
    (tmp_path / "Kakeibo.exe").write_bytes(b"")
    modulo = tmp_path / "app" / "home_budget" / "app" / "services" / "inicio_windows.py"
    monkeypatch.setattr(inicio_windows, "__file__", str(modulo))

    assert inicio_windows.ruta_ejecutable() == tmp_path / "Kakeibo.exe"
