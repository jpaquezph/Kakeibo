from datetime import date

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.app.repositories.categorias import CategoriaRepository
from home_budget.app.services.asistente import (
    AsistenteError,
    AsistenteIAService,
    MODEL_DEFAULT,
    _rango_fechas_de_pregunta,
    construir_contexto,
)
from home_budget.app.services.config import CLAVE_OLLAMA_HOST, CLAVE_OLLAMA_MODEL, ConfigService
from home_budget.app.services.dashboard import DashboardService
from home_budget.app.services.gastos_fijos import GastoFijoService
from home_budget.app.services.movimientos import MovimientoService
from home_budget.app.services.prestamos import PrestamoService
from home_budget.app.services.tarjetas import TarjetaService


# ---- _rango_fechas_de_pregunta ----

HOY = date(2026, 6, 15)


def test_rango_este_mes():
    desde, hasta = _rango_fechas_de_pregunta("¿cuánto gasté este mes?", HOY)
    assert (desde, hasta) == (date(2026, 6, 1), HOY)


def test_rango_mes_pasado():
    desde, hasta = _rango_fechas_de_pregunta("¿qué gasté el mes pasado?", HOY)
    assert (desde, hasta) == (date(2026, 5, 1), date(2026, 5, 31))


def test_rango_este_anio():
    desde, hasta = _rango_fechas_de_pregunta("total de este año", HOY)
    assert (desde, hasta) == (date(2026, 1, 1), HOY)


def test_rango_mes_por_nombre():
    desde, hasta = _rango_fechas_de_pregunta("¿cuánto gasté en marzo?", HOY)
    assert (desde, hasta) == (date(2026, 3, 1), date(2026, 3, 31))


def test_rango_ultimos_n_meses():
    desde, hasta = _rango_fechas_de_pregunta("resumen de los ultimos 6 meses", HOY)
    assert (desde, hasta) == (date(2026, 1, 1), HOY)


def test_rango_por_defecto_sin_mencion_de_fecha():
    desde, hasta = _rango_fechas_de_pregunta("¿en qué categoría gasto más?", HOY)
    assert (desde, hasta) == (date(2026, 4, 1), HOY)


# ---- construir_contexto ----


def _categoria_id(conn, nombre="Comida"):
    cats = {c.nombre: c.id for c in CategoriaRepository(conn).listar()}
    return cats[nombre]


def test_construir_contexto_incluye_movimientos_y_totales(conn):
    from home_budget.app.domain.models import TipoMovimiento

    movimiento_service = MovimientoService(conn)
    movimiento_service.registrar(
        TipoMovimiento.EGRESO, HOY, "Compra semanal", "", Money.from_decimal("15000", Moneda.ARS), _categoria_id(conn),
    )

    contexto = construir_contexto(
        "¿cuánto gasté este mes?",
        DashboardService(conn), movimiento_service, GastoFijoService(conn),
        PrestamoService(conn), TarjetaService(conn), hoy=HOY,
    )

    assert "Compra semanal" in contexto
    assert "Comida" in contexto
    assert "Balance historico total" in contexto
    assert "Movimientos entre 2026-06-01 y 2026-06-15" in contexto


def test_construir_contexto_incluye_gastos_fijos_activos(conn):
    gasto_fijo_service = GastoFijoService(conn)
    gasto_fijo_service.registrar("Alquiler", "", Money.from_decimal("100000", Moneda.ARS), _categoria_id(conn, "Casa"), 10)

    contexto = construir_contexto(
        "¿tengo gastos fijos pendientes?",
        DashboardService(conn), MovimientoService(conn), gasto_fijo_service,
        PrestamoService(conn), TarjetaService(conn), hoy=HOY,
    )

    assert "Gastos fijos activos" in contexto
    assert "Alquiler" in contexto


# ---- AsistenteIAService (con post_json/get_json inyectados, sin red real) ----


def test_modelo_y_host_usan_default_sin_configuracion(conn):
    service = AsistenteIAService(ConfigService(conn))
    assert service.modelo() == MODEL_DEFAULT
    assert service.host() == "http://localhost:11434"


