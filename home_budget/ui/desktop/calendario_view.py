from __future__ import annotations

import calendar as calendar_mod
from dataclasses import dataclass
from datetime import date

import flet as ft

from ...app.domain.money import Money
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.prestamos import PrestamoService
from ...app.services.tarjetas import TarjetaService
from ...app.services.vencimientos import VencimientoService
from .. import theme

_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
_DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_GASTO_FIJO_COLOR = theme.MOVIMIENTOS_COLOR


@dataclass
class _Evento:
    origen: str  # "tarjeta" | "prestamo" | "fijo"
    titulo: str
    color: str
    monto: Money
    referencia_id: int  # cuota_id (tarjeta/prestamo) o gasto_fijo_id (fijo)
    etiqueta: str  # texto secundario ("cuota N" o "gasto fijo")


def build_calendario_view(page: ft.Page, tarjeta_service: TarjetaService, prestamo_service: PrestamoService, gasto_fijo_service: GastoFijoService) -> ft.Control:
    hoy = date.today()
    estado = {"anio": hoy.year, "mes": hoy.month}
    root = ft.Column(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
    vencimiento_service = VencimientoService(tarjeta_service, prestamo_service, gasto_fijo_service)

    def eventos_del_mes(anio: int, mes: int) -> dict[int, list[_Evento]]:
        colores = {"prestamo": theme.PRESTAMOS_COLOR, "fijo": _GASTO_FIJO_COLOR}
        por_dia: dict[int, list[_Evento]] = {}
        for v in vencimiento_service.pendientes_del_mes(anio, mes):
            por_dia.setdefault(v.fecha.day, []).append(
                _Evento(v.origen, v.titulo, v.color or colores[v.origen], v.monto, v.referencia_id, v.etiqueta)
            )
        return por_dia

    def cambiar_mes(delta: int):
        indice = estado["mes"] - 1 + delta
        estado["anio"] += indice // 12
        estado["mes"] = indice % 12 + 1
        refrescar()

    def refrescar():
        root.controls = _construir(estado["anio"], estado["mes"])
        page.update()

    def abrir_dia(dia: int, eventos: list[_Evento]):
        def confirmar_pagar(evento: _Evento):
            def pedir_confirmacion(_e):
                verbo = "registrar el pago de" if evento.origen == "fijo" else "pagar"
                def confirmar(_e2):
                    if evento.origen == "tarjeta":
                        tarjeta_service.pagar_cuota(evento.referencia_id)
                    elif evento.origen == "prestamo":
                        prestamo_service.pagar_cuota(evento.referencia_id)
                    else:
                        gasto_fijo_service.generar_movimiento_del_mes(evento.referencia_id, date(estado["anio"], estado["mes"], dia))
                    page.pop_dialog()  # cierra la confirmacion
                    page.pop_dialog()  # cierra la lista de vencimientos del dia (datos ahora desactualizados)
                    refrescar()

                confirm_dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Confirmar pago"),
                    content=ft.Text(f'¿Seguro que querés {verbo} "{evento.titulo}" ({evento.monto.formatted()})?'),
                    actions=[
                        theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                        theme.primary_button("Sí, confirmar", confirmar, color=evento.color, icon=ft.Icons.CHECK_ROUNDED),
                    ],
                )
                page.show_dialog(confirm_dialog)
            return pedir_confirmacion

        filas = [
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=ev.color, border_radius=5),
                    ft.Text(f"{ev.titulo} ({ev.etiqueta})", size=13, color=theme.TEXT_PRIMARY, expand=True),
                    ft.Text(ev.monto.formatted(), size=13, weight=ft.FontWeight.BOLD, color=ev.color),
                    theme.secondary_button("Registrar pago" if ev.origen == "fijo" else "Pagar", confirmar_pagar(ev)),
                ],
                spacing=8,
            )
            for ev in eventos
        ]

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Vencimientos del {dia:02d}/{estado['mes']:02d}/{estado['anio']}"),
            content=ft.Container(ft.Column(filas, spacing=10, tight=True, scroll=ft.ScrollMode.AUTO), width=440),
            actions=[theme.secondary_button("Cerrar", lambda e: page.pop_dialog())],
        )
        page.show_dialog(dialog)

    def _celda_dia(dia: int, eventos: list[_Evento]) -> ft.Container:
        if dia == 0:
            return ft.Container(height=92, expand=True)

        es_hoy = date(estado["anio"], estado["mes"], dia) == hoy
        chips = [ft.Container(width=8, height=8, bgcolor=ev.color, border_radius=4) for ev in eventos[:4]]
        extra = len(eventos) - 4
        contenido = ft.Column(
            [
                ft.Text(str(dia), size=13, weight=ft.FontWeight.BOLD if es_hoy else ft.FontWeight.NORMAL, color=theme.CALENDARIO_COLOR if es_hoy else theme.TEXT_PRIMARY),
                ft.Row(chips, spacing=3, wrap=True),
                ft.Text(f"+{extra} más", size=9, color=theme.TEXT_MUTED) if extra > 0 else ft.Container(),
            ],
            spacing=4,
        )
        return ft.Container(
            content=contenido,
            height=92, expand=True,
            padding=8,
            bgcolor=theme.CALENDARIO_BG if es_hoy else theme.SURFACE,
            border=theme.border_all(1, theme.BORDER),
            border_radius=theme.RADIUS_SM,
            on_click=(lambda e, d=dia, evs=eventos: abrir_dia(d, evs)) if eventos else None,
            ink=bool(eventos),
        )

    def _construir(anio: int, mes: int) -> list[ft.Control]:
        eventos_por_dia = eventos_del_mes(anio, mes)
        semanas = calendar_mod.Calendar(firstweekday=0).monthdayscalendar(anio, mes)

        header = ft.Row(
            [
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, on_click=lambda e: cambiar_mes(-1)),
                ft.Text(f"{_MESES[mes - 1]} {anio}", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True, text_align=ft.TextAlign.CENTER),
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, on_click=lambda e: cambiar_mes(1)),
            ],
        )
        encabezado_dias = ft.Row(
            [ft.Container(ft.Text(d, size=11, color=theme.TEXT_MUTED, weight=ft.FontWeight.W_600), expand=True, alignment=ft.Alignment.CENTER) for d in _DIAS_SEMANA],
            spacing=4,
        )
        filas_semana = [
            ft.Row([_celda_dia(dia, eventos_por_dia.get(dia, [])) for dia in semana], spacing=4)
            for semana in semanas
        ]

        totales: dict = {}
        for eventos in eventos_por_dia.values():
            for ev in eventos:
                totales[ev.monto.moneda] = totales.get(ev.monto.moneda, Money.zero(ev.monto.moneda)) + ev.monto

        if totales:
            resumen_control = ft.Row(
                [ft.Text(f"Total del mes ({moneda.value}): {total.formatted()}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY) for moneda, total in totales.items()],
                spacing=20,
            )
        else:
            resumen_control = ft.Text("Sin vencimientos este mes.", size=13, color=theme.TEXT_MUTED)

        return [
            ft.Text("Calendario de cuotas", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ft.Container(height=4),
            header,
            ft.Container(
                content=ft.Column([encabezado_dias, *filas_semana], spacing=4),
                padding=12, bgcolor=theme.SURFACE, border_radius=theme.RADIUS, border=theme.border_all(1, theme.BORDER),
            ),
            ft.Container(height=4),
            resumen_control,
        ]

    root.controls = _construir(estado["anio"], estado["mes"])
    return root
