import struct
import zlib

import pytest

from home_budget.app.auth.avatar import MAX_BYTES, ImagenInvalidaError, validar_imagen
from home_budget.app.auth.service import MAX_INTENTOS_PIN, AuthError, AuthService


def _png(ancho, alto):
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk


def _jpeg(ancho, alto):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, alto, ancho, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


@pytest.fixture
def auth(conn):
    service = AuthService(conn)
    service.crear_usuario("ana", "secreta1")
    service.login("ana", "secreta1")
    return service


def test_cambiar_nombre_actualiza_la_sesion_y_permite_login(auth):
    auth.cambiar_nombre(auth.session.usuario_id, "ana maria")
    assert auth.session.username == "ana maria"
    auth.login("ana maria", "secreta1")


def test_cambiar_nombre_a_uno_existente_falla(auth):
    auth.crear_usuario("beto", "secreta2")
    with pytest.raises(ValueError):
        auth.cambiar_nombre(auth.session.usuario_id, "beto")


def test_cambiar_password_pide_la_actual(auth):
    uid = auth.session.usuario_id
    with pytest.raises(AuthError):
        auth.cambiar_password(uid, "incorrecta", "nueva123")
    auth.cambiar_password(uid, "secreta1", "nueva123")
    auth.login("ana", "nueva123")
    with pytest.raises(AuthError):
        auth.login("ana", "secreta1")


def test_perfil_guarda_color_e_imagen(auth):
    uid = auth.session.usuario_id
    auth.cambiar_avatar_color(uid, "#2A78D6")
    imagen = _png(64, 64)
    auth.cambiar_avatar_imagen(uid, imagen)

    perfil = auth.obtener_perfil(uid)
    assert perfil.avatar_color == "#2A78D6"
    assert perfil.avatar_imagen == imagen

    auth.cambiar_avatar_imagen(uid, None)
    assert auth.obtener_perfil(uid).avatar_imagen is None


def test_validar_imagen_acepta_png_y_jpeg_dentro_del_limite():
    validar_imagen(_png(512, 512))
    validar_imagen(_jpeg(800, 600))


@pytest.mark.parametrize(
    "datos",
    [_png(3000, 100), _jpeg(100, 3000), b"GIF89a....", _png(10, 10) + b"\x00" * MAX_BYTES],
    ids=["png-muy-ancho", "jpeg-muy-alto", "gif", "muy-pesada"],
)
def test_validar_imagen_rechaza_formatos_y_tamanos_invalidos(datos):
    with pytest.raises(ImagenInvalidaError):
        validar_imagen(datos)


def test_pin_desbloquea_la_sesion(auth):
    uid = auth.session.usuario_id
    auth.establecer_pin(uid, "secreta1", "1234")
    auth.session.locked = True

    auth.desbloquear_con_pin("1234")

    assert auth.session.locked is False


def test_establecer_pin_valida_password_y_formato(auth):
    uid = auth.session.usuario_id
    with pytest.raises(AuthError):
        auth.establecer_pin(uid, "incorrecta", "1234")
    for pin in ("123", "12345", "12a4"):
        with pytest.raises(ValueError):
            auth.establecer_pin(uid, "secreta1", pin)


def test_pin_se_deshabilita_tras_varios_intentos_fallidos(auth):
    auth.establecer_pin(auth.session.usuario_id, "secreta1", "1234")
    for _ in range(MAX_INTENTOS_PIN):
        with pytest.raises(AuthError):
            auth.desbloquear_con_pin("0000")

    assert auth.puede_desbloquear_con_pin() is False
    with pytest.raises(AuthError):
        auth.desbloquear_con_pin("1234")


def test_quitar_pin(auth):
    uid = auth.session.usuario_id
    auth.establecer_pin(uid, "secreta1", "1234")
    with pytest.raises(AuthError):
        auth.quitar_pin(uid, "incorrecta")
    assert auth.obtener_perfil(uid).tiene_pin is True

    auth.quitar_pin(uid, "secreta1")
    assert auth.obtener_perfil(uid).tiene_pin is False
    assert auth.puede_desbloquear_con_pin() is False
