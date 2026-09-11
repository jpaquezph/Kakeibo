from __future__ import annotations

from datetime import date, datetime

import flet as ft

from ...app.domain.models import EstadoMovimiento, Movimiento, TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.movimientos import MovimientoService
from .. import theme
from . import components

_COLORES_CATEGORIA_NUEVA = [
    theme.MOVIMIENTOS_COLOR, theme.TARJETAS_COLOR, theme.PRESTAMOS_COLOR,
    theme.HISTORIAL_COLOR, theme.DASHBOARD_COLOR, "#7CB342", "#8D6E63", "#5C6BC0",
]


def build_movimientos_view(page: ft.Page, movimiento_service: MovimientoService, categoria_repo: CategoriaRepository) -> ft.Control:
    categorias = categoria_repo.listar()
    lista_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar():
        movimientos = movimiento_service.listar()
        lista_col.controls.clear()
        if not movimientos:
            lista_col.controls.append(components.empty_state("Todavía no cargaste ningún movimiento.", "receipt_long_rounded"))
        else:
            for m in movimientos:
                lista_col.controls.append(components.movimiento_row(m, editar, eliminar))
        page.update()

    def eliminar(movimiento: Movimiento):
        def confirmar(_e):
            movimiento_service.eliminar(movimiento.id)
            page.pop_dialog()
            refrescar()

        def cancelar(_e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar movimiento"),
            content=ft.Text(f'¿Seguro que querés eliminar "{movimiento.concepto}"?'),
            actions=[
                theme.secondary_button("Cancelar", cancelar),
                theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def editar(movimiento: Movimiento | None):
        abrir_formulario(movimiento)

    def nuevo(_e=None):
        abrir_formulario(None)

    def categorias_de(tipo: TipoMovimiento) -> list:
        return [c for c in categorias if c.tipo == tipo]

    def abrir_formulario(movimiento: Movimiento | None):
        es_edicion = movimiento is not None
        tipo_inicial = movimiento.tipo if es_edicion else TipoMovimiento.EGRESO
        fecha_elegida = {"value": movimiento.fecha if es_edicion else date.today()}

        tipo_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="ingreso", label=ft.Text("Ingreso"), icon=ft.Icons.TRENDING_UP_ROUNDED),
                ft.Segment(value="egreso", label=ft.Text("Egreso"), icon=ft.Icons.TRENDING_DOWN_ROUNDED),
            ],
            selected=[tipo_inicial.value],
            allow_multiple_selection=False,
            allow_empty_selection=False,
        )
        fecha_text = ft.Text(fecha_elegida["value"].strftime("%d/%m/%Y"), size=14, color=theme.TEXT_PRIMARY)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_elegida["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_elegida["value"].strftime("%d/%m/%Y")
                page.update()

        date_picker = ft.DatePicker(value=fecha_elegida["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        def abrir_calendario(_e):
            date_picker.open = True
            page.update()

        concepto_field = ft.TextField(label="Concepto", value=movimiento.concepto if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_field = ft.TextField(label="Detalle (opcional)", value=movimiento.detalle if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        monto_field = ft.TextField(label="Monto", value=str(movimiento.monto.amount) if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        moneda_dd = ft.Dropdown(
            label="Moneda",
            value=movimiento.monto.moneda.value if es_edicion else Moneda.ARS.value,
            options=[ft.dropdown.Option(m.value) for m in Moneda],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )

        opciones_iniciales = categorias_de(tipo_inicial)
        categoria_dd = ft.Dropdown(
            label="Categoría",
            value=str(movimiento.categoria_id) if es_edicion else (str(opciones_iniciales[0].id) if opciones_iniciales else None),
            options=[ft.dropdown.Option(str(c.id), c.nombre) for c in opciones_iniciales],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
            expand=True,
        )
        estado_dd = ft.Dropdown(
            label="Estado",
            value=movimiento.estado.value if es_edicion else EstadoMovimiento.CONFIRMADO.value,
            options=[ft.dropdown.Option(e.value) for e in EstadoMovimiento],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        fijo_check = ft.Checkbox(label="Es un gasto fijo", value=movimiento.fijo if es_edicion else False, visible=tipo_inicial == TipoMovimiento.EGRESO)

        nueva_categoria_field = ft.TextField(
            label="Nombre de la categoría nueva", filled=True, bgcolor=theme.SURFACE_ALT,
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, dense=True,
        )
        nueva_categoria_row = ft.Row([nueva_categoria_field], spacing=8, visible=False)

        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def tipo_actual() -> TipoMovimiento:
            return TipoMovimiento(next(iter(tipo_selector.selected)))

        def on_tipo_change(_e):
            tipo = tipo_actual()
            opciones = categorias_de(tipo)
            categoria_dd.options = [ft.dropdown.Option(str(c.id), c.nombre) for c in opciones]
            categoria_dd.value = str(opciones[0].id) if opciones else None
            fijo_check.visible = tipo == TipoMovimiento.EGRESO
            if tipo == TipoMovimiento.INGRESO:
                fijo_check.value = False
            nueva_categoria_row.visible = False
            nueva_categoria_field.value = ""
            page.update()

        tipo_selector.on_change = on_tipo_change

        def alternar_nueva_categoria(_e):
            nueva_categoria_row.visible = not nueva_categoria_row.visible
            page.update()

        def crear_categoria(_e):
            nombre = (nueva_categoria_field.value or "").strip()
            if not nombre:
                return
            tipo = tipo_actual()
            color = _COLORES_CATEGORIA_NUEVA[len(categorias) % len(_COLORES_CATEGORIA_NUEVA)]
            try:
                nueva = categoria_repo.crear(nombre, color, "label_rounded", tipo)
            except ValueError as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            categorias.append(nueva)
            opciones = categorias_de(tipo)
            categoria_dd.options = [ft.dropdown.Option(str(c.id), c.nombre) for c in opciones]
            categoria_dd.value = str(nueva.id)
            nueva_categoria_field.value = ""
            nueva_categoria_row.visible = False
            error_text.visible = False
            page.update()

        categoria_row = ft.Row(
            [
                categoria_dd,
                ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, icon_color=theme.MOVIMIENTOS_COLOR, tooltip="Nueva categoría", on_click=alternar_nueva_categoria),
            ],
            spacing=4,
        )
        nueva_categoria_row.controls.append(
            ft.IconButton(icon=ft.Icons.CHECK_CIRCLE_ROUNDED, icon_color=theme.INCOME_GREEN, tooltip="Crear categoría", on_click=crear_categoria)
        )

        def guardar(_e):
            try:
                monto = Money.from_decimal((monto_field.value or "0").replace(",", "."), moneda_dd.value)
                if not categoria_dd.value:
                    raise ValueError("Elegí o creá una categoría")
                if es_edicion:
                    movimiento.tipo = tipo_actual()
                    movimiento.fecha = fecha_elegida["value"]
                    movimiento.concepto = concepto_field.value or ""
                    movimiento.detalle = detalle_field.value or ""
                    movimiento.monto = monto
                    movimiento.categoria_id = int(categoria_dd.value)
                    movimiento.estado = EstadoMovimiento(estado_dd.value)
                    movimiento.fijo = fijo_check.value
                    movimiento_service.editar(movimiento)
                else:
                    movimiento_service.registrar(
                        tipo=tipo_actual(),
                        fecha=fecha_elegida["value"],
                        concepto=concepto_field.value or "",
                        detalle=detalle_field.value or "",
                        monto=monto,
                        categoria_id=int(categoria_dd.value),
                        estado=EstadoMovimiento(estado_dd.value),
                        fijo=fijo_check.value,
                    )
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return

            page.pop_dialog()
            refrescar()

        def cancelar(_e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar movimiento" if es_edicion else "Nuevo movimiento", color=theme.TEXT_PRIMARY),
            content=ft.Container(
                content=ft.Column(
                    [
                        tipo_selector,
                        ft.Row([ft.Text("Fecha:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=abrir_calendario)]),
                        concepto_field,
                        detalle_field,
                        ft.Row([ft.Container(monto_field, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
                        categoria_row,
                        nueva_categoria_row,
                        estado_dd,
                        fijo_check,
                        error_text,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=420,
            ),
            actions=[
                theme.secondary_button("Cancelar", cancelar),
                theme.primary_button("Guardar", guardar, color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    header = ft.Row(
        [
            ft.Text("Movimientos", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            theme.primary_button("Nuevo movimiento", nuevo, color=theme.MOVIMIENTOS_COLOR, icon=ft.Icons.ADD_ROUNDED),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar()

    return ft.Column([header, ft.Container(height=8), lista_col], expand=True, spacing=0)
