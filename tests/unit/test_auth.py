import pytest

from home_budget.app.auth.service import AuthError, AuthService


def test_crear_usuario_y_login_valido(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    session = auth.login("juan", "clave123")
    assert session.username == "juan"
    assert auth.is_authenticated()


def test_login_con_password_incorrecta_falla(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    with pytest.raises(AuthError):
        auth.login("juan", "otraclave")


def test_login_usuario_inexistente_falla(conn):
    auth = AuthService(conn)
    with pytest.raises(AuthError):
        auth.login("nadie", "clave123")


def test_password_nunca_se_guarda_en_texto_plano(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    row = conn.execute("SELECT password_hash FROM usuarios WHERE username = 'juan'").fetchone()
    assert row["password_hash"] != "clave123"
    assert "clave123" not in row["password_hash"]


def test_logout_invalida_la_sesion(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    auth.login("juan", "clave123")
    auth.logout()
    assert not auth.is_authenticated()


def test_sesion_se_bloquea_tras_inactividad(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    session = auth.login("juan", "clave123")
    session.inactivity_timeout = 0
    assert not auth.is_authenticated()


def test_recuperar_password_con_respuesta_correcta(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123", "¿Cuál es tu comida favorita?", "Milanesas")

    assert auth.obtener_pregunta_secreta("juan") == "¿Cuál es tu comida favorita?"

    auth.restablecer_password("juan", "milanesas", "claveNueva1")
    with pytest.raises(AuthError):
        auth.login("juan", "clave123")
    session = auth.login("juan", "claveNueva1")
    assert session.username == "juan"


def test_recuperar_password_con_respuesta_incorrecta_falla(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123", "¿Cuál es tu comida favorita?", "Milanesas")

    with pytest.raises(AuthError):
        auth.restablecer_password("juan", "pizza", "claveNueva1")


def test_obtener_pregunta_secreta_usuario_sin_pregunta(conn):
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    assert auth.obtener_pregunta_secreta("juan") is None
