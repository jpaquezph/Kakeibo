"""Resumen general en el celular: las mismas tarjetas que en escritorio, una
debajo de la otra. Cada una se achica al tocar su titulo (queda solo el
titulo), y la app recuerda cuales quedaron achicadas."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.dashboard import distribucion_por_categoria
from .. import theme
from ..desktop import components
from . import componentes as mc
from .cambio_view import formulario_cambio

# Tarjetas del resumen que el usuario dejo achicadas, separadas por coma.
CLAVE_PLEGADAS = "movil_resumen_plegadas"

_ICONOS_ORIGEN = {"fijo": "receipt_long_rounded", "tarjeta": "credit_card_rounded", "prestamo": "account_balance_rounded"}


def _color_origen(origen: str) -> str:
    # Funcion (no dict de modulo) para tomar la paleta activa, clara u oscura.
    return {"fijo": theme.MOVIMIENTOS_COLOR, "tarjeta": theme.TARJETAS_COLOR, "prestamo": theme.PRESTAMOS_COLOR}.get(origen, theme.TEXT_MUTED)


def build_resumen_view(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    resumen = servicios.dashboard.resumen()
    mes = mc.MESES[date.today().month - 1]
    tarjeta = mc.Plegadas(servicios.config, CLAVE_PLEGADAS).tarjeta

    controles: list[ft.Control] = [tarjeta("pendiente", f"Pendiente de pagar en {mes}", _pendiente(resumen.pendiente_del_mes))]

    monedas = [r for r in resumen.por_moneda if r.ingresos.cents or r.egresos.cents]
    if not monedas:
        controles.append(components.empty_state("Todavía no registraste movimientos.", "savings_rounded"))
    controles += [tarjeta(f"balance_{r.moneda.value}", f"Balance {r.moneda.value}", _balance(r)) for r in monedas]

    controles.append(tarjeta("categorias", "Gastos por categoría", _categorias(page, resumen.por_categoria), theme.MOVIMIENTOS_COLOR))
    controles.append(tarjeta("tarjetas", f"Pendiente en tarjetas · {mes}", _tarjetas(resumen.por_tarjeta), theme.TARJETAS_COLOR))
    controles.append(tarjeta(
        "prestamos", "Préstamos pendientes", _prestamos(resumen), theme.PRESTAMOS_COLOR,
        components.category_chip(f"{resumen.prestamos_pendientes_cantidad} activo(s)", theme.PRESTAMOS_COLOR, "hourglass_top_rounded"),
    ))
    controles.append(tarjeta("pagado", "Pagado este mes", _pagado(resumen.pagado_este_mes)))
    controles.append(tarjeta("cambio", "Compra / venta de dólares", [
        ft.Text("Se descuenta de una moneda y se acredita en la otra.", size=12, color=theme.TEXT_SECONDARY),
        mc.boton_ancho("Nueva operación",
                       lambda e: nav.abrir("Compra / venta de dólares", lambda: formulario_cambio(page, nav, servicios), theme.CAMBIO_COLOR),
                       theme.CAMBIO_COLOR, ft.Icons.CURRENCY_EXCHANGE_ROUNDED),
    ], theme.CAMBIO_COLOR))
    return mc.pantalla(controles)


def _pendiente(pendiente: dict[Moneda, Money]) -> list[ft.Control]:
    montos = [pendiente[m] for m in Moneda if m in pendiente and (pendiente[m].cents or m == Moneda.ARS)]
    color = theme.INCOME_GREEN if all(m.cents == 0 for m in montos) else theme.EXPENSE_RED
    return [ft.Row([ft.Text(m.formatted(), size=22, weight=ft.FontWeight.BOLD, color=color) for m in montos], spacing=16, wrap=True)]


def _balance(r) -> list[ft.Control]:
    """Balance grande y, debajo, ingresos y egresos: en el celular las tres
    cifras no entran lado a lado."""
    def mitad(titulo: str, monto: Money, icono, color: str, bg: str) -> ft.Container:
        return ft.Container(
            ft.Column(
                [
                    ft.Row([ft.Icon(icono, size=14, color=color), ft.Text(titulo, size=11, color=theme.TEXT_SECONDARY)], spacing=4),
                    ft.Text(monto.formatted(), size=14, weight=ft.FontWeight.BOLD, color=color),
                ],
                spacing=2,
            ),
            bgcolor=bg, border_radius=theme.RADIUS_SM, padding=10, expand=True,
        )

    return [
        ft.Text(r.balance.formatted(), size=26, weight=ft.FontWeight.BOLD,
                color=theme.EXPENSE_RED if r.balance.is_negative() else theme.INCOME_GREEN),
        ft.Row(
            [
                mitad("Ingresos", r.ingresos, ft.Icons.TRENDING_UP_ROUNDED, theme.INCOME_GREEN, theme.INCOME_GREEN_BG),
                mitad("Egresos", r.egresos, ft.Icons.TRENDING_DOWN_ROUNDED, theme.EXPENSE_RED, theme.EXPENSE_RED_BG),
            ],
            spacing=8,
        ),
    ]


def _categorias(page: ft.Page, por_categoria) -> list[ft.Control]:
    distribuciones = {m: distribucion_por_categoria(por_categoria, m) for m in Moneda}
    monedas = [m for m in Moneda if distribuciones[m]]
    if not monedas:
        return [components.empty_state("Sin gastos registrados todavía.")]
    cuerpo = ft.Container()

    def mostrar(moneda: Moneda):
        porciones = distribuciones[moneda]
        # La torta arriba y la leyenda debajo (en escritorio van lado a lado).
        cuerpo.content = ft.Column(
            [ft.Row([components.torta(porciones)], alignment=ft.MainAxisAlignment.CENTER), ft.Row([_leyenda(porciones)])],
            spacing=14,
        )

    def al_cambiar_moneda(e):
        mostrar(Moneda(next(iter(e.control.selected))))
        page.update()

    mostrar(monedas[0])
    if len(monedas) == 1:
        return [cuerpo]
    # ARS y USD no se suman: cada moneda tiene su propia torta. El selector va
    # en el cuerpo y no junto al titulo, que es lo que se toca para achicar.
    selector = ft.SegmentedButton(
        segments=[ft.Segment(value=m.value, label=ft.Text(m.value)) for m in monedas],
        selected=[monedas[0].value], allow_multiple_selection=False, allow_empty_selection=False,
        show_selected_icon=False, on_change=al_cambiar_moneda,
    )
    return [ft.Row([selector], alignment=ft.MainAxisAlignment.CENTER), cuerpo]


def _leyenda(porciones) -> ft.Control:
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=p.color, border_radius=5),
                    ft.Text(p.nombre, size=13, color=theme.TEXT_PRIMARY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{p.porcentaje:.1f}%", size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Text(p.total.formatted(), size=12, color=theme.TEXT_SECONDARY, width=104, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=8,
            )
            for p in porciones
        ],
        spacing=8, expand=True,
    )


def _tarjetas(por_tarjeta) -> list[ft.Control]:
    filas = []
    for tt in por_tarjeta:
        partes = []
        if tt.total_pendiente_un_pago.cents > 0:
            partes.append(f"1 pago {tt.total_pendiente_un_pago.formatted()}")
        if tt.total_pendiente_cuotas.cents > 0:
            partes.append(f"cuotas {tt.total_pendiente_cuotas.formatted()}")
        if tt.total_pendiente_debitos and tt.total_pendiente_debitos.cents > 0:
            partes.append(f"débitos {tt.total_pendiente_debitos.formatted()}")
        filas.append(mc.fila_dato("credit_card_rounded", theme.TARJETAS_COLOR, f"{tt.nombre} · {tt.moneda.value}",
                                  " · ".join(partes), tt.total_pendiente.formatted()))
    return filas or [components.empty_state("Este mes no vence nada de tarjetas.", "credit_card_rounded")]


def _prestamos(resumen) -> list[ft.Control]:
    return [
        *[
            ft.Row([ft.Text(moneda, size=13, color=theme.TEXT_SECONDARY, expand=True),
                    ft.Text(total.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)])
            for moneda, total in (("ARS", resumen.prestamos_pendientes_ars), ("USD", resumen.prestamos_pendientes_usd))
        ],
        *([mc.separador(), ft.Text("Próximas cuotas", size=12, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY)]
          if resumen.prestamos_activos else []),
        *[
            mc.fila_dato("account_balance_rounded", theme.PRESTAMOS_COLOR, pc.nombre,
                         f"Cuota {pc.numero_cuota} de {pc.cantidad_cuotas} · vence el {pc.fecha_vencimiento.strftime('%d/%m/%Y')}",
                         pc.monto.formatted())
            for pc in resumen.prestamos_activos
        ],
    ]


def _pagado(pagos) -> list[ft.Control]:
    if not pagos:
        return [components.empty_state("Todavía no pagaste nada este mes.", "task_alt_rounded")]
    totales = mc.totales_por_moneda(p.monto for p in pagos)
    return [
        *[
            mc.fila_dato(_ICONOS_ORIGEN.get(p.origen, "check_circle_rounded"), _color_origen(p.origen), p.concepto,
                         p.fecha.strftime("%d/%m"), p.monto.formatted())
            for p in pagos
        ],
        ft.Row([ft.Text(f"Total {t.moneda.value}: {t.formatted()}", size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY)
                for t in totales], spacing=16, wrap=True),
    ]
