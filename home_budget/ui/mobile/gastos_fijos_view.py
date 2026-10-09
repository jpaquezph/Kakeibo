"""Gastos fijos en el celular: lo que falta pagar este mes y la lista, con
buscador, orden y los mismos filtros que en escritorio. Tocar un gasto lo
abre para editarlo, registrar su pago del mes o eliminarlo. El formulario
pide los mismos datos que el de escritorio."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.models import METODOS_PAGO, GastoFijo, TipoMovimiento
from ...app.domain.money import Moneda
from ...app.services.gastos_fijos import FiltroGastosFijos
from .. import theme
from ..desktop import components
from . import componentes as mc

# Valor del desplegable "Método de pago" para el debito automatico (no es un
# metodo guardado: se indica con la tarjeta del gasto).
_DEBITO = "debito_automatico"

_ORDENES = [("vencimiento", "Fecha de vencimiento"), *mc.ORDENES_COMUNES]

# Filtros y orden elegidos: a nivel de modulo para que se mantengan al
# cambiar de seccion y volver, mientras la app esta abierta.
_filtro = FiltroGastosFijos()


def build_gastos_fijos_view(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    hoy = date.today()
    lista = ft.Column(spacing=12)
    busqueda = {"texto": ""}
    categorias = servicios.categorias.listar(TipoMovimiento.EGRESO)
    nombres_tarjeta = {t.id: t.nombre for t in servicios.tarjetas.listar_tarjetas()}
    contador = ft.Text("", size=12, color=theme.TEXT_SECONDARY, expand=True)

    def refrescar():
        todos = servicios.gastos_fijos.listar()
        ocurrencias = {o.gasto.id: o for o in servicios.gastos_fijos.proximas_ocurrencias(hoy.year, hoy.month)}
        # Filtros y orden son los de escritorio (los resuelve el servicio).
        gastos = servicios.gastos_fijos.filtrar_y_ordenar(todos, _filtro, hoy)
        gastos = mc.filtrar_y_ordenar(gastos, busqueda["texto"], "", lambda g: f"{g.concepto} {g.detalle}")
        contador.value = f"Mostrando {len(gastos)} de {len(todos)}" if _filtro.activo or busqueda["texto"].strip() else ""
        boton_filtros.icon_color = theme.MOVIMIENTOS_COLOR if _filtro.activo else theme.TEXT_SECONDARY
        quitar_btn.visible = _filtro.activo
        fila_contador.visible = bool(contador.value) or _filtro.activo
        if not todos:
            lista.controls = [components.empty_state("Todavía no cargaste gastos fijos.", "event_repeat_rounded")]
        elif not gastos:
            lista.controls = [components.empty_state("Ningún gasto fijo coincide con los filtros.", "filter_alt_off_rounded")]
        else:
            lista.controls = [theme.card(ft.Column([_fila(ocurrencias[g.id]) for g in gastos], spacing=4), padding=8)]

    def _fila(o) -> ft.Control:
        """El gasto en el mes actual: pagado, o cuando vence. Se toca para abrirlo."""
        g = o.gasto
        debito = f" · débito en {nombres_tarjeta.get(g.tarjeta_id, 'tarjeta')}" if g.tarjeta_id else ""
        if o.ya_registrado:
            fila = mc.fila_dato("check_circle_rounded", theme.INCOME_GREEN, g.concepto, f"Pagado este mes{debito}",
                                g.monto.formatted(), theme.TEXT_SECONDARY)
        else:
            vencido = o.fecha < hoy
            fila = mc.fila_dato("event_repeat_rounded", theme.EXPENSE_RED if vencido else theme.MOVIMIENTOS_COLOR, g.concepto,
                                f"{'Venció' if vencido else 'Vence'} el {o.fecha.strftime('%d/%m')}{debito}",
                                g.monto.formatted(), theme.TEXT_PRIMARY)
        return ft.Container(fila, padding=8, border_radius=theme.RADIUS_SM, ink=True,
                            on_click=lambda e: nav.abrir("Gasto fijo", lambda: _formulario(page, nav, servicios, g, o.ya_registrado),
                                                         theme.MOVIMIENTOS_COLOR))

    def al_buscar(texto: str, orden: str):
        busqueda["texto"], _filtro.orden = texto, orden
        refrescar()
        page.update()

    def nuevo(_e=None):
        nav.abrir("Nuevo gasto fijo", lambda: _formulario(page, nav, servicios), theme.MOVIMIENTOS_COLOR)

    # --- filtros (los mismos que en escritorio), plegados detras del boton del embudo ---
    def _filtro_dd(label: str, opciones: list[tuple[str, str]], valor: str, campo: str, convertir=lambda v: v) -> ft.Row:
        def al_elegir(e):
            setattr(_filtro, campo, convertir(e.control.value))
            refrescar()
            page.update()

        return ft.Row([mc.desplegable(label, valor, [ft.dropdown.Option(v, t) for v, t in opciones], on_select=al_elegir, expand=True)])

    def armar_filtros() -> list[ft.Control]:
        return [
            _filtro_dd("Estado", [("todos", "Todos"), ("en_curso", "En curso (falta pagar)"), ("finalizados", "Finalizados (pagado)")],
                       _filtro.estado, "estado"),
            _filtro_dd("Débito automático", [("todos", "Todos"), ("con", "Con débito"), ("sin", "Sin débito")], _filtro.debito, "debito"),
            _filtro_dd("Categoría", [("todas", "Todas")] + [(str(c.id), c.nombre) for c in categorias],
                       str(_filtro.categoria_id) if _filtro.categoria_id is not None else "todas", "categoria_id",
                       lambda v: None if v in (None, "todas") else int(v)),
        ]

    def quitar_filtros(_e=None):
        _filtro.estado, _filtro.debito, _filtro.categoria_id = "todos", "todos", None
        panel_filtros.controls = armar_filtros()
        refrescar()
        page.update()

    def alternar_filtros(_e=None):
        panel_filtros.visible = not panel_filtros.visible
        page.update()

    panel_filtros = ft.Column(armar_filtros(), spacing=10, visible=_filtro.activo)
    boton_filtros = ft.IconButton(icon=ft.Icons.FILTER_LIST_ROUNDED, tooltip="Filtros", on_click=alternar_filtros)
    quitar_btn = ft.TextButton("Quitar filtros", icon=ft.Icons.FILTER_ALT_OFF_ROUNDED, on_click=quitar_filtros,
                               style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))
    fila_contador = ft.Row([contador, quitar_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER)
    # Arranca con el orden que quedo elegido (el primero de la barra es el inicial).
    ordenes = sorted(_ORDENES, key=lambda o: o[0] != _filtro.orden)
    barra = mc.barra_busqueda(ordenes, al_buscar, theme.MOVIMIENTOS_COLOR)
    barra.controls.append(boton_filtros)

    pendiente = mc.totales_por_moneda(o.gasto.monto for o in servicios.gastos_fijos.proximas_ocurrencias(hoy.year, hoy.month)
                                      if not o.ya_registrado)
    refrescar()
    return ft.Stack(
        [
            mc.pantalla([
                theme.card(
                    ft.Column(
                        [
                            ft.Text(f"Falta pagar en {mc.MESES[hoy.month - 1]}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                            ft.Row([ft.Text(m.formatted(), size=22, weight=ft.FontWeight.BOLD, color=theme.EXPENSE_RED) for m in pendiente]
                                   or [ft.Text("Todo pagado", size=22, weight=ft.FontWeight.BOLD, color=theme.INCOME_GREEN)],
                                   spacing=16, wrap=True),
                        ],
                        spacing=6,
                    ),
                    padding=16,
                ),
                barra,
                panel_filtros,
                fila_contador,
                lista,
            ]),
            mc.boton_flotante(ft.Icons.ADD_ROUNDED, theme.MOVIMIENTOS_COLOR, nuevo, "Nuevo gasto fijo"),
        ],
        expand=True,
    )


def _texto_vencimiento_tarjeta(t) -> str:
    if t.dia_vencimiento is None:
        return (f"La tarjeta {t.nombre} no tiene cargado el día de vencimiento. "
                "Cargalo en Tarjetas (editar tarjeta) para usar débito automático.")
    cierre = f" (cierra el día {t.dia_cierre})" if t.dia_cierre else ""
    return f"El vencimiento es el de la tarjeta {t.nombre}: vence el día {t.dia_vencimiento} de cada mes{cierre}."


def _formulario(page: ft.Page, nav: mc.Navegacion, servicios, gasto: GastoFijo | None = None, pagado_este_mes: bool = False) -> ft.Control:
    """Alta o edicion de un gasto fijo. Pide lo mismo y en el mismo orden que
    el dialogo de escritorio: concepto, detalle, monto y moneda, categoria,
    metodo de pago (con debito automatico: la tarjeta) y dia de vencimiento.
    Al editar suma registrar el pago del mes y eliminar."""
    es_edicion = gasto is not None
    categorias = servicios.categorias.listar(TipoMovimiento.EGRESO)
    # Si su categoria fue quitada (Configuracion), se sigue ofreciendo para no cambiarla sin querer.
    if es_edicion and all(c.id != gasto.categoria_id for c in categorias):
        actual = servicios.categorias.obtener(gasto.categoria_id)
        if actual is not None:
            categorias.append(actual)
    tarjetas = servicios.tarjetas.listar_tarjetas()
    tarjeta_actual = gasto.tarjeta_id if es_edicion else None

    concepto_f = mc.campo("Concepto (ej: Alquiler, Luz, Netflix)", value=gasto.concepto if es_edicion else "", autofocus=not es_edicion)
    detalle_f = mc.campo("Detalle (opcional)", value=gasto.detalle if es_edicion else "")
    monto_f = mc.campo("Monto", value=components.monto_editable(gasto.monto) if es_edicion else "", keyboard_type=ft.KeyboardType.NUMBER)
    moneda_dd = mc.desplegable("Moneda", gasto.monto.moneda.value if es_edicion else Moneda.ARS.value,
                               [ft.dropdown.Option(m.value) for m in Moneda])
    categoria_dd = mc.desplegable("Categoría", str(gasto.categoria_id) if es_edicion else (str(categorias[0].id) if categorias else None),
                                  [ft.dropdown.Option(str(c.id), c.nombre) for c in categorias], expand=True)
    metodo_dd = mc.desplegable(
        "Método de pago", _DEBITO if tarjeta_actual is not None else (gasto.metodo_pago if es_edicion else "efectivo"),
        [ft.dropdown.Option("", "Sin especificar")] + [ft.dropdown.Option(k, v) for k, v in METODOS_PAGO.items()]
        + ([ft.dropdown.Option(_DEBITO, "Débito automático (tarjeta de crédito)")] if tarjetas else []),
        expand=True,
    )
    tarjeta_dd = mc.desplegable("¿A qué tarjeta se debita?",
                                str(tarjeta_actual) if tarjeta_actual else (str(tarjetas[0].id) if tarjetas else None),
                                [ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas], expand=True)
    fila_tarjeta = ft.Row([tarjeta_dd])
    # Con debito automatico el dia no se carga: es el de la tarjeta, y se informa en lugar del campo.
    texto_vencimiento = ft.Text("", size=12, color=theme.TEXT_PRIMARY, expand=True)
    icono_vencimiento = ft.Icon(ft.Icons.EVENT_ROUNDED, size=16, color=theme.TARJETAS_COLOR)
    info_vencimiento = ft.Container(
        ft.Row([icono_vencimiento, texto_vencimiento], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
        bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=10,
    )
    ayuda = ft.Text(
        "Aparece en el resumen de esa tarjeta, pero se cuenta una sola vez: como gasto fijo. "
        "Para quitarlo, elegí otro método de pago y cargá el día de vencimiento propio." if tarjetas
        else "Para usar débito automático, cargá una tarjeta en la sección Tarjetas.",
        size=11, color=theme.TEXT_MUTED, italic=True,
    )
    dia_f = mc.campo("Día de vencimiento (1-28)", value=str(gasto.dia_mes) if es_edicion else "1", keyboard_type=ft.KeyboardType.NUMBER)
    error = ft.Text("", color=theme.EXPENSE_RED, size=13, visible=False)

    def con_debito() -> bool:
        return metodo_dd.value == _DEBITO

    def tarjeta_elegida() -> int | None:
        return int(tarjeta_dd.value) if con_debito() and tarjeta_dd.value else None

    def actualizar(_e=None):
        tarjeta = next((t for t in tarjetas if str(t.id) == tarjeta_dd.value), None)
        fila_tarjeta.visible = con_debito()
        ayuda.visible = con_debito() or not tarjetas
        dia_f.visible = not con_debito()
        info_vencimiento.visible = con_debito() and tarjeta is not None
        if tarjeta is not None:
            texto_vencimiento.value = _texto_vencimiento_tarjeta(tarjeta)
            icono_vencimiento.color = theme.EXPENSE_RED if tarjeta.dia_vencimiento is None else theme.TARJETAS_COLOR
        if _e is not None:
            page.update()

    metodo_dd.on_select = actualizar
    tarjeta_dd.on_select = actualizar
    actualizar()

    def mostrar_error(exc: Exception):
        error.value = str(exc)
        error.visible = True
        page.update()

    def guardar(_e):
        try:
            monto = components.parse_monto(monto_f.value, moneda_dd.value)
            dia_mes = None if tarjeta_elegida() else components.parse_entero(dia_f.value, "Día de vencimiento", maximo=28)
            if not categoria_dd.value:
                raise ValueError("Elegí una categoría")
            metodo = "" if con_debito() else (metodo_dd.value or "")
            if es_edicion:
                servicios.gastos_fijos.editar(
                    gasto.id, monto, dia_mes, tarjeta_id=tarjeta_elegida(), concepto=concepto_f.value or "",
                    detalle=detalle_f.value or "", categoria_id=int(categoria_dd.value), metodo_pago=metodo,
                )
            else:
                servicios.gastos_fijos.registrar(concepto_f.value or "", detalle_f.value or "", monto, int(categoria_dd.value), dia_mes,
                                                 tarjeta_elegida(), metodo_pago=metodo)
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar("Gasto fijo guardado" if es_edicion else "Gasto fijo creado")

    def confirmar(titulo: str, mensaje: str, boton: str, color: str, icono: str, accion, aviso: str):
        def aceptar(_e):
            page.pop_dialog()
            try:
                accion()
            except ValueError as exc:
                mostrar_error(exc)
                return
            nav.volver()
            nav.avisar(aviso)

        page.show_dialog(theme.dialogo(
            titulo, ft.Text(mensaje, color=theme.TEXT_PRIMARY),
            [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button(boton, aceptar, color=color, icon=icono)],
            icono=icono, color=color, ancho=300,
        ))

    def registrar_pago(_e):
        # Se registra el gasto como esta guardado: los cambios sin guardar del formulario no cuentan.
        confirmar("Confirmar pago", f'¿Registrar el pago de "{gasto.concepto}" ({gasto.monto.formatted()}) este mes?', "Sí, registrar",
                  theme.MOVIMIENTOS_COLOR, "check_rounded", lambda: servicios.gastos_fijos.generar_movimiento_del_mes(gasto.id),
                  "Pago registrado")

    def eliminar(_e):
        confirmar("Eliminar gasto fijo", "¿Seguro que querés eliminar este gasto fijo? Los pagos ya registrados no se borran.", "Eliminar",
                  theme.EXPENSE_RED, "delete_outline_rounded", lambda: servicios.gastos_fijos.eliminar(gasto.id), "Gasto fijo eliminado")

    cabecera: list[ft.Control] = []
    if es_edicion:
        if pagado_este_mes:
            cabecera.append(ft.Row([components.category_chip("Pagado este mes", theme.INCOME_GREEN, "check_circle_rounded")]))
        else:
            cabecera.append(mc.boton_ancho("Registrar pago de este mes", registrar_pago, theme.INCOME_GREEN,
                                           ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED))
        cabecera.append(ft.Text("Los cambios se usan desde el próximo pago que registres. Los pagos ya hechos no se modifican.",
                                size=12, color=theme.TEXT_SECONDARY))

    return mc.pantalla([
        *cabecera,
        concepto_f,
        detalle_f,
        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
        ft.Row([categoria_dd]),
        ft.Row([metodo_dd]),
        fila_tarjeta,
        info_vencimiento,
        ayuda,
        dia_f,
        error,
        mc.boton_ancho("Guardar" if es_edicion else "Crear", guardar, theme.MOVIMIENTOS_COLOR, ft.Icons.CHECK_ROUNDED),
        *([ft.Row([ft.TextButton("Eliminar gasto fijo", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=eliminar,
                                 style=ft.ButtonStyle(color=theme.EXPENSE_RED))], alignment=ft.MainAxisAlignment.CENTER)]
          if es_edicion else []),
    ])
