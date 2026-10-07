from __future__ import annotations

import calendar
from datetime import date, datetime

import flet as ft

from ...app.domain.dates import add_months
from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.tarjetas import TarjetaService, monto_total_desde_cuota
from .. import theme
from . import components

_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _formatear_totales(montos) -> str:
    """Suma los montos por moneda y los muestra juntos sin mezclarlos
    ("$ 1.000,00 + $us 50,00"). Los totales en cero no se muestran."""
    por_moneda: dict[Moneda, Money] = {}
    for m in montos:
        por_moneda[m.moneda] = por_moneda[m.moneda] + m if m.moneda in por_moneda else m
    partes = [por_moneda[m].formatted() for m in Moneda if m in por_moneda and por_moneda[m].cents]
    return " + ".join(partes) if partes else Money.zero(Moneda.ARS).formatted()


# Filtro de las compras: se mantiene al cambiar de tarjeta o de seccion.
# pagadas: si ademas de lo que falta pagar del mes se ve lo ya pagado.
_filtro = {"forma": "todas", "pagadas": False}


def _mes_y_anio(fecha: date) -> str:
    return f"{_MESES[fecha.month - 1].lower()} {fecha.year}"


class SelectorResumen:
    """En que resumen entra una compra. Lo propone segun el dia de cierre y de
    vencimiento de la tarjeta y lo avisa; se puede cambiar, porque el cierre
    se corre algunos dias de un mes a otro."""

    def __init__(self, page: ft.Page, tarjeta_service: TarjetaService, **estilo):
        self._page = page
        self._service = tarjeta_service
        self._fecha = date.today()
        self._propuesto = 0
        self._origen = ""
        self._que = "Se paga"
        self.dropdown = ft.Dropdown(label="Entra en el resumen de", on_select=self._al_elegir, **estilo)
        self.aviso = ft.Text("", size=12, color=theme.TEXT_SECONDARY, italic=True)

    @property
    def meses(self) -> int:
        """Cuantos meses despues de la fecha de la compra se paga."""
        return int(self.dropdown.value or 0)

    @property
    def fecha(self) -> date:
        """La fecha de compra para la que se armaron los meses."""
        return self._fecha

    @property
    def mes(self) -> date:
        """El mes elegido (su dia 1)."""
        return add_months(self._fecha.replace(day=1), self.meses)

    def proponer(self, tarjeta_id: int | None, fecha: date, cantidad_cuotas: int, que: str = "Se paga", meses: int | None = None) -> None:
        """Arma los meses para esa fecha y deja elegido el que corresponde a
        la tarjeta. `meses`: el que ya tiene la compra, si se esta editando."""
        tarjeta = self._service.obtener_tarjeta(tarjeta_id) if tarjeta_id is not None else None
        self._fecha, self._que = fecha, que
        self._propuesto = self._service.meses_al_resumen(tarjeta_id, fecha, cantidad_cuotas) if tarjeta else 0
        if tarjeta and tarjeta.dia_cierre and tarjeta.dia_vencimiento:
            self._origen = f"{tarjeta.nombre} cierra el {tarjeta.dia_cierre} y vence el {tarjeta.dia_vencimiento}."
        else:
            self._origen = "La tarjeta no tiene cargados el día de cierre y el de vencimiento: revisá el mes."
        elegido = self._propuesto if meses is None else max(meses, 0)
        primero = fecha.replace(day=1)
        self.dropdown.options = [
            ft.dropdown.Option(str(i), _mes_y_anio(add_months(primero, i)).capitalize()) for i in range(max(elegido, 3) + 1)
        ]
        self.dropdown.value = str(elegido)
        self._actualizar_aviso()

    def describir(self, que: str) -> None:
        """Cambia como se nombra lo que se paga ("La cuota 4 se paga")."""
        self._que = que
        self._actualizar_aviso()

    def _actualizar_aviso(self) -> None:
        self.aviso.value = f"{self._origen} {self._que} en {_mes_y_anio(self.mes)}."
        if self.meses != self._propuesto:
            propuesto = _mes_y_anio(add_months(self._fecha.replace(day=1), self._propuesto))
            self.aviso.value += f" (Por las fechas de la tarjeta sería {propuesto}.)"

    def _al_elegir(self, _e) -> None:
        self._actualizar_aviso()
        self._page.update()


def filtrar_por_forma(compras, forma: str) -> list:
    """`forma`: "todas", "cuotas" (2 o mas cuotas) o "un_pago"."""
    if forma == "cuotas":
        return [c for c in compras if c.cantidad_cuotas > 1]
    if forma == "un_pago":
        return [c for c in compras if c.cantidad_cuotas == 1]
    return list(compras)


def vencimiento_en_resumen(vence: date, dia_vencimiento: int | None) -> date:
    """Cuando se paga una cuota: el dia en que vence el resumen de la tarjeta,
    en el mes de la cuota. Si la tarjeta no tiene cargado el dia de
    vencimiento, vale la fecha de la cuota."""
    if dia_vencimiento is None:
        return vence
    return vence.replace(day=min(dia_vencimiento, calendar.monthrange(vence.year, vence.month)[1]))


