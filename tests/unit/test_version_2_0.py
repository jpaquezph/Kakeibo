"""Version 2.0: ingreso con huella y secciones de la version movil."""
from datetime import date

import pytest

from home_budget.app.auth.service import AuthError, AuthService
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.tarjetas import TarjetaService
from home_budget.ui import theme
from home_budget.ui.mobile.app_shell import FUERA_DEL_MENU, _secciones
from home_budget.ui.mobile.tarjetas_forms import partes_pendientes


def test_el_menu_movil_no_tiene_historial_ni_compra_mensual():
    theme.aplicar_modo(False)
    claves = [s[0] for s in _secciones()]
    assert "historial" not in claves and "compra_mensual" not in claves
    # A Configuracion se entra por la foto de perfil: existe, pero fuera del menu.
    assert "configuracion" in claves and "configuracion" in FUERA_DEL_MENU


def test_pagar_tarjeta_separa_cuotas_de_compras_en_un_pago(conn):
    tarjetas = TarjetaService(conn)
    tarjeta = tarjetas.crear_tarjeta("Visa", "Banco", "1234")
    categoria = conn.execute("SELECT id FROM categorias WHERE nombre = 'Tarjeta de crédito'").fetchone()["id"]
    hoy = date.today()
    tarjetas.registrar_compra(tarjeta.id, hoy, "Zapatillas", "", Money(9000000, Moneda.ARS), categoria, 3, meses_al_resumen=0)
    tarjetas.registrar_compra(tarjeta.id, hoy, "Cena", "", Money(2500000, Moneda.ARS), categoria, 1, meses_al_resumen=0)

    partes = partes_pendientes(tarjetas.resumen_del_mes(tarjeta.id, hoy.year, hoy.month), [])

    assert [(titulo, [m.cents for m in montos]) for titulo, montos in partes] == [
        ("1 cuota(s)", [3000000]), ("1 compra(s) en 1 pago", [2500000]),
    ]


def _auth_con_usuario(conn) -> AuthService:
    auth = AuthService(conn)
    auth.crear_usuario("juan", "clave123")
    return auth


def test_sin_activar_no_hay_usuario_con_huella(conn):
    auth = _auth_con_usuario(conn)
    assert auth.usuario_con_huella() is None
    with pytest.raises(AuthError):
        auth.login_con_huella()


def test_activar_huella_pide_sesion_abierta(conn):
    auth = _auth_con_usuario(conn)
    with pytest.raises(AuthError):
        auth.activar_huella()


def test_login_con_huella_abre_la_sesion_del_que_la_activo(conn):
    auth = _auth_con_usuario(conn)
    auth.login("juan", "clave123")
    auth.activar_huella()
    auth.logout()

    session = auth.login_con_huella()

    assert session.username == "juan"
    assert auth.is_authenticated()
    abiertas = conn.execute("SELECT COUNT(*) AS n FROM sesiones WHERE logout_at IS NULL").fetchone()["n"]
    assert abiertas == 1


def test_la_huella_sigue_activada_en_otra_apertura_de_la_app(conn):
    auth = _auth_con_usuario(conn)
    auth.login("juan", "clave123")
    auth.activar_huella()

    assert AuthService(conn).usuario_con_huella() == "juan"


def test_desactivar_huella(conn):
    auth = _auth_con_usuario(conn)
    auth.login("juan", "clave123")
    auth.activar_huella()
    auth.desactivar_huella()
    auth.logout()

    assert auth.usuario_con_huella() is None
    with pytest.raises(AuthError):
        auth.login_con_huella()


def test_desbloquear_con_huella_reanuda_la_sesion_bloqueada(conn):
    auth = _auth_con_usuario(conn)
    session = auth.login("juan", "clave123")
    auth.activar_huella()
    session.inactivity_timeout = 0
    assert session.check_inactivity()

    auth.desbloquear_con_huella()

    assert not session.locked


def test_la_huella_no_desbloquea_la_sesion_de_otro_usuario(conn):
    auth = _auth_con_usuario(conn)
    auth.crear_usuario("ana", "clave456")
    auth.login("juan", "clave123")
    auth.activar_huella()
    auth.logout()
    auth.login("ana", "clave456")

    with pytest.raises(AuthError):
        auth.desbloquear_con_huella()


def test_si_se_elimina_el_usuario_la_huella_deja_de_servir(conn):
    auth = _auth_con_usuario(conn)
    auth.login("juan", "clave123")
    auth.activar_huella()
    auth.logout()
    auth.eliminar_usuario("juan", "clave123")

    assert auth.usuario_con_huella() is None
