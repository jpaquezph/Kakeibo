from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.gastos_fijos import FiltroGastosFijos, GastoFijoService
from ...app.services.tarjetas import TarjetaService
from .. import theme
from . import components

# Filtros y orden elegidos: a nivel de modulo para que se mantengan al
# cambiar de seccion y volver, mientras la app esta abierta.
_filtro = FiltroGastosFijos()


def build_gastos_fijos_view(
    page: ft.Page, gasto_fijo_service: GastoFijoService, categoria_repo: CategoriaRepository, tarjeta_service: TarjetaService,
) -> ft.Control:
    categorias = categoria_repo.listar(TipoMovimiento.EGRESO)

    def _texto_vencimiento_tarjeta(t) -> str:
        if t is None:
            return ""
        if t.dia_vencimiento is None:
            return (f"La tarjeta {t.nombre} no tiene cargado el día de vencimiento. "
                    "Cargalo en Tarjetas (editar tarjeta) para usar débito automático.")
        cierre = f" (cierra el día {t.dia_cierre})" if t.dia_cierre else ""
        return f"El vencimiento es el de la tarjeta {t.nombre}: vence el día {t.dia_vencimiento} de cada mes{cierre}."

    def _campos_debito(tarjeta_actual: int | None, dia_field: ft.TextField):
        """Casilla de debito automatico + tarjeta a la que se debita. Con debito
        automatico el dia de vencimiento no se carga: es el de la tarjeta, y se
        informa en lugar del campo. Devuelve (controles, funcion que lee la
        tarjeta elegida o None)."""
        tarjetas = tarjeta_service.listar_tarjetas()
        check = ft.Checkbox(
            label="Se paga con débito automático de tarjeta", value=tarjeta_actual is not None,
            active_color=theme.MOVIMIENTOS_COLOR, disabled=not tarjetas,
        )
        tarjeta_dd = ft.Dropdown(
            label="¿A qué tarjeta se debita?",
            value=str(tarjeta_actual) if tarjeta_actual else (str(tarjetas[0].id) if tarjetas else None),
            options=[ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
            visible=tarjeta_actual is not None,
        )
        ayuda = ft.Text(
            "Aparece en el resumen de esa tarjeta, pero se cuenta una sola vez: como gasto fijo. "
            "Para quitarlo, destildá la casilla y cargá el día de vencimiento propio." if tarjetas
            else "Cargá una tarjeta en la sección Tarjetas para poder usar débito automático.",
            size=11, color=theme.TEXT_MUTED, italic=True,
        )

        info_vencimiento = ft.Container(
            ft.Row(
                [ft.Icon(ft.Icons.EVENT_ROUNDED, size=16, color=theme.TARJETAS_COLOR),
                 ft.Text("", size=12, color=theme.TEXT_PRIMARY, expand=True)],
                spacing=8, vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=10,
        )

        def actualizar(_e=None):
            con_debito = bool(check.value)
            tarjeta_dd.visible = con_debito
            dia_field.visible = not con_debito
            tarjeta = next((t for t in tarjetas if str(t.id) == tarjeta_dd.value), None)
            info_vencimiento.visible = con_debito and tarjeta is not None
            info_vencimiento.content.controls[1].value = _texto_vencimiento_tarjeta(tarjeta)
            sin_dia = tarjeta is not None and tarjeta.dia_vencimiento is None
            info_vencimiento.content.controls[0].color = theme.EXPENSE_RED if sin_dia else theme.TARJETAS_COLOR
            if _e is not None:
                page.update()

        check.on_change = actualizar
        tarjeta_dd.on_select = actualizar
        actualizar()
        return [check, tarjeta_dd, info_vencimiento, ayuda], lambda: int(tarjeta_dd.value) if check.value and tarjeta_dd.value else None

    def _nombre_tarjeta(tarjeta_id: int) -> str:
        t = tarjeta_service.obtener_tarjeta(tarjeta_id)
        return t.nombre if t else "tarjeta"
    # Grilla de fichas compactas: 2 por fila con la ventana normal, 3 con la
    # ventana grande (y 1 si se achica mucho).
    grilla = ft.ResponsiveRow(spacing=12, run_spacing=12)
    lista_col = ft.Column([grilla], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    contador_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def refrescar():
        todos = gasto_fijo_service.listar()
        gastos = gasto_fijo_service.filtrar_y_ordenar(todos, _filtro)
        contador_text.value = f"Mostrando {len(gastos)} de {len(todos)}" if _filtro.activo else f"{len(todos)} gasto(s) fijo(s)"
        limpiar_btn.visible = _filtro.activo
        grilla.controls.clear()
        if not todos:
            grilla.controls.append(components.empty_state("Todavía no cargaste gastos fijos.", "event_repeat_rounded"))
        elif not gastos:
            grilla.controls.append(components.empty_state("Ningún gasto fijo coincide con los filtros.", "filter_alt_off_rounded"))
        for g in gastos:
            grilla.controls.append(ft.Container(_gasto_card(g), col={"xs": 12, "md": 6, "xl": 4}))
        page.update()

    # --- filtros y orden (chicos, arriba de la lista) ---
    def _filtro_dd(label: str, opciones: list[tuple[str, str]], valor: str, al_cambiar, ancho: int) -> ft.Dropdown:
        # Mismo estilo que los filtros de Historial: la etiqueta queda dentro del recuadro.
        return ft.Dropdown(
            label=label, value=valor, options=[ft.dropdown.Option(v, t) for v, t in opciones],
            border=ft.InputBorder.NONE, content_padding=components.PADDING_FILTRO, width=ancho, on_select=al_cambiar,
        )

    def _al_cambiar(campo: str, convertir=lambda v: v):
        def handler(e):
            setattr(_filtro, campo, convertir(e.control.value))
            refrescar()
        return handler

    estado_dd = _filtro_dd("Estado", [("todos", "Todos"), ("en_curso", "En curso (falta pagar)"), ("finalizados", "Finalizados (pagado)")],
                           _filtro.estado, _al_cambiar("estado"), 190)
    debito_dd = _filtro_dd("Déb. auto.", [("todos", "Todos"), ("con", "Con débito"), ("sin", "Sin débito")],
                           _filtro.debito, _al_cambiar("debito"), 160)
    categoria_dd = _filtro_dd("Categoría", [("todas", "Todas")] + [(str(c.id), c.nombre) for c in categorias],
                              str(_filtro.categoria_id) if _filtro.categoria_id is not None else "todas",
                              _al_cambiar("categoria_id", lambda v: None if v in (None, "todas") else int(v)), 170)
    orden_dd = _filtro_dd("Ordenar por", [("vencimiento", "Fecha de vencimiento"), ("monto_mayor", "Monto mayor"),
                                          ("monto_menor", "Monto menor"), ("alfabetico", "Orden alfabético")],
                          _filtro.orden, _al_cambiar("orden"), 180)

    def limpiar(_e=None):
        _filtro.estado, _filtro.debito, _filtro.categoria_id = "todos", "todos", None
        estado_dd.value, debito_dd.value, categoria_dd.value = "todos", "todos", "todas"
        refrescar()

    limpiar_btn = ft.TextButton("Quitar filtros", icon=ft.Icons.FILTER_ALT_OFF_ROUNDED, on_click=limpiar,
                                style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))
    barra_filtros = ft.Row(
        [ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, size=18, color=theme.TEXT_SECONDARY),
         *[components.recuadro_filtro(dd) for dd in (estado_dd, debito_dd, categoria_dd)],
         ft.Container(width=8), components.recuadro_filtro(orden_dd), limpiar_btn, contador_text],
        spacing=8, wrap=True, run_spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def _nombre_categoria(categoria_id: int) -> str:
        cat = next((c for c in categorias if c.id == categoria_id), None)
        return cat.nombre if cat else "Categoría"

    def _gasto_card(g):
        hoy = date.today()
        proximo = gasto_fijo_service.proximo_vencimiento(g, hoy)
        ya_este_mes = gasto_fijo_service.ya_registrado_este_mes(g.id, hoy.year, hoy.month)

        if ya_este_mes:
            estado_pago = components.category_chip("Pagado este mes", theme.INCOME_GREEN, "check_circle_rounded")
        else:
            estado_pago = ft.FilledButton(
                "Registrar pago", icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                style=ft.ButtonStyle(bgcolor=theme.MOVIMIENTOS_COLOR, color="#FFFFFF", padding=theme.pad(horizontal=12, vertical=6),
                                     shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM)),
                on_click=lambda e, gasto=g: confirmar_registrar(gasto),
            )
        vence = (f"Vence con {_nombre_tarjeta(g.tarjeta_id)} (día {gasto_fijo_service.dia_vencimiento(g)})" if g.tarjeta_id
                 else f"Vence el día {g.dia_mes}")

        return theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(g.concepto, size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=g.concepto),
                            ft.Text(g.monto.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.MOVIMIENTOS_COLOR),
                        ],
                        spacing=8,
                    ),
                    *([ft.Text(g.detalle, size=11, color=theme.TEXT_SECONDARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=g.detalle)]
                      if g.detalle else []),
                    ft.Row(
                        [
                            components.category_chip(_nombre_categoria(g.categoria_id), theme.MOVIMIENTOS_COLOR, "sell_rounded"),
                            *([ft.Container(
                                components.category_chip(f"Débito · {_nombre_tarjeta(g.tarjeta_id)}", theme.TARJETAS_COLOR, "autorenew_rounded"),
                                on_click=lambda e, gasto=g: dialogo_editar_gasto(gasto),
                                tooltip="Débito automático. Tocá para cambiarlo o quitarlo",
                            )] if g.tarjeta_id else []),
                        ],
                        spacing=6, wrap=True, run_spacing=6,
                    ),
                    ft.Text(f"{vence} · próximo {proximo.strftime('%d/%m/%Y')}", size=11, color=theme.TEXT_SECONDARY),
                    ft.Row(
                        [
                            estado_pago,
                            ft.Row(
                                [
                                    ft.TextButton("Editar", icon=ft.Icons.EDIT_ROUNDED,
                                                  style=ft.ButtonStyle(color=theme.TEXT_SECONDARY, padding=theme.pad(horizontal=8, vertical=4)),
                                                  tooltip="Cambiar monto, vencimiento o débito automático",
                                                  on_click=lambda e, gasto=g: dialogo_editar_gasto(gasto)),
                                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=theme.EXPENSE_RED, icon_size=18,
                                                  tooltip="Eliminar", on_click=lambda e, gid=g.id: eliminar(gid)),
                                ],
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=6,
            ),
            padding=14,
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
        campos_debito, tarjeta_elegida = _campos_debito(gasto.tarjeta_id, vencimiento_f)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                nuevo_monto = components.parse_monto(monto_f.value, gasto.monto.moneda, "Nuevo monto")
                nuevo_dia = None if tarjeta_elegida() else components.parse_entero(vencimiento_f.value, "Día de vencimiento", maximo=28)
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
            title=components.titulo_con_error("Editar gasto fijo", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Los cambios se usan desde el próximo pago que registres. Los pagos ya hechos no se modifican.", size=12, color=theme.TEXT_SECONDARY),
                        monto_f, vencimiento_f, *campos_debito,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
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
        campos_debito, tarjeta_elegida = _campos_debito(None, dia_f)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                monto = components.parse_monto(monto_f.value, moneda_dd.value)
                dia_mes = None if tarjeta_elegida() else components.parse_entero(dia_f.value, "Día de vencimiento", maximo=28)
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
            title=components.titulo_con_error("Nuevo gasto fijo", error_text),
            content=ft.Container(
                ft.Column(
                    [concepto_f, detalle_f, ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8), dia_f, categoria_dd, *campos_debito],
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

    return ft.Column([header, ft.Container(height=10), barra_filtros, ft.Container(height=10), lista_col], expand=True, spacing=0)
