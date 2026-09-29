"""Compra mensual: tabla tipo planilla para comparar precios entre locales.

Filas = productos; por cada local un bloque de columnas (precio unitario,
% de descuento, total y detalle). Las celdas se editan en el lugar y se guardan
al salir del campo o con Enter. El local mas barato de cada producto se marca
en verde; los productos sin precio en ningun local, en rosa.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.compra_mensual import MESES, CompraMensualService, ListaCompra, calcular
from ...app.services.tarjetas import TarjetaService, vencimiento_cuota
from .. import theme
from . import components
from .inversiones_forms import _CampoFecha, fmt_decimal, parse_decimal

# Mes que se esta viendo: se recuerda al volver a la seccion.
_estado = {"anio": date.today().year, "mes": date.today().month, "detalle": True}

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


def _campo(valor: str, alinear_derecha: bool = False, hint: str = "") -> ft.TextField:
    return ft.TextField(
        value=valor, dense=True, text_size=13, border=ft.InputBorder.NONE, hint_text=hint,
        text_style=ft.TextStyle(color=theme.TEXT_PRIMARY), hint_style=ft.TextStyle(color=theme.TEXT_MUTED),
        content_padding=ft.padding.Padding(left=2, right=2, top=6, bottom=6),
        text_align=ft.TextAlign.RIGHT if alinear_derecha else ft.TextAlign.LEFT,
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

    def avisar(mensaje: str, error: bool = False):
        page.show_dialog(ft.SnackBar(ft.Text(mensaje), bgcolor=theme.EXPENSE_RED if error else None))

    def mover_mes(delta: int):
        total = _estado["anio"] * 12 + (_estado["mes"] - 1) + delta
        _estado["anio"], _estado["mes"] = total // 12, total % 12 + 1
        reconstruir()

    def ir_a_hoy(_e=None):
        _estado["anio"], _estado["mes"] = date.today().year, date.today().month
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

    # ---------- tabla ----------

    def construir() -> list[ft.Control]:
        anio, mes = _estado["anio"], _estado["mes"]
        hoy = date.today()
        es_mes_actual = (anio, mes) == (hoy.year, hoy.month)
        lista = service.obtener_o_crear(anio, mes) if es_mes_actual else service.lista_del_mes(anio, mes)

        navegacion = ft.Row(
            [
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, tooltip="Mes anterior", on_click=lambda e: mover_mes(-1)),
                ft.Text(f"{MESES[mes - 1]} {anio}", size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
                        width=190, text_align=ft.TextAlign.CENTER),
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, tooltip="Mes siguiente", on_click=lambda e: mover_mes(1)),
                *([] if es_mes_actual else [ft.TextButton("Mes actual", on_click=ir_a_hoy, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))]),
            ],
            spacing=0,
        )
        acciones = ft.Row(
            [
                theme.secondary_button("Agregar local", lambda e: nuevo_local(lista), icon=ft.Icons.STOREFRONT_ROUNDED),
                theme.primary_button("Agregar producto", lambda e: nuevo_producto(lista), color=theme.COMPRAS_COLOR, icon=ft.Icons.ADD_ROUNDED),
            ],
            spacing=10,
        ) if lista else ft.Container()
        encabezado = [
            ft.Row([ft.Text("Compra mensual", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True), acciones]),
            navegacion,
        ]

        if lista is None:
            anterior = service.lista_anterior(anio, mes)
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
            ], spacing=6))
            return encabezado + [ayuda] + ([_tabla(lista)] if lista.locales or lista.productos else [])

        return encabezado + [_tabla(lista)]

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
            cerrada = ft.Checkbox(label="La tarjeta ya cerró el resumen de este mes", value=False, active_color=theme.TARJETAS_COLOR)
            cuando = ft.Text("", size=12, color=theme.TEXT_SECONDARY, italic=True)

            def actualizar_cuando(_e=None):
                try:
                    n = int(cuotas_f.value or "1")
                except ValueError:
                    n = 1
                vence = vencimiento_cuota(fecha.valor or date.today(), 1, max(n, 1), bool(cerrada.value))
                que = "La primera cuota se paga" if n > 1 else "Se paga"
                cuando.value = f"{que} en {MESES[vence.month - 1].lower()} {vence.year}."

            bloque_tarjeta = ft.Column(
                [ft.Row([tarjeta_dd, cuotas_f], spacing=10), cerrada, cuando] if tarjetas else
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
            cerrada.on_change = on_cambio_tarjeta
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
                    como = f"en la tarjeta {tarjeta.nombre}" + (f", en {cuotas} cuotas" if cuotas > 1 else ", en 1 pago")
                else:
                    como = "como egreso"
                texto = f"Se va a registrar {monto.formatted()} {como}, en la categoría {categoria.nombre}."

                def confirmar(_e2):
                    try:
                        if es_tarjeta:
                            service.registrar_en_tarjeta(lista.id, int(tarjeta_dd.value), fecha.valor or date.today(), concepto_f.value or "",
                                                         monto, categoria.id, cuotas, bool(cerrada.value))
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

        for producto in lista.productos:
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
            izq.append(ft.Row([
                celda_producto,
                _celda(cantidad_f, ANCHO_CANTIDAD),
                _celda(ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=theme.TEXT_MUTED, tooltip="Eliminar producto",
                    on_click=lambda e, p=producto: eliminar_producto(p), style=ft.ButtonStyle(padding=0),
                ), ANCHO_ACCION),
            ], spacing=0))

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
                # Con el detalle oculto el campo igual existe (con su valor) para no borrarlo al guardar.
                celdas = (_celda(precio_f, ANCHO_PRECIO, borde_izq=True), _celda(desc_f, ANCHO_DESC),
                          _celda(total_t, ANCHO_TOTAL), *([_celda(detalle_f, ANCHO_DETALLE)] if con_detalle else []))
                celdas_local[local.id] = (total_t, celdas)
                controles += celdas
            refs["filas"][producto.id] = (celda_producto, celdas_local)
            der.append(ft.Row(controles, spacing=0))

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

        # Los locales se desplazan de costado: barra siempre visible y flechas arriba.
        # El espacio al final deja la barra debajo de la ultima fila, sin taparla.
        izq.append(ft.Container(height=16))
        der.append(ft.Container(height=16))
        desplazable = ft.Row([ft.Column(der, spacing=0)], scroll=ft.ScrollMode.ALWAYS)

        async def mover_locales(delta: int):
            await desplazable.scroll_to(delta=delta * ancho_local, duration=250)

        def alternar_detalle(e):
            _estado["detalle"] = bool(e.control.value)
            reconstruir()

        barra = ft.Row(
            [
                ft.Switch(label="Mostrar marca / detalle", value=con_detalle, active_color=theme.COMPRAS_COLOR,
                          label_text_style=ft.TextStyle(size=12, color=theme.TEXT_SECONDARY), on_change=alternar_detalle),
                ft.Container(expand=True),
                *([
                    ft.Text("Locales", size=12, color=theme.TEXT_SECONDARY),
                    ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, tooltip="Ver locales anteriores", icon_size=20,
                                  on_click=lambda e: mover_locales(-1)),
                    ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, tooltip="Ver más locales", icon_size=20,
                                  on_click=lambda e: mover_locales(1)),
                ] if len(lista.locales) > 1 else []),
            ],
            spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        planilla = ft.Column([
            barra,
            ft.Row(
                [ft.Column(izq, spacing=0), ft.Container(desplazable, expand=True)],
                spacing=0, vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        ], spacing=6)

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
    return ft.Column([root], expand=True, scroll=ft.ScrollMode.AUTO)
