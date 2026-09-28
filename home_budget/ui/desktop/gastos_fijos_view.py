from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.tarjetas import TarjetaService
from .. import theme
from . import components


def build_gastos_fijos_view(
    page: ft.Page, gasto_fijo_service: GastoFijoService, categoria_repo: CategoriaRepository, tarjeta_service: TarjetaService,
) -> ft.Control:
    categorias = categoria_repo.listar(TipoMovimiento.EGRESO)

    def _campos_debito(tarjeta_actual: int | None):
        """Casilla de debito automatico + tarjeta a la que se debita. Devuelve
        (controles, funcion que lee la tarjeta elegida o None)."""
        tarjetas = tarjeta_service.listar_tarjetas()
        check = ft.Checkbox(
            label="Se paga con débito automático de tarjeta", value=tarjeta_actual is not None,
            active_color=theme.MOVIMIENTOS_COLOR, disabled=not tarjetas,
        )
        tarjeta_dd = ft.Dropdown(
            label="¿A qué tarjeta se debita?",
            value=str(tarjeta_actual) if tarjeta_actual else (str(tarjetas[0].id) if tarjetas else None),
            options=[ft.dropdown.Option(str(t.id), f"{t.nombre} ({t.moneda.value})") for t in tarjetas],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
            visible=tarjeta_actual is not None,
        )
        ayuda = ft.Text(
            "Aparece en el resumen de esa tarjeta, pero se cuenta una sola vez: como gasto fijo." if tarjetas
            else "Cargá una tarjeta en la sección Tarjetas para poder usar débito automático.",
            size=11, color=theme.TEXT_MUTED, italic=True,
        )

        def on_check(_e):
            tarjeta_dd.visible = bool(check.value)
            page.update()

        check.on_change = on_check
        return [check, tarjeta_dd, ayuda], lambda: int(tarjeta_dd.value) if check.value and tarjeta_dd.value else None

    def _nombre_tarjeta(tarjeta_id: int) -> str:
        t = tarjeta_service.obtener_tarjeta(tarjeta_id)
        return t.nombre if t else "tarjeta"
    lista_col = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar():
        gastos = gasto_fijo_service.listar()
        lista_col.controls.clear()
        if not gastos:
            lista_col.controls.append(components.empty_state("Todavía no cargaste gastos fijos.", "event_repeat_rounded"))
        for g in gastos:
            lista_col.controls.append(_gasto_card(g))
        page.update()

    def _nombre_categoria(categoria_id: int) -> str:
        cat = next((c for c in categorias if c.id == categoria_id), None)
        return cat.nombre if cat else "Categoría"

    def _gasto_card(g):
        hoy = date.today()
        proximo = gasto_fijo_service.proximo_vencimiento(g, hoy)
        ya_este_mes = gasto_fijo_service.ya_registrado_este_mes(g.id, hoy.year, hoy.month)

        acciones = [
            ft.IconButton(icon=ft.Icons.EDIT_ROUNDED, icon_color=theme.TEXT_MUTED, icon_size=18, on_click=lambda e, gasto=g: dialogo_editar_gasto(gasto)),
            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=theme.EXPENSE_RED, icon_size=18, on_click=lambda e, gid=g.id: eliminar(gid)),
        ]
        if ya_este_mes:
            acciones.insert(0, components.category_chip("Pagado este mes", theme.INCOME_GREEN, "check_circle_rounded"))
        else:
            acciones.insert(0, theme.primary_button("Registrar pago", lambda e, gasto=g: confirmar_registrar(gasto), color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED))

        return theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(g.concepto, size=16, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                            ft.Text(g.monto.formatted(), size=16, weight=ft.FontWeight.BOLD, color=theme.MOVIMIENTOS_COLOR),
                        ]
                    ),
                    ft.Text(g.detalle, size=12, color=theme.TEXT_SECONDARY) if g.detalle else ft.Container(),
                    ft.Row(
                        [
                            components.category_chip(_nombre_categoria(g.categoria_id), theme.MOVIMIENTOS_COLOR, "sell_rounded"),
                            *([components.category_chip(f"Débito automático · {_nombre_tarjeta(g.tarjeta_id)}", theme.TARJETAS_COLOR, "autorenew_rounded")] if g.tarjeta_id else []),
                            ft.Text(f"Vence el día {g.dia_mes} de cada mes", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(f"Próximo vencimiento: {proximo.strftime('%d/%m/%Y')}", size=12, color=theme.TEXT_SECONDARY),
                        ],
                        spacing=14, wrap=True,
                    ),
                    ft.Row(acciones, alignment=ft.MainAxisAlignment.START),
                ],
                spacing=10,
            ),
            padding=18,
        )

    def confirmar_registrar(gasto):
        def confirmar(_e):
            gasto_fijo_service.generar_movimiento_del_mes(gasto.id)
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar pago"),
            content=ft.Text(f'¿Registrar el pago de "{gasto.concepto}" ({gasto.monto.formatted()}) este mes?'),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, registrar", confirmar, color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def eliminar(gasto_fijo_id: int):
        def confirmar(_e):
            gasto_fijo_service.eliminar(gasto_fijo_id)
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar gasto fijo"),
            content=ft.Text("¿Seguro que querés eliminar este gasto fijo? Los pagos ya registrados no se borran."),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED)],
        )
        page.show_dialog(dialog)

    def dialogo_editar_gasto(gasto):
        monto_f = ft.TextField(label="Nuevo monto", value=str(gasto.monto.amount), filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        vencimiento_f = ft.TextField(label="Día de vencimiento (1-28)", value=str(gasto.dia_mes), filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        campos_debito, tarjeta_elegida = _campos_debito(gasto.tarjeta_id)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                nuevo_monto = Money.from_decimal((monto_f.value or "0").replace(",", "."), gasto.monto.moneda)
                nuevo_dia = int(vencimiento_f.value or "0")
                gasto_fijo_service.editar(gasto.id, nuevo_monto, nuevo_dia, tarjeta_id=tarjeta_elegida())
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar gasto fijo"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Los cambios se usan desde el próximo pago que registres. Los pagos ya hechos no se modifican.", size=12, color=theme.TEXT_SECONDARY),
                        monto_f, vencimiento_f, *campos_debito, error_text,
                    ],
                    spacing=12, tight=True,
                ),
                width=360,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Guardar", guardar, color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    def nuevo_gasto_fijo(_e=None):
        concepto_f = ft.TextField(label="Concepto (ej: Alquiler, Luz, Netflix)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        monto_f = ft.TextField(label="Monto", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        moneda_dd = ft.Dropdown(label="Moneda", value=Moneda.ARS.value, options=[ft.dropdown.Option(m.value) for m in Moneda], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        dia_f = ft.TextField(label="Día de vencimiento (1-28)", value="1", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        categoria_dd = ft.Dropdown(label="Categoría", value=str(categorias[0].id) if categorias else None, options=[ft.dropdown.Option(str(c.id), c.nombre) for c in categorias], filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        campos_debito, tarjeta_elegida = _campos_debito(None)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                monto = Money.from_decimal((monto_f.value or "0").replace(",", "."), moneda_dd.value)
                dia_mes = int(dia_f.value or "1")
                gasto_fijo_service.registrar(concepto_f.value or "", detalle_f.value or "", monto, int(categoria_dd.value), dia_mes, tarjeta_elegida())
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nuevo gasto fijo"),
            content=ft.Container(
                ft.Column(
                    [concepto_f, detalle_f, ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8), dia_f, categoria_dd, *campos_debito, error_text],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Crear", guardar, color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text("Gastos fijos", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Text("Gastos recurrentes (alquiler, servicios, suscripciones) que se repiten cada mes.", size=12, color=theme.TEXT_SECONDARY),
                ],
                spacing=2,
            ),
            theme.primary_button("Nuevo gasto fijo", nuevo_gasto_fijo, color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.ADD_ROUNDED),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar()

    return ft.Column([header, ft.Container(height=12), lista_col], expand=True, spacing=0)
