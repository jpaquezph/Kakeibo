from home_budget.app.services.logs import NOMBRE_ARCHIVO, leer_log, ruta_log


def test_ruta_log_apunta_al_nombre_esperado(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ruta_log().name == NOMBRE_ARCHIVO


def test_leer_log_sin_archivo_devuelve_vacio(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert leer_log() == ""


def test_leer_log_devuelve_el_contenido_completo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / NOMBRE_ARCHIVO).write_text("--- error en x ---\nTraceback...\n", encoding="utf-8")

    assert leer_log() == "--- error en x ---\nTraceback...\n"


def test_leer_log_trunca_archivos_muy_largos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    contenido_grande = "x" * 100
    (tmp_path / NOMBRE_ARCHIVO).write_text(contenido_grande, encoding="utf-8")

    resultado = leer_log(max_caracteres=20)

    assert resultado.endswith("x" * 20)
    assert "se omitió" in resultado
    assert len(resultado) < len(contenido_grande) + 200
