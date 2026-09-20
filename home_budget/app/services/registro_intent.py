"""Deteccion de intencion de registrar un movimiento a partir de una frase
libre en el chat del asistente (ej: "compre una gaseosa", "cobre el sueldo").

Es deliberadamente reglas simples (regex + palabras clave) y no una llamada
al modelo de lenguaje: crear un movimiento escribe en la base del usuario, asi
que preferimos algo determinístico y sin alucinaciones antes que dejar que un
modelo local chico (3B) invente montos o categorias. La categoria y el monto
sugeridos siempre se le muestran al usuario para confirmar/corregir antes de
guardar nada; esta funcion nunca escribe en la base."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..domain.models import TipoMovimiento
from ..domain.money import Money, Moneda

_PATRONES_EGRESO = [
    r"\bcompr[eé]\b", r"\bgast[eé]\b", r"\bpagu[eé]\b", r"\bgasto de\b", r"\bcompra de\b",
]
_PATRONES_INGRESO = [
    r"\bcobr[eé]\b", r"\brecib[ií]\b", r"\bdeposit[eé]\b", r"\bvend[ií]\b",
    r"\bme pagaron\b", r"\bingreso de\b", r"\bgan[eé]\b",
]

_NUMERO_RE = re.compile(r"\d+(?:[.,]\d{1,2})?")
_USD_RE = re.compile(r"\b(usd|u\$s|dolares|dólares)\b", re.IGNORECASE)

_HINTS_CATEGORIA = {
    "Comida": ["gaseosa", "comida", "supermercado", "almuerzo", "cena", "verduler", "carnicer", "kiosco", "restaurant", "delivery", "rappi", "pedidosya"],
    "Auto": ["nafta", "combustible", "peaje", "estacionamiento", "colectivo", "sube"],
    "Farmacia": ["farmacia", "remedio", "medicamento"],
    "Salidas": ["cine", "bar", "boliche", "previa", "recital"],
    "Servicios esenciales": ["luz", "factura de gas", "agua", "internet", "expensas", "telefono", "celular"],
    "Sueldo": ["sueldo", "salario"],
    "Mascotas": ["veterinaria", "alimento balanceado", "mascota"],
}

_ARTICULOS_RE = re.compile(r"^(de|del|un|una|unos|unas|el|la|los|las)\s+", re.IGNORECASE)

_PALABRAS_INTERROGATIVAS = {
    "cuánto", "cuanto", "cuánta", "cuanta", "cuántos", "cuantos", "cuántas", "cuantas",
    "cuál", "cual", "cuáles", "cuales", "qué", "que", "cómo", "como", "dónde", "donde",
    "cuándo", "cuando", "quién", "quien", "quiénes", "quienes",
}


def _parece_pregunta(texto: str) -> bool:
    """Filtro de precision: 'gasté'/'cobré' aparecen tanto en pedidos de
    registro ('gasté 500 en nafta') como en preguntas sobre el historico
    ('¿cuánto gasté este mes?'). Si tiene signo de pregunta o arranca con un
    interrogativo, se trata como pregunta para el asistente, no como alta."""
    if "?" in texto:
        return True
    primera_palabra = re.sub(r"^[¿¡\s]+", "", texto.lower()).split(" ", 1)[0].strip(",.;:")
    return primera_palabra in _PALABRAS_INTERROGATIVAS


@dataclass
class IntencionRegistro:
    tipo: TipoMovimiento
    concepto: str
    monto: Money | None
    categoria_sugerida: str | None  # nombre de categoria, no id (no depende de la base)


def detectar_intencion_registro(texto: str) -> IntencionRegistro | None:
    """Devuelve la intencion detectada, o None si la frase no parece un
    pedido de registrar un ingreso/egreso (en ese caso se trata como una
    pregunta normal para el asistente)."""
    texto = texto.strip()
    if _parece_pregunta(texto):
        return None
    texto_low = texto.lower()

    es_egreso = any(re.search(p, texto_low) for p in _PATRONES_EGRESO)
    es_ingreso = any(re.search(p, texto_low) for p in _PATRONES_INGRESO)
    if not es_egreso and not es_ingreso:
        return None

    tipo = TipoMovimiento.EGRESO if es_egreso else TipoMovimiento.INGRESO
    return IntencionRegistro(
        tipo=tipo,
        concepto=_limpiar_concepto(texto, texto_low),
        monto=_extraer_monto(texto),
        categoria_sugerida=_sugerir_categoria(texto_low),
    )


def _extraer_monto(texto: str) -> Money | None:
    match = _NUMERO_RE.search(texto)
    if not match:
        return None
    try:
        valor = Decimal(match.group(0).replace(",", "."))
    except InvalidOperation:
        return None
    if valor <= 0:
        return None
    moneda = Moneda.USD if _USD_RE.search(texto) else Moneda.ARS
    return Money.from_decimal(valor, moneda)


def _limpiar_concepto(texto: str, texto_low: str) -> str:
    limpio = texto.rstrip(".!? ")
    for patron in _PATRONES_EGRESO + _PATRONES_INGRESO:
        m = re.match(patron, texto_low)
        if m:
            limpio = limpio[m.end():].strip()
            break
    limpio = _ARTICULOS_RE.sub("", limpio).strip()
    # saca un monto/moneda sueltos del final para que no queden en el concepto
    limpio = _NUMERO_RE.sub("", limpio)
    limpio = _USD_RE.sub("", limpio)
    limpio = re.sub(r"\s{2,}", " ", limpio).strip(" .,-")
    if not limpio:
        limpio = texto.rstrip(".!? ")
    return limpio[:1].upper() + limpio[1:]


def _sugerir_categoria(texto_low: str) -> str | None:
    for nombre_categoria, palabras in _HINTS_CATEGORIA.items():
        if any(p in texto_low for p in palabras):
            return nombre_categoria
    return None
