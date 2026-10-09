"""Calendario en el celular: lo que vence y falta pagar en el mes, con
buscador y orden. Es solo de consulta: cada cosa se paga desde su seccion."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.dates import add_months
from .. import theme
from ..desktop import components
from . import componentes as mc

_ICONOS_ORIGEN = {"fijo": "event_repeat_rounded", "tarjeta": "credit_card_rounded", "prestamo": "account_balance_rounded"}


def build_calendario_view(page: ft.Page, servicios) -> ft.Control:
    hoy = date.today()
    estado = {"anio": hoy.year, "mes": hoy.month, "busqueda": "", "orden": "fecha"}
    cuerpo = ft.Column(spacing=12)

    def mover_mes(delta: int):
        nuevo = add_months(date(estado["anio"], estado["mes"], 1), delta)
        estado["anio"], estado["mes"] = nuevo.year, nuevo.month
        refrescar()
        page.update()

    def al_buscar(busqueda: str, orden: str):
        estado["busqueda"], estado["orden"] = busqueda, orden
        refrescar()
        page.update()

    def refrescar():
        del_mes = servicios.vencimientos.pendientes_del_mes(estado["anio"], estado["mes"])  # vienen por fecha
        vencimientos = mc.filtrar_y_ordenar(del_mes, estado["busqueda"], estado["orden"], lambda v: f"{v.titulo} {v.etiqueta}",
                                            lambda v: v.monto)
        colores = {"fijo": theme.MOVIMIENTOS_COLOR, "prestamo": theme.PRESTAMOS_COLOR}
        filas = [
            mc.fila_dato(_ICONOS_ORIGEN.get(v.origen, "event_rounded"), v.color or colores.get(v.origen, theme.TARJETAS_COLOR), v.titulo,
                         f"{v.fecha.strftime('%d/%m')} · {v.etiqueta}", v.monto.formatted(),
                         theme.EXPENSE_RED if v.fecha < hoy else theme.TEXT_PRIMARY)
            for v in vencimientos
        ]
        if not del_mes:
            filas = [components.empty_state("No queda nada por pagar este mes.", "task_alt_rounded")]
        total = mc.totales_por_moneda(v.monto for v in vencimientos)
        cuerpo.controls = [
            mc.selector_mes(estado["anio"], estado["mes"], mover_mes, theme.CALENDARIO_COLOR),
            theme.card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(mc.titulo_tarjeta("Vence y falta pagar", theme.CALENDARIO_COLOR), expand=True),
                                ft.Text(" + ".join(m.formatted() for m in total), size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                            ],
                        ),
                        mc.separador(),
                        *(filas or [mc.sin_resultados()]),
                    ],
                    spacing=12,
                ),
                padding=16,
            ),
        ]

    refrescar()
    return mc.pantalla([
        mc.barra_busqueda([("fecha", "Por fecha"), *mc.ORDENES_COMUNES], al_buscar, theme.CALENDARIO_COLOR),
        cuerpo,
    ])
