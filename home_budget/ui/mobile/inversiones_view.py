"""Inversiones en el celular: los mismos apartados que en escritorio (Resumen,
Calendario, Ahorro, Acciones, Bonos/Lecap, FCI y Crypto). Todo se ve por
moneda (selector ARS / USD); los totales nunca mezclan monedas.

Cada inversion es una tarjeta achicada (titulo y monto) que se despliega al
tocarla, con sus datos y sus acciones."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.inversiones import (
    EstadoInversion, InversionService, OperacionCrypto, TipoTitulo, Totales,
    tenencias_crypto, tenencias_por_simbolo, totales_crypto, totales_de,
)
from .. import theme
from ..desktop import components
from ..desktop.inversiones_forms import MESES_CORTOS, PLAZOS, fmt_decimal
from . import componentes as mc
from .inversiones_forms import confirmar_eliminar, form_ahorro, form_crypto, form_fci, form_salida, form_titulo

# Bloques (totales, tenencias, torta...) que el usuario dejo achicados.
CLAVE_PLEGADAS = "movil_inversiones_plegadas"

# Apartado, moneda y mes del calendario elegidos: se recuerdan al volver a la seccion.
_estado = {"apartado": "resumen", "moneda": Moneda.ARS, "cal_anio": date.today().year, "cal_mes": date.today().month}

_ORDENES = [("vigentes", "Vigentes primero"), *mc.ORDENES_COMUNES]


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


@dataclass
class _Item:
    """Una inversion (o una operacion crypto) lista para mostrar."""
    titulo: str
    subtitulo: str
    monto: Money
    chip: ft.Control
    datos: list[tuple[str, str]]
    acciones: list[tuple[str, object, Callable[[], None], str | None]]  # texto, icono, al tocar, color
    apagada: bool = False


@dataclass
class _Apartado:
    """Lo que muestra un apartado con lista: totales, tenencias (si tiene),
    sus inversiones y el alta."""
    totales: Totales
    items: list[_Item]
    texto_nuevo: str
    nuevo: Callable[[], ft.Control]
    vacio: str
    tenencias: list[ft.Control] = field(default_factory=list)
    titulo_tenencias: str = ""
    ayuda_tenencias: str = ""


def _fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def _con_signo(m: Money) -> str:
    return ("+" if m.cents >= 0 else "") + m.formatted()


# --- piezas visuales ---

def _pestana(clave, texto, icono, color, activa, al_tocar) -> ft.Control:
    return ft.Container(
        ft.Row(
            [
                ft.Icon(theme.to_icon(icono), size=16, color="#FFFFFF" if activa else color),
                ft.Text(texto, size=13, weight=ft.FontWeight.W_600, color="#FFFFFF" if activa else theme.TEXT_SECONDARY),
            ],
            spacing=6, tight=True,
        ),
        bgcolor=color if activa else theme.SURFACE, border=None if activa else theme.border_all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG, padding=theme.pad(horizontal=14, vertical=8), on_click=lambda e: al_tocar(clave), ink=True,
    )


def _totales(t: Totales, color: str) -> list[ft.Control]:
    """Los cuatro totales del apartado, de a dos por renglon."""
    def celda(titulo: str, valor: str, ayuda: str, color_valor: str | None = None) -> ft.Container:
        return ft.Container(
            ft.Column(
                [
                    ft.Text(titulo, size=11, color=theme.TEXT_SECONDARY),
                    ft.Text(valor, size=14, weight=ft.FontWeight.BOLD, color=color_valor or theme.TEXT_PRIMARY),
                    ft.Text(ayuda, size=10, color=theme.TEXT_MUTED),
                ],
                spacing=1,
            ),
            bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=10, expand=True,
        )

    return [
        ft.Row([celda("Total vigente", t.vigente.formatted(), f"{t.cantidad_vigentes} vigente(s) hoy", color),
                celda("Total invertido", t.invertido.formatted(), "Vigente o no")], spacing=8),
        ft.Row([celda("Recibido", t.recibido.formatted(), "Al finalizar o vender"),
                celda("Resultado", _con_signo(t.resultado), "De lo finalizado",
                      theme.INCOME_GREEN if t.resultado.cents >= 0 else theme.EXPENSE_RED)], spacing=8),
    ]


def _chip(texto: str, positivo: bool, negativo: bool = False) -> ft.Control:
    color = theme.INCOME_GREEN if positivo else theme.EXPENSE_RED if negativo else theme.TEXT_MUTED
    bg = theme.INCOME_GREEN_BG if positivo else theme.EXPENSE_RED_BG if negativo else theme.SURFACE_ALT
    return ft.Container(ft.Text(texto, size=11, weight=ft.FontWeight.W_600, color=color), bgcolor=bg,
                        padding=theme.pad(horizontal=8, vertical=3), border_radius=theme.RADIUS_LG)


def _tarjeta_item(item: _Item, color: str) -> ft.Control:
    datos = [
        ft.Row([ft.Text(etiqueta, size=12, color=theme.TEXT_MUTED, width=130),
                ft.Text(valor or "—", size=13, color=theme.TEXT_PRIMARY, expand=True, selectable=True)],
               spacing=8, vertical_alignment=ft.CrossAxisAlignment.START)
        for etiqueta, valor in item.datos
    ]
    acciones = ft.Row(
        [ft.TextButton(texto, icon=icono, on_click=lambda e, f=al_tocar: f(), style=ft.ButtonStyle(color=c or theme.TEXT_SECONDARY))
         for texto, icono, al_tocar, c in item.acciones],
        spacing=0, wrap=True, alignment=ft.MainAxisAlignment.END,
    )
    # Arranca achicada: con varias inversiones, desplegadas no entran en la pantalla.
    tarjeta = mc.tarjeta_plegable(
        item.titulo, [ft.Row([item.chip, ft.Text(item.subtitulo, size=12, color=theme.TEXT_SECONDARY, expand=True, no_wrap=True,
                                                 overflow=ft.TextOverflow.ELLIPSIS)], spacing=8), *datos, acciones],
        True, lambda plegada: None, color if not item.apagada else theme.TEXT_SECONDARY,
        ft.Text(item.monto.formatted(), size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
    )
    tarjeta.opacity = 0.75 if item.apagada else 1.0
    return tarjeta


# --- vista ---

def build_inversiones_view(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    service: InversionService = servicios.inversiones
    plegadas = mc.Plegadas(servicios.config, CLAVE_PLEGADAS)
    raiz = ft.Container(expand=True)

    def refrescar():
        raiz.content = construir()
        page.update()

    def elegir_apartado(clave: str):
        _estado["apartado"] = clave
        refrescar()

    def elegir_moneda(e):
        _estado["moneda"] = Moneda(next(iter(e.control.selected)))
        refrescar()

    def abrir(titulo: str, constructor: Callable[[], ft.Control]):
        nav.abrir(titulo, constructor, theme.INVERSIONES_COLOR)

    def eliminar(descripcion: str, accion: Callable[[], None]):
        confirmar_eliminar(page, descripcion, lambda: (accion(), refrescar(), nav.avisar("Eliminado")))

    def construir() -> ft.Control:
        moneda, apartado = _estado["moneda"], _estado["apartado"]
        color = next(c for clave, _t, _i, c in _apartados() if clave == apartado)
        pestanas = ft.Row(
            [_pestana(clave, texto, icono, c, clave == apartado, elegir_apartado) for clave, texto, icono, c in _apartados()],
            spacing=8, scroll=ft.ScrollMode.HIDDEN,
        )
        selector_moneda = ft.SegmentedButton(
            segments=[ft.Segment(value=m.value, label=ft.Text(m.value)) for m in Moneda],
            selected=[moneda.value], allow_multiple_selection=False, allow_empty_selection=False,
            show_selected_icon=False, on_change=elegir_moneda, expand=True,
        )
        # El calendario muestra ambas monedas: que no se pierda un dividendo por tener el filtro en la otra.
        cabecera = [pestanas, *([ft.Row([selector_moneda])] if apartado != "calendario" else [])]

        if apartado == "resumen":
            return mc.pantalla([*cabecera, *_resumen(moneda)])
        if apartado == "calendario":
            return mc.pantalla([*cabecera, *_calendario()])

        datos = {"ahorro": _ahorro, "acciones": lambda m: _titulos(m, TipoTitulo.ACCION), "bonos": lambda m: _titulos(m, TipoTitulo.BONO),
                 "fci": _fci, "crypto": _crypto}[apartado](moneda)
        lista = ft.Column(spacing=10)

        def listar(busqueda: str = "", orden: str = "vigentes"):
            elegidos = mc.filtrar_y_ordenar(datos.items, busqueda, orden, lambda i: f"{i.titulo} {i.subtitulo}", lambda i: i.monto)
            if not datos.items:
                lista.controls = [components.empty_state(datos.vacio, "inbox_rounded")]
            else:
                lista.controls = [_tarjeta_item(i, color) for i in elegidos] or [mc.sin_resultados()]

        def al_buscar(busqueda: str, orden: str):
            listar(busqueda, orden)
            page.update()

        listar()
        bloques = [plegadas.tarjeta(f"totales_{apartado}", "Totales", _totales(datos.totales, color), color)]
        if datos.titulo_tenencias:
            bloques.append(plegadas.tarjeta(
                f"tenencias_{apartado}", datos.titulo_tenencias,
                [ft.Text(datos.ayuda_tenencias, size=11, color=theme.TEXT_MUTED),
                 *(datos.tenencias or [ft.Text("Sin tenencias vigentes.", size=13, color=theme.TEXT_MUTED)])],
                color,
            ))
        return ft.Stack(
            [
                mc.pantalla([*cabecera, *bloques, mc.barra_busqueda(_ORDENES, al_buscar, color), lista]),
                mc.boton_flotante(ft.Icons.ADD_ROUNDED, color, lambda e: abrir(datos.texto_nuevo, datos.nuevo), datos.texto_nuevo),
            ],
            expand=True,
        )

    # --- Resumen ---

    def _resumen(moneda: Moneda) -> list[ft.Control]:
        totales = service.totales_por_apartado(moneda)
        colores = {clave: color for clave, _, _, color in _apartados()}
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
        torta = [
            ft.Row([components.torta(porciones)], alignment=ft.MainAxisAlignment.CENTER),
            *[ft.Row([ft.Container(width=10, height=10, bgcolor=p.color, border_radius=5),
                      ft.Text(p.nombre, size=13, color=theme.TEXT_PRIMARY, expand=True),
                      ft.Text(f"{p.porcentaje:.1f}%", size=12, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                      ft.Text(p.total.formatted(), size=12, color=theme.TEXT_SECONDARY, width=110, text_align=ft.TextAlign.RIGHT)], spacing=8)
              for p in porciones],
        ] if porciones else [components.empty_state(f"Todavía no tenés inversiones vigentes en {moneda.value}.", "donut_large_rounded")]

        filas = [
            ft.Container(
                mc.fila_dato("circle", colores[clave], nombres[clave], f"Invertido {t.invertido.formatted()}", t.vigente.formatted(),
                             theme.TEXT_PRIMARY),
                on_click=lambda e, c=clave: elegir_apartado(c), padding=theme.pad(vertical=4), ink=True, border_radius=theme.RADIUS_SM,
            )
            for clave, t in totales.items()
        ]
        return [
            plegadas.tarjeta("totales_resumen", "Totales", _totales(general, theme.INVERSIONES_COLOR), theme.INVERSIONES_COLOR),
            plegadas.tarjeta("torta", f"Distribución de lo vigente ({moneda.value})", torta),
            plegadas.tarjeta("por_apartado", "Por apartado (vigente)", filas),
        ]

    # --- Ahorro ---

    def _ahorro(moneda: Moneda) -> _Apartado:
        color = theme.PRESTAMOS_COLOR
        ahorros = [a for a in service.listar_ahorros() if a.monto.moneda == moneda]
        ahorros.sort(key=lambda a: a.estado != EstadoInversion.VIGENTE)

        items = []
        for a in ahorros:
            vigente = a.estado == EstadoInversion.VIGENTE
            datos = [("Fecha", _fecha(a.fecha)), ("Descontado de la app", "Sí" if a.entrada_mov_id else "No")]
            if not vigente:
                datos += [("Retirado el", _fecha(a.fecha_salida)), ("Monto retirado", a.monto_salida.formatted() if a.monto_salida else "—")]
            datos.append(("Observaciones", a.observaciones))
            acciones = []
            if vigente:
                acciones.append(("Retirar", ft.Icons.LOGOUT_ROUNDED, lambda a=a: abrir("Retirar ahorro", lambda: form_salida(
                    page, nav, "Monto retirado", a.monto.moneda, a.monto,
                    lambda f, m, acr: service.retirar_ahorro(a.id, f, m, acr))), color))
            acciones += [
                ("Editar", ft.Icons.EDIT_OUTLINED, lambda a=a: abrir("Editar ahorro", lambda: form_ahorro(page, nav, service, moneda, a)), None),
                ("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED,
                 lambda a=a: eliminar("este ahorro", lambda: service.eliminar_ahorro(a.id)), theme.EXPENSE_RED),
            ]
            items.append(_Item(a.ubicacion or "Ahorro", "Ahorro", a.monto, _chip("Vigente" if vigente else "Retirado", vigente),
                               datos, acciones, apagada=not vigente))
        return _Apartado(totales_de(ahorros, moneda), items, "Nuevo ahorro", lambda: form_ahorro(page, nav, service, moneda),
                         f"No cargaste ahorros en {moneda.value}.")

    # --- Acciones y Bonos/Lecap ---

    def _titulos(moneda: Moneda, tipo: TipoTitulo) -> _Apartado:
        es_accion = tipo == TipoTitulo.ACCION
        color = theme.CALENDARIO_COLOR if es_accion else theme.HISTORIAL_COLOR
        titulos = [t for t in service.listar_titulos(tipo) if t.precio_compra.moneda == moneda]
        titulos.sort(key=lambda t: t.estado != EstadoInversion.VIGENTE)

        tenencias = [
            mc.fila_dato("show_chart_rounded" if es_accion else "receipt_long_rounded", color,
                         f"{ten.simbolo} · {ten.nombre}" if ten.nombre else ten.simbolo,
                         f"{fmt_decimal(ten.cantidad)} u. · prom. {ten.precio_promedio.formatted()} · {ten.transacciones} compra(s)",
                         ten.costo.formatted(), theme.TEXT_PRIMARY)
            for ten in tenencias_por_simbolo(titulos, moneda)
        ]

        items = []
        for t in titulos:
            vigente = t.estado == EstadoInversion.VIGENTE
            datos = [
                ("Tipo de empresa", t.tipo_empresa), ("Plazo", PLAZOS[t.plazo]), ("Broker", t.broker), ("Transacción", t.transaccion),
                ("Fecha de suscripción", _fecha(t.fecha_suscripcion)), ("Cantidad", fmt_decimal(t.cantidad)),
                ("Precio de compra", t.precio_compra.formatted()),
                ("Dividendos" if es_accion else "Renta", ", ".join(MESES_CORTOS[m - 1] for m in t.meses_pago) if t.meses_pago else "—"),
            ]
            if not vigente and t.monto_salida is not None:
                datos += [("Vendida el", _fecha(t.fecha_salida)), ("Cobrado", t.monto_salida.formatted()),
                          ("Resultado", _con_signo(t.monto_salida - t.costo))]
            datos.append(("Observaciones", t.observaciones))
            acciones = []
            if vigente:
                acciones.append(("Finalizar", ft.Icons.SELL_OUTLINED, lambda t=t: abrir(f"Finalizar {t.simbolo}", lambda: form_salida(
                    page, nav, "Precio de venta (por unidad)", t.precio_compra.moneda, t.costo,
                    lambda f, m, acr: service.finalizar_titulo(t.id, f, m, acr), cantidad=t.cantidad)), color))
            nombre_tipo = "acción" if es_accion else "bono / Lecap"
            acciones += [
                ("Editar", ft.Icons.EDIT_OUTLINED,
                 lambda t=t: abrir(f"Editar {nombre_tipo}", lambda: form_titulo(page, nav, service, tipo, moneda, t)), None),
                ("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED,
                 lambda t=t: eliminar(f"la compra de {t.simbolo}", lambda: service.eliminar_titulo(t.id)), theme.EXPENSE_RED),
            ]
            items.append(_Item(t.simbolo, t.nombre or ("Acción" if es_accion else "Bono / Lecap"), t.costo,
                               _chip("En posesión" if vigente else "Finalizada", vigente), datos, acciones, apagada=not vigente))

        return _Apartado(
            totales_de(titulos, moneda), items, "Nueva acción" if es_accion else "Nuevo bono / Lecap",
            lambda: form_titulo(page, nav, service, tipo, moneda), f"No cargaste {'acciones' if es_accion else 'bonos / Lecap'} en {moneda.value}.",
            tenencias, f"Tenencias por {'acción' if es_accion else 'bono'} (en posesión)",
            "Suma las compras vigentes de cada símbolo: cantidad total, precio promedio y total pagado.",
        )

    # --- FCI ---

    def _fci(moneda: Moneda) -> _Apartado:
        color = theme.DASHBOARD_COLOR
        fcis = [f for f in service.listar_fcis() if f.monto.moneda == moneda]
        fcis.sort(key=lambda f: f.estado != EstadoInversion.VIGENTE)

        items = []
        for f in fcis:
            vigente = f.estado == EstadoInversion.VIGENTE
            datos = [
                ("Símbolo", f.simbolo), ("Plazo", PLAZOS[f.plazo]), ("Broker", f.broker), ("Transacción", f.transaccion),
                ("Fecha de suscripción", _fecha(f.fecha_suscripcion)), ("Fecha de rescate", _fecha(f.fecha_rescate)),
                ("TNA", f"{fmt_decimal(f.tna)}%" if f.tna is not None else "—"),
            ]
            if not vigente and f.monto_salida is not None:
                datos += [("Rescatado", f.monto_salida.formatted()), ("Resultado", _con_signo(f.monto_salida - f.monto))]
            datos.append(("Observaciones", f.observaciones))
            acciones = []
            if vigente:
                acciones.append(("Rescatar", ft.Icons.LOGOUT_ROUNDED, lambda f=f: abrir(f"Rescatar {f.nombre}", lambda: form_salida(
                    page, nav, "Monto rescatado", f.monto.moneda, f.monto,
                    lambda fe, m, acr: service.rescatar_fci(f.id, fe, m, acr))), color))
            acciones += [
                ("Editar", ft.Icons.EDIT_OUTLINED, lambda f=f: abrir("Editar FCI", lambda: form_fci(page, nav, service, moneda, f)), None),
                ("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED,
                 lambda f=f: eliminar(f"el FCI {f.nombre}", lambda: service.eliminar_fci(f.id)), theme.EXPENSE_RED),
            ]
            items.append(_Item(f.nombre, f.simbolo or "Fondo común de inversión", f.monto,
                               _chip("Vigente" if vigente else "Rescatado", vigente), datos, acciones, apagada=not vigente))
        return _Apartado(totales_de(fcis, moneda), items, "Nuevo FCI", lambda: form_fci(page, nav, service, moneda),
                         f"No cargaste FCI en {moneda.value}.")

    # --- Crypto ---

    def _crypto(moneda: Moneda) -> _Apartado:
        color = theme.MOVIMIENTOS_COLOR
        operaciones = [op for op in service.listar_crypto() if op.monto.moneda == moneda]

        tenencias = [
            mc.fila_dato("currency_bitcoin_rounded", color, ten.activo,
                         f"{fmt_decimal(ten.cantidad)} u. · invertido {ten.invertido.formatted()} · vendido {ten.recibido.formatted()}",
                         ten.vigente.formatted(), theme.TEXT_PRIMARY)
            for ten in tenencias_crypto(operaciones, moneda)
        ]

        items = []
        for op in operaciones:
            es_compra = op.operacion == OperacionCrypto.COMPRA
            datos = [
                ("Fecha", _fecha(op.fecha)), ("Cantidad", fmt_decimal(op.cantidad)),
                ("Precio unitario", f"{fmt_decimal(op.precio_unitario)} {op.monto.moneda.value}"),
                ("Con plata de la app", "Sí" if op.mov_id else "No"), ("Observaciones", op.observaciones),
            ]
            acciones = [
                ("Editar", ft.Icons.EDIT_OUTLINED,
                 lambda op=op: abrir("Editar operación crypto", lambda: form_crypto(page, nav, service, moneda, op)), None),
                ("Eliminar", ft.Icons.DELETE_OUTLINE_ROUNDED,
                 lambda op=op: eliminar(f"esta operación de {op.activo}", lambda: service.eliminar_crypto(op.id)), theme.EXPENSE_RED),
            ]
            items.append(_Item(op.activo, f"{'Compra' if es_compra else 'Venta'} · {_fecha(op.fecha)}", op.monto,
                               _chip("Compra" if es_compra else "Venta", es_compra, negativo=not es_compra), datos, acciones))
        return _Apartado(
            totales_crypto(operaciones, moneda), items, "Nueva operación crypto", lambda: form_crypto(page, nav, service, moneda),
            f"No cargaste operaciones crypto en {moneda.value}.", tenencias, "Tenencias por moneda",
            "Cantidad = compras − ventas. El vigente se valúa al precio promedio de compra.",
        )

    # --- Calendario ---

    def _calendario() -> list[ft.Control]:
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

        # Mapa anual de dividendos/renta: que acciones y bonos en posesion pagan cada mes.
        pagos = service.pagos_por_mes()

        def celda_mes(m: int) -> ft.Control:
            elegido = m == mes
            es_actual = m == hoy.month and anio == hoy.year
            return ft.Container(
                ft.Column(
                    [
                        ft.Text(MESES_CORTOS[m - 1], size=12, weight=ft.FontWeight.BOLD, color=theme.CAMBIO_COLOR if elegido else theme.TEXT_PRIMARY),
                        ft.Row([ft.Container(ft.Text(t.simbolo, size=10, weight=ft.FontWeight.W_600, color="#FFFFFF"), bgcolor=color_tipo[t.tipo],
                                             border_radius=theme.RADIUS_SM, padding=theme.pad(horizontal=5, vertical=1)) for t in pagos[m]],
                               spacing=3, run_spacing=3, wrap=True)
                        if pagos[m] else ft.Text("—", size=12, color=theme.TEXT_MUTED),
                    ],
                    spacing=4,
                ),
                expand=True, padding=8, border_radius=theme.RADIUS_SM, bgcolor=theme.CAMBIO_BG if elegido else theme.SURFACE_ALT,
                border=theme.border_all(2, theme.CAMBIO_COLOR) if es_actual else theme.border_all(1, theme.BORDER),
                on_click=lambda e: ir_a(anio, m), ink=True,
            )

        def punto(color: str, texto: str) -> ft.Control:
            return ft.Row([ft.Container(width=10, height=10, bgcolor=color, border_radius=5), ft.Text(texto, size=11, color=theme.TEXT_SECONDARY)],
                          spacing=4, tight=True)

        mapa = [
            ft.Row([punto(colores["acciones"], "Acción (dividendos)"), punto(colores["bonos"], "Bono / Lecap (renta)")], spacing=16, wrap=True),
            ft.Text("Tocá un mes para ver el detalle.", size=11, color=theme.TEXT_MUTED),
            *[ft.Row([celda_mes(m) for m in range(fila * 3 + 1, fila * 3 + 4)], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START)
              for fila in range(4)],
        ]

        # Cobros del mes elegido, con la tenencia total de cada simbolo (por moneda).
        tenencias: dict[tuple, list] = {}
        for tipo in TipoTitulo:
            titulos = service.listar_titulos(tipo)
            for m in Moneda:
                for ten in tenencias_por_simbolo(titulos, m):
                    tenencias.setdefault((tipo, ten.simbolo), []).append(ten)

        cobros = []
        for t in pagos[mes]:
            es_accion = t.tipo == TipoTitulo.ACCION
            tenencia = " · ".join(f"{fmt_decimal(ten.cantidad)} u. ({ten.costo.formatted()} {ten.costo.moneda.value})"
                                  for ten in tenencias.get((t.tipo, t.simbolo.upper()), []))
            cobros.append(mc.fila_dato(
                "show_chart_rounded" if es_accion else "receipt_long_rounded", color_tipo[t.tipo],
                f"{t.simbolo} · {t.nombre}" if t.nombre else t.simbolo,
                " · ".join(p for p in ["Dividendo" if es_accion else "Renta", tenencia, t.broker] if p), "",
            ))

        # Transacciones del mes: compras, ventas, rescates (hechos o previstos), retiros y crypto.
        eventos = [
            mc.fila_dato("circle", colores[ev.apartado], ev.titulo,
                         f"{ev.fecha.strftime('%d/%m')} · {nombres[ev.apartado]} · {ev.detalle}{' (previsto)' if ev.previsto else ''}",
                         f"{ev.monto.formatted()} {ev.monto.moneda.value}" if ev.monto else "", theme.TEXT_PRIMARY)
            for ev in service.eventos_del_mes(anio, mes)
        ]
        nombre_mes = mc.MESES[mes - 1]
        return [
            mc.selector_mes(anio, mes, mover, theme.CAMBIO_COLOR),
            *([ft.Row([ft.TextButton("Ir a hoy", on_click=lambda e: ir_a(hoy.year, hoy.month), style=ft.ButtonStyle(color=theme.TEXT_SECONDARY))],
                      alignment=ft.MainAxisAlignment.CENTER)] if (anio, mes) != (hoy.year, hoy.month) else []),
            plegadas.tarjeta("mapa", f"Dividendos y renta · {anio}", mapa, theme.CAMBIO_COLOR),
            plegadas.tarjeta("cobros", f"Cobros de {nombre_mes}",
                             cobros or [ft.Text("Ninguna acción o bono en posesión paga este mes.", size=13, color=theme.TEXT_MUTED)]),
            plegadas.tarjeta("eventos", f"Movimientos de {nombre_mes}",
                             eventos or [ft.Text("No hubo movimientos de inversiones este mes.", size=13, color=theme.TEXT_MUTED)]),
        ]

    raiz.content = construir()
    return raiz
