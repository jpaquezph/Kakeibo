"""Volver al login desde una pantalla secundaria no debe romper el "Ingresar".

Antes, eliminar usuario y recuperar contraseña volvian al login con una accion
de entrar vacia: la contraseña se validaba pero la app nunca se abria.
"""
import flet as ft
import pytest

from home_budget.app.auth.service import AuthService
from home_budget.ui.desktop.login_view import build_login_view


class _Page:
    def __init__(self):
        self.overlay = []

    def update(self):
        pass

    def show_dialog(self, d):
        pass

    def pop_dialog(self):
        pass


def _recorrer(c):
    yield c
    for attr in ("controls", "content", "actions"):
        v = getattr(c, attr, None)
        if isinstance(v, list):
            for x in v:
                if isinstance(x, ft.BaseControl):
                    yield from _recorrer(x)
        elif isinstance(v, ft.BaseControl):
            yield from _recorrer(v)


def _textos(c):
    for x in _recorrer(c):
        if isinstance(x, ft.Text) and isinstance(x.value, str):
            yield x.value
        if isinstance(getattr(x, "content", None), str):
            yield x.content


def _click(raiz, texto):
    candidatos = [x for x in _recorrer(raiz) if getattr(x, "on_click", None) and texto in list(_textos(x))]
    boton = min(candidatos, key=lambda x: sum(1 for _ in _recorrer(x)))
    boton.on_click(None)


def _campo(raiz, label):
    return next(x for x in _recorrer(raiz) if isinstance(x, ft.TextField) and x.label == label)


@pytest.fixture
def login(conn):
    auth = AuthService(conn)
    auth.crear_usuario("ana", "secreta1", "¿Cuál es tu comida favorita?", "asado")
    entradas = []
    vista = build_login_view(_Page(), auth, on_success=lambda s: entradas.append(s.username))
    return vista, entradas


def _ingresar(vista, usuario="ana", password="secreta1"):
    _campo(vista, "Usuario").value = usuario
    _campo(vista, "Contraseña").value = password
    _click(vista, "Ingresar")


@pytest.mark.parametrize("ida, vuelta", [
    ("Eliminar un usuario", "Cancelar"),
    ("¿Olvidaste tu contraseña?", "Volver a iniciar sesión"),
    ("Crear usuario nuevo", "Volver a iniciar sesión"),
])
def test_ingresar_funciona_despues_de_volver_de_otra_pantalla(login, ida, vuelta):
    vista, entradas = login
    _click(vista, ida)
    _click(vista, vuelta)

    _ingresar(vista)

    assert entradas == ["ana"]


def test_ingresar_funciona_despues_de_recuperar_la_contrasena(login):
    vista, entradas = login
    _click(vista, "¿Olvidaste tu contraseña?")
    _campo(vista, "Tu usuario").value = "ana"
    _click(vista, "Continuar")
    _campo(vista, "Tu respuesta").value = "asado"
    _campo(vista, "Nueva contraseña").value = "nueva123"
    _campo(vista, "Confirmar nueva contraseña").value = "nueva123"
    _click(vista, "Restablecer contraseña")
    _click(vista, "Ir a iniciar sesión")

    _ingresar(vista, password="nueva123")

    assert entradas == ["ana"]


def test_crear_usuario_entra_despues_de_pasar_por_eliminar(login):
    vista, entradas = login
    _click(vista, "Eliminar un usuario")
    _click(vista, "Cancelar")
    _click(vista, "Crear usuario nuevo")
    _campo(vista, "Usuario").value = "beto"
    _campo(vista, "Contraseña").value = "secreta2"
    _campo(vista, "Confirmar contraseña").value = "secreta2"
    _campo(vista, "Respuesta").value = "pizza"
    _click(vista, "Crear cuenta e ingresar")

    assert entradas == ["beto"]