def build_tarjetas_view(
    page: ft.Page, tarjeta_service: TarjetaService, categoria_repo: CategoriaRepository, gasto_fijo_service: GastoFijoService,
) -> ft.Control:
    categoria_tarjeta = next((c for c in categoria_repo.listar(TipoMovimiento.EGRESO) if c.nombre == "Tarjeta de crédito"), None)
    categoria_tarjeta_id = categoria_tarjeta.id if categoria_tarjeta else None
    # anio/mes: el resumen que se esta viendo (al entrar, el del mes actual).
    estado = {"tarjeta_id": None, "anio": date.today().year, "mes": date.today().month}

    tarjetas_row = ft.Row(spacing=12, wrap=True)
    detalle_col = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)
    navegacion_mes = ft.Row(spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def es_mes_actual() -> bool:
        return (estado["anio"], estado["mes"]) == (date.today().year, date.today().month)

    def nombre_mes() -> str:
        """El mes que se esta viendo, con el anio si no es el actual."""
        mes = _MESES[estado["mes"] - 1].lower()
        return mes if estado["anio"] == date.today().year else f"{mes} {estado['anio']}"

    def ir_a_mes(anio: int, mes: int):
        estado["anio"], estado["mes"] = anio, mes
        refrescar_tarjetas()

    def mover_mes(delta: int):
        total = estado["anio"] * 12 + (estado["mes"] - 1) + delta
        ir_a_mes(total // 12, total % 12 + 1)

    def refrescar_navegacion():
        # Desplegable para saltar a cualquier mes: un anio para atras y dos
        # para adelante (las cuotas largas), mas el que se esta viendo.
        visto = date(estado["anio"], estado["mes"], 1)
        primero = date.today().replace(day=1)
        meses = sorted({add_months(primero, i) for i in range(-12, 25)} | {visto})
        mes_dd = ft.Dropdown(
            value=visto.isoformat(), width=190, text_size=15,
            options=[ft.dropdown.Option(m.isoformat(), f"{_MESES[m.month - 1]} {m.year}") for m in meses],
            on_select=lambda e: ir_a_mes(*date.fromisoformat(e.control.value).timetuple()[:2]),
            border=ft.InputBorder.NONE, content_padding=components.PADDING_FILTRO,
        )
        navegacion_mes.controls = [
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, tooltip="Mes anterior", on_click=lambda e: mover_mes(-1)),
            components.recuadro_filtro(mes_dd),
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, tooltip="Mes siguiente", on_click=lambda e: mover_mes(1)),
            *([] if es_mes_actual() else [ft.TextButton("Mes actual", on_click=lambda e: ir_a_mes(date.today().year, date.today().month),
                                                        style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))]),
        ]

    def refrescar_tarjetas():
        refrescar_navegacion()
        tarjetas = tarjeta_service.listar_tarjetas()
        tarjetas_row.controls.clear()
        if not tarjetas:
            tarjetas_row.controls.append(components.empty_state("Todavía no cargaste tarjetas.", "credit_card_rounded"))
        for t in tarjetas:
            seleccionada = t.id == estado["tarjeta_id"]
            tarjetas_row.controls.append(_tarjeta_card(t, seleccionada, lambda e, tid=t.id: seleccionar(tid)))
        if estado["tarjeta_id"] is None and tarjetas:
            estado["tarjeta_id"] = tarjetas[0].id
        refrescar_detalle()
        page.update()

    def _tarjeta_card(t, seleccionada, on_click):
        # Lo que hay que pagar en el mes que se esta viendo (cuotas del mes,
        # compras en 1 pago y debitos automaticos) y, aparte, todo lo que
        # falta de las compras.
        resumen, debitos_pendientes, debitos_pagados = _resumen_mes(t.id)
        del_mes = [cu.monto for _co, cu in resumen.pendientes] + [o.gasto.monto for o in debitos_pendientes]
        deuda = [tarjeta_service.total_pendiente(t.id, m) for m in Moneda]
        mes = nombre_mes()
        if del_mes:
            total_mes = _formatear_totales(del_mes)
            linea_mes = ft.Text(f"{'Este mes' if es_mes_actual() else mes.capitalize()}: {total_mes}", color="#FFFFFF", size=12,
                                weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=f"A pagar en {mes}: {total_mes}")
        elif resumen.pagos or resumen.pagadas or debitos_pagados:
            linea_mes = ft.Row(
                [ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color="#FFFFFF", size=14),
                 ft.Text("Mes saldado" if es_mes_actual() else f"{mes.capitalize()} saldado", color="#FFFFFF", size=12,
                         weight=ft.FontWeight.BOLD)],
                spacing=4,
            )
        else:
            linea_mes = ft.Text(f"Sin consumos {'este mes' if es_mes_actual() else 'en ' + mes}", color="#FFFFFF", size=12,
                                weight=ft.FontWeight.BOLD)
        return ft.Container(
            content=ft.Column(
                [
                    # Nombre y lapiz de editar en la misma linea (antes el lapiz
                    # ocupaba una linea propia y el contenido se salia del recuadro).
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color="#FFFFFF", size=18),
                            ft.Text(t.nombre, color="#FFFFFF", weight=ft.FontWeight.BOLD, size=14, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=t.nombre),
                            ft.Container(
                                ft.Icon(ft.Icons.EDIT_ROUNDED, color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=15),
                                on_click=lambda e, tarjeta=t: dialogo_tarjeta(tarjeta), tooltip="Editar tarjeta",
                                padding=2, border_radius=theme.RADIUS_SM,
                            ),
                        ],
                        spacing=6,
                    ),
                    # Banco, digitos, cierre y vencimiento en una sola linea chica
                    # (antes eran dos y la ficha ocupaba mucho alto).
                    ft.Text(" · ".join(p for p in [
                                f"{t.banco} ••{t.ultimos_digitos}" if t.ultimos_digitos else t.banco,
                                f"cierra {t.dia_cierre}" if t.dia_cierre else "",
                                f"vence {t.dia_vencimiento}" if t.dia_vencimiento else ""] if p),
                            color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    linea_mes,
                    *([ft.Text(f"Deuda total: {_formatear_totales(deuda)}", color=ft.Colors.with_opacity(0.85, "#FFFFFF"), size=10,
                               max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                               tooltip="Todas las cuotas que faltan pagar, de este mes y de los que vienen")]
                      if any(d.cents for d in deuda) else []),
                ],
                spacing=1,
            ),
            width=210,
            height=92,
            padding=theme.pad(horizontal=12, vertical=8),
            border_radius=theme.RADIUS,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[t.color, theme.darken(t.color)],
            ),
            border=theme.border_all(3, theme.TEXT_PRIMARY) if seleccionada else None,
            on_click=on_click,
            ink=True,
        )

    def seleccionar(tarjeta_id: int):
        estado["tarjeta_id"] = tarjeta_id
        refrescar_tarjetas()

    def refrescar_detalle():
        detalle_col.controls.clear()
        if estado["tarjeta_id"] is None:
            detalle_col.controls.append(components.empty_state("Elegí o creá una tarjeta para ver sus compras."))
            return
        compras = tarjeta_service.listar_compras(estado["tarjeta_id"])
        tarjeta_actual = tarjeta_service.obtener_tarjeta(estado["tarjeta_id"])
        banner = _banner_mes(estado["tarjeta_id"])
        if banner:
            detalle_col.controls.append(banner)
        debitos = _debitos_card(estado["tarjeta_id"])
        if debitos:
            detalle_col.controls.append(debitos)
        if not compras:
            detalle_col.controls.append(components.empty_state("Esta tarjeta todavía no tiene compras.", "shopping_bag_rounded"))
            return
        # Solo lo del mes que se esta viendo: lo que falta pagar y, si se pide,
        # lo ya pagado (aparte, para que no se mezcle con lo nuevo).
        resumen, _debitos, _pagados = _resumen_mes(estado["tarjeta_id"])
        ids = {c.id for c in filtrar_por_forma(compras, _filtro["forma"])}
        pendientes = [(co, cu) for co, cu in resumen.pendientes if co.id in ids]
        pagadas = [(co, cu) for co, cu in resumen.pagadas if co.id in ids]
        visibles = pendientes + (pagadas if _filtro["pagadas"] else [])
        if resumen.pendientes or resumen.pagadas:
            detalle_col.controls.append(_barra_filtro(pendientes, pagadas))
        if not visibles:
            if _filtro["forma"] != "todas" and (resumen.pendientes or resumen.pagadas) and not pagadas:
                detalle_col.controls.append(components.empty_state("Ninguna compra coincide con el filtro.", "filter_alt_off_rounded"))
            elif pagadas:
                detalle_col.controls.append(components.empty_state(f"No queda nada por pagar en {nombre_mes()}.", "check_circle_rounded"))
            else:
                detalle_col.controls.append(components.empty_state(f"No hay compras ni cuotas en {nombre_mes()}.", "shopping_bag_rounded"))
        # Grilla de fichas compactas: 2 por fila con la ventana normal, 3 con la grande.
        detalle_col.controls.append(ft.ResponsiveRow(
            [ft.Container(_compra_card(co, cu, tarjeta_actual), col={"xs": 12, "md": 6, "xl": 4}) for co, cu in visibles],
            spacing=12, run_spacing=12,
        ))

    def _barra_filtro(pendientes: list, pagadas: list) -> ft.Control:
        def cambiar(e):
            _filtro["forma"] = e.control.value
            refrescar_detalle()
            page.update()

        def ver_pagadas(e):
            _filtro["pagadas"] = bool(e.control.value)
            refrescar_detalle()
            page.update()

        forma_dd = ft.Dropdown(
            label="Forma de pago", value=_filtro["forma"], width=170, on_select=cambiar,
            options=[ft.dropdown.Option("todas", "Todas"), ft.dropdown.Option("cuotas", "En cuotas"),
                     ft.dropdown.Option("un_pago", "1 pago")],
            border=ft.InputBorder.NONE, content_padding=components.PADDING_FILTRO,
        )
        contador = f"{len(pendientes)} por pagar"
        # Lo ya pagado del mes no se muestra salvo que se pida.
        pagadas_check = ft.Checkbox(
            label=f"Ver pagadas ({len(pagadas)})", value=_filtro["pagadas"], on_change=ver_pagadas, active_color=theme.TARJETAS_COLOR,
            label_style=ft.TextStyle(size=12, color=theme.TEXT_SECONDARY),
        ) if pagadas else ft.Container()
        # Lo que hay que pagar en el mes de las compras que muestra el filtro
        # (por moneda, sin mezclar). Sin filtro suma tambien los debitos
        # automaticos: es el total del mes de la tarjeta.
        _resumen, debitos, _pagados = _resumen_mes(estado["tarjeta_id"])
        del_mes = [cu.monto for _co, cu in pendientes]
        if _filtro["forma"] == "todas":
            del_mes += [o.gasto.monto for o in debitos]
        que = {"todas": "", "cuotas": " en cuotas", "un_pago": " en 1 pago"}[_filtro["forma"]]
        totales = ft.Row(
            [
                ft.Text(f"Total mensual{que}:", size=12, color=theme.TEXT_SECONDARY),
                ft.Text(_formatear_totales(del_mes), size=13, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR,
                        tooltip=f"Lo que hay que pagar en {nombre_mes()}"),
            ],
            spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ) if del_mes else ft.Container()
        # Los totales van a la derecha, en la misma fila del filtro (sin wrap:
        # en una fila con wrap no puede ir el espaciador con expand).
        return ft.Row(
            [ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, size=18, color=theme.TEXT_SECONDARY), components.recuadro_filtro(forma_dd),
             ft.Text(contador, size=12, color=theme.TEXT_SECONDARY), pagadas_check, ft.Container(expand=True), totales],
            spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _resumen_mes(tarjeta_id: int):
        """El resumen del mes que se esta viendo, y sus debitos automaticos sin pagar y pagados."""
        resumen = tarjeta_service.resumen_del_mes(tarjeta_id, estado["anio"], estado["mes"])
        debitos = gasto_fijo_service.debitos_del_mes(tarjeta_id, estado["anio"], estado["mes"])
        return resumen, [o for o in debitos if not o.ya_registrado], [o for o in debitos if o.ya_registrado]

    def _partes_pendientes(resumen, debitos) -> list[tuple[str, list[Money]]]:
        """Lo que falta pagar del mes separado en cuotas, compras en 1 pago y
        debitos automaticos (solo los grupos que tienen algo)."""
        cuotas = [cu.monto for co, cu in resumen.pendientes if co.cantidad_cuotas > 1]
        un_pago = [cu.monto for co, cu in resumen.pendientes if co.cantidad_cuotas == 1]
        automaticos = [o.gasto.monto for o in debitos]
        partes = [
            (f"{len(cuotas)} cuota(s)", cuotas),
            (f"{len(un_pago)} compra(s) en 1 pago", un_pago),
            (f"{len(automaticos)} débito(s) automático(s)", automaticos),
        ]
        return [(titulo, montos) for titulo, montos in partes if montos]

    def _debitos_card(tarjeta_id: int):
        debitos = gasto_fijo_service.debitos_del_mes(tarjeta_id, estado["anio"], estado["mes"])
        if not debitos:
            return None
        filas = []
        for o in debitos:
            estado_chip = (
                components.category_chip("Pagado", theme.INCOME_GREEN, "check_circle_rounded") if o.ya_registrado
                else ft.Text(f"Vence el {o.fecha.strftime('%d/%m')}", size=12, color=theme.TEXT_SECONDARY)
            )
            filas.append(ft.Row(
                [
                    ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=16, color=theme.MOVIMIENTOS_COLOR),
                    ft.Text(o.gasto.concepto, size=13, color=theme.TEXT_PRIMARY, expand=True),
                    estado_chip,
                    ft.Text(o.gasto.monto.formatted(), size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY, width=120, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=10,
            ))
        return theme.card(
            ft.Column(
                [
                    ft.Text(f"Débitos automáticos de {nombre_mes()}", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Text("Son gastos fijos: se cuentan una sola vez, en Gastos fijos. Pagar la tarjeta también registra su pago.",
                            size=11, color=theme.TEXT_MUTED),
                    *filas,
                ],
                spacing=8,
            ),
            padding=14,
        )

    def _banner_mes(tarjeta_id: int):
        mes = nombre_mes()
        resumen, debitos_pendientes, debitos_pagados = _resumen_mes(tarjeta_id)
        partes = _partes_pendientes(resumen, debitos_pendientes)
        if partes:
            total = _formatear_totales([m for _titulo, montos in partes for m in montos])
            return theme.card(
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(f"Total a pagar en {mes}: {total}", size=14, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                                ft.Text(" · ".join(f"{titulo}: {_formatear_totales(montos)}" for titulo, montos in partes),
                                        size=12, color=theme.TEXT_SECONDARY),
                            ],
                            spacing=2, expand=True,
                        ),
                        theme.primary_button("Pagar tarjeta (mes)", lambda e, tid=tarjeta_id: confirmar_pagar_mes(tid), color=theme.TARJETAS_COLOR, icon=ft.Icons.PAYMENTS_ROUNDED),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=14,
            )
        if not (resumen.pagos or resumen.pagadas or debitos_pagados):
            return None
        if resumen.pagos:
            pagado = _formatear_totales([p.monto for p in resumen.pagos])
            detalle = f"Pagaste {pagado} el {resumen.pagos[-1].fecha_pago.strftime('%d/%m/%Y')}."
        else:
            detalle = "Ya está pago todo lo que vencía en el mes."
        return theme.card(
            ft.Row(
                [
                    components.category_chip("Mes saldado", theme.INCOME_GREEN, "check_circle_rounded"),
                    ft.Text(f"{mes.capitalize()}: {detalle}", size=13, color=theme.TEXT_PRIMARY, expand=True),
                ],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
        )

    def confirmar_pagar_mes(tarjeta_id: int):
        anio, mes = estado["anio"], estado["mes"]
        resumen, debitos, _pagados = _resumen_mes(tarjeta_id)
        partes = _partes_pendientes(resumen, debitos)
        calculado: dict[Moneda, Money] = {}
        for _titulo, montos in partes:
            for m in montos:
                calculado[m.moneda] = calculado[m.moneda] + m if m.moneda in calculado else m
        # El saldo se puede corregir: el resumen de la tarjeta puede venir con
        # otro importe (impuestos, intereses, ajustes). Un campo por moneda.
        campos = {
            moneda: ft.TextField(
                label=f"Saldo a pagar ({moneda.value})", value=components.monto_editable(total), keyboard_type=ft.KeyboardType.NUMBER,
                filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
            )
            for moneda, total in calculado.items()
        }
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def confirmar(_e):
            try:
                pagado = {moneda: components.parse_monto(campo.value, moneda, f"Saldo a pagar ({moneda.value})")
                          for moneda, campo in campos.items()}
                tarjeta_service.pagar_mes(tarjeta_id, anio, mes, [o.gasto.monto for o in debitos], pagado)
                gasto_fijo_service.registrar_debitos_del_mes(tarjeta_id, anio, mes)
            except (ValueError, ArithmeticError) as exc:
                error_text.value, error_text.visible = str(exc), True
                page.update()
                return
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error(f"Pagar tarjeta de {nombre_mes()}", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text(f"Se marca como pagado todo lo de {nombre_mes()}:", size=13, weight=ft.FontWeight.W_600),
                        *[ft.Text(f"•  {titulo}: {_formatear_totales(montos)}", size=13) for titulo, montos in partes],
                        *campos.values(),
                        ft.Text("Si el resumen vino con otro importe (impuestos, intereses, ajustes), corregí el saldo antes de pagar.",
                                size=11, color=theme.TEXT_MUTED),
                        ft.Text(
                            "Nota: si compraste algo en cuotas hace poco, su 1ra cuota recién vence el mes que viene, "
                            "por eso puede no estar incluida todavía.",
                            size=11, color=theme.TEXT_MUTED, italic=True,
                        ),
                    ],
                    spacing=10, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
            ),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, pagar todo", confirmar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def _compra_card(c, cuota, tarjeta_actual):
        """La ficha de una compra en el mes que se esta viendo: `cuota` es la
        que entra en ese resumen (o la compra entera, si es en 1 pago)."""
        comprada = c.fecha.strftime("%d/%m/%Y")
        vence = vencimiento_en_resumen(cuota.fecha_vencimiento, tarjeta_actual.dia_vencimiento if tarjeta_actual else None)
        if cuota.pagada:
            pagada_el = f" el {cuota.fecha_pago.strftime('%d/%m/%Y')}" if cuota.fecha_pago else ""
            estado_pago = components.category_chip(f"Pagada{pagada_el}", theme.INCOME_GREEN, "check_circle_rounded")
            fecha_txt = ft.Text(f"Comprado el {comprada}", size=11, color=theme.TEXT_SECONDARY)
        else:
            estado_pago = ft.FilledButton(
                f"Pagar cuota {cuota.numero_cuota}" if c.cantidad_cuotas > 1 else "Pagar",
                icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                style=ft.ButtonStyle(bgcolor=theme.TARJETAS_COLOR, color="#FFFFFF", padding=theme.pad(horizontal=12, vertical=6),
                                     shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM)),
                on_click=lambda e, cid=cuota.id, num=cuota.numero_cuota, concepto=c.concepto: confirmar_pago_compra(cid, num, concepto),
            )
            # Lo que quedo sin pagar de un mes anterior se marca como vencido.
            vencida = vence < date.today()
            fecha_txt = ft.Text(f"{'Venció' if vencida else 'Vence'} {vence.strftime('%d/%m/%Y')}", size=11,
                                color=theme.EXPENSE_RED if vencida else theme.TEXT_SECONDARY, tooltip=f"Comprado el {comprada}")

        if c.cantidad_cuotas > 1:
            forma = components.category_chip(f"Cuota {cuota.numero_cuota} de {c.cantidad_cuotas}", theme.TARJETAS_COLOR, "calendar_view_month_rounded")
            cuotas_txt = f"Cuota {c.monto_cuota.formatted()} · restan {c.cuotas_restantes}"
        else:
            forma = components.category_chip("1 pago", theme.TARJETAS_COLOR, "payments_rounded")
            cuotas_txt = ""

        return theme.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(c.concepto, size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=c.concepto),
                            ft.Text(c.monto_total.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.TARJETAS_COLOR),
                        ],
                        spacing=8,
                    ),
                    # El detalle que carga el usuario (antes solo se veia al editar).
                    *([ft.Text(c.detalle, size=12, color=theme.TEXT_SECONDARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, tooltip=c.detalle)]
                      if c.detalle else []),
                    ft.Row(
                        [forma, fecha_txt],
                        spacing=8, wrap=True,
                    ),
                    ft.Row(
                        [
                            *([ft.Text(cuotas_txt, size=11, color=theme.TEXT_SECONDARY)] if cuotas_txt else []),
                            ft.Text(f"Pendiente {c.monto_pendiente.formatted()}", size=11, weight=ft.FontWeight.W_600, color=theme.EXPENSE_RED),
                        ],
                        spacing=10, wrap=True,
                    ),
                    ft.Row(
                        [
                            estado_pago,
                            ft.Row(
                                [
                                    ft.TextButton("Editar", icon=ft.Icons.EDIT_ROUNDED,
                                                  style=ft.ButtonStyle(color=theme.TEXT_SECONDARY, padding=theme.pad(horizontal=8, vertical=4)),
                                                  tooltip="Corregir cualquier dato de la compra",
                                                  on_click=lambda e, compra=c: dialogo_editar_compra(compra)),
                                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=theme.EXPENSE_RED, icon_size=18,
                                                  tooltip="Eliminar", on_click=lambda e, cid=c.id: eliminar_compra(cid)),
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

    def confirmar_pago_compra(cuota_id: int, numero_cuota: int, concepto: str):
        def confirmar(_e):
            tarjeta_service.pagar_cuota(cuota_id)
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar pago"),
            content=ft.Text(f'¿Seguro que querés pagar la cuota {numero_cuota} de "{concepto}"?'),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Sí, pagar", confirmar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def eliminar_compra(compra_id: int):
        compra = next((c for c in tarjeta_service.listar_compras(estado["tarjeta_id"]) if c.id == compra_id), None)
        descripcion = f'"{compra.concepto}" ({compra.monto_total.formatted()})' if compra else "esta compra"

        def confirmar(_e):
            tarjeta_service.eliminar_compra(compra_id)
            page.pop_dialog()
            refrescar_tarjetas()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar compra"),
            content=ft.Text(f"¿Seguro que querés eliminar la compra {descripcion}? Se borran también todas sus cuotas, "
                            "incluidas las ya pagadas. No se puede deshacer."),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Eliminar", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        ))

    def eliminar_tarjeta(tarjeta):
        cantidad = len(tarjeta_service.listar_compras(tarjeta.id))
        hoy = date.today()
        debitos = gasto_fijo_service.debitos_del_mes(tarjeta.id, hoy.year, hoy.month)
        detalle = [f'¿Seguro que querés eliminar la tarjeta "{tarjeta.nombre}"?']
        if cantidad:
            detalle.append(f"Se borran también sus {cantidad} compra(s) con todas sus cuotas, incluidas las ya pagadas.")
        if debitos:
            detalle.append(f"Sus {len(debitos)} débito(s) automático(s) no se pierden: pasan a ser gastos fijos comunes.")
        detalle.append("No se puede deshacer.")

        def confirmar(_e):
            tarjeta_service.eliminar_tarjeta(tarjeta.id)
            if estado["tarjeta_id"] == tarjeta.id:
                estado["tarjeta_id"] = None
            page.pop_dialog()
            refrescar_tarjetas()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar tarjeta"),
            content=ft.Container(ft.Column([ft.Text(t) for t in detalle], spacing=8, tight=True), width=380),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Eliminar tarjeta", confirmar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        ))

    def dialogo_tarjeta(tarjeta=None):
        es_edicion = tarjeta is not None
        nombre_f = ft.TextField(label="Nombre (ej: Visa Galicia)", value=tarjeta.nombre if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        banco_f = ft.TextField(label="Banco", value=tarjeta.banco if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        digitos_f = ft.TextField(label="Últimos 4 dígitos (opcional)", value=tarjeta.ultimos_digitos if es_edicion else "", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, max_length=4)
        # La tarjeta opera en pesos y en dolares: la moneda se elige en cada compra.
        moneda_tarjeta = tarjeta.moneda if es_edicion else Moneda.ARS
        def _campo_dia(label, valor):
            return ft.TextField(label=label, value=str(valor) if valor else "", filled=True, bgcolor=theme.SURFACE_ALT,
                                border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER,
                                max_length=2, expand=True)
        cierre_f = _campo_dia("Día de cierre", tarjeta.dia_cierre if es_edicion else None)
        vencimiento_f = _campo_dia("Día de vencimiento", tarjeta.dia_vencimiento if es_edicion else None)
        dias_ayuda = ft.Text("Opcionales. El día de vencimiento lo usan los gastos fijos con débito automático.",
                             size=11, color=theme.TEXT_MUTED, italic=True)
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        color_elegido = {"value": tarjeta.color if es_edicion else theme.TARJETA_COLORES[0]}
        swatches_row = ft.Row(spacing=10)

        def elegir_color(color):
            color_elegido["value"] = color
            _redibujar_swatches()
            page.update()

        def _swatch(color):
            seleccionado = color == color_elegido["value"]
            return ft.Container(
                width=30, height=30, bgcolor=color, border_radius=15,
                border=theme.border_all(3, theme.TEXT_PRIMARY) if seleccionado else theme.border_all(1, theme.BORDER),
                on_click=lambda e, c=color: elegir_color(c),
                ink=True,
            )

        def _redibujar_swatches():
            swatches_row.controls = [_swatch(c) for c in theme.TARJETA_COLORES]

        _redibujar_swatches()

        def _leer_dia(campo, que):
            texto = (campo.value or "").strip()
            if not texto:
                return None
            if not texto.isdigit():
                raise ValueError(f"El día de {que} debe ser un número entre 1 y 31")
            return int(texto)

        def guardar(_e):
            try:
                if not (nombre_f.value or "").strip():
                    raise ValueError("El nombre de la tarjeta es obligatorio")
                dia_cierre = _leer_dia(cierre_f, "cierre")
                dia_vencimiento = _leer_dia(vencimiento_f, "vencimiento")
                if es_edicion:
                    tarjeta_service.editar_tarjeta(
                        tarjeta.id, nombre_f.value.strip(), banco_f.value or "", digitos_f.value or "",
                        moneda_tarjeta, color_elegido["value"], dia_cierre=dia_cierre, dia_vencimiento=dia_vencimiento,
                    )
                else:
                    t = tarjeta_service.crear_tarjeta(
                        nombre_f.value.strip(), banco_f.value or "", digitos_f.value or "",
                        moneda_tarjeta, color_elegido["value"], dia_cierre=dia_cierre, dia_vencimiento=dia_vencimiento,
                    )
                    estado["tarjeta_id"] = t.id
            except ValueError as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar tarjeta" if es_edicion else "Nueva tarjeta"),
            content=ft.Container(
                ft.Column(
                    [
                        nombre_f, banco_f, digitos_f,
                        ft.Text("Opera en pesos y en dólares: la moneda se elige en cada compra.", size=11, color=theme.TEXT_MUTED, italic=True),
                        ft.Row([cierre_f, vencimiento_f], spacing=8), dias_ayuda,
                        ft.Text("Color para identificarla", size=12, color=theme.TEXT_SECONDARY),
                        swatches_row,
                        error_text,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=360,
            ),
            actions=[
                # Eliminar se ofrece desde la edicion; primero se cierra este dialogo para mostrar la confirmacion.
                *([ft.TextButton("Eliminar tarjeta", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, style=ft.ButtonStyle(color=theme.EXPENSE_RED),
                                 on_click=lambda e: (page.pop_dialog(), eliminar_tarjeta(tarjeta)))] if es_edicion else []),
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Guardar" if es_edicion else "Crear", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    def dialogo_editar_compra(compra):
        """Edicion completa de una compra (por si se cargo mal). Antes de
        guardar muestra que cambia y pide confirmacion, porque las cuotas se
        recalculan."""
        tarjetas_disponibles = tarjeta_service.listar_tarjetas()
        fecha_holder = {"value": compra.fecha}
        fecha_text = ft.Text(compra.fecha.strftime("%d/%m/%Y"), size=14)

        def proponer_resumen(_e=None, meses=None):
            """Al cambiar la fecha o la tarjeta se vuelve a proponer el mes."""
            que = "Se paga"
            if compra.cantidad_cuotas > 1:
                que = f"La cuota {compra.cuota_inicial} se paga" if compra.cuota_inicial > 1 else "La primera cuota se paga"
            resumen_sel.proponer(int(tarjeta_dd.value), fecha_holder["value"], compra.cantidad_cuotas, que, meses)
            if _e is not None:
                page.update()

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                proponer_resumen()
                page.update()

        date_picker = ft.DatePicker(value=compra.fecha, on_change=on_fecha_change)
        page.overlay.append(date_picker)

        campo = dict(filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        tarjeta_dd = ft.Dropdown(label="Tarjeta", value=str(compra.tarjeta_id), on_select=proponer_resumen,
                                 options=[ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas_disponibles], **campo)
        resumen_sel = SelectorResumen(page, tarjeta_service, **campo)
        meses_antes = tarjeta_service.meses_al_resumen_de(compra)
        proponer_resumen(meses=meses_antes)
        concepto_f = ft.TextField(label="Concepto", value=compra.concepto, **campo)
        detalle_f = ft.TextField(label="Detalle (opcional)", value=compra.detalle, **campo)
        monto_f = ft.TextField(label="Monto total", value=components.monto_editable(compra.monto_total), keyboard_type=ft.KeyboardType.NUMBER, **campo)
        moneda_dd = ft.Dropdown(label="Moneda", value=compra.monto_total.moneda.value, options=[ft.dropdown.Option(m.value) for m in Moneda], **campo)
        en_cuotas = compra.cantidad_cuotas > 1
        tipo_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="un_pago", label=ft.Text("1 pago"), icon=ft.Icons.PAYMENTS_ROUNDED),
                ft.Segment(value="cuotas", label=ft.Text("En cuotas"), icon=ft.Icons.CALENDAR_VIEW_MONTH_ROUNDED),
            ],
            selected=["cuotas" if en_cuotas else "un_pago"], allow_multiple_selection=False, allow_empty_selection=False,
        )
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value=str(compra.cantidad_cuotas if en_cuotas else 2), keyboard_type=ft.KeyboardType.NUMBER, **campo)
        pagadas_f = ft.TextField(label="Cuotas ya pagadas", value=str(compra.cuotas_pagadas if en_cuotas else 0), keyboard_type=ft.KeyboardType.NUMBER,
                                 helper="Las cuotas ya pagadas no se modifican: se recalculan solo las que faltan.", **campo)
        cuotas_container = ft.Column([cuotas_f, pagadas_f], spacing=12, visible=en_cuotas)
        pagada_check = ft.Checkbox(label="Ya está pagada", value=not en_cuotas and compra.cuotas_pagadas > 0,
                                   active_color=theme.TARJETAS_COLOR, visible=not en_cuotas)

        def on_tipo_change(_e):
            cuotas_container.visible = "cuotas" in tipo_selector.selected
            pagada_check.visible = not cuotas_container.visible
            page.update()

        tipo_selector.on_change = on_tipo_change
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def leer():
            monto = components.parse_monto(monto_f.value, moneda_dd.value)
            if "cuotas" in tipo_selector.selected:
                cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas", minimo=2)
                pagadas = components.parse_entero(pagadas_f.value, "Cuotas ya pagadas", minimo=0, maximo=cantidad)
            else:
                cantidad, pagadas = 1, 1 if pagada_check.value else 0
            concepto = (concepto_f.value or "").strip()
            if not concepto:
                raise ValueError("El concepto no puede estar vacío")
            return dict(tarjeta_id=int(tarjeta_dd.value), fecha=fecha_holder["value"], concepto=concepto,
                        detalle=detalle_f.value or "", monto_total=monto, cantidad_cuotas=cantidad,
                        cuotas_pagadas=pagadas, meses_al_resumen=resumen_sel.meses)

        def _cambios(nuevo) -> list[str]:
            nombre = {t.id: t.nombre for t in tarjetas_disponibles}

            def cuotas_txt(n):
                return "1 pago" if n == 1 else f"{n} cuotas"

            pares = [
                ("Tarjeta", nombre.get(compra.tarjeta_id, "?"), nombre.get(nuevo["tarjeta_id"], "?")),
                ("Fecha", compra.fecha.strftime("%d/%m/%Y"), nuevo["fecha"].strftime("%d/%m/%Y")),
                ("Concepto", compra.concepto, nuevo["concepto"]),
                ("Detalle", compra.detalle or "(vacío)", nuevo["detalle"] or "(vacío)"),
                ("Monto", compra.monto_total.formatted(), nuevo["monto_total"].formatted()),
                ("Forma de pago", cuotas_txt(compra.cantidad_cuotas), cuotas_txt(nuevo["cantidad_cuotas"])),
                ("Cuotas pagadas", str(compra.cuotas_pagadas), str(nuevo["cuotas_pagadas"])),
                ("Entra en el resumen de", _mes_y_anio(add_months(compra.fecha, meses_antes)),
                 _mes_y_anio(add_months(nuevo["fecha"], nuevo["meses_al_resumen"]))),
            ]
            return [f"{que}: {antes}  →  {despues}" for que, antes, despues in pares if antes != despues]

        def guardar(_e):
            try:
                nuevo = leer()
            except (ValueError, ArithmeticError) as exc:
                error_text.value, error_text.visible = str(exc), True
                page.update()
                return
            cambios = _cambios(nuevo)
            page.pop_dialog()
            if cambios:
                confirmar_edicion(nuevo, cambios)

        def confirmar_edicion(nuevo, cambios):
            recalcula = any(not c.startswith(("Concepto", "Detalle")) for c in cambios)
            conservadas = tarjeta_service.cuotas_que_se_conservan(compra, nuevo["cuotas_pagadas"])
            moneda = nuevo["monto_total"].moneda
            ya_pagado = sum((c.monto.amount for c in conservadas), 0)
            restantes = nuevo["cantidad_cuotas"] - len(conservadas)

            def aplicar(_e):
                try:
                    tarjeta_service.editar_compra(compra.id, **nuevo)
                except (ValueError, ArithmeticError) as exc:
                    page.pop_dialog()
                    error_text.value, error_text.visible = str(exc), True
                    page.show_dialog(dialog)
                    return
                estado["tarjeta_id"] = nuevo["tarjeta_id"]
                page.pop_dialog()
                refrescar_tarjetas()

            def volver(_e):
                page.pop_dialog()
                page.show_dialog(dialog)  # vuelve al formulario con lo que habia escrito

            lineas = [ft.Text("Se van a hacer estos cambios:", size=13, weight=ft.FontWeight.W_600)]
            lineas += [ft.Text(f"•  {c}", size=13) for c in cambios]
            if recalcula:
                if conservadas:
                    lineas.append(ft.Text(
                        f"Las {len(conservadas)} cuota(s) ya pagada(s) no se modifican "
                        f"({Money.from_decimal(ya_pagado, moneda).formatted()} en total).",
                        size=12, weight=ft.FontWeight.W_600, color=theme.INCOME_GREEN,
                    ))
                if restantes:
                    falta = nuevo["monto_total"].amount - ya_pagado
                    lineas.append(ft.Text(
                        f"{'Lo que falta' if conservadas else 'El monto'} ({Money.from_decimal(falta, moneda).formatted()}) se reparte en "
                        f"{restantes} cuota(s) de {Money.from_decimal(falta / restantes, moneda).formatted()} aprox.",
                        size=12, color=theme.TEXT_SECONDARY,
                    ))
            page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("¿Confirmás los cambios?"),
                content=ft.Container(ft.Column(lineas, spacing=6, tight=True, scroll=ft.ScrollMode.AUTO), width=420),
                actions=[
                    theme.secondary_button("Volver a editar", volver),
                    theme.primary_button("Sí, guardar", aplicar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED),
                ],
            ))

        dialog = ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error("Editar compra", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        tarjeta_dd,
                        ft.Row([ft.Text("Fecha:", size=13, color=theme.TEXT_SECONDARY), fecha_text,
                                ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        concepto_f, detalle_f,
                        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
                        tipo_selector, cuotas_container, pagada_check, resumen_sel.dropdown, resumen_sel.aviso,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                     theme.primary_button("Guardar", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    def nueva_compra(_e=None):
        tarjetas_disponibles = tarjeta_service.listar_tarjetas()
        if not tarjetas_disponibles:
            return
        fecha_holder = {"value": date.today()}
        fecha_text = ft.Text(fecha_holder["value"].strftime("%d/%m/%Y"), size=14)

        def on_fecha_change(e):
            if date_picker.value:
                fecha_holder["value"] = date_picker.value.date() if isinstance(date_picker.value, datetime) else date_picker.value
                fecha_text.value = fecha_holder["value"].strftime("%d/%m/%Y")
                proponer_resumen()
                page.update()

        date_picker = ft.DatePicker(value=fecha_holder["value"], on_change=on_fecha_change)
        page.overlay.append(date_picker)

        tarjeta_id_inicial = estado["tarjeta_id"] if estado["tarjeta_id"] is not None else tarjetas_disponibles[0].id
        tarjeta_dd = ft.Dropdown(
            label="Tarjeta",
            value=str(tarjeta_id_inicial),
            options=[ft.dropdown.Option(str(t.id), t.nombre) for t in tarjetas_disponibles],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        # El mes del resumen sale del dia de cierre y de vencimiento de la
        # tarjeta; se puede cambiar porque el cierre se corre de un mes a otro.
        resumen_sel = SelectorResumen(page, tarjeta_service, filled=True, bgcolor=theme.SURFACE_ALT,
                                      border_radius=theme.RADIUS_SM, border_color=theme.BORDER)

        tipo_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="un_pago", label=ft.Text("1 pago"), icon=ft.Icons.PAYMENTS_ROUNDED),
                ft.Segment(value="cuotas", label=ft.Text("En cuotas"), icon=ft.Icons.CALENDAR_VIEW_MONTH_ROUNDED),
            ],
            selected=["un_pago"],
            allow_multiple_selection=False,
            allow_empty_selection=False,
        )

        concepto_f = ft.TextField(label="Concepto", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        detalle_f = ft.TextField(label="Detalle (opcional)", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        monto_f = ft.TextField(label="Monto total", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        moneda_dd = ft.Dropdown(label="Moneda", value=Moneda.ARS.value, options=[ft.dropdown.Option(m.value) for m in Moneda],
                                filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER)
        cuotas_f = ft.TextField(label="Cantidad de cuotas", value="2", filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER)
        cuota_inicial_f = ft.TextField(
            label="¿En qué cuota empezás?", value="1", filled=True, bgcolor=theme.SURFACE_ALT,
            border_radius=theme.RADIUS_SM, border_color=theme.BORDER, keyboard_type=ft.KeyboardType.NUMBER,
            helper="Si ya veniás pagando (ej: compraste hace 3 meses), dejá la fecha de hoy y poné la cuota que te toca pagar ahora.",
        )
        # En cuotas se puede cargar el total de la compra o el valor de cada
        # cuota (el total se calcula: valor de cuota x cantidad de cuotas).
        modo_monto = ft.SegmentedButton(
            segments=[
                ft.Segment(value="total", label=ft.Text("Cargo el monto total")),
                ft.Segment(value="cuota", label=ft.Text("Cargo el valor de la cuota")),
            ],
            selected=["total"], allow_multiple_selection=False, allow_empty_selection=False,
        )
        calculo_text = ft.Text("", size=12, weight=ft.FontWeight.W_600, color=theme.TARJETAS_COLOR)
        cuotas_container = ft.Column([modo_monto, cuotas_f, cuota_inicial_f, calculo_text], spacing=12, visible=False)

        def por_cuota() -> bool:
            return "cuotas" in tipo_selector.selected and "cuota" in modo_monto.selected

        def actualizar_calculo(_e=None):
            """Muestra la cuenta: total a partir de la cuota, o cuota a partir del total."""
            monto_f.label = "Valor de cada cuota" if por_cuota() else "Monto total"
            try:
                monto = components.parse_monto(monto_f.value, moneda_dd.value)
                cantidad = components.parse_entero(cuotas_f.value, "Cuotas", minimo=2)
            except ValueError:
                calculo_text.value = ""
            else:
                if por_cuota():
                    total = monto_total_desde_cuota(monto, cantidad)
                    calculo_text.value = f"Total de la compra: {total.formatted()} ({cantidad} cuotas de {monto.formatted()})"
                else:
                    cuota = Money.from_decimal(monto.amount / cantidad, monto.moneda)
                    calculo_text.value = f"{cantidad} cuotas de {cuota.formatted()} aprox."
            if _e is not None:
                page.update()

        for control in (monto_f, cuotas_f):
            control.on_change = actualizar_calculo
        modo_monto.on_change = actualizar_calculo
        moneda_dd.on_select = actualizar_calculo

        def que_se_paga() -> str:
            if "cuotas" not in tipo_selector.selected:
                return "Se paga"
            # Cargada ya empezada, la cuota en la que se esta es la primera que se paga.
            inicial = (cuota_inicial_f.value or "").strip()
            return f"La cuota {inicial} se paga" if inicial.isdigit() and int(inicial) > 1 else "La primera cuota se paga"

        def proponer_resumen(_e=None):
            resumen_sel.proponer(int(tarjeta_dd.value), fecha_holder["value"], 2 if "cuotas" in tipo_selector.selected else 1,
                                 que_se_paga())
            if _e is not None:
                page.update()

        def on_tipo_change(_e):
            cuotas_container.visible = "cuotas" in tipo_selector.selected
            proponer_resumen()
            actualizar_calculo()
            page.update()

        def on_cuota_inicial_change(_e):
            resumen_sel.describir(que_se_paga())
            page.update()

        tipo_selector.on_change = on_tipo_change
        tarjeta_dd.on_select = proponer_resumen
        cuota_inicial_f.on_change = on_cuota_inicial_change
        proponer_resumen()

        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e):
            try:
                if categoria_tarjeta_id is None:
                    raise ValueError("Falta la categoría base 'Tarjeta de crédito'")
                tarjeta_id = int(tarjeta_dd.value)
                es_en_cuotas = "cuotas" in tipo_selector.selected
                cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas", minimo=2) if es_en_cuotas else 1
                cuota_inicial = components.parse_entero(cuota_inicial_f.value, "¿En qué cuota empezás?", maximo=cantidad) if es_en_cuotas else 1
                if por_cuota():
                    monto = monto_total_desde_cuota(components.parse_monto(monto_f.value, moneda_dd.value, "Valor de cada cuota"), cantidad)
                else:
                    monto = components.parse_monto(monto_f.value, moneda_dd.value, "Monto total")
                tarjeta_service.registrar_compra(
                    tarjeta_id, fecha_holder["value"], concepto_f.value or "", detalle_f.value or "",
                    monto, categoria_tarjeta_id, cantidad, cuota_inicial, meses_al_resumen=resumen_sel.meses,
                )
                estado["tarjeta_id"] = tarjeta_id
                # Se pasa al mes en el que entra la compra, para verla recien cargada.
                estado["anio"], estado["mes"] = resumen_sel.mes.year, resumen_sel.mes.month
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            refrescar_tarjetas()

        dialog = ft.AlertDialog(
            modal=True,
            title=components.titulo_con_error("Nueva compra", error_text),
            content=ft.Container(
                ft.Column(
                    [
                        tarjeta_dd,
                        ft.Row([ft.Text("Fecha:", size=13, color=theme.TEXT_SECONDARY), fecha_text, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(date_picker, "open", True), page.update()))]),
                        concepto_f, detalle_f,
                        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
                        tipo_selector,
                        cuotas_container,
                        resumen_sel.dropdown,
                        resumen_sel.aviso,
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
            ),
            actions=[theme.secondary_button("Cancelar", lambda e: page.pop_dialog()), theme.primary_button("Registrar compra", guardar, color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED)],
        )
        page.show_dialog(dialog)

    header = ft.Row(
        [
            ft.Row([ft.Text("Tarjetas", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY), navegacion_mes], spacing=16),
            ft.Row([theme.secondary_button("Nueva tarjeta", lambda e: dialogo_tarjeta(None), icon=ft.Icons.ADD_CARD_ROUNDED), theme.primary_button("Nueva compra", nueva_compra, color=theme.TARJETAS_COLOR, icon=ft.Icons.ADD_SHOPPING_CART_ROUNDED)]),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    refrescar_tarjetas()

    return ft.Column(
        [header, ft.Container(height=10), tarjetas_row, ft.Container(height=6), ft.Divider(color=theme.BORDER), ft.Container(height=4), detalle_col],
        expand=True, spacing=0,
    )
