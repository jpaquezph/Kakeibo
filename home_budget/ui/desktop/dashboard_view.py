from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.cambio import CambioDivisaService
from ...app.services.dashboard import DashboardService, distribucion_por_categoria
from .. import theme
from . import components


def _icono_origen(origen: str) -> tuple[str, str]:
    # Funcion (no dict de modulo) para tomar la paleta activa, clara u oscura.
    return {
        "fijo": ("receipt_long_rounded", theme.MOVIMIENTOS_COLOR),
        "tarjeta": ("credit_card_rounded", theme.TARJETAS_COLOR),
        "prestamo": ("account_balance_rounded", theme.PRESTAMOS_COLOR),
    }.get(origen, ("check_circle_rounded", theme.TEXT_MUTED))


_ALTURA_PAGADO_INICIAL = 240
_ALTURA_PAGADO_MINIMA = 160
_SEPARACION_TARJETAS = 16


def _construir_pagado_card(pagos) -> ft.Container:
    totales: dict[Moneda, Money] = {}
    for p in pagos:
        totales[p.monto.moneda] = totales.get(p.monto.moneda, Money.zero(p.monto.moneda)) + p.monto

    items = []
    for p in pagos:
        icono, color = _icono_origen(p.origen)
        items.append(
            ft.Row(
                [
                    ft.Icon(theme.to_icon(icono), size=15, color=color),
                    ft.Text(p.concepto, size=12, color=theme.TEXT_PRIMARY, expand=True),
                    ft.Text(p.monto.formatted(), size=12, weight=ft.FontWeight.W_600, color=color),
                ],
                spacing=8,
            )
        )

    totales_row = ft.Row(
        [ft.Text(f"Total {moneda.value}: {total.formatted()}", size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY) for moneda, total in totales.items()],
        spacing=16,
    ) if totales else ft.Container()

    # La altura de la tarjeta la fija build_dashboard_view para alinearla con
    # la columna izquierda; si los pagos no entran, la lista se scrollea.
    card = theme.card(
        ft.Column(
            [
                ft.Text("Pagado este mes", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                ft.Divider(height=1, color=theme.BORDER),
                ft.Column(
                    items or [components.empty_state("Todavía no pagaste nada este mes.", "task_alt_rounded")],
                    spacing=8, scroll=ft.ScrollMode.AUTO, expand=True,
                ),
                totales_row,
            ],
            spacing=8,
        )
    )
    card.height = _ALTURA_PAGADO_INICIAL
    return card


def _construir_pendiente_card(pendiente: dict[Moneda, Money]) -> ft.Container:
    """Un solo numero: todo lo que falta pagar este mes, sin detalle. Pesos y
    dolares por separado (el de dolares solo si hay algo)."""
    montos = [pendiente[m] for m in Moneda if m in pendiente and (pendiente[m].cents or m == Moneda.ARS)]
    nada = all(m.cents == 0 for m in montos)
    mes = _MESES_RESUMEN[date.today().month - 1]
    color = theme.INCOME_GREEN if nada else theme.EXPENSE_RED
    # Una sola linea, chica: es un dato de un vistazo, no una seccion.
    return theme.card(
        ft.Row(
            [
                ft.Icon(ft.Icons.PENDING_ACTIONS_ROUNDED, color=color, size=18),
                ft.Text(f"Pendiente de pagar en {mes}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                *[ft.Text(m.formatted(), size=15, weight=ft.FontWeight.BOLD, color=color) for m in montos],
            ],
            spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=10,
    )


def _construir_categorias_card(page: ft.Page, por_categoria) -> ft.Container:
    distribuciones = {m: distribucion_por_categoria(por_categoria, m) for m in Moneda}
    monedas = [m for m in Moneda if distribuciones[m]]
    cuerpo = ft.Container()

    def mostrar(moneda: Moneda):
        porciones = distribuciones[moneda]
        cuerpo.content = ft.Row(
            [components.torta(porciones), components.leyenda_torta(porciones)],
            spacing=24, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def on_moneda_change(e):
        mostrar(Moneda(next(iter(e.control.selected))))
        page.update()

    encabezado = [ft.Text("Gastos por categoría", size=15, weight=ft.FontWeight.BOLD, color=theme.MOVIMIENTOS_COLOR, expand=True)]
    if len(monedas) > 1:
        # ARS y USD no se suman: cada moneda tiene su propia torta.
        encabezado.append(ft.SegmentedButton(
            segments=[ft.Segment(value=m.value, label=ft.Text(m.value)) for m in monedas],
            selected=[monedas[0].value], allow_multiple_selection=False, allow_empty_selection=False,
            show_selected_icon=False, on_change=on_moneda_change,
        ))

    if monedas:
        mostrar(monedas[0])
    else:
        cuerpo.content = components.empty_state("Sin gastos registrados todavía.")

    return theme.card(
        ft.Column(
            [
                ft.Row(encabezado, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=theme.BORDER),
                cuerpo,
            ],
            spacing=10,
        )
    )


_MESES_RESUMEN = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                  "septiembre", "octubre", "noviembre", "diciembre"]


def build_dashboard_view(page: ft.Page, dashboard_service: DashboardService, cambio_service: CambioDivisaService) -> ft.Control:
    root = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar():
        root.controls = _construir(dashboard_service.resumen())
        page.update()

    def _construir(resumen) -> list[ft.Control]:
        moneda_rows = []
        for r in resumen.por_moneda:
            if r.ingresos.cents == 0 and r.egresos.cents == 0:
                continue
            moneda_rows.append(
                ft.Column(
                    [
                        ft.Text(r.moneda.value, size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY),
                        ft.ResponsiveRow(
                            [
                                ft.Container(components.stat_card("Ingresos", r.ingresos, "trending_up_rounded", is_income=True), col=4),
                                ft.Container(components.stat_card("Egresos", r.egresos, "trending_down_rounded", is_income=False), col=4),
                                ft.Container(components.stat_card("Balance", r.balance, "account_balance_wallet_rounded", is_income=not r.balance.is_negative()), col=4),
                            ],
                            spacing=12,
                        ),
                    ],
                    spacing=8,
                )
            )

        if not moneda_rows:
            moneda_rows = [components.empty_state("Todavía no registraste movimientos.", "savings_rounded")]

        categoria_card = _construir_categorias_card(page, resumen.por_categoria)

        tarjeta_items = []
        for tt in resumen.por_tarjeta:
            detalle_partes = []
            if tt.total_pendiente_un_pago.cents > 0:
                detalle_partes.append(f"1 pago: {tt.total_pendiente_un_pago.formatted()}")
            if tt.total_pendiente_cuotas.cents > 0:
                detalle_partes.append(f"cuotas del mes: {tt.total_pendiente_cuotas.formatted()}")
            if tt.total_pendiente_debitos and tt.total_pendiente_debitos.cents > 0:
                detalle_partes.append(f"débitos automáticos del mes: {tt.total_pendiente_debitos.formatted()}")
            tarjeta_items.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=16, color=theme.TARJETAS_COLOR),
                                ft.Text(f"{tt.nombre} · {tt.moneda.value}", size=13, color=theme.TEXT_PRIMARY, expand=True),
                                ft.Text(tt.total_pendiente.formatted(), size=13, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                            ],
                            spacing=10,
                        ),
                        ft.Column(
                            [ft.Text(parte, size=11, color=theme.TEXT_SECONDARY) for parte in detalle_partes],
                            spacing=1,
                        ),
                    ],
                    spacing=2,
                )
            )
        tarjetas_card = theme.card(
            ft.Column(
                [
                    ft.Text(f"Pendiente en tarjetas · {_MESES_RESUMEN[date.today().month - 1]}", size=15, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                    ft.Text("Lo que vence este mes: cuotas, compras en 1 pago y débitos automáticos.", size=11, color=theme.TEXT_MUTED),
                    ft.Divider(height=1, color=theme.BORDER),
                    *(tarjeta_items or [components.empty_state("Este mes no vence nada de tarjetas.", "credit_card_rounded")]),
                ],
                spacing=10,
            )
        )

        prestamos_card = theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Préstamos pendientes", size=15, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR, expand=True),
                            components.category_chip(f"{resumen.prestamos_pendientes_cantidad} activo(s)", theme.PRESTAMOS_COLOR, "hourglass_top_rounded"),
                        ],
                    ),
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Row([ft.Text("ARS", size=13, color=theme.TEXT_SECONDARY, expand=True), ft.Text(resumen.prestamos_pendientes_ars.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)]),
                    ft.Row([ft.Text("USD", size=13, color=theme.TEXT_SECONDARY, expand=True), ft.Text(resumen.prestamos_pendientes_usd.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR)]),
                    *([ft.Divider(height=1, color=theme.BORDER),
                       ft.Text("Próximas cuotas", size=12, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY)]
                      if resumen.prestamos_activos else []),
                    *[
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, size=16, color=theme.PRESTAMOS_COLOR),
                                ft.Column(
                                    [
                                        ft.Text(pc.nombre, size=13, color=theme.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(f"Cuota {pc.numero_cuota} de {pc.cantidad_cuotas} · vence el {pc.fecha_vencimiento.strftime('%d/%m/%Y')}",
                                                size=11, color=theme.TEXT_SECONDARY),
                                    ],
                                    spacing=0, expand=True,
                                ),
                                ft.Text(pc.monto.formatted(), size=13, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR),
                            ],
                            spacing=10,
                        )
                        for pc in resumen.prestamos_activos
                    ],
                ],
                spacing=10,
            )
        )

        cambio_card = theme.card(
            ft.Column(
                [
                    ft.Text("Compra / venta de dólares", size=15, weight=ft.FontWeight.BOLD, color=theme.CAMBIO_COLOR),
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Text("Registrá una operación de cambio: se descuenta de una moneda y se acredita en la otra.", size=12, color=theme.TEXT_SECONDARY),
                    theme.primary_button("Nueva operación", nueva_operacion_cambio, color=theme.CAMBIO_COLOR, icon=ft.Icons.CURRENCY_EXCHANGE_ROUNDED),
                ],
                spacing=10,
            )
        )

        pagado_card = _construir_pagado_card(resumen.pagado_este_mes)

        # "Pagado este mes" ocupa lo que le falta a la columna derecha para
        # terminar a la misma altura que la izquierda. Las alturas reales solo
        # se conocen despues del layout, por eso se miden con on_size_change.
        alturas: dict[str, float] = {}

        def medir(clave: str):
            def on_size(e):
                alturas[clave] = e.height
                if len(alturas) < 3:
                    return
                disponible = alturas["izquierda"] - alturas["tarjetas"] - alturas["prestamos"] - 2 * _SEPARACION_TARJETAS
                nueva = max(_ALTURA_PAGADO_MINIMA, round(disponible))
                if pagado_card.height != nueva:
                    pagado_card.height = nueva
                    pagado_card.update()
            return on_size

        tarjetas_card.on_size_change = medir("tarjetas")
        prestamos_card.on_size_change = medir("prestamos")

        return [
            ft.Text("Resumen general", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=4),
            _construir_pendiente_card(resumen.pendiente_del_mes),
            *moneda_rows,
            ft.Container(height=8),
            ft.ResponsiveRow(
                [
                    ft.Container(ft.Column([categoria_card, cambio_card], spacing=_SEPARACION_TARJETAS, on_size_change=medir("izquierda")), col=6),
                    ft.Container(
                        ft.Column([tarjetas_card, prestamos_card, pagado_card], spacing=_SEPARACION_TARJETAS),
                        col=6,
                    ),
                ],
                spacing=16,
            ),
        ]

    def nueva_operacion_cambio(_e=None):
        operacion_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="comprar", label=ft.Text("Comprar USD"), icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED),
                ft.Segment(value="vender", label=ft.Text("Vender USD"), icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED),
            ],
            selected=["comprar"],
            allow_multiple_selection=False,
            allow_empty_selection=False,
        )

        fecha_holder = {"value": date.today()}
        fecha_text = ft.Text(fecha_holder["value"].strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                page.update()

        date_picker = ft.DatePicker(value=fecha_holder["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        cantidad_f = ft.TextField(label="Cantidad de USD", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cotizacion_f = ft.TextField(label="Cotización (ARS por USD 1)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def operacion_actual() -> str:
            return next(iter(operacion_selector.selected))

        def continuar(_e):
            try:
                cantidad_usd = components.parse_monto(cantidad_f.value, Moneda.USD, "Cantidad de dólares")
                cotizacion = components.parse_monto(cotizacion_f.value, Moneda.ARS, "Cotización").amount
                if cantidad_usd.cents <= 0:
                    raise ValueError("La cantidad debe ser mayor a cero")
                if cotizacion <= 0:
                    raise ValueError("La cotización debe ser mayor a cero")
            except (InvalidOperation, ValueError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return

            page.pop_dialog()
            confirmar_operacion(operacion_actual(), fecha_holder["value"], cantidad_usd, cotizacion)

        dialog = ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error("Compra / venta de dólares", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        operacion_selector,
                        ft.Row([ft.Text("Fecha:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        cantidad_f, cotizacion_f,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Continuar", continuar, color=theme.CAMBIO_COLOR, icon=ft.Icons.ARROW_FORWARD_ROUNDED)],
        )
        page.show_dialog(dialog)

    def confirmar_operacion(operacion: str, fecha: date, cantidad_usd: Money, cotizacion: Decimal):
        total_ars = Money.from_decimal(cantidad_usd.amount * cotizacion, Moneda.ARS)
        if operacion == "comprar":
            mensaje = f"¿Confirmás comprar {cantidad_usd.formatted()} a {Money.from_decimal(cotizacion, Moneda.ARS).formatted()} cada uno?\n\nSe van a descontar {total_ars.formatted()} y se van a sumar {cantidad_usd.formatted()}."
        else:
            mensaje = f"¿Confirmás vender {cantidad_usd.formatted()} a {Money.from_decimal(cotizacion, Moneda.ARS).formatted()} cada uno?\n\nSe van a descontar {cantidad_usd.formatted()} y se van a sumar {total_ars.formatted()}."

        def confirmar(_e):
            if operacion == "comprar":
                cambio_service.comprar_dolares(fecha, cantidad_usd, cotizacion)
            else:
                cambio_service.vender_dolares(fecha, cantidad_usd, cotizacion)
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar operación"),
            content=ft.Text(mensaje),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, confirmar", confirmar, color=theme.CAMBIO_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    refrescar()
    return root
