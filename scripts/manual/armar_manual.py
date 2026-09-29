"""Arma 'Kakeibo - Manual de uso 1.3.pdf' con las capturas anotadas,
respetando el manual de identidad visual (colores, tipografia, logo)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

import anotar  # noqa: E402

PROYECTO = Path(__file__).resolve().parents[2]
F = r"C:\Windows\Fonts"
for nombre, archivo in [("Segoe", "segoeui.ttf"), ("Segoe-B", "segoeuib.ttf"), ("Segoe-SB", "seguisb.ttf"), ("Segoe-I", "segoeuii.ttf")]:
    pdfmetrics.registerFont(TTFont(nombre, str(Path(F) / archivo)))
from reportlab.lib.fonts import addMapping  # noqa: E402
addMapping("Segoe", 0, 0, "Segoe"); addMapping("Segoe", 1, 0, "Segoe-B"); addMapping("Segoe", 0, 1, "Segoe-I"); addMapping("Segoe", 1, 1, "Segoe-B")

# Paleta del manual de marca
AMBAR = colors.HexColor("#F1AB00")   # solo sobre fondos oscuros
AZUL = colors.HexColor("#003C97")    # solo sobre fondos claros
TINTA = colors.HexColor("#1C1B17")
PAPEL = colors.HexColor("#FAF7EF")
BORDE = colors.HexColor("#E4DFD5")
TEXTO = colors.HexColor("#2A261E")
TEXTO_CLARO = colors.HexColor("#F1EDE7")
SECUNDARIO = colors.HexColor("#6B6358")
BLANCO = colors.white

ISO_AMBAR = str(PROYECTO / "assets" / "logo.png")
ISO_AZUL = str(PROYECTO / "assets" / "logo_claro.png")
VERSION = "1.3"

ES = {
    "h1": ParagraphStyle("h1", fontName="Segoe-B", fontSize=21, leading=26, textColor=TEXTO, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName="Segoe-B", fontSize=13.5, leading=18, textColor=AZUL, spaceBefore=10, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="Segoe", fontSize=10.3, leading=15, textColor=TEXTO, spaceAfter=5, alignment=TA_LEFT),
    "li": ParagraphStyle("li", fontName="Segoe", fontSize=10.3, leading=15, textColor=TEXTO, leftIndent=14, bulletIndent=3, spaceAfter=2),
    "pie": ParagraphStyle("pie", fontName="Segoe-I", fontSize=9, leading=12, textColor=SECUNDARIO, spaceBefore=3, spaceAfter=6),
    "exp": ParagraphStyle("exp", fontName="Segoe", fontSize=10, leading=14, textColor=TEXTO),
    "nota": ParagraphStyle("nota", fontName="Segoe", fontSize=9.8, leading=14, textColor=TEXTO),
    "toc1": ParagraphStyle("toc1", fontName="Segoe", fontSize=11, leading=19, textColor=TEXTO, leftIndent=4),
    "cel": ParagraphStyle("cel", fontName="Segoe", fontSize=9.4, leading=13, textColor=TEXTO),
    "celb": ParagraphStyle("celb", fontName="Segoe-B", fontSize=9.4, leading=13, textColor=TEXTO),
}
ANCHO_UTIL = A4[0] - 40 * mm

FIGURAS = {}
_contador = {"fig": 0, "cap": 0}


def boton(t: str) -> str:
    """Nombre de un boton o campo, igual que en pantalla (en azul)."""
    return f'<font name="Segoe-SB" color="#003C97">{t}</font>'


def _formato(texto: str) -> str:
    """[Boton] -> nombre de pantalla en azul; (Nuevo en 1.3) -> etiqueta."""
    texto = re.sub(r"\[([^\]]+)\]", lambda m: boton(m.group(1)), texto)
    return texto.replace("(Nuevo en 1.3)", '<font name="Segoe-B" color="#003C97" size="8"> NUEVO 1.3</font>')


def P(texto, estilo="p"):
    return Paragraph(_formato(texto), ES[estilo])


def lista(items):
    return [Paragraph(_formato(i), ES["li"], bulletText="•") for i in items]


def pasos(items):
    return [Table([[Paragraph(f'<font name="Segoe-B" color="#FFFFFF">{n}</font>', ParagraphStyle("n", alignment=1, fontSize=9.5, leading=12)),
                    Paragraph(_formato(t), ES["exp"])]],
                  colWidths=[6.5 * mm, ANCHO_UTIL - 8 * mm],
                  style=TableStyle([("BACKGROUND", (0, 0), (0, 0), AZUL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                    ("LEFTPADDING", (1, 0), (1, 0), 8)]))
            for n, t in enumerate(items, 1)]


def nota(titulo, texto, tono="info"):
    fondo = colors.HexColor("#EEF2FA") if tono == "info" else colors.HexColor("#FBF1E9")
    raya = AZUL if tono == "info" else colors.HexColor("#B4541E")
    t = Table([[Paragraph(f'<font name="Segoe-B">{titulo}</font> {_formato(texto)}', ES["nota"])]], colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fondo), ("LINEBEFORE", (0, 0), (0, -1), 3, raya),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return [Spacer(1, 4), t, Spacer(1, 6)]


def sub(titulo):
    """Subtitulo que nunca queda solo al pie de la pagina: si no entra lo
    que sigue (en general una captura), pasa con el a la pagina siguiente."""
    return [CondPageBreak(165 * mm), Paragraph(titulo, ES["h2"])]


class Capitulo(Paragraph):
    """Titulo de capitulo que ademas entra al indice."""


def capitulo(titulo):
    _contador["cap"] += 1
    n = _contador["cap"]
    par = Capitulo(f'<font color="#003C97">{n}.</font> {titulo}', ES["h1"])
    par._titulo_indice = f"{n}. {titulo}"
    raya = Table([[""]], colWidths=[18 * mm], rowHeights=[1.6 * mm], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL)]))
    return [PageBreak(), raya, Spacer(1, 3 * mm), par, Spacer(1, 2 * mm)]


def figura(nombre, alto_max=150 * mm, ancho=None):
    """Captura anotada + pie + explicacion numerada de cada flecha."""
    info = FIGURAS[nombre]
    _contador["fig"] += 1
    ruta = str(AQUI / "anotadas" / f"{nombre}.png")
    from PIL import Image as PILImage
    w, h = PILImage.open(ruta).size
    ancho = ancho or (ANCHO_UTIL if w > 1200 else min(ANCHO_UTIL * 0.62, ANCHO_UTIL))
    alto = ancho * h / w
    if alto > alto_max:
        alto, ancho = alto_max, alto_max * w / h
    img = Image(ruta, width=ancho, height=alto)
    marco = Table([[img]], colWidths=[ancho + 2], style=TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDE),
                                                                    ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                                                                    ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    marco.hAlign = "CENTER"
    bloque = [marco, Paragraph(f"Figura {_contador['fig']}. {info['pie']}", ES["pie"])]
    filas = []
    for n, ((titulo, expl), caja) in enumerate(zip(info["textos"], info["cajas"]), 1):
        if caja is None:
            continue
        filas.append(Table(
            [[Paragraph(f'<font name="Segoe-B" color="#FFFFFF">{n}</font>', ParagraphStyle("b", alignment=1, fontSize=9.5, leading=12)),
              Paragraph(f'{boton(titulo)}: {_formato(expl)}', ES["exp"])]],
            colWidths=[6.5 * mm, ANCHO_UTIL - 8 * mm],
            style=TableStyle([("BACKGROUND", (0, 0), (0, 0), AZUL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                              ("LEFTPADDING", (1, 0), (1, 0), 8)]),
        ))
    return [CondPageBreak(alto + 30 * mm), KeepTogether(bloque + filas[:2]), *filas[2:], Spacer(1, 5 * mm)]


def tabla(filas, anchos):
    datos = [[Paragraph(_formato(c), ES["celb" if i == 0 else "cel"]) for c in f] for i, f in enumerate(filas)]
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE8DE")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANCO, PAPEL]),
                           ("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return [t, Spacer(1, 6)]


# ------------------------------------------------------------------ contenido
def contenido():
    h = []
    # Indice
    h.append(Paragraph("Contenido", ES["h1"]))
    h.append(Spacer(1, 4 * mm))
    toc = TableOfContents()
    toc.levelStyles = [ES["toc1"]]
    toc.dotsMinLevel = 0
    h.append(toc)

    h += capitulo("Bienvenida")
    h.append(P("Kakeibo es una aplicación para llevar las cuentas de tu casa: lo que entra, lo que sale, las tarjetas de "
               "crédito, los préstamos, los gastos que se repiten todos los meses, la compra del mes y tus inversiones. "
               "Este manual recorre cada sección con capturas reales de la aplicación, señaladas con flechas y números, "
               "para que sepas exactamente dónde tocar y qué cargar en cada campo."))
    h += sub("Cómo leer las capturas")
    h += lista([
        "Los <b>recuadros y flechas azules</b> señalan el botón o el campo del que se habla.",
        "El <b>número</b> de cada flecha es el mismo que el de la explicación que está debajo de la captura.",
        "Los nombres de botones y campos aparecen en azul, escritos igual que en la pantalla: por ejemplo [Nueva compra].",
        "Lo que es nuevo en esta versión está marcado con (Nuevo en 1.3).",
        "Las capturas usan datos de ejemplo de una familia ficticia.",
    ])
    h += sub("Ideas que conviene tener claras")
    h += lista([
        "<b>Pesos y dólares nunca se mezclan.</b> Cada monto tiene su moneda (ARS o USD) y los totales se muestran por separado.",
        "<b>Tus datos quedan en tu computadora.</b> No se envían a internet. Por eso es importante hacer copias de seguridad (capítulo 16).",
        "<b>Todo se guarda al instante.</b> Cada vez que confirmás algo, ya queda guardado.",
        "<b>Montos:</b> escribí los decimales con coma o con punto, sin puntos de miles: 15250,50 o 15250.50.",
        "<b>Si algo está mal escrito</b>, el aviso aparece en rojo debajo del título de la ventana y no se guarda nada hasta corregirlo.",
        "<b>Escape</b> cierra la ventana que esté abierta, igual que [Cancelar]. (Nuevo en 1.3)",
        "El lápiz sirve para editar y el tacho de basura para eliminar. Antes de borrar, la app pide confirmación.",
    ])

    h += capitulo("Novedades de la versión 1.3")
    h.append(P("Esta versión reúne los cambios pedidos después de las pruebas con usuarios."))
    h += tabla([
        ["Qué cambió", "Dónde"],
        ["Una tarjeta opera en <b>pesos y en dólares</b>: cada compra elige su moneda. Las tarjetas que estaban cargadas dos veces (una por moneda) se unen solas al actualizar.", "Tarjetas (cap. 10)"],
        ["Tarjetas con <b>día de cierre y de vencimiento</b>.", "Tarjetas (cap. 10)"],
        ["<b>Editar compra</b> permite cambiar todo, con confirmación; las cuotas ya pagadas no se tocan.", "Tarjetas (cap. 10)"],
        ["Compras en cuotas cargando el <b>valor de la cuota</b>.", "Tarjetas (cap. 10)"],
        ["Fichas más chicas, 2 o 3 por fila, y el <b>detalle visible</b> en compras y movimientos.", "Tarjetas, Gastos fijos, Movimientos"],
        ["Gastos fijos con <b>débito automático</b>: vencen cuando vence la tarjeta.", "Gastos fijos (cap. 8)"],
        ["<b>Filtros y orden</b> en Gastos fijos.", "Gastos fijos (cap. 8)"],
        ["Préstamos: <b>cuota actual</b>, <b>día de vencimiento</b>, edición completa y <b>monto de cuota variable</b>.", "Préstamos (cap. 11)"],
        ["Resumen: <b>pendiente de tarjetas del mes</b> y <b>próxima cuota</b> de cada préstamo.", "Resumen (cap. 6)"],
        ["<b>Iniciar con Windows</b>.", "Configuración (cap. 15)"],
        ["<b>Escape</b> cierra la ventana abierta; mensajes de error claros y siempre a la vista.", "En toda la app"],
    ], [ANCHO_UTIL * 0.68, ANCHO_UTIL * 0.32])

    h += capitulo("Instalación y actualización")
    h.append(P("Kakeibo se instala con un único archivo: <b>KakeiboSetup.exe</b>. No necesitás instalar nada más."))
    h += sub("Requisitos")
    h += lista(["Windows 10 u 11 de 64 bits.", "Unos 150 MB libres en disco.", "No hace falta internet ni permisos de administrador."])
    h += sub("Instalar paso a paso")
    h += pasos([
        "Hacé doble clic en <b>KakeiboSetup.exe</b>.",
        "Si Windows muestra el aviso azul “Windows protegió su PC”, tocá <b>Más información</b> y después <b>Ejecutar de todas formas</b>. "
        "Aparece porque la aplicación no está firmada digitalmente; es normal en programas de uso personal.",
        "Dejá tildado <b>Crear un ícono en el Escritorio</b>.",
        "Esperá a que termine la copia de archivos y, en la última pantalla, tocá <b>Finalizar</b>.",
    ])
    h += sub("Actualizar a la versión 1.3")
    h.append(P("Ejecutá el nuevo KakeiboSetup.exe igual que la primera vez, con Kakeibo cerrado. Se instala encima de la versión "
               "anterior y <b>tus datos se conservan</b>: el instalador nunca trae datos ni reemplaza tu base."))
    h += nota("Al abrirla por primera vez:", "si tenías la misma tarjeta cargada dos veces (una en pesos y otra en dólares, con el mismo "
              "nombre, banco y últimos 4 dígitos), la app las une en una sola, con sus compras y débitos. Antes de hacerlo guarda "
              "sola una copia de tu base junto a ella.")
    h += nota("Consejo:", "antes de actualizar, hacé un backup (capítulo 16).", "aviso")
    h += sub("Desinstalar")
    h.append(P("Configuración de Windows → Aplicaciones → Aplicaciones instaladas → Kakeibo → Desinstalar. Windows pregunta si "
               "querés borrar también tus datos: si elegís <b>Sí</b>, se eliminan definitivamente. Si pensás volver a usar la app, "
               "elegí <b>No</b> o hacé un backup antes. Si tenías activado “Iniciar con Windows”, se quita solo."))

    h += capitulo("Primer ingreso y acceso")
    h.append(P("Cada persona que usa la computadora puede tener su propio usuario. Los datos de gastos son de la instalación: "
               "todos los usuarios ven la misma información."))
    h += figura("login")
    h += sub("Si olvidaste la contraseña")
    h.append(P("Se recupera con la pregunta de seguridad que elegiste al crear el usuario, sin email."))
    h += figura("recuperar_1", alto_max=95 * mm)
    h += figura("recuperar_2", alto_max=95 * mm)
    h += sub("Varios usuarios en la misma computadora")
    h += figura("crear_usuario", alto_max=100 * mm)
    h += figura("eliminar_usuario", alto_max=100 * mm)
    h += sub("Bloqueo por inactividad")
    h.append(P("Si la app queda 5 minutos sin usarse, se bloquea. Para seguir, escribí tu contraseña o tu PIN (si configuraste uno "
               "en Configuración). Si te equivocás 5 veces con el PIN, pide la contraseña."))

    h += capitulo("La pantalla principal")
    h += figura("principal")
    h += nota("Bueno saber:", "para pasar a otro usuario sin cerrar la app, tocá tu nombre abajo a la izquierda y elegí el otro "
              "usuario: se abre el inicio de sesión con ese usuario ya completado.")

    h += capitulo("Resumen")
    h.append(P("Es la primera pantalla al entrar: muestra de un vistazo cómo van tus cuentas."))
    h += figura("resumen_arriba")
    h += figura("resumen_abajo")
    h += figura("resumen_pagado", alto_max=110 * mm)
    h += sub("Comprar o vender dólares")
    h.append(P("Registra el cambio de moneda: se descuenta de una moneda y se suma a la otra, con la cotización que indiques."))
    h += figura("dolares", alto_max=120 * mm)
    h += figura("dolares_confirmar", alto_max=60 * mm)

    h += capitulo("Movimientos")
    h.append(P("Acá se cargan los ingresos (sueldo, ventas, regalos) y los egresos del día a día (supermercado, farmacia, salidas)."))
    h += figura("movimientos")
    h += sub("Cargar un movimiento")
    h += figura("movimiento_nuevo", alto_max=150 * mm)
    h += figura("movimiento_error", alto_max=90 * mm)
    h += sub("Crear una categoría nueva")
    h += figura("categoria_nueva", alto_max=120 * mm)

    h += capitulo("Gastos fijos")
    h.append(P("Los gastos que se repiten todos los meses (alquiler, expensas, servicios, suscripciones) se cargan una sola vez. "
               "Cada mes registrás su pago con un botón."))
    h += figura("gastos_fijos")
    h += sub("Crear un gasto fijo")
    h += figura("gasto_fijo_nuevo", alto_max=130 * mm)
    h += sub("Con débito automático")
    h.append(P("Si el gasto se cobra solo en una tarjeta, tildá la casilla de débito automático. El gasto se cuenta una sola vez "
               "(como gasto fijo), pero aparece en el resumen de esa tarjeta y se paga al tocar [Pagar tarjeta (mes)]."))
    h += figura("gasto_fijo_debito", alto_max=130 * mm)
    h += nota("Importante:", "para usar débito automático, la tarjeta tiene que tener cargado el día de vencimiento "
              "(Tarjetas → lápiz de la tarjeta). Si no lo tiene, el formulario lo avisa en rojo.", "aviso")
    h += sub("Registrar el pago del mes")
    h += figura("gasto_fijo_pago", alto_max=55 * mm)
    h += sub("Filtrar y ordenar")
    h += figura("gastos_fijos_filtro")

    h += capitulo("Compra mensual")
    h.append(P("Una planilla para comparar el precio de cada producto en varios locales, ver dónde conviene comprar y registrar lo "
               "que gastaste. Cada mes nuevo copia del anterior los locales y productos, sin los precios."))
    h += figura("compra_mensual")
    h += pasos([
        "Cargá los locales con [Agregar local] y los productos con [Agregar producto].",
        "Completá el precio de cada producto en cada local. Si un local no lo tiene, dejá la casilla vacía.",
        "El más barato de cada producto queda en verde; si ningún local lo tiene, el producto queda en rosa.",
        "Abajo ves cuánto sale comprar todo en cada local y cuánto comprando lo más barato de cada uno.",
    ])
    h += figura("compra_mensual_registrar")
    h += nota("Bueno saber:", "la compra se puede registrar en cualquier tarjeta y en varias partes. Si te equivocaste, tocá "
              "[Deshacer] en ese registro.")

    h += capitulo("Tarjetas de crédito")
    h.append(P("Cada tarjeta muestra lo que tenés pendiente, en pesos y en dólares por separado. Tocando una tarjeta se ven sus "
               "débitos automáticos del mes y sus compras."))
    h += figura("tarjetas")
    h += figura("tarjetas_compras")
    h += sub("Agregar una tarjeta")
    h += figura("tarjeta_nueva", alto_max=140 * mm)
    h += sub("Cargar una compra")
    h += figura("compra_1pago", alto_max=150 * mm)
    h.append(P("En cuotas podés cargar el monto total o, si lo que tenés a mano es el valor de cada cuota, cargar ese valor: "
               "el total se calcula solo."))
    h += figura("compra_cuotas", alto_max=150 * mm)
    h += sub("Pagar")
    h.append(P("Con [Pagar tarjeta (mes)] se marca pagado todo lo que vence este mes en esa tarjeta: cuotas, compras en 1 pago y "
               "débitos automáticos. Para pagar una sola cuota, usá [Pagar cuota] en la ficha de la compra."))
    h += figura("tarjeta_pagar_mes", alto_max=60 * mm)
    h += sub("Corregir una compra")
    h.append(P("Si te equivocaste al cargar una compra (el monto, las cuotas, la tarjeta o la moneda), tocá [Editar] en su ficha."))
    h += figura("compra_editar", alto_max=150 * mm)
    h += figura("compra_editar_confirmar", alto_max=130 * mm)
    h += nota("Eliminar:", "el tacho de basura de cada compra la borra con todas sus cuotas. Para borrar una tarjeta, tocá su "
              "lápiz y después [Eliminar tarjeta]; sus débitos automáticos pasan a ser gastos fijos comunes.")

    h += capitulo("Préstamos")
    h.append(P("Registrá los préstamos que estás pagando para ver cuánto falta, cuándo vence cada cuota y pagarlas."))
    h += figura("prestamos")
    h += sub("Registrar un préstamo")
    h += figura("prestamo_nuevo", alto_max=150 * mm)
    h += sub("Pagar una cuota")
    h += figura("prestamo_pagar", alto_max=80 * mm)
    h += sub("Cuotas que cambian de monto")
    h.append(P("En préstamos UVA o con ajustes, la cuota cambia. Podés corregirla al pagar o, por adelantado, desde [Ver cuotas]."))
    h += figura("prestamo_cuotas", alto_max=140 * mm)
    h += sub("Corregir un préstamo")
    h += figura("prestamo_editar", alto_max=150 * mm)
    h += nota("Bueno saber:", "si después de cambiar montos en [Ver cuotas] usás [Editar] para cambiar el monto, las cuotas o las "
              "fechas, las cuotas pendientes vuelven a quedar iguales. La confirmación lo avisa.", "aviso")

    h += capitulo("Inversiones")
    h.append(P("Llevá el registro de tus ahorros, acciones, bonos, fondos y criptomonedas, en pesos o en dólares. Con el selector "
               "de arriba a la derecha elegís la moneda."))
    h += figura("inversiones")
    h += lista([
        "<b>Ahorro</b>: plazos fijos, dólares guardados, cuentas remuneradas.",
        "<b>Acciones</b> y <b>Bonos / Lecap</b>: cada compra con su cantidad y precio; se agrupan por símbolo.",
        "<b>FCI</b>: fondos comunes de inversión, con su TNA.",
        "<b>Crypto</b>: compras y ventas de criptomonedas.",
        "Al cargar una inversión podés elegir <b>operar con la plata de la app</b>: invertir genera un egreso y retirar un ingreso.",
    ])
    h += figura("inv_ahorro")
    h += figura("inv_acciones")
    h += figura("inv_calendario")

    h += capitulo("Calendario")
    h.append(P("Muestra el mes con todo lo que vence: cuotas de tarjetas, de préstamos y gastos fijos. Cada punto de color es un "
               "vencimiento; tocando un día se ve el detalle."))
    h += figura("calendario")
    h += figura("calendario_dia", alto_max=100 * mm)

    h += capitulo("Historial")
    h += figura("historial")

    h += capitulo("Configuración")
    h.append(P("Tocá el título de cada apartado para abrirlo o cerrarlo."))
    h += figura("config_usuario")
    h += figura("config_general")
    h += nota("Iniciar con Windows:", "con el interruptor encendido, Kakeibo se abre solo cuando iniciás sesión en Windows. "
              "Aparece en el Administrador de tareas → Aplicaciones de arranque. (Nuevo en 1.3)")
    h += nota("Registro de errores:", "si algo falla, en Configuración → Registro de errores tocá [Abrir carpeta] y enviá el "
              "archivo a quien administre la app. Se guarda solo en tu PC.")

    h += capitulo("Copias de seguridad")
    h.append(P("Todos tus datos están en un único archivo en tu computadora. Si la PC se rompe, se pierden, salvo que tengas una copia."))
    h += pasos([
        "En la barra lateral, abajo, tocá [Hacer backup].",
        "Elegí la carpeta: un pendrive, un disco externo o una carpeta sincronizada en la nube.",
        "La app avisa si la copia se creó y en qué ruta quedó (un archivo como kakeibo_backup_20260929_153000.db).",
    ])
    h += nota("Importante:", "hacé un backup al menos una vez por semana y siempre antes de actualizar la app. Guardalo fuera de la computadora.", "aviso")

    h += capitulo("Buenas prácticas")
    h += lista([
        "Cargá los movimientos el mismo día: el Resumen queda al día.",
        "Usá Gastos fijos para todo lo mensual y marcá el débito automático cuando corresponda.",
        "Cargá el día de cierre y de vencimiento de tus tarjetas.",
        "Al cargar una compra con tarjeta, fijate si el resumen ya cerró: así las cuotas caen en el mes correcto.",
        "Revisá el aviso de vencimientos al abrir la app y pagá desde ahí o desde el Calendario.",
        "Si la cuota de un préstamo cambió, corregila al pagarla.",
        "Configurá un PIN si la computadora la usan otras personas.",
        "Hacé backups seguido.",
    ])

    h += capitulo("Problemas frecuentes")
    h += tabla([
        ["Qué pasa", "Qué hacer"],
        ["Windows dice “Windows protegió su PC” al instalar", "Tocá “Más información” y “Ejecutar de todas formas”."],
        ["No me deja guardar un monto", "Leé el aviso en rojo debajo del título. Escribí los decimales con coma o punto y sin puntos de miles: 15250,50."],
        ["Veo una tarjeta repetida", "Desde la 1.3 se unen solas si tienen el mismo nombre, banco y últimos 4 dígitos. Si difieren, borrá la que sobra (primero pasá sus compras con Editar)."],
        ["El monto de la tarjeta no coincide con el resumen del banco", "Revisá las compras con [Editar]: el monto, las cuotas y si el resumen ya había cerrado."],
        ["No me deja usar débito automático", "Cargá el día de vencimiento de la tarjeta (lápiz de la tarjeta)."],
        ["Quiero quitar un débito automático", "En Gastos fijos tocá [Editar] (o la etiqueta Débito) y destildá la casilla."],
        ["La cuota del préstamo vino distinta", "Corregila al pagar, o en [Ver cuotas]."],
        ["No veo mis gastos en dólares en la torta", "Elegí USD en el selector ARS / USD arriba del gráfico."],
        ["La app se bloqueó sola", "Es el bloqueo por inactividad. Escribí tu contraseña o tu PIN."],
        ["Olvidé mi PIN", "Tocá “Usar contraseña” en el bloqueo y cambiá el PIN desde Configuración."],
        ["Algo no funciona como debería", "Configuración → Registro de errores → [Abrir carpeta], y enviá el archivo."],
    ], [ANCHO_UTIL * 0.38, ANCHO_UTIL * 0.62])

    h += capitulo("Glosario")
    h += tabla([
        ["Término", "Significado"],
        ["ARS / USD", "Pesos argentinos / dólares estadounidenses."],
        ["Egreso / Ingreso", "Plata que sale / plata que entra."],
        ["Balance", "Ingresos menos egresos."],
        ["Categoría", "Grupo al que pertenece un movimiento (Comida, Casa, Sueldo…)."],
        ["Gasto fijo", "Gasto que se repite todos los meses."],
        ["Débito automático", "Gasto fijo que se cobra solo en una tarjeta; vence cuando vence la tarjeta."],
        ["Cierre del resumen", "Día en que la tarjeta corta las compras del mes. Lo comprado después pasa al resumen siguiente."],
        ["Vencimiento", "Día en que hay que pagar el resumen de la tarjeta, una cuota o un gasto fijo."],
        ["Cuota", "Cada una de las partes en que se paga una compra o un préstamo."],
        ["UVA", "Unidad que ajusta por inflación: la cuota de un préstamo UVA cambia cada mes."],
        ["Local", "En Compra mensual, cada lugar donde comprás."],
        ["Vigente / Finalizada", "Inversión que todavía tenés / que ya vendiste, rescataste o retiraste."],
        ["FCI / TNA", "Fondo común de inversión / tasa nominal anual."],
        ["PIN", "Código de 4 números para desbloquear la app."],
        ["Backup", "Copia de seguridad de tus datos."],
    ], [ANCHO_UTIL * 0.3, ANCHO_UTIL * 0.7])
    return h


# ------------------------------------------------------------------ paginas
class Manual(BaseDocTemplate):
    def __init__(self, archivo):
        super().__init__(archivo, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=24 * mm, bottomMargin=20 * mm,
                         title=f"Kakeibo {VERSION} - Manual de uso", author="Kakeibo", subject="Manual de uso con capturas")
        cuerpo = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="cuerpo")
        self.addPageTemplates([
            PageTemplate("portada", [Frame(0, 0, A4[0], A4[1], id="p")], onPage=_portada),
            PageTemplate("normal", [cuerpo], onPage=_pagina),
        ])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Capitulo):
            self.notify("TOCEntry", (0, flowable._titulo_indice, self.page))


def _fondo(c):
    c.setFillColor(PAPEL)
    c.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)


def _portada(c, doc):
    _fondo(c)
    # Banda superior: version principal de la marca, ambar sobre tinta.
    alto_banda = 118 * mm
    c.setFillColor(TINTA)
    c.rect(0, A4[1] - alto_banda, A4[0], alto_banda, stroke=0, fill=1)
    # Isologotipo horizontal: isotipo 10X de ancho, palabra de 6X de alto a 5X de distancia.
    ancho_iso = 26 * mm
    x_mod = ancho_iso / 10
    alto_iso = ancho_iso * 1.059
    x0, y0 = 26 * mm, A4[1] - alto_banda / 2 - alto_iso / 2
    c.drawImage(ISO_AMBAR, x0, y0, width=ancho_iso, height=alto_iso, mask="auto")
    c.setFillColor(TEXTO_CLARO)
    tam = 6 * x_mod / 0.72  # altura de la palabra (ascendentes a base) ~ 0,72 del cuerpo en Segoe UI Bold
    c.setFont("Segoe-B", tam)
    c.drawString(x0 + ancho_iso + 5 * x_mod, y0 + alto_iso / 2 - 3 * x_mod, "Kakeibo")
    c.setFont("Segoe", 11)
    c.setFillColor(colors.HexColor("#B9B2A6"))
    c.drawString(x0 + ancho_iso + 5 * x_mod, y0 - 9 * mm + 2 * mm, "Gestión de la economía del hogar")
    # Titulo del documento, sobre papel.
    c.setFillColor(TEXTO)
    c.setFont("Segoe-B", 30)
    c.drawString(26 * mm, A4[1] - alto_banda - 30 * mm, "Manual de uso")
    c.setFillColor(AZUL)
    c.rect(26 * mm, A4[1] - alto_banda - 36 * mm, 18 * mm, 1.6 * mm, stroke=0, fill=1)
    c.setFillColor(SECUNDARIO)
    c.setFont("Segoe", 12)
    for i, linea in enumerate(["Guía paso a paso, con capturas señaladas con flechas,",
                               "para cargar cada cosa en cada sección."]):
        c.drawString(26 * mm, A4[1] - alto_banda - 48 * mm - i * 6.5 * mm, linea)
    c.setFont("Segoe-B", 12)
    c.setFillColor(AZUL)
    c.drawString(26 * mm, A4[1] - alto_banda - 70 * mm, f"Versión {VERSION} para Windows")
    c.setFont("Segoe", 9)
    c.setFillColor(SECUNDARIO)
    c.drawString(26 * mm, 16 * mm, "Septiembre 2026 · Las capturas usan datos de ejemplo")


def _pagina(c, doc):
    _fondo(c)
    # Encabezado: isotipo azul (tema claro) + nombre del documento.
    c.drawImage(ISO_AZUL, 20 * mm, A4[1] - 15.5 * mm, width=5.2 * mm, height=5.5 * mm, mask="auto")
    c.setFont("Segoe", 8.5)
    c.setFillColor(SECUNDARIO)
    c.drawString(27.5 * mm, A4[1] - 13.6 * mm, f"Kakeibo {VERSION} · Manual de uso")
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.6)
    c.line(20 * mm, A4[1] - 18 * mm, A4[0] - 20 * mm, A4[1] - 18 * mm)
    c.drawRightString(A4[0] - 20 * mm, 11 * mm, f"Página {doc.page}")


def main():
    global FIGURAS
    FIGURAS = anotar.anotar_todo(AQUI / "capturas", AQUI / "anotadas")
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / f"Kakeibo - Manual de uso {VERSION}.pdf"
    doc = Manual(str(salida))
    historia = [NextPageTemplate("normal"), PageBreak()] + contenido()
    doc.multiBuild(historia)
    print("OK", salida)


if __name__ == "__main__":
    main()
