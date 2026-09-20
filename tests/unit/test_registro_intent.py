from decimal import Decimal

from home_budget.app.domain.models import TipoMovimiento
from home_budget.app.domain.money import Money, Moneda
from home_budget.app.services.registro_intent import detectar_intencion_registro


def test_frase_sin_intencion_de_registro_devuelve_none():
    assert detectar_intencion_registro("¿cuánto gasté este mes?") is None
    assert detectar_intencion_registro("¿cuál es mi categoría con más gastos?") is None


def test_pregunta_con_verbo_de_registro_no_se_confunde_con_alta():
    """Regresion: 'gasté'/'cobré' aparecen tanto en pedidos de alta como en
    preguntas sobre el historico; sin el signo de pregunta tambien debe
    reconocerse por la palabra interrogativa inicial."""
    assert detectar_intencion_registro("cuanto gaste este mes") is None
    assert detectar_intencion_registro("¿cuánto cobré este mes?") is None


def test_detecta_egreso_simple():
    intencion = detectar_intencion_registro("compré una gaseosa")

    assert intencion is not None
    assert intencion.tipo == TipoMovimiento.EGRESO
    assert intencion.concepto == "Gaseosa"
    assert intencion.monto is None
    assert intencion.categoria_sugerida == "Comida"


def test_detecta_ingreso_simple():
    intencion = detectar_intencion_registro("cobré el sueldo")

    assert intencion.tipo == TipoMovimiento.INGRESO
    assert intencion.concepto == "Sueldo"
    assert intencion.categoria_sugerida == "Sueldo"


def test_detecta_egreso_con_monto_en_pesos():
    intencion = detectar_intencion_registro("gasté 500 en nafta")

    assert intencion.tipo == TipoMovimiento.EGRESO
    assert intencion.monto == Money.from_decimal(Decimal("500"), Moneda.ARS)
    assert intencion.categoria_sugerida == "Auto"


def test_detecta_monto_en_dolares():
    intencion = detectar_intencion_registro("pagué 20 usd de suscripción")

    assert intencion.monto == Money.from_decimal(Decimal("20"), Moneda.USD)


def test_detecta_monto_con_decimales():
    intencion = detectar_intencion_registro("compré algo por 199,50")

    assert intencion.monto == Money.from_decimal(Decimal("199.50"), Moneda.ARS)


def test_verbo_de_ingreso_no_se_confunde_con_egreso():
    intencion = detectar_intencion_registro("vendí el auto viejo")

    assert intencion.tipo == TipoMovimiento.INGRESO


def test_sin_categoria_reconocida_devuelve_none_en_sugerida():
    intencion = detectar_intencion_registro("pagué algo raro sin categoría clara")

    assert intencion is not None
    assert intencion.categoria_sugerida is None


def test_concepto_nunca_queda_vacio():
    intencion = detectar_intencion_registro("compré")

    assert intencion.concepto.strip() != ""
