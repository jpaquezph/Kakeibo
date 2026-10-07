"""Compra mensual: tabla tipo planilla para comparar precios entre locales.

Filas = productos; por cada local un bloque de columnas (precio unitario,
% de descuento, total y detalle). Las celdas se editan en el lugar y se guardan
al salir del campo o con Enter. El local mas barato de cada producto se marca
en verde; los productos sin precio en ningun local, en rosa.
"""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.compra_mensual import (
    MAX_LOCALES, MENSAJE_MAX_LOCALES, MESES, ORDENES_PRODUCTOS, CompraMensualService, InfoLista, ListaCompra, calcular,
    coincide_busqueda, ordenar_productos,
)
from ...app.services.tarjetas import TarjetaService
from .. import theme
from . import components
from .inversiones_forms import _CampoFecha, fmt_decimal, parse_decimal
from .tarjetas_view import SelectorResumen

# Mes que se esta viendo, orden y busqueda: se recuerdan al volver a la seccion.
# ver_detalle: id de la compra cerrada cuyo detalle se esta consultando.
_estado = {"anio": date.today().year, "mes": date.today().month, "detalle": True, "orden": "carga", "busqueda": "",
           "ver_detalle": None}

ANCHO_PRODUCTO = 170
ANCHO_CANTIDAD = 70
ANCHO_ACCION = 36
ANCHO_PRECIO = 86
ANCHO_DESC = 58
ANCHO_TOTAL = 104
ANCHO_DETALLE = 130
ANCHO_FIJO = ANCHO_PRODUCTO + ANCHO_CANTIDAD + ANCHO_ACCION   # columnas que no se desplazan


def _ancho_local(con_detalle: bool) -> int:
    return ANCHO_PRECIO + ANCHO_DESC + ANCHO_TOTAL + (ANCHO_DETALLE if con_detalle else 0)
ALTO_FILA = 40
FILAS_PRIMERA_TANDA = 12
ALTO_LOCAL = 32
ALTO_COLUMNAS = 30
ALTO_PIE = 44


def _celda(control: ft.Control, ancho: int, bg=None, borde_izq: bool = False) -> ft.Container:
    return ft.Container(
        control, width=ancho, height=ALTO_FILA, bgcolor=bg, alignment=ft.Alignment.CENTER_LEFT,
        padding=theme.pad(horizontal=6),
        border=ft.border.Border(
            left=ft.border.BorderSide(2 if borde_izq else 0, theme.BORDER),
            bottom=ft.border.BorderSide(1, theme.BORDER),
        ),
    )


# Una tabla tiene cientos de casillas y cada propiedad se envia a la ventana:
# los colores del texto salen del tema (no se repiten en cada casilla).
_PADDING_CAMPO = ft.padding.Padding(left=2, right=2, top=6, bottom=6)


def _lineas_columnas(cantidad_locales: int, con_detalle: bool) -> ft.BoxDecoration:
    """Lineas verticales finas entre Precio / Desc. / Total / Detalle de cada
    local, pintadas como una sola decoracion encima del bloque de filas (una
    linea por casilla serian cientos de controles mas y la seccion tardaria
    mas en abrir). Es un degradado de franjas que se repite una vez por
    local. Se pinta encima, asi tambien se ve sobre las casillas en verde."""
    ancho = _ancho_local(con_detalle)
    bordes = [ANCHO_PRECIO, ANCHO_PRECIO + ANCHO_DESC] + ([ANCHO_PRECIO + ANCHO_DESC + ANCHO_TOTAL] if con_detalle else [])
    transparente = ft.Colors.TRANSPARENT
    colores, paradas = [], []
    for x in bordes:
        colores += [transparente, theme.BORDER, theme.BORDER, transparente]
        paradas += [x / ancho, x / ancho, (x + 1) / ancho, (x + 1) / ancho]
    total = cantidad_locales * ancho
    return ft.BoxDecoration(gradient=ft.LinearGradient(
        begin=ft.Alignment(-1, 0), end=ft.Alignment(-1 + 2 * ancho / total, 0),
        colors=colores, stops=paradas, tile_mode=ft.GradientTileMode.REPEATED,
    ))


def _campo(valor: str, alinear_derecha: bool = False, hint: str = "") -> ft.TextField:
    return ft.TextField(
        value=valor, dense=True, text_size=13, border=ft.InputBorder.NONE, hint_text=hint or None,
        content_padding=_PADDING_CAMPO, text_align=ft.TextAlign.RIGHT if alinear_derecha else None,
    )


def _texto_encabezado(texto: str, ancho: int, derecha: bool = False, borde_izq: bool = False) -> ft.Container:
    return ft.Container(
        ft.Text(texto, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY,
                text_align=ft.TextAlign.RIGHT if derecha else ft.TextAlign.LEFT),
        width=ancho, height=ALTO_COLUMNAS, padding=theme.pad(horizontal=6),
        alignment=ft.Alignment.CENTER_RIGHT if derecha else ft.Alignment.CENTER_LEFT,
        border=ft.border.Border(left=ft.border.BorderSide(2, theme.BORDER)) if borde_izq else None,
    )


def _decimal_o_none(texto: str | None, campo: str) -> Decimal | None:
    return parse_decimal(texto, campo) if (texto or "").strip() else None


