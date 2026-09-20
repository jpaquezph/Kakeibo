from home_budget.app.services.config import ConfigService


def test_obtener_clave_inexistente_devuelve_none(conn):
    service = ConfigService(conn)
    assert service.obtener("no_existe") is None


def test_guardar_y_obtener(conn):
    service = ConfigService(conn)
    service.guardar("anthropic_api_key", "sk-ant-123")

    assert service.obtener("anthropic_api_key") == "sk-ant-123"


def test_guardar_sobreescribe_valor_previo(conn):
    service = ConfigService(conn)
    service.guardar("clave", "valor-viejo")
    service.guardar("clave", "valor-nuevo")

    assert service.obtener("clave") == "valor-nuevo"


def test_eliminar(conn):
    service = ConfigService(conn)
    service.guardar("clave", "valor")
    service.eliminar("clave")

    assert service.obtener("clave") is None
