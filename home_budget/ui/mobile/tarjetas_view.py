"""Tarjetas en el celular: se elige el mes y cada tarjeta muestra, debajo de
su ficha, lo que entra en ese resumen. Lo ya pagado queda plegado.

Se toca la ficha para editar la tarjeta y una compra para abrirla (pagarla,
corregirla o eliminarla); el boton flotante carga una tarjeta nueva."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.dates import add_months
from ...app.domain.money import Money, Moneda
from .. import theme
from ..desktop import components
from . import componentes as mc
from .tarjetas_forms import formulario_compra, formulario_tarjeta, pantalla_compra, pantalla_pagar_mes

# El mes que tiene que mostrar la seccion al volver de una pantalla de carga
# (el que se estaba viendo, o el del resumen en el que entro la compra nueva).
_al_volver: dict = {}


def _totales(montos) -> str:
    """Suma por moneda sin mezclarlas ("$ 1.000,00 + $us 50,00")."""
    return " + ".join(m.formatted() for m in mc.totales_por_moneda(montos)) or Money.zero(Moneda.ARS).formatted()


def build_tarjetas_view(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    hoy = date.today()
    anio_inicial, mes_inicial = _al_volver.pop("mes", (hoy.year, hoy.month))
    # pagadas: tarjetas con lo pagado desplegado. busqueda y orden: sobre las compras de cada resumen.
    estado = {"anio": anio_inicial, "mes": mes_inicial, "pagadas": set(), "busqueda": "", "orden": "vencimiento"}
    cuerpo = ft.Column(spacing=12)

    def es_mes_actual() -> bool:
        return (estado["anio"], estado["mes"]) == (hoy.year, hoy.month)

    def ver_mes(anio: int, mes: int):
        _al_volver["mes"] = (anio, mes)

    def abrir(titulo: str, constructor):
        """Abre una pantalla de carga; al volver se sigue en el mes que se estaba viendo."""
        ver_mes(estado["anio"], estado["mes"])
        nav.abrir(titulo, constructor, theme.TARJETAS_COLOR)

    def nueva_tarjeta(_e=None):
        abrir("Nueva tarjeta", lambda: formulario_tarjeta(page, nav, servicios))

    def mover_mes(delta: int):
        nuevo = add_months(date(estado["anio"], estado["mes"], 1), delta)
        estado["anio"], estado["mes"] = nuevo.year, nuevo.month
        refrescar()
        page.update()

    def alternar_pagadas(tarjeta_id: int):
        estado["pagadas"] ^= {tarjeta_id}
        refrescar()
        page.update()

    def al_buscar(busqueda: str, orden: str):
        estado["busqueda"], estado["orden"] = busqueda, orden
        refrescar()
        page.update()

    def elegidas(pares: list) -> list:
        """Las (compra, cuota) que coinciden con lo buscado, en el orden elegido."""
        return mc.filtrar_y_ordenar(pares, estado["busqueda"], estado["orden"],
                                    lambda par: f"{par[0].concepto} {par[0].detalle}", lambda par: par[1].monto)

    def refrescar():
        tarjetas = servicios.tarjetas.listar_tarjetas()
        cuerpo.controls = [mc.selector_mes(estado["anio"], estado["mes"], mover_mes, theme.TARJETAS_COLOR)]
        if not es_mes_actual():
            cuerpo.controls.append(ft.Row(
                [ft.TextButton("Volver al mes actual", on_click=lambda e: mover_mes(
                    (hoy.year - estado["anio"]) * 12 + hoy.month - estado["mes"]), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))],
                alignment=ft.MainAxisAlignment.CENTER,
            ))
        if not tarjetas:
            cuerpo.controls.append(components.empty_state("Todavía no cargaste tarjetas.", "credit_card_rounded"))
            cuerpo.controls.append(mc.boton_ancho("Cargar una tarjeta", nueva_tarjeta, theme.TARJETAS_COLOR, ft.Icons.ADD_CARD_ROUNDED))
        for t in tarjetas:
            cuerpo.controls.append(_bloque_tarjeta(t))

    def _bloque_tarjeta(t) -> ft.Control:
        anio, mes = estado["anio"], estado["mes"]
        resumen = servicios.tarjetas.resumen_del_mes(t.id, anio, mes)
        debitos = servicios.gastos_fijos.debitos_del_mes(t.id, anio, mes)
        debitos_pendientes = [o for o in debitos if not o.ya_registrado]
        debitos_pagados = [o for o in debitos if o.ya_registrado]
        del_mes = [cu.monto for _co, cu in resumen.pendientes] + [o.gasto.monto for o in debitos_pendientes]
        deuda = [servicios.tarjetas.total_pendiente(t.id, m) for m in Moneda]
        nombre_mes = mc.MESES[mes - 1]

        if del_mes:
            linea_mes = f"{'Este mes' if es_mes_actual() else nombre_mes.capitalize()}: {_totales(del_mes)}"
        elif resumen.pagos or resumen.pagadas or debitos_pagados:
            linea_mes = "Mes saldado" if es_mes_actual() else f"{nombre_mes.capitalize()} saldado"
        else:
            linea_mes = f"Sin consumos {'este mes' if es_mes_actual() else 'en ' + nombre_mes}"

        blanco_suave = ft.Colors.with_opacity(0.85, "#FFFFFF")
        ficha = ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color="#FFFFFF", size=20),
                            ft.Text(t.nombre, color="#FFFFFF", weight=ft.FontWeight.BOLD, size=16, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Icon(ft.Icons.EDIT_ROUNDED, color=blanco_suave, size=16),
                        ],
                        spacing=8,
                    ),
                    ft.Text(" · ".join(p for p in [
                                f"{t.banco} ••{t.ultimos_digitos}" if t.ultimos_digitos else t.banco,
                                f"cierra {t.dia_cierre}" if t.dia_cierre else "",
                                f"vence {t.dia_vencimiento}" if t.dia_vencimiento else ""] if p),
                            color=blanco_suave, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(height=6),
                    ft.Text(linea_mes, color="#FFFFFF", size=18, weight=ft.FontWeight.BOLD),
                    *([ft.Text(f"Deuda total: {_totales(deuda)}", color=blanco_suave, size=12)] if any(d.cents for d in deuda) else []),
                ],
                spacing=2,
            ),
            padding=16, border_radius=theme.RADIUS, tooltip="Editar tarjeta",
            on_click=lambda e: abrir("Editar tarjeta", lambda: formulario_tarjeta(page, nav, servicios, t)),
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=[t.color, theme.darken(t.color)]),
        )

        filas = [_fila_cuota(compra, cuota) for compra, cuota in elegidas(resumen.pendientes)]
        filas += [_fila_debito(mc.fila_dato("event_repeat_rounded", theme.MOVIMIENTOS_COLOR, o.gasto.concepto, "Débito automático",
                                            o.gasto.monto.formatted(), theme.TEXT_PRIMARY))
                  for o in mc.filtrar_y_ordenar(debitos_pendientes, estado["busqueda"], estado["orden"],
                                                lambda o: o.gasto.concepto, lambda o: o.gasto.monto)]
        hay_pendientes = bool(resumen.pendientes or debitos_pendientes)

        cantidad_pagadas = len(resumen.pagadas) + len(debitos_pagados)
        pie = []
        if cantidad_pagadas:
            abierto = t.id in estado["pagadas"]
            pie.append(ft.TextButton(
                f"{'Ocultar' if abierto else 'Ver'} pagadas ({cantidad_pagadas})",
                icon=ft.Icons.EXPAND_LESS_ROUNDED if abierto else ft.Icons.EXPAND_MORE_ROUNDED,
                on_click=lambda e, tid=t.id: alternar_pagadas(tid), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
            ))
            if abierto:
                pie += [_fila_cuota(compra, cuota) for compra, cuota in elegidas(resumen.pagadas)]
                pie += [_fila_debito(mc.fila_dato("check_circle_rounded", theme.INCOME_GREEN, o.gasto.concepto, "Débito automático · pagado",
                                                  o.gasto.monto.formatted(), theme.TEXT_SECONDARY)) for o in debitos_pagados]

        botones = [theme.secondary_button(
            "Nueva compra", lambda e: abrir("Nueva compra", lambda: formulario_compra(page, nav, servicios, t.id, ver_mes)),
            color=theme.TARJETAS_COLOR, icon=ft.Icons.ADD_ROUNDED)]
        if del_mes:
            botones.append(theme.primary_button(
                "Pagar tarjeta", lambda e: abrir("Pagar tarjeta", lambda: pantalla_pagar_mes(page, nav, servicios, t, anio, mes)),
                color=theme.TARJETAS_COLOR, icon=ft.Icons.CHECK_ROUNDED))
        for boton in botones:
            boton.expand = True
        acciones = ft.Container(ft.Row(botones, spacing=8), padding=theme.pad_only(top=6))

        return ft.Column(
            [
                ficha,
                theme.card(
                    ft.Column(
                        [
                            *(filas or [_fila_debito(ft.Text("Ninguna compra pendiente coincide con la búsqueda." if hay_pendientes
                                                             else "Nada pendiente en este resumen.", size=13, color=theme.TEXT_MUTED))]),
                            *pie,
                            mc.separador(),
                            acciones,
                        ],
                        spacing=2,
                    ),
                    padding=8,
                ),
            ],
            spacing=8,
        )

    def _fila_debito(fila: ft.Control) -> ft.Control:
        """Lo que no se abre (los debitos se manejan en Gastos fijos), alineado con las compras."""
        return ft.Container(fila, padding=8)

    def _fila_cuota(compra, cuota) -> ft.Control:
        """Una compra en el resumen: se toca para pagarla, corregirla o eliminarla."""
        return mc.fila_tocable(_datos_cuota(compra, cuota),
                               lambda e: abrir("Compra", lambda: pantalla_compra(page, nav, servicios, compra, cuota)))

    def _datos_cuota(compra, cuota) -> ft.Control:
        forma = f"Cuota {cuota.numero_cuota} de {compra.cantidad_cuotas}" if compra.cantidad_cuotas > 1 else "1 pago"
        if cuota.pagada:
            cuando = f"pagada el {cuota.fecha_pago.strftime('%d/%m')}" if cuota.fecha_pago else "pagada"
            return mc.fila_dato("check_circle_rounded", theme.INCOME_GREEN, compra.concepto, f"{forma} · {cuando}",
                                cuota.monto.formatted(), theme.TEXT_SECONDARY)
        # Lo que quedo sin pagar de un mes anterior se marca como vencido.
        vencida = cuota.fecha_vencimiento < date(hoy.year, hoy.month, 1)
        return mc.fila_dato("error_outline_rounded" if vencida else "shopping_bag_rounded",
                            theme.EXPENSE_RED if vencida else theme.TARJETAS_COLOR, compra.concepto,
                            f"{forma} · venció en {mc.MESES[cuota.fecha_vencimiento.month - 1]}" if vencida else forma,
                            cuota.monto.formatted(), theme.TEXT_PRIMARY)

    refrescar()
    return ft.Stack(
        [
            mc.pantalla([
                mc.barra_busqueda([("vencimiento", "Por vencimiento"), *mc.ORDENES_COMUNES], al_buscar, theme.TARJETAS_COLOR),
                cuerpo,
            ]),
            mc.boton_flotante(ft.Icons.ADD_CARD_ROUNDED, theme.TARJETAS_COLOR, nueva_tarjeta, "Nueva tarjeta"),
        ],
        expand=True,
    )
