"""Seccion Inversiones: Resumen, Ahorro, Acciones, Bonos/Lecap, FCI y Crypto.
Todo se ve por moneda (selector ARS / USD); los totales nunca mezclan monedas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.inversiones import (
    EstadoInversion, InversionService, OperacionCrypto, TipoTitulo, Totales,
    tenencias_crypto, tenencias_por_simbolo, totales_crypto, totales_de,
)
from .. import theme
from . import components
from .inversiones_forms import (
    MESES_CORTOS, PLAZOS, confirmar_eliminar, fmt_decimal, form_ahorro, form_crypto, form_fci, form_salida, form_titulo,
)

# Apartado, moneda y mes del calendario elegidos: se recuerdan al volver a la seccion.
_estado = {"apartado": "resumen", "moneda": Moneda.ARS, "cal_anio": date.today().year, "cal_mes": date.today().month}

_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _apartados():
    # Funcion (no constante) para tomar la paleta activa, clara u oscura.
    return [
        ("resumen", "Resumen", "donut_large_rounded", theme.INVERSIONES_COLOR),
        ("calendario", "Calendario", "calendar_month_rounded", theme.CAMBIO_COLOR),
        ("ahorro", "Ahorro", "savings_rounded", theme.PRESTAMOS_COLOR),
        ("acciones", "Acciones", "show_chart_rounded", theme.CALENDARIO_COLOR),
        ("bonos", "Bonos / Lecap", "receipt_long_rounded", theme.HISTORIAL_COLOR),
        ("fci", "FCI", "account_balance_rounded", theme.DASHBOARD_COLOR),
        ("crypto", "Crypto", "currency_bitcoin_rounded", theme.MOVIMIENTOS_COLOR),
    ]


@dataclass
class _Porcion:
    nombre: str
    color: str
    total: Money
    porcentaje: float


def _fmt(m: Money) -> str:
    return f"{m.formatted()} {m.moneda.value}"


def _fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


# --- piezas visuales ---

def _tile(titulo: str, valor: str, color: str, icono: str, ayuda: str) -> ft.Control:
    return ft.Container(
        theme.card(
            ft.Column(
                [
                    ft.Row([ft.Icon(theme.to_icon(icono), size=16, color=color), ft.Text(titulo, size=12, color=theme.TEXT_SECONDARY)], spacing=6),
                    ft.Text(valor, size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Text(ayuda, size=11, color=theme.TEXT_MUTED),
                ],
                spacing=4,
            ),
            padding=16,
        ),
        col={"xs": 12, "md": 6, "lg": 3},
    )


def _tiles_totales(t: Totales, color: str) -> ft.Control:
    signo = "+" if t.resultado.cents >= 0 else ""
    return ft.ResponsiveRow(
        [
            _tile("Total vigente", _fmt(t.vigente), color, "account_balance_wallet_rounded", f"{t.cantidad_vigentes} vigente(s) hoy"),
            _tile("Total invertido", _fmt(t.invertido), color, "trending_up_rounded", "Todo lo invertido, vigente o no"),
            _tile("Recibido", _fmt(t.recibido), color, "payments_rounded", "Cobrado al finalizar o vender"),
            _tile(
                "Resultado", f"{signo}{_fmt(t.resultado)}",
                theme.INCOME_GREEN if t.resultado.cents >= 0 else theme.EXPENSE_RED,
                "insights_rounded", "Ganancia o pérdida de lo finalizado",
            ),
        ],
        spacing=12, run_spacing=12,
    )


def _chip_estado(vigente: bool, texto_vigente: str, texto_finalizada: str) -> ft.Control:
    color = theme.INCOME_GREEN if vigente else theme.TEXT_MUTED
    return ft.Container(
        ft.Text(texto_vigente if vigente else texto_finalizada, size=11, weight=ft.FontWeight.W_600, color=color),
        bgcolor=theme.INCOME_GREEN_BG if vigente else theme.SURFACE_ALT,
        padding=theme.pad(horizontal=8, vertical=3), border_radius=theme.RADIUS_LG,
    )


def _dato(etiqueta: str, valor: str) -> ft.Control:
    return ft.Column(
        [ft.Text(etiqueta, size=11, color=theme.TEXT_MUTED), ft.Text(valor or "—", size=13, color=theme.TEXT_PRIMARY, selectable=True)],
        spacing=0, col=6,
    )


def _tarjeta(
    titulo: str, subtitulo: str, monto: str, chip: ft.Control | None, datos: list[tuple[str, str]],
    acciones: list[ft.Control], color: str, apagada: bool = False,
) -> ft.Control:
    return ft.Container(
        ft.Container(
            theme.card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(width=4, height=36, bgcolor=color, border_radius=2),
                                ft.Column(
                                    [
                                        ft.Text(titulo, size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(subtitulo, size=12, color=theme.TEXT_SECONDARY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                    spacing=0, expand=True,
                                ),
                                *([chip] if chip else []),
                            ],
                            spacing=10,
                        ),
                        ft.Text(monto, size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                        ft.ResponsiveRow([_dato(e, v) for e, v in datos], spacing=8, run_spacing=8),
                        ft.Row(acciones, spacing=4, alignment=ft.MainAxisAlignment.END, wrap=True),
                    ],
                    spacing=12,
                ),
                padding=18,
            ),
            opacity=0.75 if apagada else 1.0,
        ),
        col={"xs": 12, "lg": 6},
    )


def _boton(texto: str, icono, on_click, color: str | None = None) -> ft.Control:
    return ft.TextButton(texto, icon=icono, on_click=lambda e: on_click(), style=ft.ButtonStyle(color=color or theme.TEXT_SECONDARY))


def _grilla(tarjetas: list[ft.Control], vacio: str) -> ft.Control:
    if not tarjetas:
        return components.empty_state(vacio, "inbox_rounded")
    return ft.ResponsiveRow(tarjetas, spacing=12, run_spacing=12)


def _encabezado_apartado(titulo: str, texto_boton: str, on_nuevo: Callable[[], None], color: str) -> ft.Control:
    return ft.Row(
        [
            ft.Text(titulo, size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
            theme.primary_button(texto_boton, lambda e: on_nuevo(), color=color, icon=ft.Icons.ADD_ROUNDED),
        ],
    )


def _titulo_bloque(texto: str) -> ft.Text:
    return ft.Text(texto, size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY)


# --- vista ---

def build_inversiones_view(page: ft.Page, service: InversionService) -> ft.Control:
    root = ft.Column(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)

    def refrescar():
        root.controls = construir()
        page.update()

    def elegir_apartado(clave: str):
        _estado["apartado"] = clave
        refrescar()

    def elegir_moneda(e):
        _estado["moneda"] = Moneda(next(iter(e.control.selected)))
        refrescar()

    def construir() -> list[ft.Control]:
        moneda = _estado["moneda"]
        selector_moneda = ft.SegmentedButton(
            segments=[ft.Segment(value=m.value, label=ft.Text(m.value)) for m in Moneda],
            selected=[moneda.value], allow_multiple_selection=False, allow_empty_selection=False,
            show_selected_icon=False, on_change=elegir_moneda,
        )
        pestanas = ft.Row(
            [_pestana(clave, texto, icono, color, clave == _estado["apartado"], elegir_apartado) for clave, texto, icono, color in _apartados()],
            spacing=8, wrap=True,
        )
        cuerpo = {
            "resumen": _resumen, "calendario": _calendario, "ahorro": _ahorro, "acciones": _acciones, "bonos": _bonos, "fci": _fci, "crypto": _crypto,
        }[_estado["apartado"]](page, service, moneda, refrescar)
        return [
            ft.Row(
                [
                    ft.Text("Inversiones", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, expand=True),
                    # El calendario muestra ambas monedas: que no se pierda un dividendo por tener el filtro en la otra.
                    *([selector_moneda] if _estado["apartado"] != "calendario" else []),
                ],
            ),
            pestanas,
            *cuerpo,
        ]

    root.controls = construir()
    return root


def _pestana(clave, texto, icono, color, activa, on_click) -> ft.Control:
    return ft.Container(
        ft.Row(
            [
                ft.Icon(theme.to_icon(icono), size=16, color="#FFFFFF" if activa else color),
                ft.Text(texto, size=13, weight=ft.FontWeight.W_600, color="#FFFFFF" if activa else theme.TEXT_SECONDARY),
            ],
            spacing=6, tight=True,
        ),
        bgcolor=color if activa else theme.SURFACE,
        border=None if activa else theme.border_all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        padding=theme.pad(horizontal=14, vertical=8),
        on_click=lambda e: on_click(clave),
        ink=True,
    )


# --- Resumen ---

def _resumen(page, service: InversionService, moneda: Moneda, refrescar) -> list[ft.Control]:
    totales = service.totales_por_apartado(moneda)
    colores = {clave: color for clave, _, _, color in _apartados()}
    colores.pop("calendario")
    nombres = {clave: texto for clave, texto, _, _ in _apartados()}

    general = Totales.vacio(moneda)
    for t in totales.values():
        general.invertido = general.invertido + t.invertido
        general.vigente = general.vigente + t.vigente
        general.recibido = general.recibido + t.recibido
        general.resultado = general.resultado + t.resultado
        general.cantidad_vigentes += t.cantidad_vigentes

    suma = general.vigente.cents
    porciones = [
        _Porcion(nombres[clave], colores[clave], t.vigente, t.vigente.cents * 100 / suma)
        for clave, t in sorted(totales.items(), key=lambda kv: kv[1].vigente.cents, reverse=True)
        if t.vigente.cents > 0
    ] if suma > 0 else []

    torta_card = theme.card(
        ft.Column(
            [
                _titulo_bloque(f"Distribución de lo vigente ({moneda.value})"),
                ft.Divider(height=1, color=theme.BORDER),
                ft.Row([components.torta(porciones), components.leyenda_torta(porciones)], spacing=24,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER)
                if porciones else components.empty_state(f"Todavía no tenés inversiones vigentes en {moneda.value}.", "donut_large_rounded"),
            ],
            spacing=10,
        )
    )

    filas = []
    for clave, t in totales.items():
        filas.append(ft.Container(
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=colores[clave], border_radius=5),
                    ft.Text(nombres[clave], size=13, color=theme.TEXT_PRIMARY, expand=True),
                    ft.Text(f"Vigente {t.vigente.formatted()}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY, width=190, text_align=ft.TextAlign.RIGHT),
                    ft.Text(f"Invertido {t.invertido.formatted()}", size=12, color=theme.TEXT_SECONDARY, width=190, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=10,
            ),
            on_click=lambda e, c=clave: (_estado.__setitem__("apartado", c), refrescar()),
            padding=theme.pad(vertical=6), ink=True, border_radius=theme.RADIUS_SM,
            tooltip="Ver apartado",
        ))
    detalle_card = theme.card(ft.Column([_titulo_bloque("Por apartado"), ft.Divider(height=1, color=theme.BORDER), *filas], spacing=4))

    return [_tiles_totales(general, theme.INVERSIONES_COLOR), torta_card, detalle_card]


# --- Ahorro ---

def _ahorro(page, service: InversionService, moneda: Moneda, refrescar) -> list[ft.Control]:
    color = theme.PRESTAMOS_COLOR
    ahorros = [a for a in service.listar_ahorros() if a.monto.moneda == moneda]
    ahorros.sort(key=lambda a: a.estado != EstadoInversion.VIGENTE)

    tarjetas = []
    for a in ahorros:
        vigente = a.estado == EstadoInversion.VIGENTE
        datos = [("Fecha", _fecha(a.fecha)), ("Descontado de la app", "Sí" if a.entrada_mov_id else "No")]
        if not vigente:
            datos += [("Retirado el", _fecha(a.fecha_salida)), ("Monto retirado", _fmt(a.monto_salida) if a.monto_salida else "—")]
        datos.append(("Observaciones", a.observaciones))
        acciones = []
        if vigente:
            acciones.append(_boton("Retirar", ft.Icons.LOGOUT_ROUNDED, lambda a=a: form_salida(
                page, "Retirar ahorro", "Monto retirado", a.monto.moneda, a.monto,
                lambda f, m, acr, a=a: (service.retirar_ahorro(a.id, f, m, acr), refrescar()),
            ), color))
        acciones += [
            _boton("Editar", ft.Icons.EDIT_OUTLINED, lambda a=a: form_ahorro(page, service, moneda, refrescar, a)),
            _boton("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED, lambda a=a: confirmar_eliminar(
                page, "este ahorro", lambda a=a: (service.eliminar_ahorro(a.id), refrescar())), theme.EXPENSE_RED),
        ]
        tarjetas.append(_tarjeta(a.ubicacion or "Ahorro", "Ahorro", _fmt(a.monto), _chip_estado(vigente, "Vigente", "Retirado"),
                                 datos, acciones, color, apagada=not vigente))

    return [
        _encabezado_apartado(f"Ahorro en {moneda.value}", "Nuevo ahorro", lambda: form_ahorro(page, service, moneda, refrescar), color),
        _tiles_totales(totales_de(ahorros, moneda), color),
        _grilla(tarjetas, f"No cargaste ahorros en {moneda.value}."),
    ]


# --- Acciones y Bonos/Lecap ---

def _meses(meses: list[int]) -> str:
    return ", ".join(MESES_CORTOS[m - 1] for m in meses) if meses else "—"


def _titulos(page, service: InversionService, moneda: Moneda, refrescar, tipo: TipoTitulo, color: str) -> list[ft.Control]:
    es_accion = tipo == TipoTitulo.ACCION
    titulos = [t for t in service.listar_titulos(tipo) if t.precio_compra.moneda == moneda]
    titulos.sort(key=lambda t: t.estado != EstadoInversion.VIGENTE)
    nombre_plural = "acciones" if es_accion else "bonos / Lecap"

    tenencias = tenencias_por_simbolo(titulos, moneda)
    filas_tenencia = [
        ft.Row(
            [
                ft.Text(ten.simbolo, size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, width=80),
                ft.Text(ten.nombre, size=13, color=theme.TEXT_SECONDARY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(f"{fmt_decimal(ten.cantidad)} u.", size=13, color=theme.TEXT_PRIMARY, width=90, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"prom. {ten.precio_promedio.formatted()}", size=12, color=theme.TEXT_SECONDARY, width=140, text_align=ft.TextAlign.RIGHT),
                ft.Text(ten.costo.formatted(), size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY, width=140, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"{ten.transacciones} compra(s)", size=11, color=theme.TEXT_MUTED, width=80, text_align=ft.TextAlign.RIGHT),
            ],
            spacing=8,
        )
        for ten in tenencias
    ]
    tenencias_card = theme.card(ft.Column(
        [
            _titulo_bloque(f"Tenencias por {'acción' if es_accion else 'bono'} (en posesión)"),
            ft.Text("Suma todas las compras vigentes de cada símbolo: cantidad total, precio promedio y total pagado.", size=11, color=theme.TEXT_MUTED),
            ft.Divider(height=1, color=theme.BORDER),
            *(filas_tenencia or [ft.Text("Sin tenencias vigentes.", size=13, color=theme.TEXT_MUTED)]),
        ],
        spacing=8,
    ))

    tarjetas = []
    for t in titulos:
        vigente = t.estado == EstadoInversion.VIGENTE
        datos = [
            ("Tipo de empresa", t.tipo_empresa), ("Plazo", PLAZOS[t.plazo]),
            ("Broker", t.broker), ("Transacción", t.transaccion),
            ("Fecha de suscripción", _fecha(t.fecha_suscripcion)), ("Cantidad", fmt_decimal(t.cantidad)),
            ("Precio de compra", _fmt(t.precio_compra)), ("Dividendos" if es_accion else "Renta", _meses(t.meses_pago)),
        ]
        if not vigente and t.monto_salida is not None:
            dif = t.monto_salida - t.costo
            datos += [("Vendida el", _fecha(t.fecha_salida)), ("Cobrado", _fmt(t.monto_salida)),
                      ("Resultado", ("+" if dif.cents >= 0 else "") + _fmt(dif))]
        datos.append(("Observaciones", t.observaciones))
        acciones = []
        if vigente:
            acciones.append(_boton("Finalizar", ft.Icons.SELL_OUTLINED, lambda t=t: form_salida(
                page, f"Finalizar {t.simbolo}", "Precio de venta (por unidad)", t.precio_compra.moneda, t.costo,
                lambda f, m, acr, t=t: (service.finalizar_titulo(t.id, f, m, acr), refrescar()), cantidad=t.cantidad,
            ), color))
        acciones += [
            _boton("Editar", ft.Icons.EDIT_OUTLINED, lambda t=t: form_titulo(page, service, tipo, moneda, refrescar, t)),
            _boton("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED, lambda t=t: confirmar_eliminar(
                page, f"la compra de {t.simbolo}", lambda t=t: (service.eliminar_titulo(t.id), refrescar())), theme.EXPENSE_RED),
        ]
        tarjetas.append(_tarjeta(
            t.simbolo, t.nombre or ("Acción" if es_accion else "Bono / Lecap"), f"Total pagado: {_fmt(t.costo)}",
            _chip_estado(vigente, "En posesión", "Finalizada"), datos, acciones, color, apagada=not vigente,
        ))

    titulo = "Acciones" if es_accion else "Bonos / Lecap"
    return [
        _encabezado_apartado(f"{titulo} en {moneda.value}", "Nueva acción" if es_accion else "Nuevo bono / Lecap",
                             lambda: form_titulo(page, service, tipo, moneda, refrescar), color),
        _tiles_totales(totales_de(titulos, moneda), color),
        tenencias_card,
        _grilla(tarjetas, f"No cargaste {nombre_plural} en {moneda.value}."),
    ]


def _acciones(page, service, moneda, refrescar):
    return _titulos(page, service, moneda, refrescar, TipoTitulo.ACCION, theme.CALENDARIO_COLOR)


def _bonos(page, service, moneda, refrescar):
    return _titulos(page, service, moneda, refrescar, TipoTitulo.BONO, theme.HISTORIAL_COLOR)


# --- FCI ---

def _fci(page, service: InversionService, moneda: Moneda, refrescar) -> list[ft.Control]:
    color = theme.DASHBOARD_COLOR
    fcis = [f for f in service.listar_fcis() if f.monto.moneda == moneda]
    fcis.sort(key=lambda f: f.estado != EstadoInversion.VIGENTE)

    tarjetas = []
    for f in fcis:
        vigente = f.estado == EstadoInversion.VIGENTE
        datos = [
            ("Símbolo", f.simbolo), ("Plazo", PLAZOS[f.plazo]),
            ("Broker", f.broker), ("Transacción", f.transaccion),
            ("Fecha de suscripción", _fecha(f.fecha_suscripcion)), ("Fecha de rescate", _fecha(f.fecha_rescate)),
            ("TNA", f"{fmt_decimal(f.tna)}%" if f.tna is not None else "—"),
        ]
        if not vigente and f.monto_salida is not None:
            dif = f.monto_salida - f.monto
            datos += [("Rescatado", _fmt(f.monto_salida)), ("Resultado", ("+" if dif.cents >= 0 else "") + _fmt(dif))]
        datos.append(("Observaciones", f.observaciones))
        acciones = []
        if vigente:
            acciones.append(_boton("Rescatar", ft.Icons.LOGOUT_ROUNDED, lambda f=f: form_salida(
                page, f"Rescatar {f.nombre}", "Monto rescatado", f.monto.moneda, f.monto,
                lambda fe, m, acr, f=f: (service.rescatar_fci(f.id, fe, m, acr), refrescar()),
            ), color))
        acciones += [
            _boton("Editar", ft.Icons.EDIT_OUTLINED, lambda f=f: form_fci(page, service, moneda, refrescar, f)),
            _boton("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED, lambda f=f: confirmar_eliminar(
                page, f"el FCI {f.nombre}", lambda f=f: (service.eliminar_fci(f.id), refrescar())), theme.EXPENSE_RED),
        ]
        tarjetas.append(_tarjeta(f.nombre, f.simbolo or "Fondo común de inversión", _fmt(f.monto),
                                 _chip_estado(vigente, "Vigente", "Rescatado"), datos, acciones, color, apagada=not vigente))

    return [
        _encabezado_apartado(f"Fondos comunes de inversión en {moneda.value}", "Nuevo FCI", lambda: form_fci(page, service, moneda, refrescar), color),
        _tiles_totales(totales_de(fcis, moneda), color),
        _grilla(tarjetas, f"No cargaste FCI en {moneda.value}."),
    ]


# --- Crypto ---

def _crypto(page, service: InversionService, moneda: Moneda, refrescar) -> list[ft.Control]:
    color = theme.MOVIMIENTOS_COLOR
    operaciones = [op for op in service.listar_crypto() if op.monto.moneda == moneda]

    tenencias = tenencias_crypto(operaciones, moneda)
    filas_tenencia = [
        ft.Row(
            [
                ft.Text(ten.activo, size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, width=80),
                ft.Text(f"{fmt_decimal(ten.cantidad)} u.", size=13, color=theme.TEXT_PRIMARY, expand=True),
                ft.Text(f"Vigente {ten.vigente.formatted()}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY, width=170, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"Invertido {ten.invertido.formatted()}", size=12, color=theme.TEXT_SECONDARY, width=170, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"Vendido {ten.recibido.formatted()}", size=12, color=theme.TEXT_SECONDARY, width=160, text_align=ft.TextAlign.RIGHT),
            ],
            spacing=8,
        )
        for ten in tenencias
    ]
    tenencias_card = theme.card(ft.Column(
        [
            _titulo_bloque("Tenencias por moneda"),
            ft.Text("Cantidad = compras − ventas. El vigente se valúa al precio promedio de compra.", size=11, color=theme.TEXT_MUTED),
            ft.Divider(height=1, color=theme.BORDER),
            *(filas_tenencia or [ft.Text("Sin operaciones.", size=13, color=theme.TEXT_MUTED)]),
        ],
        spacing=8,
    ))

    tarjetas = []
    for op in operaciones:
        es_compra = op.operacion == OperacionCrypto.COMPRA
        datos = [
            ("Fecha", _fecha(op.fecha)), ("Cantidad", fmt_decimal(op.cantidad)),
            ("Precio unitario", f"{fmt_decimal(op.precio_unitario)} {op.monto.moneda.value}"),
            ("Con plata de la app", "Sí" if op.mov_id else "No"),
            ("Observaciones", op.observaciones),
        ]
        chip = ft.Container(
            ft.Text("Compra" if es_compra else "Venta", size=11, weight=ft.FontWeight.W_600,
                    color=theme.INCOME_GREEN if es_compra else theme.EXPENSE_RED),
            bgcolor=theme.INCOME_GREEN_BG if es_compra else theme.EXPENSE_RED_BG,
            padding=theme.pad(horizontal=8, vertical=3), border_radius=theme.RADIUS_LG,
        )
        acciones = [
            _boton("Editar", ft.Icons.EDIT_OUTLINED, lambda op=op: form_crypto(page, service, moneda, refrescar, op)),
            _boton("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED, lambda op=op: confirmar_eliminar(
                page, f"esta operación de {op.activo}", lambda op=op: (service.eliminar_crypto(op.id), refrescar())), theme.EXPENSE_RED),
        ]
        tarjetas.append(_tarjeta(op.activo, "Compra" if es_compra else "Venta", _fmt(op.monto), chip, datos, acciones, color))

    return [
        _encabezado_apartado(f"Crypto en {moneda.value}", "Nueva operación", lambda: form_crypto(page, service, moneda, refrescar), color),
        _tiles_totales(totales_crypto(operaciones, moneda), color),
        tenencias_card,
        _grilla(tarjetas, f"No cargaste operaciones crypto en {moneda.value}."),
    ]


# --- Calendario ---

def _calendario(page, service: InversionService, moneda: Moneda, refrescar) -> list[ft.Control]:
    anio, mes = _estado["cal_anio"], _estado["cal_mes"]
    hoy = date.today()
    colores = {clave: color for clave, _, _, color in _apartados()}
    nombres = {clave: texto for clave, texto, _, _ in _apartados()}
    color_tipo = {TipoTitulo.ACCION: colores["acciones"], TipoTitulo.BONO: colores["bonos"]}

    def ir_a(nuevo_anio: int, nuevo_mes: int):
        _estado["cal_anio"], _estado["cal_mes"] = nuevo_anio, nuevo_mes
        refrescar()

    def mover(delta: int):
        total = anio * 12 + (mes - 1) + delta
        ir_a(total // 12, total % 12 + 1)

    navegacion = ft.Row(
        [
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, tooltip="Mes anterior", on_click=lambda e: mover(-1)),
            ft.Text(f"{_MESES[mes - 1]} {anio}", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, width=200, text_align=ft.TextAlign.CENTER),
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, tooltip="Mes siguiente", on_click=lambda e: mover(1)),
            ft.TextButton("Hoy", on_click=lambda e: ir_a(hoy.year, hoy.month), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    # Mapa anual de dividendos/renta: lo principal de esta pestana.
    pagos = service.pagos_por_mes()

    def chip_simbolo(t) -> ft.Control:
        return ft.Container(
            ft.Text(t.simbolo, size=11, weight=ft.FontWeight.W_600, color="#FFFFFF"),
            bgcolor=color_tipo[t.tipo], border_radius=theme.RADIUS_SM, padding=theme.pad(horizontal=6, vertical=2),
            tooltip=f"{t.nombre or t.simbolo} · {'dividendos' if t.tipo == TipoTitulo.ACCION else 'renta'}",
        )

    def celda_mes(m: int) -> ft.Control:
        seleccionado = m == mes
        es_actual = m == hoy.month and anio == hoy.year
        return ft.Container(
            ft.Column(
                [
                    ft.Text(_MESES[m - 1], size=12, weight=ft.FontWeight.BOLD if seleccionado else ft.FontWeight.W_600,
                            color=theme.CAMBIO_COLOR if seleccionado else theme.TEXT_PRIMARY),
                    ft.Row([chip_simbolo(t) for t in pagos[m]], spacing=4, run_spacing=4, wrap=True)
                    if pagos[m] else ft.Text("—", size=12, color=theme.TEXT_MUTED),
                ],
                spacing=6, scroll=ft.ScrollMode.AUTO,
            ),
            col={"xs": 6, "md": 4, "lg": 2},
            height=96, padding=10, border_radius=theme.RADIUS_SM,
            bgcolor=theme.CAMBIO_BG if seleccionado else theme.SURFACE_ALT,
            border=theme.border_all(2, theme.CAMBIO_COLOR) if es_actual else theme.border_all(1, theme.BORDER),
            on_click=lambda e, m=m: ir_a(anio, m), ink=True,
        )

    def punto(color: str, texto: str) -> ft.Control:
        return ft.Row([ft.Container(width=10, height=10, bgcolor=color, border_radius=5), ft.Text(texto, size=11, color=theme.TEXT_SECONDARY)], spacing=4)

    mapa_card = theme.card(ft.Column(
        [
            ft.Row(
                [
                    _titulo_bloque(f"Dividendos y renta · {anio}"),
                    ft.Row([punto(colores["acciones"], "Acción (dividendos)"), punto(colores["bonos"], "Bono / Lecap (renta)")], spacing=16),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True,
            ),
            ft.Text("Qué acciones y bonos en posesión pagan en cada mes. Tocá un mes para ver el detalle.", size=11, color=theme.TEXT_MUTED),
            ft.ResponsiveRow([celda_mes(m) for m in range(1, 13)], spacing=8, run_spacing=8),
        ],
        spacing=10,
    ))

    # Cobros del mes elegido, con la tenencia total de cada simbolo (por moneda).
    tenencias: dict[tuple, list] = {}
    for tipo in TipoTitulo:
        titulos = service.listar_titulos(tipo)
        for m in Moneda:
            for ten in tenencias_por_simbolo(titulos, m):
                tenencias.setdefault((tipo, ten.simbolo), []).append(ten)

    filas_cobro = []
    for t in pagos[mes]:
        es_accion = t.tipo == TipoTitulo.ACCION
        tenencia = " · ".join(f"{fmt_decimal(ten.cantidad)} u. ({_fmt(ten.costo)})" for ten in tenencias.get((t.tipo, t.simbolo.upper()), []))
        filas_cobro.append(ft.Row(
            [
                ft.Container(
                    ft.Text("Dividendo" if es_accion else "Renta", size=11, weight=ft.FontWeight.W_600, color="#FFFFFF"),
                    bgcolor=color_tipo[t.tipo], border_radius=theme.RADIUS_LG, padding=theme.pad(horizontal=8, vertical=3),
                    width=84, alignment=ft.Alignment.CENTER,
                ),
                ft.Text(t.simbolo, size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, width=70),
                ft.Text(t.nombre, size=13, color=theme.TEXT_SECONDARY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(tenencia, size=12, color=theme.TEXT_PRIMARY),
                ft.Text(t.broker, size=12, color=theme.TEXT_MUTED, width=90, text_align=ft.TextAlign.RIGHT),
            ],
            spacing=10,
        ))
    cobros_card = theme.card(ft.Column(
        [
            _titulo_bloque(f"Cobros de {_MESES[mes - 1].lower()}"),
            ft.Divider(height=1, color=theme.BORDER),
            *(filas_cobro or [ft.Text("Ninguna acción o bono en posesión paga este mes.", size=13, color=theme.TEXT_MUTED)]),
        ],
        spacing=8,
    ))

    # Transacciones del mes: compras, ventas, rescates (hechos o previstos), retiros y crypto.
    filas_eventos = []
    for ev in service.eventos_del_mes(anio, mes):
        filas_eventos.append(ft.Row(
            [
                ft.Container(
                    ft.Text(ev.fecha.strftime("%d/%m"), size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_SECONDARY),
                    bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=theme.pad(horizontal=8, vertical=4),
                ),
                ft.Container(width=10, height=10, bgcolor=colores[ev.apartado], border_radius=5),
                ft.Text(nombres[ev.apartado], size=12, color=theme.TEXT_MUTED, width=100),
                ft.Text(ev.titulo, size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY, width=160, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(ev.detalle + (" (previsto)" if ev.previsto else ""), size=12, italic=ev.previsto,
                        color=theme.TEXT_MUTED if ev.previsto else theme.TEXT_SECONDARY, expand=True),
                ft.Text(_fmt(ev.monto) if ev.monto else "", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
            ],
            spacing=10,
        ))
    eventos_card = theme.card(ft.Column(
        [
            _titulo_bloque(f"Movimientos de {_MESES[mes - 1].lower()}"),
            ft.Divider(height=1, color=theme.BORDER),
            *(filas_eventos or [ft.Text("No hubo movimientos de inversiones este mes.", size=13, color=theme.TEXT_MUTED)]),
        ],
        spacing=8,
    ))

    return [navegacion, mapa_card, cobros_card, eventos_card]
