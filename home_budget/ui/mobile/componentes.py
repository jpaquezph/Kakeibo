"""Piezas visuales de la version movil: todo en una sola columna, filas altas
para tocar con el dedo y formularios a pantalla completa (no dialogos)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

import flet as ft

from ...app.domain.models import METODOS_PAGO
from ...app.domain.money import Money, Moneda
from ...app.services.compra_mensual import coincide_busqueda
from .. import theme
from ..desktop import components
from ..desktop.components import METODOS_PAGO_CORTO

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

MARGEN = 16  # separacion del contenido con los bordes de la pantalla

# Ordenes que comparten todas las listas; cada seccion le antepone el suyo (por fecha, por vencimiento...).
ORDENES_COMUNES = [("monto_mayor", "Monto mayor"), ("monto_menor", "Monto menor"), ("alfabetico", "Orden alfabético")]


@dataclass
class Navegacion:
    """Lo que una pantalla le pide al armazon: abrir otra pantalla encima (con
    la flecha de volver), volver a la anterior y mostrar un aviso corto."""
    abrir: Callable[[str, Callable[[], ft.Control], str | None], None]
    volver: Callable[[], None]
    avisar: Callable[[str], None]


def totales_por_moneda(montos) -> list[Money]:
    """Totales por moneda (ARS y USD no se suman), sin los que dan cero."""
    totales: dict[Moneda, Money] = {}
    for m in montos:
        totales[m.moneda] = totales.get(m.moneda, Money.zero(m.moneda)) + m
    return [totales[m] for m in Moneda if m in totales and totales[m].cents]


def campo(label: str, **kwargs) -> ft.TextField:
    return ft.TextField(label=label, filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM,
                        border_color=theme.BORDER, **kwargs)


def desplegable(label: str, value, options: list, **kwargs) -> ft.Dropdown:
    return ft.Dropdown(label=label, value=value, options=options, filled=True, bgcolor=theme.SURFACE_ALT,
                       border_radius=theme.RADIUS_SM, border_color=theme.BORDER, **kwargs)


def pantalla(controles: list[ft.Control], spacing: int = 12) -> ft.Column:
    """Contenido de una pantalla: una columna con scroll y margen a los costados."""
    return ft.Column(
        [ft.Container(ft.Column(controles, spacing=spacing, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), padding=theme.pad_only(left=MARGEN, top=MARGEN, right=MARGEN, bottom=96))],
        scroll=ft.ScrollMode.AUTO, expand=True, spacing=0,
    )


def titulo_tarjeta(texto: str, color: str | None = None) -> ft.Text:
    return ft.Text(texto, size=15, weight=ft.FontWeight.BOLD, color=color or theme.TEXT_PRIMARY)


def tarjeta_plegable(titulo: str, cuerpo: list[ft.Control], plegada: bool, al_alternar: Callable[[bool], None],
                     color: str | None = None, extra: ft.Control | None = None) -> ft.Container:
    """Tarjeta que se achica al tocar el titulo: plegada muestra solo el
    titulo (y `extra`, si tiene), para recorrer la pantalla sin tanto scroll.
    `al_alternar` recibe el estado nuevo, para que la pantalla lo recuerde."""
    estado = {"plegada": plegada}
    flecha = ft.Icon(ft.Icons.EXPAND_LESS_ROUNDED, size=20, color=theme.TEXT_MUTED)
    contenido = ft.Column([separador(), *cuerpo], spacing=10)

    def aplicar():
        flecha.icon = ft.Icons.EXPAND_MORE_ROUNDED if estado["plegada"] else ft.Icons.EXPAND_LESS_ROUNDED
        contenido.visible = not estado["plegada"]

    def alternar(_e):
        estado["plegada"] = not estado["plegada"]
        aplicar()
        al_alternar(estado["plegada"])
        tarjeta.update()

    aplicar()
    cabecera = ft.Container(
        ft.Row(
            [ft.Container(titulo_tarjeta(titulo, color), expand=True), *([extra] if extra else []), flecha],
            spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        on_click=alternar, tooltip="Tocar para achicar o desplegar",
    )
    tarjeta = theme.card(ft.Column([cabecera, contenido], spacing=10), padding=16)
    return tarjeta


class Plegadas:
    """Las tarjetas de una pantalla que el usuario dejo achicadas. Se guardan
    en la configuracion (bajo `clave`, separadas por coma) para que la
    pantalla vuelva a abrirse igual."""

    def __init__(self, config, clave: str):
        self._config = config
        self._clave = clave
        self._ids = {i for i in (config.obtener(clave) or "").split(",") if i}

    def tarjeta(self, id_: str, titulo: str, cuerpo: list[ft.Control], color: str | None = None,
                extra: ft.Control | None = None) -> ft.Container:
        def al_alternar(plegada: bool):
            (self._ids.add if plegada else self._ids.discard)(id_)
            self._config.guardar(self._clave, ",".join(sorted(self._ids)))

        return tarjeta_plegable(titulo, cuerpo, id_ in self._ids, al_alternar, color, extra)


def barra_busqueda(ordenes: list[tuple[str, str]], al_cambiar: Callable[[str, str], None], color: str) -> ft.Row:
    """Buscador y boton de orden que van arriba de cada lista. `ordenes`:
    pares (clave, texto); el primero es el orden inicial. `al_cambiar` recibe
    el texto buscado y la clave del orden cada vez que cambia alguno."""
    estado = {"texto": "", "orden": ordenes[0][0]}

    def items() -> list[ft.PopupMenuItem]:
        return [
            ft.PopupMenuItem(
                content=ft.Row(
                    [ft.Icon(ft.Icons.CHECK_ROUNDED, size=18, color=color, opacity=1 if clave == estado["orden"] else 0),
                     ft.Text(texto, size=14)],
                    spacing=10,
                ),
                on_click=lambda e, c=clave: elegir(c),
            )
            for clave, texto in ordenes
        ]

    def elegir(clave: str):
        estado["orden"] = clave
        menu.items = items()
        al_cambiar(estado["texto"], clave)

    def al_escribir(e):
        estado["texto"] = e.control.value or ""
        al_cambiar(estado["texto"], estado["orden"])

    menu = ft.PopupMenuButton(icon=ft.Icons.SORT_ROUNDED, icon_color=color, items=items(), tooltip="Ordenar")
    buscador = campo("Buscar", prefix_icon=ft.Icons.SEARCH_ROUNDED, dense=True, on_change=al_escribir, expand=True)
    return ft.Row([buscador, menu], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def filtrar_y_ordenar(items: list, busqueda: str, orden: str, texto: Callable, monto: Callable | None = None) -> list:
    """Deja los items cuyo `texto` coincide con lo buscado (sin distinguir
    mayusculas ni acentos) y aplica los ORDENES_COMUNES. Con cualquier otro
    orden respeta el que traian. Pesos y dolares no se comparan: primero ARS."""
    resultado = [i for i in items if coincide_busqueda(texto(i), busqueda)]
    if orden == "alfabetico":
        resultado.sort(key=lambda i: texto(i).casefold())
    elif orden in ("monto_mayor", "monto_menor") and monto is not None:
        signo = -1 if orden == "monto_mayor" else 1
        resultado.sort(key=lambda i: (monto(i).moneda.value, signo * monto(i).cents))
    return resultado


def sin_resultados() -> ft.Container:
    return components.empty_state("Nada coincide con la búsqueda.", "search_off_rounded")


def separador() -> ft.Divider:
    return ft.Divider(height=1, color=theme.BORDER)


def boton_flotante(icono, color: str, on_click, tooltip: str) -> ft.Container:
    """Boton redondo de "agregar", abajo a la derecha (va dentro de un Stack)."""
    return ft.Container(
        ft.Icon(icono, color="#FFFFFF", size=26),
        width=56, height=56, bgcolor=color, border_radius=28, alignment=ft.Alignment.CENTER,
        right=MARGEN, bottom=MARGEN, on_click=on_click, ink=True, tooltip=tooltip,
        shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.25, "#000000"), offset=ft.Offset(0, 4)),
    )


def boton_ancho(texto: str, on_click, color: str, icono=None) -> ft.Row:
    """Boton principal de un formulario: ocupa todo el ancho de la pantalla."""
    boton = theme.primary_button(texto, on_click, color=color, icon=icono)
    boton.expand = True
    return ft.Row([boton])


def confirmar(page: ft.Page, titulo: str, mensaje: str | ft.Control, boton: str, color: str, icono: str,
              al_aceptar: Callable[[], None], cancelar: str = "Cancelar") -> None:
    """Dialogo corto para confirmar una accion. `al_aceptar` corre con el
    dialogo ya cerrado."""
    def aceptar(_e):
        page.pop_dialog()
        al_aceptar()

    contenido = ft.Text(mensaje, color=theme.TEXT_PRIMARY) if isinstance(mensaje, str) else mensaje
    page.show_dialog(theme.dialogo(
        titulo, contenido,
        [theme.secondary_button(cancelar, lambda e: page.pop_dialog()), theme.primary_button(boton, aceptar, color=color, icon=icono)],
        icono=icono, color=color, ancho=300,
    ))


def selector(opciones: list[tuple[str, str]], elegido: str, al_cambiar=None) -> ft.SegmentedButton:
    """Botonera para elegir una entre pocas opciones (clave, texto). Ocupa
    todo el ancho: va dentro de un Row."""
    return ft.SegmentedButton(
        segments=[ft.Segment(value=clave, label=ft.Text(texto)) for clave, texto in opciones],
        selected=[elegido], allow_multiple_selection=False, allow_empty_selection=False, show_selected_icon=False,
        expand=True, on_change=al_cambiar,
    )


def elegido(botonera: ft.SegmentedButton) -> str:
    return next(iter(botonera.selected))


def nota(texto: str) -> ft.Text:
    """Aclaracion chica debajo de un campo."""
    return ft.Text(texto, size=11, color=theme.TEXT_MUTED, italic=True)


def texto_error(page: ft.Page) -> tuple[ft.Text, Callable[[object], None]]:
    """El renglon rojo de un formulario y la funcion que lo muestra."""
    error = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def mostrar(mensaje):
        error.value, error.visible = str(mensaje), True
        page.update()

    return error, mostrar


def muestras_color(page: ft.Page, colores: list[str], inicial: str, al_elegir: Callable[[str], None] | None = None,
                   ) -> tuple[ft.Row, Callable[[], str]]:
    """Circulos de color para elegir uno. Devuelve la fila y una funcion que
    da el elegido."""
    estado = {"color": inicial}
    fila = ft.Row(spacing=10, wrap=True, run_spacing=10)

    def dibujar():
        fila.controls = [
            ft.Container(
                width=34, height=34, bgcolor=c, border_radius=17, ink=True, on_click=lambda e, c=c: elegir(c),
                border=theme.border_all(3, theme.TEXT_PRIMARY) if c == estado["color"] else theme.border_all(1, theme.BORDER),
            )
            for c in colores
        ]

    def elegir(color: str):
        estado["color"] = color
        dibujar()
        page.update()
        if al_elegir:
            al_elegir(color)

    dibujar()
    return fila, lambda: estado["color"]


def selector_fecha(page: ft.Page, etiqueta: str, inicial: date | None, opcional: bool = False,
                   al_elegir: Callable[[], None] | None = None) -> tuple[ft.Control, Callable[[], date | None]]:
    """Fila "etiqueta: fecha" que abre el calendario al tocarla. Devuelve la
    fila y una funcion que da la fecha elegida. Con `opcional` la fecha puede
    quedar sin definir (arranca asi si `inicial` es None) y se puede quitar.
    `al_elegir` corre cada vez que se elige otra fecha."""
    elegida = {"value": inicial}

    def formato() -> str:
        return elegida["value"].strftime("%d/%m/%Y") if elegida["value"] else "Sin definir"

    texto = ft.Text(formato(), size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)

    def al_cambiar(_e):
        if picker.value:
            elegida["value"] = picker.value.date() if isinstance(picker.value, datetime) else picker.value
            texto.value = formato()
            if al_elegir:
                al_elegir()
            page.update()

    def quitar(_e):
        elegida["value"] = None
        texto.value = formato()
        page.update()

    picker = ft.DatePicker(value=inicial, on_change=al_cambiar)
    page.overlay.append(picker)

    def abrir(_e):
        picker.open = True
        page.update()

    fila = ft.Container(
        ft.Row(
            [
                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=20, color=theme.TEXT_SECONDARY),
                ft.Text(etiqueta, size=13, color=theme.TEXT_SECONDARY, expand=True),
                texto,
                *([ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, tooltip="Quitar fecha", on_click=quitar)] if opcional else []),
            ],
            spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE_ALT, border=theme.border_all(1, theme.BORDER), border_radius=theme.RADIUS_SM,
        padding=theme.pad(horizontal=12, vertical=4 if opcional else 14), on_click=abrir, ink=True,
    )
    return fila, lambda: elegida["value"]


def selector_mes(anio: int, mes: int, al_mover: Callable[[int], None], color: str) -> ft.Control:
    """Flechas para pasar de mes, con el mes que se esta viendo en el medio."""
    return ft.Row(
        [
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, icon_color=color, on_click=lambda e: al_mover(-1), tooltip="Mes anterior"),
            ft.Text(f"{MESES[mes - 1].capitalize()} {anio}", size=16, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
                    expand=True, text_align=ft.TextAlign.CENTER),
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, icon_color=color, on_click=lambda e: al_mover(1), tooltip="Mes siguiente"),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def fila_movimiento(movimiento, on_tap=None) -> ft.Container:
    """Un movimiento en la lista: se toca la fila entera para editarlo (en el
    celular no hay lugar para los botones de editar y eliminar)."""
    es_ingreso = movimiento.tipo.value == "ingreso"
    color = theme.INCOME_GREEN if es_ingreso else theme.EXPENSE_RED
    bg = theme.INCOME_GREEN_BG if es_ingreso else theme.EXPENSE_RED_BG

    notas = [movimiento.fecha.strftime("%d/%m")]
    if getattr(movimiento, "metodo_pago", "") in METODOS_PAGO:
        notas.append(METODOS_PAGO_CORTO.get(movimiento.metodo_pago, METODOS_PAGO[movimiento.metodo_pago]))
    if movimiento.fijo:
        notas.append("Fijo")
    pendiente = movimiento.estado.value == "pendiente"

    return ft.Container(
        ft.Row(
            [
                ft.Container(
                    ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED if es_ingreso else ft.Icons.ARROW_DOWNWARD_ROUNDED, color=color, size=16),
                    bgcolor=bg, padding=10, border_radius=theme.RADIUS_SM,
                ),
                ft.Column(
                    [
                        # El monto comparte renglon con el concepto: el de abajo queda entero para categoria y fecha.
                        ft.Row(
                            [
                                ft.Text(movimiento.concepto, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY,
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                ft.Text(f"{'+' if es_ingreso else '-'} {movimiento.monto.formatted()}", size=14, weight=ft.FontWeight.BOLD, color=color),
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                components.category_chip(movimiento.categoria_nombre or "", movimiento.categoria_color or theme.TEXT_MUTED,
                                                         movimiento.categoria_icono or "category"),
                                ft.Text(" · ".join(notas), size=11, color=theme.TEXT_MUTED, expand=True, no_wrap=True,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                                *([ft.Text("Pendiente", size=11, color=theme.HISTORIAL_COLOR, italic=True)] if pendiente else []),
                            ],
                            spacing=6,
                        ),
                    ],
                    spacing=4, expand=True,
                ),
            ],
            spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE, padding=theme.pad(horizontal=12, vertical=10), border_radius=theme.RADIUS_SM,
        border=theme.border_all(1, theme.BORDER),
        on_click=(lambda e: on_tap(movimiento)) if on_tap else None, ink=on_tap is not None,
    )


def fila_dato(icono, color: str, titulo: str, detalle: str, valor: str, color_valor: str | None = None) -> ft.Row:
    """Fila de una lista dentro de una tarjeta: icono, titulo con una linea de
    detalle debajo y un valor a la derecha."""
    return ft.Row(
        [
            ft.Icon(theme.to_icon(icono), size=18, color=color),
            ft.Column(
                [
                    ft.Text(titulo, size=13, color=theme.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    *([ft.Text(detalle, size=11, color=theme.TEXT_SECONDARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)] if detalle else []),
                ],
                spacing=0, expand=True,
            ),
            ft.Text(valor, size=13, weight=ft.FontWeight.BOLD, color=color_valor or color),
        ],
        spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def fila_tocable(fila: ft.Control, al_tocar) -> ft.Container:
    """Una fila de lista que se toca para abrir lo que muestra."""
    return ft.Container(fila, padding=8, border_radius=theme.RADIUS_SM, ink=True, on_click=al_tocar)


def boton_eliminar(texto: str, al_tocar) -> ft.Row:
    """El "Eliminar ..." rojo que va al pie de un formulario de edicion."""
    return ft.Row([ft.TextButton(texto, icon=ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=al_tocar,
                                 style=ft.ButtonStyle(color=theme.EXPENSE_RED))], alignment=ft.MainAxisAlignment.CENTER)