def build_compra_mensual_view(
    page: ft.Page, service: CompraMensualService, categoria_repo: CategoriaRepository, tarjeta_service: TarjetaService,
) -> ft.Control:
    root = ft.Column(expand=True, spacing=14)
    # Barrita para mover los locales, fija al pie (la llena _tabla).
    barra_inferior = ft.Container(visible=False, padding=theme.pad_only(left=13, top=4, right=13, bottom=2))

    def avisar(mensaje: str, error: bool = False):
        page.show_dialog(ft.SnackBar(ft.Text(mensaje), bgcolor=theme.EXPENSE_RED if error else None))

    def mover_mes(delta: int):
        total = _estado["anio"] * 12 + (_estado["mes"] - 1) + delta
        _estado["anio"], _estado["mes"] = total // 12, total % 12 + 1
        _estado["ver_detalle"] = None
        reconstruir()

    def ir_a_hoy(_e=None):
        _estado["anio"], _estado["mes"] = date.today().year, date.today().month
        _estado["ver_detalle"] = None
        reconstruir()

    def reconstruir():
        root.controls = construir()
        page.update()

    # ---------- dialogos ----------

    def dialogo_nombre(titulo: str, etiqueta: str, valor: str, guardar, extra_accion=None, con_cantidad: str | None = None,
                       ejemplo: str = "", icono: str = "storefront_rounded"):
        nombre_f = ft.TextField(label=etiqueta, value=valor, hint_text=ejemplo, autofocus=True, filled=True, bgcolor=theme.SURFACE_ALT,
                                border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        cantidad_f = ft.TextField(label="Cantidad", value=con_cantidad, filled=True, bgcolor=theme.SURFACE_ALT,
                                  border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=140,
                                  hint_text="Ej: 10") if con_cantidad is not None else None
        error = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

        def ok(_e=None):
            try:
                if cantidad_f is not None:
                    guardar(nombre_f.value or "", parse_decimal(cantidad_f.value, "Cantidad"))
                else:
                    guardar(nombre_f.value or "")
            except ValueError as exc:
                error.value, error.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            reconstruir()

        nombre_f.on_submit = ok
        if cantidad_f is not None:
            cantidad_f.on_submit = ok
        acciones = []
        if extra_accion:
            acciones.append(extra_accion)
        acciones += [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                     theme.primary_button("Guardar", ok, color=theme.COMPRAS_COLOR)]
        page.show_dialog(theme.dialogo(
            titulo, ft.Column([c for c in (nombre_f, cantidad_f, error) if c is not None], spacing=12, tight=True),
            acciones, icono=icono, color=theme.COMPRAS_COLOR, ancho=380,
        ))

    def confirmar(titulo: str, texto: str, accion):
        def si(_e):
            page.pop_dialog()
            accion()
            reconstruir()

        page.show_dialog(theme.dialogo(
            titulo, ft.Text(texto, size=13, color=theme.TEXT_SECONDARY),
            [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
             theme.primary_button("Eliminar", si, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED)],
            icono="delete_outline_rounded", color=theme.EXPENSE_RED,
        ))

    def nuevo_local(lista: ListaCompra):
        if len(lista.locales) >= MAX_LOCALES:
            page.show_dialog(theme.dialogo(
                "No se pueden agregar más locales", ft.Text(MENSAJE_MAX_LOCALES, size=13, color=theme.TEXT_SECONDARY),
                [theme.primary_button("Entendido", lambda e: page.pop_dialog(), color=theme.COMPRAS_COLOR)],
                icono="storefront_rounded", color=theme.COMPRAS_COLOR, ancho=380,
            ))
            return
        dialogo_nombre("Agregar local", "Nombre del local", "", lambda nombre: service.agregar_local(lista.id, nombre),
                       ejemplo="Ej: COTO, Carrefour, PedidosYa")

    def editar_local(local):
        eliminar = ft.TextButton(
            "Eliminar local", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, style=ft.ButtonStyle(color=theme.EXPENSE_RED),
            on_click=lambda e: (page.pop_dialog(), confirmar(
                "Eliminar local", f'¿Eliminar "{local.nombre}" de la lista de este mes? Se borran los precios cargados para ese local.',
                lambda: service.eliminar_local(local.id))),
        )
        dialogo_nombre("Editar local", "Nombre del local", local.nombre,
                       lambda nombre: service.renombrar_local(local.id, nombre), extra_accion=eliminar)

    def nuevo_producto(lista: ListaCompra):
        dialogo_nombre("Agregar producto", "Producto", "",
                       lambda nombre, cantidad: service.agregar_producto(lista.id, nombre, cantidad), con_cantidad="1",
                       ejemplo="Ej: Fideos", icono="add_shopping_cart_rounded")

    def eliminar_producto(producto):
        confirmar("Eliminar producto", f'¿Eliminar "{producto.nombre}" de la lista de este mes?',
                  lambda: service.eliminar_producto(producto.id))

    def confirmar_accion(titulo: str, texto: str, boton: str, icono: str, accion):
        def si(_e):
            page.pop_dialog()
            accion()

        page.show_dialog(theme.dialogo(
            titulo, ft.Text(texto, size=13, color=theme.TEXT_SECONDARY),
            [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
             theme.primary_button(boton, si, color=theme.COMPRAS_COLOR, icon=theme.to_icon(icono))],
            icono=icono, color=theme.COMPRAS_COLOR, ancho=400,
        ))

    def copiar_de_otro_mes(lista: ListaCompra):
        otras = [i for i in service.listas() if i.id != lista.id]
        if not otras:
            page.show_dialog(theme.dialogo(
                "Copiar de otro mes", ft.Text("Todavía no hay otro mes con lista para copiar.", size=13, color=theme.TEXT_SECONDARY),
                [theme.primary_button("Entendido", lambda e: page.pop_dialog(), color=theme.COMPRAS_COLOR)],
                icono="content_copy_rounded", color=theme.COMPRAS_COLOR, ancho=380,
            ))
            return
        anterior = next((i for i in otras if (i.anio, i.mes) < (lista.anio, lista.mes)), otras[0])
        origen_dd = ft.Dropdown(
            label="Copiar de", value=str(anterior.id), filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM,
            border_color=theme.BORDER, width=380,
            options=[ft.dropdown.Option(str(i.id), f"{i.titulo} · {i.cantidad_locales} locales, {i.cantidad_productos} productos"
                                        + (" (cerrada)" if i.cerrada else "")) for i in otras],
        )
        locales_c = ft.Checkbox(label="Locales", value=True, active_color=theme.COMPRAS_COLOR)
        productos_c = ft.Checkbox(label="Productos (con su cantidad)", value=True, active_color=theme.COMPRAS_COLOR)
        error = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

        def copiar(_e):
            try:
                n_locales, n_productos = service.copiar_de(lista.id, int(origen_dd.value), bool(locales_c.value), bool(productos_c.value))
            except ValueError as exc:
                error.value, error.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            reconstruir()
            if n_locales or n_productos:
                avisar(f"Se copiaron {n_locales} local(es) y {n_productos} producto(s).")
            else:
                avisar("No había nada nuevo para copiar: ya estaban todos en este mes.")

        page.show_dialog(theme.dialogo(
            f"Copiar a {lista.titulo}",
            ft.Column([
                origen_dd, locales_c, productos_c,
                ft.Text("No se copian precios ni descuentos. Lo que ya está en este mes no se duplica "
                        f"y se respeta el máximo de {MAX_LOCALES} locales.", size=12, color=theme.TEXT_SECONDARY),
                error,
            ], spacing=8, tight=True),
            [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
             theme.primary_button("Copiar", copiar, color=theme.COMPRAS_COLOR, icon=ft.Icons.CONTENT_COPY_ROUNDED)],
            icono="content_copy_rounded", color=theme.COMPRAS_COLOR, ancho=400,
        ))

    def cerrar_compra(lista: ListaCompra):
        def accion():
            service.cerrar_lista(lista.id)
            _estado["ver_detalle"] = None
            reconstruir()
            avisar(f"Compra de {lista.titulo} cerrada")

        confirmar_accion(
            "Cerrar compra mensual",
            f"¿Cerrar la compra de {lista.titulo}? Queda guardada como resumen (solo lectura) y la sección carga más rápido. "
            "Podés ver el detalle o reabrirla cuando quieras.",
            "Cerrar compra", "lock_rounded", accion,
        )

    def reabrir_compra(info: InfoLista):
        def accion():
            service.reabrir_lista(info.id)
            _estado["ver_detalle"] = None
            reconstruir()
            avisar(f"Compra de {info.titulo} reabierta")

        confirmar_accion(
            "Reabrir compra",
            f"¿Reabrir la compra de {info.titulo}? Vuelve a la tabla editable con todo lo que tenía.",
            "Reabrir", "lock_open_rounded", accion,
        )

    def ir_a(info: InfoLista):
        page.pop_dialog()
        _estado["anio"], _estado["mes"], _estado["ver_detalle"] = info.anio, info.mes, None
        reconstruir()

    def ver_cerradas(_e=None):
        filas = []
        for info in service.listas(solo_cerradas=True):
            filas.append(ft.Row([
                ft.Icon(ft.Icons.LOCK_ROUNDED, size=16, color=theme.TEXT_MUTED),
                ft.Column([
                    ft.Text(info.titulo, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                    ft.Text(f"{info.cantidad_productos} artículos · {info.total.formatted() if info.total else '—'}", size=12,
                            color=theme.TEXT_SECONDARY),
                ], spacing=0, expand=True),
                ft.TextButton("Ver", on_click=lambda e, i=info: ir_a(i), style=ft.ButtonStyle(color=theme.COMPRAS_COLOR)),
            ], spacing=10))
        page.show_dialog(theme.dialogo(
            "Compras cerradas", ft.Column(filas, spacing=8, tight=True, scroll=ft.ScrollMode.AUTO, height=min(360, 52 * len(filas))),
            [theme.secondary_button("Cerrar", lambda e: page.pop_dialog())],
            icono="lock_rounded", color=theme.COMPRAS_COLOR, ancho=380,
        ))

    # ---------- compra cerrada: resumen y detalle de solo lectura ----------

    def tarjeta_cerrada(info: InfoLista) -> ft.Control:
        registrado = info.total_registrado is not None and info.total_registrado.cents > 0
        lineas = [
            ft.Row([
                ft.Icon(ft.Icons.LOCK_ROUNDED, size=18, color=theme.TEXT_SECONDARY),
                ft.Text(info.titulo, size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                ft.Container(ft.Text("CERRADA", size=11, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY),
                             bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=theme.pad(horizontal=8, vertical=3)),
            ], spacing=10),
            ft.Text(f"{info.cantidad_productos} artículos · {info.cantidad_locales} locales", size=13, color=theme.TEXT_SECONDARY),
            ft.Text(f"Total{' registrado' if registrado else ' (lo más barato de cada local)'}: "
                    f"{info.total.formatted() if info.total else '—'}", size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
        ]
        if registrado and info.total_optimo is not None:
            lineas.append(ft.Text(f"Lo más barato de cada local daba {info.total_optimo.formatted()}", size=12, color=theme.TEXT_MUTED))
        if info.cerrada_at:
            lineas.append(ft.Text(f"Cerrada el {info.cerrada_at.strftime('%d/%m/%Y')}", size=12, color=theme.TEXT_MUTED))

        def ver_detalle(_e):
            _estado["ver_detalle"] = info.id
            reconstruir()

        lineas.append(ft.Row([
            theme.secondary_button("Ver detalle", ver_detalle, icon=ft.Icons.VISIBILITY_ROUNDED),
            theme.secondary_button("Reabrir compra", lambda e: reabrir_compra(info), icon=ft.Icons.LOCK_OPEN_ROUNDED),
        ], spacing=10))
        return theme.card(ft.Column(lineas, spacing=6), padding=18)

    def detalle_cerrada(info: InfoLista) -> ft.Control:
        """Solo lectura y con textos (no casillas editables): se arma solo al
        pedirlo y solo para este mes."""
        lista = service.detalle(info.id)
        r = calcular(lista)
        chico = lambda t: ft.Text(t, size=10, color=theme.TEXT_MUTED, no_wrap=True)  # noqa: E731
        columnas = [ft.DataColumn(ft.Text("Producto")), ft.DataColumn(ft.Text("Cant."), numeric=True)]
        columnas += [ft.DataColumn(ft.Text(l.nombre), numeric=True) for l in lista.locales]
        filas = []
        for fila in r.filas:
            celdas = [ft.DataCell(ft.Text(fila.producto.nombre, size=13)), ft.DataCell(ft.Text(fmt_decimal(fila.producto.cantidad), size=13))]
            for local in lista.locales:
                total, celda = fila.totales[local.id], lista.precio(fila.producto.id, local.id)
                barato = local.id in fila.mas_baratos
                nota = " · ".join(x for x in (
                    f"{celda.precio.formatted()} c/u" if celda.precio is not None else "",
                    f"-{fmt_decimal(celda.descuento)} %" if celda.descuento else "",
                    celda.detalle,
                ) if x)
                celdas.append(ft.DataCell(ft.Column([
                    ft.Text(total.formatted() if total is not None else "—", size=13, weight=ft.FontWeight.W_600,
                            color=theme.INCOME_GREEN if barato else theme.TEXT_PRIMARY),
                    *([chico(nota)] if nota else []),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END, alignment=ft.MainAxisAlignment.CENTER)))
            filas.append(ft.DataRow(celdas, color=theme.EXPENSE_RED_BG if fila.sin_precio else None))
        if lista.productos:
            filas.append(ft.DataRow([
                ft.DataCell(ft.Text("Total comprando todo en cada local", size=12, weight=ft.FontWeight.BOLD)), ft.DataCell(ft.Text("")),
                *[ft.DataCell(ft.Text(r.total_por_local[l.id].formatted(), size=13, weight=ft.FontWeight.BOLD)) for l in lista.locales],
            ], color=theme.SURFACE_ALT))
        tabla = ft.DataTable(columnas, filas, column_spacing=24, data_row_min_height=40, data_row_max_height=52,
                             heading_row_height=40, heading_text_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD,
                                                                                    color=theme.TEXT_SECONDARY))
        registros = service.registros(info.id)
        lineas_registro = [ft.Row([
            ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED if reg.tipo == "tarjeta" else ft.Icons.PAYMENTS_ROUNDED, size=16,
                    color=theme.TARJETAS_COLOR if reg.tipo == "tarjeta" else theme.MOVIMIENTOS_COLOR),
            ft.Text(reg.fecha.strftime("%d/%m/%Y"), size=12, color=theme.TEXT_MUTED, width=80),
            ft.Text(reg.descripcion, size=13, color=theme.TEXT_PRIMARY, expand=True),
            ft.Text(reg.monto.formatted(), size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
        ], spacing=10) for reg in registros]

        def volver(_e):
            _estado["ver_detalle"] = None
            reconstruir()

        return ft.Column([
            ft.Row([
                theme.secondary_button("Volver al resumen", volver, icon=ft.Icons.ARROW_BACK_ROUNDED),
                theme.secondary_button("Reabrir compra", lambda e: reabrir_compra(info), icon=ft.Icons.LOCK_OPEN_ROUNDED),
                ft.Text("Compra cerrada: solo lectura.", size=12, color=theme.TEXT_MUTED),
            ], spacing=10),
            theme.card(ft.Column([
                ft.Text(f"{info.titulo} · lo más barato de cada local: {r.total_optimo.formatted()}", size=15,
                        weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
            ], spacing=10), padding=14),
            *([theme.card(ft.Column([
                ft.Text("Registrado en las cuentas", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY), *lineas_registro,
            ], spacing=10), padding=18)] if registros else []),
        ], spacing=14)

    # ---------- tabla ----------

    def construir() -> list[ft.Control]:
        barra_inferior.visible = False  # la muestra _tabla si hay locales para mover
        anio, mes = _estado["anio"], _estado["mes"]
        hoy = date.today()
        es_mes_actual = (anio, mes) == (hoy.year, hoy.month)
        # Primero el resumen liviano: una compra cerrada no carga su tabla.
        info = service.info_del_mes(anio, mes)
        cerrada = info is not None and info.cerrada
        if cerrada:
            lista = None
        elif info is not None:
            lista = service.detalle(info.id)
        else:
            lista = service.crear_lista(anio, mes) if es_mes_actual else None
        n_cerradas = len(service.listas(solo_cerradas=True))

        navegacion = ft.Row(
            [
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, tooltip="Mes anterior", on_click=lambda e: mover_mes(-1)),
                ft.Text(f"{MESES[mes - 1]} {anio}", size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
                        width=190, text_align=ft.TextAlign.CENTER),
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, tooltip="Mes siguiente", on_click=lambda e: mover_mes(1)),
                *([] if es_mes_actual else [ft.TextButton("Mes actual", on_click=ir_a_hoy, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))]),
                *([ft.TextButton(f"Compras cerradas ({n_cerradas})", icon=ft.Icons.LOCK_ROUNDED, on_click=ver_cerradas,
                                 style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))] if n_cerradas else []),
            ],
            spacing=0,
        )
        acciones = ft.Row(
            [
                theme.secondary_button("Copiar de otro mes", lambda e: copiar_de_otro_mes(lista), icon=ft.Icons.CONTENT_COPY_ROUNDED),
                theme.secondary_button("Agregar local", lambda e: nuevo_local(lista), icon=ft.Icons.STOREFRONT_ROUNDED),
                theme.primary_button("Agregar producto", lambda e: nuevo_producto(lista), color=theme.COMPRAS_COLOR, icon=ft.Icons.ADD_ROUNDED),
            ],
            spacing=10,
        ) if lista else ft.Container()
        encabezado = [
            ft.Row([ft.Text("Compra mensual", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True), acciones]),
            navegacion,
        ]

        if cerrada:
            return encabezado + [detalle_cerrada(info) if _estado["ver_detalle"] == info.id else tarjeta_cerrada(info)]

        if lista is None:
            anterior = next((i for i in service.listas() if (i.anio, i.mes) < (anio, mes)), None)
            detalle = (f"Se copian los locales, productos, cantidades y detalles de {anterior.titulo} (sin precios)."
                       if anterior else "Arranca vacía: agregá tus locales y productos.")

            def crear(_e):
                service.crear_lista(anio, mes)
                reconstruir()

            return encabezado + [theme.card(ft.Column([
                ft.Text(f"Todavía no hay lista para {MESES[mes - 1].lower()} {anio}.", size=14, color=theme.TEXT_PRIMARY),
                ft.Text(detalle, size=12, color=theme.TEXT_SECONDARY),
                theme.primary_button("Crear lista de este mes", crear, color=theme.COMPRAS_COLOR, icon=ft.Icons.ADD_ROUNDED),
            ], spacing=10))]

        if not lista.locales or not lista.productos:
            faltan = []
            if not lista.locales:
                faltan.append("• Los locales donde comprás (Agregar local).")
            if not lista.productos:
                faltan.append("• Los productos con su cantidad (Agregar producto).")
            ayuda = theme.card(ft.Column([
                ft.Text("Para empezar, cargá una sola vez:", size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                *[ft.Text(f, size=13, color=theme.TEXT_SECONDARY) for f in faltan],
                ft.Text("Después solo completás el precio de cada producto en cada local.", size=12, color=theme.TEXT_MUTED),
                ft.Row([theme.secondary_button("Copiar locales y productos de otro mes", lambda e: copiar_de_otro_mes(lista),
                                               icon=ft.Icons.CONTENT_COPY_ROUNDED)]),
            ], spacing=6))
            return (encabezado + [ayuda] + ([_tabla(lista)] if lista.locales or lista.productos else [])
                    + [cierre(lista)])

        return encabezado + [_tabla(lista)] + [cierre(lista)]

    def cierre(lista: ListaCompra) -> ft.Control:
        """Al pie de la lista: cerrar la compra para que quede como resumen."""
        return theme.card(ft.Row([
            ft.Column([
                ft.Text("¿Terminaste la compra de este mes?", size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                ft.Text("Cerrala para que quede guardada como resumen: la sección carga más liviana y podés ver el detalle "
                        "o reabrirla cuando quieras (por ejemplo, si la cerraste antes de terminar).", size=12, color=theme.TEXT_SECONDARY),
            ], spacing=4, expand=True),
            theme.primary_button("Cerrar compra mensual", lambda e: cerrar_compra(lista), color=theme.COMPRAS_COLOR,
                                 icon=ft.Icons.LOCK_ROUNDED),
        ], spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=16)

    def _registrar_card_factory():
        """Devuelve _registrar_card(lista, base_dd, monto_f). Separado para leer mejor."""

        def _registrar_card(lista: ListaCompra, base_dd: ft.Dropdown, monto_f: ft.TextField) -> ft.Control:
            categorias = categoria_repo.listar(TipoMovimiento.EGRESO)
            tarjetas = tarjeta_service.listar_tarjetas()
            concepto_f = ft.TextField(label="Concepto", value=f"Compra mensual {lista.titulo}", filled=True, bgcolor=theme.SURFACE_ALT,
                                      border_radius=theme.RADIUS_SM, border_color=theme.BORDER, expand=True)
            fecha = _CampoFecha(page, "Fecha", date.today())
            comida = next((c for c in categorias if c.nombre == "Comida"), categorias[0] if categorias else None)
            categoria_dd = ft.Dropdown(label="Categoría", value=str(comida.id) if comida else None,
                                       options=[ft.dropdown.Option(str(c.id), c.nombre) for c in categorias],
                                       filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=240)
            tipo = ft.SegmentedButton(
                segments=[ft.Segment(value="egreso", label=ft.Text("Egreso (efectivo / débito)"), icon=ft.Icons.PAYMENTS_ROUNDED),
                          ft.Segment(value="tarjeta", label=ft.Text("Tarjeta de crédito"), icon=ft.Icons.CREDIT_CARD_ROUNDED)],
                selected=["egreso"], allow_multiple_selection=False, allow_empty_selection=False,
            )
            tarjeta_dd = ft.Dropdown(label="Tarjeta", value=str(tarjetas[0].id) if tarjetas else None,
                                     options=[ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas],
                                     filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=240)
            cuotas_f = ft.TextField(label="Cuotas", value="1", width=100, filled=True, bgcolor=theme.SURFACE_ALT,
                                    border_radius=theme.RADIUS_SM, border_color=theme.BORDER, input_filter=ft.NumbersOnlyInputFilter())
            # El mes del resumen sale del cierre y el vencimiento de la tarjeta (se puede cambiar).
            resumen_sel = SelectorResumen(page, tarjeta_service, filled=True, bgcolor=theme.SURFACE_ALT,
                                          border_radius=theme.RADIUS_SM, border_color=theme.BORDER, width=240)

            def actualizar_cuando(_e=None):
                if not tarjeta_dd.value:
                    return
                try:
                    n = int(cuotas_f.value or "1")
                except ValueError:
                    n = 1
                resumen_sel.proponer(int(tarjeta_dd.value), fecha.valor or date.today(), max(n, 1),
                                     "La primera cuota se paga" if n > 1 else "Se paga")

            bloque_tarjeta = ft.Column(
                [ft.Row([tarjeta_dd, cuotas_f, resumen_sel.dropdown], spacing=10), resumen_sel.aviso] if tarjetas else
                [ft.Text("No tenés tarjetas en pesos cargadas. Agregalas en la sección Tarjetas.", size=12, color=theme.EXPENSE_RED)],
                spacing=8, visible=False,
            )

            def on_tipo(_e):
                bloque_tarjeta.visible = "tarjeta" in tipo.selected
                actualizar_cuando()
                page.update()

            def on_cambio_tarjeta(_e):
                actualizar_cuando()
                page.update()

            tipo.on_change = on_tipo
            cuotas_f.on_change = on_cambio_tarjeta
            tarjeta_dd.on_select = on_cambio_tarjeta
            actualizar_cuando()

            def registrar(_e=None):
                try:
                    monto = Money.from_decimal(parse_decimal(monto_f.value, "Monto"), Moneda.ARS)
                    if categoria_dd.value is None:
                        raise ValueError("Elegí una categoría")
                    es_tarjeta = "tarjeta" in tipo.selected
                    if es_tarjeta and not tarjeta_dd.value:
                        raise ValueError("Elegí una tarjeta")
                    cuotas = int(cuotas_f.value or "1") if es_tarjeta else 1
                    if monto.cents <= 0:
                        raise ValueError("El monto tiene que ser mayor a cero")
                except ValueError as exc:
                    avisar(str(exc), error=True)
                    return
                categoria = next(c for c in categorias if str(c.id) == categoria_dd.value)
                if es_tarjeta:
                    tarjeta = next(t for t in tarjetas if str(t.id) == tarjeta_dd.value)
                    if resumen_sel.fecha != (fecha.valor or date.today()):
                        actualizar_cuando()  # cambio la fecha despues de elegir el mes: se vuelve a calcular
                    como = f"en la tarjeta {tarjeta.nombre}" + (f", en {cuotas} cuotas" if cuotas > 1 else ", en 1 pago")
                    como += f" (resumen de {MESES[resumen_sel.mes.month - 1].lower()} {resumen_sel.mes.year})"
                else:
                    como = "como egreso"
                texto = f"Se va a registrar {monto.formatted()} {como}, en la categoría {categoria.nombre}."

                def confirmar(_e2):
                    try:
                        if es_tarjeta:
                            service.registrar_en_tarjeta(lista.id, int(tarjeta_dd.value), fecha.valor or date.today(), concepto_f.value or "",
                                                         monto, categoria.id, cuotas, meses_al_resumen=resumen_sel.meses)
                        else:
                            service.registrar_egreso(lista.id, fecha.valor or date.today(), concepto_f.value or "", monto, categoria.id,
                                                     f"Egreso · {categoria.nombre}")
                    except ValueError as exc:
                        page.pop_dialog()
                        avisar(str(exc), error=True)
                        return
                    page.pop_dialog()
                    reconstruir()
                    avisar("Compra registrada")

                page.show_dialog(theme.dialogo(
                    "Registrar la compra", ft.Text(texto, size=13, color=theme.TEXT_SECONDARY),
                    [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                     theme.primary_button("Registrar", confirmar, color=theme.COMPRAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
                    icono="shopping_cart_checkout_rounded", color=theme.COMPRAS_COLOR,
                ))

            # Compras ya registradas desde esta lista
            registros = service.registros(lista.id)
            filas_registro = []
            for reg in registros:
                def deshacer(_e, reg=reg):
                    donde = "el egreso" if reg.tipo == "egreso" else "la compra de la tarjeta"
                    confirmar_accion = lambda: service.deshacer_registro(reg.id)
                    confirmar("Deshacer registro", f"¿Deshacer el registro de {reg.monto.formatted()}? Se borra {donde} que generó.",
                              confirmar_accion)

                filas_registro.append(ft.Row([
                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED if reg.tipo == "tarjeta" else ft.Icons.PAYMENTS_ROUNDED, size=16,
                            color=theme.TARJETAS_COLOR if reg.tipo == "tarjeta" else theme.MOVIMIENTOS_COLOR),
                    ft.Text(reg.fecha.strftime("%d/%m/%Y"), size=12, color=theme.TEXT_MUTED, width=80),
                    ft.Text(reg.descripcion, size=13, color=theme.TEXT_PRIMARY, expand=True),
                    ft.Text(reg.monto.formatted(), size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                    ft.TextButton("Deshacer", icon=ft.Icons.UNDO_ROUNDED, on_click=deshacer, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
                ], spacing=10))
            total_registrado = sum((r_.monto for r_ in registros), Money.zero(Moneda.ARS))

            return theme.card(ft.Column([
                ft.Text("Registrar la compra", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                ft.Text("Cargala en tus cuentas como egreso o en una tarjeta de crédito. Podés registrar varias partes "
                        "(ej: una en efectivo y otra con tarjeta).", size=12, color=theme.TEXT_SECONDARY),
                ft.Row([base_dd, monto_f], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([concepto_f, fecha.control], spacing=10),
                ft.Row([categoria_dd, tipo], spacing=16, wrap=True),
                bloque_tarjeta,
                ft.Row([theme.primary_button("Registrar compra", registrar, color=theme.COMPRAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
                       alignment=ft.MainAxisAlignment.END),
                *([ft.Divider(height=1, color=theme.BORDER),
                   ft.Text(f"Ya registrado este mes: {total_registrado.formatted()}", size=13, weight=ft.FontWeight.W_600,
                           color=theme.TEXT_PRIMARY),
                   *filas_registro] if registros else []),
            ], spacing=12), padding=18)

        return _registrar_card

    registrar_card = _registrar_card_factory()

    def _tabla(lista: ListaCompra) -> ft.Control:
        """Arma la planilla. Guarda referencias a los controles calculados para
        actualizarlos al editar un precio sin reconstruir toda la tabla."""
        refs = {"filas": {}, "totales_local": {}, "faltan_local": {}, "plan_local": {}}
        con_detalle = _estado["detalle"]
        ancho_local = _ancho_local(con_detalle)
        con_totales = bool(lista.productos)
        colores = theme.TARJETA_COLORES

        # Planilla en dos partes con las mismas alturas de fila: a la izquierda
        # Producto / Cantidad / borrar (fijas) y a la derecha los locales, que se
        # desplazan de costado como en una planilla con paneles inmovilizados.
        izq = [
            ft.Container(width=ANCHO_FIJO, height=ALTO_LOCAL),
            ft.Row([_texto_encabezado("Producto", ANCHO_PRODUCTO), _texto_encabezado("Cantidad", ANCHO_CANTIDAD, derecha=True),
                    ft.Container(width=ANCHO_ACCION)], spacing=0),
        ]
        encabezado_locales, encabezado_columnas = [], []
        for i, local in enumerate(lista.locales):
            color = colores[i % len(colores)]
            encabezado_locales.append(ft.Container(
                ft.Row([
                    ft.Text(local.nombre, size=13, weight=ft.FontWeight.BOLD, color="#FFFFFF", expand=True,
                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER),
                    ft.Icon(ft.Icons.EDIT_ROUNDED, size=14, color=ft.Colors.with_opacity(0.85, "#FFFFFF")),
                ], spacing=4),
                width=ancho_local, height=ALTO_LOCAL, bgcolor=color, padding=theme.pad(horizontal=10),
                border_radius=ft.BorderRadius.only(top_left=theme.RADIUS_SM, top_right=theme.RADIUS_SM),
                on_click=lambda e, l=local: editar_local(l), tooltip="Editar o eliminar el local", ink=True,
            ))
            encabezado_columnas += [
                _texto_encabezado("Precio unit.", ANCHO_PRECIO, derecha=True, borde_izq=True),
                _texto_encabezado("Desc. %", ANCHO_DESC, derecha=True),
                _texto_encabezado("Total", ANCHO_TOTAL, derecha=True),
                *([_texto_encabezado("Marca / detalle", ANCHO_DETALLE)] if con_detalle else []),
            ]
        der = [ft.Row(encabezado_locales, spacing=0), ft.Row(encabezado_columnas, spacing=0)]
        filas_producto: dict[int, tuple] = {}  # id -> (fila izq, fila der, producto)

        for producto in ordenar_productos(calcular(lista), _estado["orden"]):
            nombre_f = _campo(producto.nombre)
            cantidad_f = _campo(fmt_decimal(producto.cantidad), alinear_derecha=True)

            def guardar_producto(_e, p=producto, nf=nombre_f, cf=cantidad_f):
                try:
                    cantidad = parse_decimal(cf.value, "Cantidad")
                    if (nf.value or "").strip() == p.nombre and cantidad == p.cantidad:
                        return
                    service.editar_producto(p.id, nf.value or "", cantidad)
                    p.nombre, p.cantidad = (nf.value or "").strip(), cantidad
                except ValueError as exc:
                    nf.value, cf.value = p.nombre, fmt_decimal(p.cantidad)
                    avisar(str(exc), error=True)
                recalcular()

            for f in (nombre_f, cantidad_f):
                f.on_blur = guardar_producto
                f.on_submit = guardar_producto
            celda_producto = _celda(nombre_f, ANCHO_PRODUCTO)
            fila_izq = ft.Row([
                celda_producto,
                _celda(cantidad_f, ANCHO_CANTIDAD),
                _celda(ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=theme.TEXT_MUTED, tooltip="Eliminar producto",
                    on_click=lambda e, p=producto: eliminar_producto(p), style=ft.ButtonStyle(padding=0),
                ), ANCHO_ACCION),
            ], spacing=0)
            izq.append(fila_izq)

            controles, celdas_local = [], {}
            for local in lista.locales:
                p_actual = lista.precio(producto.id, local.id)
                precio_f = _campo(fmt_decimal(p_actual.precio.amount) if p_actual.precio is not None else "", True, "—")
                desc_f = _campo(fmt_decimal(p_actual.descuento) if p_actual.descuento else "", True)
                total_t = ft.Text("", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY,
                                  text_align=ft.TextAlign.RIGHT, width=ANCHO_TOTAL - 12)
                detalle_f = _campo(p_actual.detalle)

                def guardar_celda(_e, p=producto, l=local, pf=precio_f, df=desc_f, dtf=detalle_f):
                    try:
                        precio = _decimal_o_none(pf.value, "Precio")
                        descuento = _decimal_o_none(df.value, "Descuento")
                        service.guardar_precio(p.id, l.id, Money.from_decimal(precio, Moneda.ARS) if precio is not None else None,
                                               descuento, dtf.value or "")
                    except ValueError as exc:
                        avisar(str(exc), error=True)
                    recalcular()

                for f in (precio_f, desc_f, detalle_f):
                    f.on_blur = guardar_celda
                    f.on_submit = guardar_celda
                # Un solo recuadro por local (antes uno por casilla): la tabla
                # tiene cientos de casillas y cada control se envia a la ventana.
                # Con el detalle oculto el campo igual existe (con su valor) para no borrarlo al guardar.
                precio_f.width, desc_f.width, detalle_f.width = ANCHO_PRECIO - 12, ANCHO_DESC - 12, ANCHO_DETALLE - 12
                grupo = ft.Container(
                    ft.Row([precio_f, desc_f, total_t, *([detalle_f] if con_detalle else [])], spacing=12),
                    width=ancho_local, height=ALTO_FILA, padding=theme.pad(horizontal=6),
                    border=ft.border.Border(left=ft.border.BorderSide(2, theme.BORDER), bottom=ft.border.BorderSide(1, theme.BORDER)),
                )
                celdas_local[local.id] = (total_t, (grupo,))
                controles.append(grupo)
            refs["filas"][producto.id] = (celda_producto, celdas_local)
            fila_der = ft.Row(controles, spacing=0)
            der.append(fila_der)
            filas_producto[producto.id] = (fila_izq, fila_der, producto)

        # Carga en dos tandas: primero las filas que entran en pantalla y, un
        # instante despues, el resto. Lo que demora es enviar a la ventana los
        # cientos de casillas; asi la tabla aparece enseguida.
        inicio_filas = 2  # antes: las dos filas de encabezado
        resto_izq = izq[inicio_filas + FILAS_PRIMERA_TANDA:]
        del izq[inicio_filas + FILAS_PRIMERA_TANDA:]
        # Las filas de productos de los locales van en su propio bloque, que
        # lleva pintadas encima las lineas entre columnas (ver _lineas_columnas).
        filas_der = der[inicio_filas:]
        resto_der = filas_der[FILAS_PRIMERA_TANDA:]
        bloque_filas = ft.Column(filas_der[:FILAS_PRIMERA_TANDA], spacing=0)
        der[inicio_filas:] = [ft.Container(
            bloque_filas, width=len(lista.locales) * ancho_local,
            foreground_decoration=_lineas_columnas(len(lista.locales), con_detalle) if lista.locales else None,
        )] if filas_der else []

        # Pie: total por local y como se reparte la compra mas barata
        def fila_pie(titulo: str, clave: str, destacar: bool = False):
            izq.append(ft.Container(
                ft.Text(titulo, size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                width=ANCHO_FIJO, height=ALTO_PIE, padding=theme.pad(horizontal=6), alignment=ft.Alignment.CENTER_LEFT,
                bgcolor=theme.SURFACE_ALT if destacar else None,
            ))
            bloques = []
            for local in lista.locales:
                texto = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, text_align=ft.TextAlign.RIGHT)
                nota = ft.Text("", size=10, color=theme.TEXT_MUTED, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.RIGHT)
                refs[clave][local.id] = (texto, nota)
                bloques.append(ft.Container(
                    ft.Column([texto, nota], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END,
                              alignment=ft.MainAxisAlignment.CENTER),
                    width=ancho_local, height=ALTO_PIE, bgcolor=theme.SURFACE_ALT if destacar else None,
                    padding=ft.padding.Padding(left=6, top=0, right=12 + (ANCHO_DETALLE if con_detalle else 0), bottom=0),
                    border=ft.border.Border(left=ft.border.BorderSide(2, theme.BORDER)),
                ))
            der.append(ft.Row(bloques, spacing=0))

        if con_totales:
            izq.append(ft.Container(height=6))
            der.append(ft.Container(height=6))
            fila_pie("Total comprando todo en cada local", "totales_local")
            fila_pie("Si comprás lo más barato de cada local", "plan_local", destacar=True)

        total_optimo_t = ft.Text("", size=22, weight=ft.FontWeight.BOLD, color=theme.INCOME_GREEN)
        ahorro_t = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
        sin_precio_t = ft.Text("", size=12, color=theme.EXPENSE_RED)
        refs["resumen"] = (total_optimo_t, ahorro_t, sin_precio_t)

        izq.append(ft.Container(height=8))
        der.append(ft.Container(height=8))
        columna_izq = ft.Column(izq, spacing=0)
        # Los locales se desplazan de costado, pero sin barra propia: la tabla
        # la mueve una sola barra fija abajo de la seccion (ver barra_inferior),
        # que esta a la vista aunque se este en el medio de una lista larga.
        columna_der = ft.Column(der, spacing=0)
        desplazable = ft.Row([columna_der], scroll=ft.ScrollMode.HIDDEN)

        # Barrita fija abajo de la seccion (como la de subir y bajar). Mueve la
        # tabla en un solo sentido: nunca al reves, porque dos barras que se
        # movian una a la otra rebotaban el movimiento hasta trabar la app.
        # El aviso de la barra solo anota a donde ir; una sola tarea mueve la
        # tabla hasta la ultima posicion pedida, asi arrastrar no acumula
        # decenas de movimientos pendientes.
        ancho_locales = len(lista.locales) * ancho_local
        medidas = {"visible": 0.0}
        movimiento = {"objetivo": None, "tarea": False}

        async def _mover_tabla():
            try:
                while movimiento["objetivo"] is not None:
                    destino, movimiento["objetivo"] = movimiento["objetivo"], None
                    await desplazable.scroll_to(offset=destino)
            except Exception:
                pass  # la tabla se reconstruyo mientras tanto
            finally:
                movimiento["tarea"] = False

        def al_mover_barra(e: ft.OnScrollEvent):
            maximo_tabla = max(0.0, ancho_locales - medidas["visible"])
            maximo_barra = e.max_scroll_extent or 0
            movimiento["objetivo"] = e.pixels / maximo_barra * maximo_tabla if maximo_barra > 0 else 0
            if not movimiento["tarea"]:
                movimiento["tarea"] = True
                page.run_task(_mover_tabla)

        def al_medir(e):
            medidas["visible"] = e.width

        contenedor_locales = ft.Container(desplazable, expand=True, on_size_change=al_medir)
        barra_locales = ft.Row([ft.Container(width=ancho_locales, height=10)], scroll=ft.ScrollMode.ALWAYS,
                               scroll_interval=30, on_scroll=al_mover_barra)

        def alternar_detalle(e):
            _estado["detalle"] = bool(e.control.value)
            reconstruir()

        # ---------- buscar y ordenar productos ----------
        def aplicar_busqueda():
            texto = _estado["busqueda"]
            mostrados = 0
            for fila_izq, fila_der, producto in filas_producto.values():
                visible = coincide_busqueda(producto.nombre, texto)  # si se renombra, ya tiene el nombre nuevo
                fila_izq.visible = fila_der.visible = visible
                mostrados += visible
            contador.value = f"{mostrados} de {len(filas_producto)}" if texto.strip() else ""
            sin_resultados.visible = bool(filas_producto) and mostrados == 0

        def al_buscar(e):
            _estado["busqueda"] = e.control.value or ""
            aplicar_busqueda()
            page.update()

        def limpiar_busqueda(_e):
            buscador.value = _estado["busqueda"] = ""
            aplicar_busqueda()
            page.update()

        def al_ordenar(e):
            _estado["orden"] = e.control.value
            reconstruir()

        buscador = ft.TextField(
            value=_estado["busqueda"], hint_text="Buscar producto", dense=True, width=220,
            prefix_icon=ft.Icons.SEARCH_ROUNDED, on_change=al_buscar,
            suffix=ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=16, tooltip="Borrar búsqueda", on_click=limpiar_busqueda,
                                 style=ft.ButtonStyle(padding=0)),
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, content_padding=components.PADDING_FILTRO,
            text_size=13,
        )
        contador = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
        orden_dd = ft.Dropdown(
            label="Ordenar por", value=_estado["orden"], width=225, on_select=al_ordenar,
            options=[ft.dropdown.Option(k, v) for k, v in ORDENES_PRODUCTOS.items()],
            border=ft.InputBorder.NONE, content_padding=components.PADDING_FILTRO,
        )
        sin_resultados = ft.Text("Ningún producto coincide con la búsqueda.", size=12, color=theme.TEXT_MUTED, italic=True, visible=False)

        barra = ft.Row(
            [
                buscador, contador, components.recuadro_filtro(orden_dd),
                ft.Switch(label="Mostrar marca / detalle", value=con_detalle, active_color=theme.COMPRAS_COLOR,
                          label_text_style=ft.TextStyle(size=12, color=theme.TEXT_SECONDARY), on_change=alternar_detalle),
            ],
            # Ojo: en una fila con wrap no puede ir nada con expand (Flet la
            # dibuja como un recuadro gris y se pierde toda la tabla).
            spacing=10, wrap=True, run_spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        # Mismo ancho visible que la parte de los locales: a la izquierda, lo que
        # ocupan Producto / Cantidad.
        barra_inferior.content = ft.Row([ft.Container(width=ANCHO_FIJO), ft.Container(barra_locales, expand=True)], spacing=0)
        barra_inferior.visible = len(lista.locales) > 1
        planilla = ft.Column([
            barra,
            ft.Row(
                [columna_izq, contenedor_locales],
                spacing=0, vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            sin_resultados,
        ], spacing=6)
        aplicar_busqueda()

        async def cargar_resto():
            await asyncio.sleep(0.05)  # que primero se vea la primera tanda
            try:
                posicion = inicio_filas + FILAS_PRIMERA_TANDA
                columna_izq.controls[posicion:posicion] = resto_izq
                bloque_filas.controls.extend(resto_der)
                columna_izq.update()
                bloque_filas.update()
            except Exception:
                pass  # la tabla ya se reemplazo (cambio de mes, de orden, de seccion)

        if resto_izq:
            page.run_task(cargar_resto)

        def aplicar(r):
            """Vuelca un ResumenCompra en los controles: totales, verdes y rosas."""
            for fila in r.filas:
                celda_producto, celdas_local = refs["filas"][fila.producto.id]
                celda_producto.bgcolor = theme.EXPENSE_RED_BG if fila.sin_precio else None
                for lid, (total_t, celdas) in celdas_local.items():
                    total = fila.totales[lid]
                    total_t.value = total.formatted() if total is not None else ""
                    barato = lid in fila.mas_baratos
                    for c in celdas:
                        c.bgcolor = theme.INCOME_GREEN_BG if barato else None
                    total_t.color = theme.INCOME_GREEN if barato else theme.TEXT_PRIMARY
            for lid, (texto, nota) in refs["totales_local"].items():
                texto.value = r.total_por_local[lid].formatted()
                faltan = r.faltantes_por_local[lid]
                nota.value = f"le falta(n) {faltan} producto(s)" if faltan else "tiene todos"
            for lid, (texto, nota) in refs["plan_local"].items():
                monto, cantidad = r.plan_por_local[lid]
                texto.value, nota.value = monto.formatted(), f"{cantidad} producto(s)"
            total_optimo_t.value = r.total_optimo.formatted()
            completos = [r.total_por_local[lid] for lid, n in r.faltantes_por_local.items() if n == 0]
            if completos:
                ahorro = min(completos, key=lambda m: m.cents) - r.total_optimo
                ahorro_t.value = (f"Ahorrás {ahorro.formatted()} frente a comprar todo en el local completo más barato."
                                  if ahorro.cents > 0 else "Comprar todo en el local más barato ya es la mejor opción.")
            else:
                ahorro_t.value = "Ningún local tiene todos los productos."
            sin_precio_t.value = (f"{r.productos_sin_precio} producto(s) sin precio en ningún local (en rosa)."
                                  if r.productos_sin_precio else "")
            actualizar_sugeridos(r)

        def recalcular():
            aplicar(calcular(service.lista_del_mes(lista.anio, lista.mes)))
            page.update()

        # ---------- registrar la compra en las cuentas ----------
        sugerido = {"editado": False, "resumen": None}
        base_dd = ft.Dropdown(label="Monto sugerido", value="optimo", options=[], filled=True, bgcolor=theme.SURFACE_ALT,
                              border_radius=theme.RADIUS_SM, border_color=theme.BORDER, expand=True)
        monto_f = ft.TextField(label="Monto a registrar", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM,
                               border_color=theme.BORDER, width=240, prefix=ft.Text("$ "),
                               helper="Sumale envío, propina, etc.")

        def monto_base(r):
            if base_dd.value == "optimo" or base_dd.value is None:
                return r.total_optimo
            return r.total_por_local.get(int(base_dd.value), r.total_optimo)

        def actualizar_sugeridos(r):
            sugerido["resumen"] = r
            opciones = [ft.dropdown.Option("optimo", f"Lo más barato de cada local · {r.total_optimo.formatted()}")]
            for local in lista.locales:
                faltan = r.faltantes_por_local.get(local.id, 0)
                extra = f" (le faltan {faltan})" if faltan else ""
                opciones.append(ft.dropdown.Option(str(local.id), f"Todo en {local.nombre} · {r.total_por_local[local.id].formatted()}{extra}"))
            base_dd.options = opciones
            if not sugerido["editado"]:
                monto_f.value = fmt_decimal(monto_base(r).amount)

        def on_base(_e):
            sugerido["editado"] = False
            if sugerido["resumen"] is not None:
                monto_f.value = fmt_decimal(monto_base(sugerido["resumen"]).amount)
            page.update()

        def on_monto(_e):
            sugerido["editado"] = True

        base_dd.on_select = on_base
        monto_f.on_change = on_monto

        resumen = theme.card(ft.Row([
            ft.Column([
                ft.Text("Total de la compra (lo más barato de cada local)", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                total_optimo_t, ahorro_t, sin_precio_t,
            ], spacing=4, expand=True),
            ft.Column([
                ft.Row([ft.Container(width=12, height=12, bgcolor=theme.INCOME_GREEN_BG, border=theme.border_all(1, theme.INCOME_GREEN)),
                        ft.Text("Más barato", size=11, color=theme.TEXT_SECONDARY)], spacing=6),
                ft.Row([ft.Container(width=12, height=12, bgcolor=theme.EXPENSE_RED_BG, border=theme.border_all(1, theme.EXPENSE_RED)),
                        ft.Text("Sin precio en ningún local", size=11, color=theme.TEXT_SECONDARY)], spacing=6),
                ft.Text("Dejá el precio vacío si el local no tiene el producto.", size=11, color=theme.TEXT_MUTED),
            ], spacing=4),
        ]), padding=16)

        registrar = registrar_card(lista, base_dd, monto_f)
        aplicar(calcular(lista))  # la vista todavia no esta en la pagina: sin page.update

        return ft.Column([theme.card(planilla, padding=12), *([resumen, registrar] if con_totales else [])], spacing=14)

    root.controls = construir()
    # La lista se desplaza hacia arriba y abajo; la barra de locales queda fija
    # debajo, siempre a la vista.
    return ft.Column([ft.Column([root], expand=True, scroll=ft.ScrollMode.AUTO), barra_inferior], expand=True, spacing=0)
