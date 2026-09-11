from __future__ import annotations

from datetime import date, datetime

import flet as ft

from ...app.domain.models import EstadoMovimiento, TipoMovimiento
from ...app.domain.money import Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.repositories.movimientos import FiltroMovimientos
from ...app.services.movimientos import MovimientoService
from .. import theme
from . import components


def build_historial_view(page: ft.Page, movimiento_service: MovimientoService, categoria_repo: CategoriaRepository) -> ft.Control:
    categorias = categoria_repo.listar()
    resultados_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
    contador_text = ft.Text("", size=12, color=theme.TEXT_MUTED)

    fecha_desde_holder = {"value": None}
    fecha_hasta_holder = {"value": None}

    fecha_desde_text = ft.Text("Sin definir", size=13, color=theme.TEXT_PRIMARY)
    fecha_hasta_text = ft.Text("Sin definir", size=13, color=theme.TEXT_PRIMARY)

    def on_desde_change(e):
        if desde_picker.value:
            fecha_desde_holder["value"] = desde_picker.value.date() if isinstance(desde_picker.value, datetime) else desde_picker.value
            fecha_desde_text.value = fecha_desde_holder["value"].strftime("%d/%m/%Y")
            page.update()

    def on_hasta_change(e):
        if hasta_picker.value:
            fecha_hasta_holder["value"] = hasta_picker.value.date() if isinstance(hasta_picker.value, datetime) else hasta_picker.value
            fecha_hasta_text.value = fecha_hasta_holder["value"].strftime("%d/%m/%Y")
            page.update()

    desde_picker = ft.DatePicker(on_change=on_desde_change)
    hasta_picker = ft.DatePicker(on_change=on_hasta_change)
    page.overlay.extend([desde_picker, hasta_picker])

    tipo_dd = ft.Dropdown(
        label="Tipo", value="todos",
        options=[ft.dropdown.Option("todos", "Todos"), ft.dropdown.Option("ingreso", "Ingresos"), ft.dropdown.Option("egreso", "Egresos")],
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=150,
    )
    categoria_dd = ft.Dropdown(
        label="Categoría", value="todas",
        options=[ft.dropdown.Option("todas", "Todas")] + [ft.dropdown.Option(str(c.id), c.nombre) for c in categorias],
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=190,
    )
    moneda_dd = ft.Dropdown(
        label="Moneda", value="todas",
        options=[ft.dropdown.Option("todas", "Todas")] + [ft.dropdown.Option(m.value) for m in Moneda],
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=140,
    )
    estado_dd = ft.Dropdown(
        label="Estado", value="todos",
        options=[ft.dropdown.Option("todos", "Todos")] + [ft.dropdown.Option(e.value) for e in EstadoMovimiento],
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=150,
    )
    concepto_field = ft.TextField(
        label="Buscar por concepto o detalle", filled=True, bgcolor=theme.SURFACE_ALT,
        border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=260,
    )

    def aplicar_filtros(_e=None):
        filtro = FiltroMovimientos(
            fecha_desde=fecha_desde_holder["value"],
            fecha_hasta=fecha_hasta_holder["value"],
            tipo=TipoMovimiento(tipo_dd.value) if tipo_dd.value != "todos" else None,
            categoria_id=int(categoria_dd.value) if categoria_dd.value != "todas" else None,
            moneda=Moneda(moneda_dd.value) if moneda_dd.value != "todas" else None,
            estado=EstadoMovimiento(estado_dd.value) if estado_dd.value != "todos" else None,
            concepto=concepto_field.value or None,
        )
        resultados = movimiento_service.listar(filtro)
        resultados_col.controls.clear()
        if not resultados:
            resultados_col.controls.append(components.empty_state("No hay movimientos que coincidan con los filtros.", "search_off_rounded"))
        else:
            for m in resultados:
                resultados_col.controls.append(components.movimiento_row(m))
        contador_text.value = f"{len(resultados)} movimiento(s) encontrado(s)"
        page.update()

    def limpiar_filtros(_e=None):
        fecha_desde_holder["value"] = None
        fecha_hasta_holder["value"] = None
        fecha_desde_text.value = "Sin definir"
        fecha_hasta_text.value = "Sin definir"
        tipo_dd.value = "todos"
        categoria_dd.value = "todas"
        moneda_dd.value = "todas"
        estado_dd.value = "todos"
        concepto_field.value = ""
        aplicar_filtros()

    filtros_card = theme.card(
        ft.Column(
            [
                ft.Text("Filtros", size=14, weight=ft.FontWeight.BOLD, color=theme.HISTORIAL_COLOR),
                ft.Row(
                    [
                        ft.Column([ft.Text("Desde", size=11, color=theme.TEXT_MUTED), ft.Row([fecha_desde_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, icon_size=16, on_click=lambda e: (setattr(desde_picker, "open", True), page.update()))])]),
                        ft.Column([ft.Text("Hasta", size=11, color=theme.TEXT_MUTED), ft.Row([fecha_hasta_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, icon_size=16, on_click=lambda e: (setattr(hasta_picker, "open", True), page.update()))])]),
                        tipo_dd, categoria_dd, moneda_dd, estado_dd, concepto_field,
                    ],
                    spacing=12, wrap=True, vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                ft.Row(
                    [
                        theme.primary_button("Aplicar filtros", aplicar_filtros, color=theme.HISTORIAL_COLOR, icon=ft.Icons.FILTER_ALT_ROUNDED),
                        theme.secondary_button("Limpiar", limpiar_filtros, icon=ft.Icons.CLOSE_ROUNDED),
                    ],
                    spacing=10,
                ),
            ],
            spacing=14,
        )
    )

    aplicar_filtros()

    return ft.Column(
        [
            ft.Text("Historial", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=8),
            filtros_card,
            ft.Container(height=12),
            contador_text,
            ft.Container(height=4),
            resultados_col,
        ],
        expand=True, spacing=0,
    )