def test_modelo_y_host_usan_lo_configurado(conn):
    config = ConfigService(conn)
    config.guardar(CLAVE_OLLAMA_MODEL, "qwen2.5:7b")
    config.guardar(CLAVE_OLLAMA_HOST, "http://localhost:9999/")

    service = AsistenteIAService(config)

    assert service.modelo() == "qwen2.5:7b"
    assert service.host() == "http://localhost:9999"  # sin la barra final


def test_diagnostico_ollama_no_disponible(conn):
    def get_json_falla(url):
        raise ConnectionError("no se pudo conectar")

    service = AsistenteIAService(ConfigService(conn), get_json=get_json_falla)

    assert service.diagnostico() is not None
    assert "Ollama" in service.diagnostico()


def test_diagnostico_modelo_no_descargado(conn):
    def get_json_ok(url):
        return {"models": [{"name": "otro-modelo:1b"}]}

    service = AsistenteIAService(ConfigService(conn), get_json=get_json_ok)

    aviso = service.diagnostico()
    assert aviso is not None
    assert MODEL_DEFAULT in aviso


def test_diagnostico_ok_cuando_el_modelo_esta_descargado(conn):
    def get_json_ok(url):
        return {"models": [{"name": MODEL_DEFAULT}]}

    service = AsistenteIAService(ConfigService(conn), get_json=get_json_ok)

    assert service.diagnostico() is None


def test_responder_devuelve_texto_de_la_respuesta(conn):
    llamadas = []

    def post_json_fake(url, payload):
        llamadas.append((url, payload))
        return {"message": {"role": "assistant", "content": "Gastaste $15.000 este mes."}}

    service = AsistenteIAService(ConfigService(conn), post_json=post_json_fake)

    respuesta = service.responder("¿cuánto gasté?", "contexto de prueba")

    assert respuesta == "Gastaste $15.000 este mes."
    url, payload = llamadas[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload["model"] == MODEL_DEFAULT
    assert payload["messages"][0]["role"] == "system"
    assert "contexto de prueba" in payload["messages"][-1]["content"]


def test_responder_con_modelo_y_host_explicitos_no_toca_la_config(conn):
    """Regresion: cuando responder() corre en otro hilo (via run_in_executor
    para no bloquear la UI), no puede tocar la conexion sqlite de
    ConfigService (fue creada en el hilo principal) o sqlite3 tira
    'objects created in a thread can only be used in that same thread'.
    Si se pasan modelo/host ya resueltos, no debe llamar a self._config."""

    class ConfigQueNuncaDeberiaTocarse:
        def obtener(self, clave):
            raise AssertionError("responder() no deberia leer la config cuando ya se le paso modelo/host")

    llamadas = []

    def post_json_fake(url, payload):
        llamadas.append((url, payload))
        return {"message": {"content": "ok"}}

    service = AsistenteIAService(ConfigQueNuncaDeberiaTocarse(), post_json=post_json_fake)

    respuesta = service.responder("pregunta", "contexto", modelo="llama3.1:8b", host="http://localhost:9999")

    assert respuesta == "ok"
    url, payload = llamadas[0]
    assert url == "http://localhost:9999/api/chat"
    assert payload["model"] == "llama3.1:8b"


def test_responder_incluye_historial_previo_en_los_mensajes(conn):
    llamadas = []

    def post_json_fake(url, payload):
        llamadas.append(payload)
        return {"message": {"content": "Respuesta"}}

    service = AsistenteIAService(ConfigService(conn), post_json=post_json_fake)

    service.responder("segunda pregunta", "contexto", historial=[("user", "primera pregunta"), ("assistant", "primera respuesta")])

    mensajes = llamadas[0]["messages"]
    assert mensajes[1] == {"role": "user", "content": "primera pregunta"}
    assert mensajes[2] == {"role": "assistant", "content": "primera respuesta"}
    assert "segunda pregunta" in mensajes[3]["content"]


def test_responder_propaga_asistente_error_del_post_json(conn):
    def post_json_falla(url, payload):
        raise AsistenteError("Ollama no está corriendo.")

    service = AsistenteIAService(ConfigService(conn), post_json=post_json_falla)

    with pytest.raises(AsistenteError):
        service.responder("pregunta", "contexto")


def test_responder_sin_texto_devuelve_mensaje_por_defecto(conn):
    service = AsistenteIAService(ConfigService(conn), post_json=lambda url, payload: {"message": {"content": ""}})

    assert service.responder("pregunta", "contexto") == "No obtuve una respuesta del asistente."
