from home_budget.app.services.logs import leer_log
from home_budget.ui.desktop.login_view import _entrar


def test_entrar_abre_la_app_si_no_hay_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    abierta, errores = [], []

    _entrar(lambda: abierta.append(True), errores.append)

    assert abierta == [True] and errores == []


def test_entrar_muestra_y_registra_el_error_si_la_app_no_abre(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    errores = []

    def falla():
        raise RuntimeError("algo se rompio")

    _entrar(falla, errores.append)

    assert len(errores) == 1
    assert "RuntimeError: algo se rompio" in errores[0]
    assert "kakeibo_debug.log" in errores[0]
    assert "RuntimeError: algo se rompio" in leer_log()
