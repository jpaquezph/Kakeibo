from decimal import Decimal

import pytest

from home_budget.app.domain.money import Money, Moneda
from home_budget.ui.desktop.components import parse_entero, parse_monto


@pytest.mark.parametrize("texto, esperado", [
    ("1500", "1500"), ("1500,50", "1500.50"), ("1500.50", "1500.50"), ("1.5", "1.5"), ("1,5", "1.5"),
    (" $ 2000 ", "2000"), ("0,5", "0.5"),
])
def test_coma_y_punto_son_separador_de_decimales(texto, esperado):
    assert parse_monto(texto, Moneda.ARS) == Money.from_decimal(Decimal(esperado), Moneda.ARS)


@pytest.mark.parametrize("texto, mensaje", [
    ("abc", "solo números"), ("12a", "solo números"), ("", "completá"), ("0", "mayor a cero"), ("-5", "mayor a cero"),
    ("1.500,50", "un solo separador"), ("1.250.000", "un solo separador"),
])
def test_parse_monto_da_un_error_claro(texto, mensaje):
    """Regresion: con letras en el monto el formulario no hacia nada y no
    mostraba ningun error entendible."""
    with pytest.raises(ValueError, match=mensaje):
        parse_monto(texto, Moneda.ARS)


def test_el_mensaje_de_error_muestra_coma_y_punto():
    with pytest.raises(ValueError, match=r"15250,50 o 15250\.50"):
        parse_monto("abc", Moneda.ARS)


def test_parse_entero():
    assert parse_entero("12", "Cuotas") == 12
    with pytest.raises(ValueError, match="número entero"):
        parse_entero("doce", "Cuotas")
    with pytest.raises(ValueError, match="entre 1 y 28"):
        parse_entero("30", "Día", maximo=28)
