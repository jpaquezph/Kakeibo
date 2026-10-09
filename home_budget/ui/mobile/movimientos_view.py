"""Movimientos en el celular: la lista con un boton flotante para cargar, y el
formulario a pantalla completa. Tocar un movimiento lo abre para editarlo."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.models import METODOS_PAGO, EstadoMovimiento, Movimiento, TipoMovimiento
from ...app.domain.money import Moneda
from ...app.repositories.movimientos import FiltroMovimientos
from .. import theme
from ..desktop import components
from . import componentes as mc

# Mas alla de esto la lista se hace larga para el pulgar: lo demas se encuentra con el buscador.
MAX_EN_LISTA = 80


def build_movimientos_view(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    lista = ft.Column(spacing=8)
    filtro = {"tipo": "todos", "busqueda": "", "orden": "recientes"}

    def refrescar():
        tipo = None if filtro["tipo"] == "todos" else TipoMovimiento(filtro["tipo"])
        todos = servicios.movimientos.listar(FiltroMovimientos(tipo=tipo))  # vienen del mas reciente al mas antiguo
        if filtro["orden"] == "antiguos":
            todos.reverse()
        movimientos = mc.filtrar_y_ordenar(todos, filtro["busqueda"], filtro["orden"],
                                           lambda m: f"{m.concepto} {m.detalle} {m.categoria_nombre or ''}", lambda m: m.monto)
        lista.controls = [mc.fila_movimiento(m, editar) for m in movimientos[:MAX_EN_LISTA]]
        if not todos:
            lista.controls = [components.empty_state("Todavía no cargaste ningún movimiento.", "receipt_long_rounded")]
        elif not movimientos:
            lista.controls = [mc.sin_resultados()]
        elif len(movimientos) > MAX_EN_LISTA:
            lista.controls.append(ft.Text(f"Se muestran {MAX_EN_LISTA} de {len(movimientos)}. Buscá para encontrar el resto.",
                                          size=12, color=theme.TEXT_MUTED, text_align=ft.TextAlign.CENTER))

    def al_filtrar(e):
        filtro["tipo"] = next(iter(e.control.selected))
        refrescar()
        page.update()

    def al_buscar(busqueda: str, orden: str):
        filtro["busqueda"], filtro["orden"] = busqueda, orden
        refrescar()
        page.update()

    def nuevo(_e=None):
        nav.abrir("Nuevo movimiento", lambda: _formulario(page, nav, servicios, None), theme.MOVIMIENTOS_COLOR)

    def editar(movimiento: Movimiento):
        nav.abrir("Editar movimiento", lambda: _formulario(page, nav, servicios, movimiento), theme.MOVIMIENTOS_COLOR)

    selector = ft.SegmentedButton(
        segments=[
            ft.Segment(value="todos", label=ft.Text("Todos")),
            ft.Segment(value="ingreso", label=ft.Text("Ingresos")),
            ft.Segment(value="egreso", label=ft.Text("Egresos")),
        ],
        selected=["todos"], allow_multiple_selection=False, allow_empty_selection=False,
        show_selected_icon=False, on_change=al_filtrar, expand=True,
    )

    refrescar()
    return ft.Stack(
        [
            mc.pantalla([
                mc.barra_busqueda([("recientes", "Más recientes"), ("antiguos", "Más antiguos"), *mc.ORDENES_COMUNES], al_buscar,
                                  theme.MOVIMIENTOS_COLOR),
                ft.Row([selector]), lista,
            ]),
            mc.boton_flotante(ft.Icons.ADD_ROUNDED, theme.MOVIMIENTOS_COLOR, nuevo, "Nuevo movimiento"),
        ],
        expand=True,
    )


def _formulario(page: ft.Page, nav: mc.Navegacion, servicios, movimiento: Movimiento | None) -> ft.Control:
    es_edicion = movimiento is not None
    tipo_inicial = movimiento.tipo if es_edicion else TipoMovimiento.EGRESO
    categorias = servicios.categorias.listar()

    def categorias_de(tipo: TipoMovimiento, actual: int | None = None) -> list:
        """Las categorias del tipo; `actual` se agrega si fue quitada, para
        que editar un movimiento viejo no le cambie la categoria."""
        opciones = [c for c in categorias if c.tipo == tipo]
        if actual is not None and all(c.id != actual for c in opciones):
            quitada = servicios.categorias.obtener(actual)
            if quitada is not None and quitada.tipo == tipo:
                opciones.append(quitada)
        return opciones

    tipo_selector = ft.SegmentedButton(
        segments=[
            ft.Segment(value="egreso", label=ft.Text("Egreso"), icon=ft.Icons.TRENDING_DOWN_ROUNDED),
            ft.Segment(value="ingreso", label=ft.Text("Ingreso"), icon=ft.Icons.TRENDING_UP_ROUNDED),
        ],
        selected=[tipo_inicial.value], allow_multiple_selection=False, allow_empty_selection=False, expand=True,
    )
    fila_fecha, fecha_elegida = mc.selector_fecha(page, "Fecha de pago", movimiento.fecha if es_edicion else date.today())
    # El monto va primero y grande: es lo que se carga parado en la caja.
    monto_f = mc.campo("Monto", value=components.monto_editable(movimiento.monto) if es_edicion else "",
                       keyboard_type=ft.KeyboardType.NUMBER, text_size=20, autofocus=not es_edicion)
    moneda_dd = mc.desplegable("Moneda", movimiento.monto.moneda.value if es_edicion else Moneda.ARS.value,
                               [ft.dropdown.Option(m.value) for m in Moneda])
    concepto_f = mc.campo("Concepto", value=movimiento.concepto if es_edicion else "")
    detalle_f = mc.campo("Detalle (opcional)", value=movimiento.detalle if es_edicion else "")

    opciones = categorias_de(tipo_inicial, movimiento.categoria_id if es_edicion else None)
    categoria_dd = mc.desplegable(
        "Categoría", str(movimiento.categoria_id) if es_edicion else (str(opciones[0].id) if opciones else None),
        [ft.dropdown.Option(str(c.id), c.nombre) for c in opciones], expand=True,
    )
    # Sin "tarjeta de credito": esas compras se cargan en Tarjetas.
    metodo_dd = mc.desplegable(
        "Medio de cobro" if tipo_inicial == TipoMovimiento.INGRESO else "Método de pago",
        movimiento.metodo_pago if es_edicion else "efectivo",
        [ft.dropdown.Option("", "Sin especificar")] + [ft.dropdown.Option(k, v) for k, v in METODOS_PAGO.items()], expand=True,
    )
    estado_dd = mc.desplegable("Estado", movimiento.estado.value if es_edicion else EstadoMovimiento.CONFIRMADO.value,
                               [ft.dropdown.Option(e.value, e.value.capitalize()) for e in EstadoMovimiento], expand=True)
    error = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def tipo_actual() -> TipoMovimiento:
        return TipoMovimiento(next(iter(tipo_selector.selected)))

    def al_cambiar_tipo(_e):
        nuevas = categorias_de(tipo_actual())
        categoria_dd.options = [ft.dropdown.Option(str(c.id), c.nombre) for c in nuevas]
        categoria_dd.value = str(nuevas[0].id) if nuevas else None
        metodo_dd.label = "Medio de cobro" if tipo_actual() == TipoMovimiento.INGRESO else "Método de pago"
        page.update()

    tipo_selector.on_change = al_cambiar_tipo

    def guardar(_e):
        try:
            monto = components.parse_monto(monto_f.value, moneda_dd.value)
            if not categoria_dd.value:
                raise ValueError("Elegí una categoría")
            if es_edicion:
                movimiento.tipo = tipo_actual()
                movimiento.fecha = fecha_elegida()
                movimiento.concepto = concepto_f.value or ""
                movimiento.detalle = detalle_f.value or ""
                movimiento.monto = monto
                movimiento.categoria_id = int(categoria_dd.value)
                movimiento.estado = EstadoMovimiento(estado_dd.value)
                movimiento.metodo_pago = metodo_dd.value or ""
                servicios.movimientos.editar(movimiento)
            else:
                servicios.movimientos.registrar(
                    tipo=tipo_actual(), fecha=fecha_elegida(), concepto=concepto_f.value or "", detalle=detalle_f.value or "",
                    monto=monto, categoria_id=int(categoria_dd.value), estado=EstadoMovimiento(estado_dd.value),
                    metodo_pago=metodo_dd.value or "",
                )
        except (ValueError, ArithmeticError) as exc:
            error.value = str(exc)
            error.visible = True
            page.update()
            return
        nav.volver()
        nav.avisar("Movimiento guardado")

    def eliminar(_e):
        def confirmar(_e):
            servicios.movimientos.eliminar(movimiento.id)
            page.pop_dialog()
            nav.volver()
            nav.avisar("Movimiento eliminado")

        page.show_dialog(theme.dialogo(
            "Eliminar movimiento", ft.Text(f'¿Seguro que querés eliminar "{movimiento.concepto}"?', color=theme.TEXT_PRIMARY),
            [
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
            icono="delete_outline_rounded", color=theme.EXPENSE_RED, ancho=300,
        ))

    return mc.pantalla([
        ft.Row([tipo_selector]),
        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
        concepto_f,
        ft.Row([categoria_dd]),
        fila_fecha,
        ft.Row([metodo_dd]),
        ft.Row([estado_dd]),
        detalle_f,
        error,
        mc.boton_ancho("Guardar", guardar, theme.MOVIMIENTOS_COLOR, ft.Icons.CHECK_ROUNDED),
        *([ft.Row([ft.TextButton("Eliminar movimiento", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=eliminar,
                                 style=ft.ButtonStyle(color=theme.EXPENSE_RED))], alignment=ft.MainAxisAlignment.CENTER)]
          if es_edicion else []),
    ])
