"""Formularios de Inversiones en el celular (alta, edicion y salida), a
pantalla completa. Piden los mismos datos y en el mismo orden que los
dialogos de escritorio; lo que alla va de a dos o tres por renglon, aca va
uno debajo del otro."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.inversiones import (
    Ahorro, EstadoInversion, Fci, InversionService, OperacionCrypto, OperacionCryptoRegistro, Plazo, TipoTitulo, Titulo,
)
from .. import theme
from ..desktop.inversiones_forms import MESES_CORTOS, PLAZOS, fmt_decimal, parse_decimal
from . import componentes as mc


# --- piezas de los formularios ---

def _opciones(pares: list[tuple[str, str]]) -> list:
    return [ft.dropdown.Option(v, t) for v, t in pares]


def _moneda_dd(valor: Moneda) -> ft.Dropdown:
    return mc.desplegable("Moneda", valor.value, _opciones([(Moneda.ARS.value, "Pesos (ARS)"), (Moneda.USD.value, "Dólares (USD)")]), expand=True)


def _plazo_dd(valor: Plazo) -> ft.Dropdown:
    return mc.desplegable("Plazo", valor.value, _opciones([(p.value, t) for p, t in PLAZOS.items()]), expand=True)


def _numero(label: str, value: str = "", **kwargs) -> ft.TextField:
    return mc.campo(label, value=value, keyboard_type=ft.KeyboardType.NUMBER, **kwargs)


def _observaciones(valor: str) -> ft.TextField:
    return mc.campo("Observaciones", value=valor, multiline=True, min_lines=2, max_lines=4)


def _check(label: str) -> ft.Checkbox:
    return ft.Checkbox(label=label, value=True, active_color=theme.INVERSIONES_COLOR)


def _subtitulo(texto: str) -> ft.Text:
    return ft.Text(texto, size=12, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY)


def _selector_meses(page: ft.Page, seleccionados: list[int]) -> tuple[ft.Control, set[int]]:
    """Los 12 meses como botones que se prenden y apagan (se puede dejar vacio)."""
    elegidos = set(seleccionados)
    fila = ft.Row(spacing=6, run_spacing=6, wrap=True)

    def boton(mes: int, nombre: str) -> ft.Control:
        activo = mes in elegidos

        def alternar(_e):
            elegidos.symmetric_difference_update({mes})
            dibujar()
            page.update()

        return ft.Container(
            ft.Text(nombre, size=12, weight=ft.FontWeight.W_600, color="#FFFFFF" if activo else theme.TEXT_SECONDARY),
            width=52, height=36, alignment=ft.Alignment.CENTER, border_radius=theme.RADIUS_SM,
            bgcolor=theme.INVERSIONES_COLOR if activo else theme.SURFACE_ALT,
            border=None if activo else theme.border_all(1, theme.BORDER), on_click=alternar,
        )

    def dibujar():
        fila.controls = [boton(i + 1, nombre) for i, nombre in enumerate(MESES_CORTOS)]

    dibujar()
    return fila, elegidos


def _formulario(page: ft.Page, nav: mc.Navegacion, controles: list[ft.Control], guardar: Callable[[], None],
                texto_boton: str = "Guardar", aviso: str = "Guardado") -> ft.Control:
    """Pantalla de un formulario; `guardar` lanza ValueError con el mensaje a mostrar si algo esta mal."""
    error = ft.Text("", size=13, color=theme.EXPENSE_RED, visible=False)

    def al_guardar(_e):
        try:
            guardar()
        except (ValueError, ArithmeticError) as exc:
            error.value, error.visible = str(exc), True
            page.update()
            return
        nav.volver()
        nav.avisar(aviso)

    return mc.pantalla([*controles, error, mc.boton_ancho(texto_boton, al_guardar, theme.INVERSIONES_COLOR, ft.Icons.CHECK_ROUNDED)])


# --- Ahorro ---

def form_ahorro(page: ft.Page, nav: mc.Navegacion, service: InversionService, moneda: Moneda, existente: Ahorro | None = None) -> ft.Control:
    a = existente
    monto_f = _numero("Monto", fmt_decimal(a.monto.amount) if a else "", autofocus=not a)
    moneda_dd = _moneda_dd(a.monto.moneda if a else moneda)
    fila_fecha, fecha = mc.selector_fecha(page, "Fecha", a.fecha if a else date.today())
    ubicacion_f = mc.campo("Dónde está guardado", value=a.ubicacion if a else "", hint_text="Ej: Banco Galicia, Mercado Pago, Ualá, efectivo")
    obs_f = _observaciones(a.observaciones if a else "")
    debitar = _check("Descontar de la plata de la app")

    def guardar():
        monto = Money.from_decimal(parse_decimal(monto_f.value, "Monto"), moneda_dd.value)
        datos = Ahorro(a.id if a else None, monto, fecha() or date.today(), ubicacion_f.value or "", obs_f.value or "")
        if a:
            datos.entrada_mov_id, datos.estado = a.entrada_mov_id, a.estado
            service.editar_ahorro(datos)
        else:
            service.registrar_ahorro(datos, debitar=bool(debitar.value))

    controles = [monto_f, ft.Row([moneda_dd]), fila_fecha, ubicacion_f, obs_f]
    if not a:
        controles.append(debitar)
    return _formulario(page, nav, controles, guardar, aviso="Ahorro guardado")


# --- Acciones y Bonos/Lecap ---

def form_titulo(page: ft.Page, nav: mc.Navegacion, service: InversionService, tipo: TipoTitulo, moneda: Moneda,
                existente: Titulo | None = None) -> ft.Control:
    t = existente
    es_accion = tipo == TipoTitulo.ACCION

    estado_dd = mc.desplegable("Estado", EstadoInversion.VIGENTE.value,
                               _opciones([(EstadoInversion.VIGENTE.value, "En posesión"), (EstadoInversion.FINALIZADA.value, "Finalizada")]),
                               expand=True)
    simbolo_f = mc.campo("Símbolo", value=t.simbolo if t else "", hint_text="Ej: NVDA" if es_accion else "Ej: AL30, S31O5",
                         capitalization=ft.TextCapitalization.CHARACTERS, autofocus=not t)
    plazo_dd = _plazo_dd(t.plazo if t else Plazo.LARGO)
    nombre_f = mc.campo("Nombre", value=t.nombre if t else "", hint_text="Ej: Nvidia Corp." if es_accion else "Ej: Bono Rep. Argentina 2030")
    tipo_empresa_f = mc.campo("Tipo de empresa", value=t.tipo_empresa if t else "", hint_text="Ej: Tecnología")
    broker_f = mc.campo("Broker", value=t.broker if t else "", hint_text="Ej: IOL")
    transaccion_f = mc.campo("Transacción", value=t.transaccion if t else "", hint_text="Ej: 129861459")
    fila_fecha, fecha = mc.selector_fecha(page, "Fecha de suscripción", t.fecha_suscripcion if t else date.today())
    cantidad_f = _numero("Cantidad", fmt_decimal(t.cantidad) if t else "", hint_text="Ej: 1")
    precio_f = _numero("Precio de compra (por unidad)", fmt_decimal(t.precio_compra.amount) if t else "", hint_text="Ej: 1500")
    moneda_dd = _moneda_dd(t.precio_compra.moneda if t else moneda)
    fila_meses, meses = _selector_meses(page, t.meses_pago if t else [])
    obs_f = _observaciones(t.observaciones if t else "")
    debitar = _check("Descontar la compra de la plata de la app")

    # Si se carga como finalizada, se piden los datos de la venta.
    fila_fecha_venta, fecha_venta = mc.selector_fecha(page, "Fecha de venta", date.today())
    precio_venta_f = _numero("Precio de venta (por unidad)")
    acreditar = _check("Sumar la venta a la plata de la app")
    bloque_venta = ft.Column([_subtitulo("Venta"), fila_fecha_venta, precio_venta_f, acreditar], spacing=10, visible=False,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def al_cambiar_estado(_e):
        bloque_venta.visible = estado_dd.value == EstadoInversion.FINALIZADA.value
        page.update()

    estado_dd.on_select = al_cambiar_estado

    def guardar():
        cantidad = parse_decimal(cantidad_f.value, "Cantidad")
        precio = Money.from_decimal(parse_decimal(precio_f.value, "Precio de compra"), moneda_dd.value)
        datos = Titulo(
            id=t.id if t else None, tipo=tipo, simbolo=simbolo_f.value or "", fecha_suscripcion=fecha() or date.today(),
            cantidad=cantidad, precio_compra=precio, nombre=nombre_f.value or "", tipo_empresa=tipo_empresa_f.value or "",
            plazo=Plazo(plazo_dd.value), broker=broker_f.value or "", transaccion=transaccion_f.value or "",
            meses_pago=sorted(meses), observaciones=obs_f.value or "",
        )
        if t:
            datos.estado, datos.entrada_mov_id = t.estado, t.entrada_mov_id
            service.editar_titulo(datos)
        else:
            venta = None
            if estado_dd.value == EstadoInversion.FINALIZADA.value:
                venta = Money.from_decimal(parse_decimal(precio_venta_f.value, "Precio de venta") * cantidad, moneda_dd.value)
            creado = service.registrar_titulo(datos, debitar=bool(debitar.value))
            if venta is not None:
                service.finalizar_titulo(creado.id, fecha_venta() or date.today(), venta, acreditar=bool(acreditar.value))

    controles = [ft.Row([estado_dd])] if not t else []
    controles += [
        simbolo_f, ft.Row([plazo_dd]), nombre_f, tipo_empresa_f, broker_f, transaccion_f, fila_fecha,
        cantidad_f, precio_f, ft.Row([moneda_dd]),
        _subtitulo(("Meses en que paga dividendos" if es_accion else "Meses en que paga renta") + " (opcional)"),
        fila_meses, obs_f,
    ]
    if not t:
        controles += [debitar, bloque_venta]
    return _formulario(page, nav, controles, guardar, aviso="Acción guardada" if es_accion else "Bono / Lecap guardado")


# --- FCI ---

def form_fci(page: ft.Page, nav: mc.Navegacion, service: InversionService, moneda: Moneda, existente: Fci | None = None) -> ft.Control:
    f = existente
    estado_dd = mc.desplegable("Estado", EstadoInversion.VIGENTE.value,
                               _opciones([(EstadoInversion.VIGENTE.value, "Vigente"), (EstadoInversion.FINALIZADA.value, "Rescatado")]),
                               expand=True)
    nombre_f = mc.campo("Nombre del fondo", value=f.nombre if f else "", autofocus=not f)
    simbolo_f = mc.campo("Símbolo", value=f.simbolo if f else "", capitalization=ft.TextCapitalization.CHARACTERS)
    plazo_dd = _plazo_dd(f.plazo if f else Plazo.CORTO)
    broker_f = mc.campo("Broker", value=f.broker if f else "")
    transaccion_f = mc.campo("Transacción", value=f.transaccion if f else "")
    fila_fecha, fecha = mc.selector_fecha(page, "Fecha de suscripción", f.fecha_suscripcion if f else date.today())
    fila_rescate, fecha_rescate = mc.selector_fecha(page, "Fecha de rescate", f.fecha_rescate if f else None, opcional=True)
    monto_f = _numero("Monto", fmt_decimal(f.monto.amount) if f else "")
    moneda_dd = _moneda_dd(f.monto.moneda if f else moneda)
    tna_f = _numero("TNA (%)", fmt_decimal(f.tna) if f and f.tna is not None else "", hint_text="Ej: 35,5")
    obs_f = _observaciones(f.observaciones if f else "")
    debitar = _check("Descontar de la plata de la app")

    monto_rescate_f = _numero("Monto rescatado")
    acreditar = _check("Sumar el rescate a la plata de la app")
    bloque_rescate = ft.Column([_subtitulo("Rescate (se usa la fecha de rescate de arriba)"), monto_rescate_f, acreditar], spacing=10,
                               visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def al_cambiar_estado(_e):
        bloque_rescate.visible = estado_dd.value == EstadoInversion.FINALIZADA.value
        page.update()

    estado_dd.on_select = al_cambiar_estado

    def guardar():
        tna = parse_decimal(tna_f.value, "TNA") if (tna_f.value or "").strip() else None
        datos = Fci(
            id=f.id if f else None, nombre=nombre_f.value or "", fecha_suscripcion=fecha() or date.today(),
            monto=Money.from_decimal(parse_decimal(monto_f.value, "Monto"), moneda_dd.value), simbolo=simbolo_f.value or "",
            plazo=Plazo(plazo_dd.value), broker=broker_f.value or "", transaccion=transaccion_f.value or "",
            fecha_rescate=fecha_rescate(), tna=tna, observaciones=obs_f.value or "",
        )
        if f:
            datos.estado, datos.entrada_mov_id = f.estado, f.entrada_mov_id
            service.editar_fci(datos)
        else:
            rescate = None
            if estado_dd.value == EstadoInversion.FINALIZADA.value:
                rescate = Money.from_decimal(parse_decimal(monto_rescate_f.value, "Monto rescatado"), moneda_dd.value)
            creado = service.registrar_fci(datos, debitar=bool(debitar.value))
            if rescate is not None:
                service.rescatar_fci(creado.id, fecha_rescate() or date.today(), rescate, acreditar=bool(acreditar.value))

    controles = [ft.Row([estado_dd])] if not f else []
    controles += [nombre_f, simbolo_f, ft.Row([plazo_dd]), broker_f, transaccion_f, fila_fecha, fila_rescate,
                  monto_f, ft.Row([moneda_dd]), tna_f, obs_f]
    if not f:
        controles += [debitar, bloque_rescate]
    return _formulario(page, nav, controles, guardar, aviso="FCI guardado")


# --- Crypto ---

def form_crypto(page: ft.Page, nav: mc.Navegacion, service: InversionService, moneda: Moneda,
                existente: OperacionCryptoRegistro | None = None) -> ft.Control:
    op = existente
    operacion_dd = mc.desplegable("Operación", (op.operacion if op else OperacionCrypto.COMPRA).value,
                                  _opciones([(OperacionCrypto.COMPRA.value, "Compra"), (OperacionCrypto.VENTA.value, "Venta")]), expand=True)
    fila_fecha, fecha = mc.selector_fecha(page, "Fecha", op.fecha if op else date.today())
    activo_f = mc.campo("Criptomoneda", value=op.activo if op else "", hint_text="Ej: USDT, BTC",
                        capitalization=ft.TextCapitalization.CHARACTERS, autofocus=not op)
    moneda_dd = _moneda_dd(op.monto.moneda if op else moneda)
    monto_f = _numero("Monto", fmt_decimal(op.monto.amount) if op else "")
    precio_f = _numero("Precio unitario", fmt_decimal(op.precio_unitario) if op else "", hint_text="Precio de 1 unidad")
    cantidad_f = _numero("Cantidad", fmt_decimal(op.cantidad) if op else "")
    obs_f = _observaciones(op.observaciones if op else "")
    cuenta = _check("Descontar de la plata de la app")

    def al_cambiar_operacion(_e):
        es_compra = operacion_dd.value == OperacionCrypto.COMPRA.value
        cuenta.label = "Descontar de la plata de la app" if es_compra else "Sumar a la plata de la app"
        page.update()

    operacion_dd.on_select = al_cambiar_operacion

    def guardar():
        datos = OperacionCryptoRegistro(
            id=op.id if op else None, fecha=fecha() or date.today(), operacion=OperacionCrypto(operacion_dd.value),
            activo=activo_f.value or "", monto=Money.from_decimal(parse_decimal(monto_f.value, "Monto"), moneda_dd.value),
            precio_unitario=parse_decimal(precio_f.value, "Precio unitario"), cantidad=parse_decimal(cantidad_f.value, "Cantidad"),
            observaciones=obs_f.value or "",
        )
        if op:
            datos.mov_id = op.mov_id
            service.editar_crypto(datos)
        else:
            service.registrar_crypto(datos, operar_con_cuenta=bool(cuenta.value))

    controles = [ft.Row([operacion_dd]), fila_fecha, activo_f, ft.Row([moneda_dd]), monto_f, precio_f, cantidad_f, obs_f]
    if not op:
        controles.append(cuenta)
    return _formulario(page, nav, controles, guardar, aviso="Operación guardada")


# --- Finalizar / rescatar / retirar ---

def form_salida(page: ft.Page, nav: mc.Navegacion, etiqueta_monto: str, moneda: Moneda, costo: Money,
                al_confirmar: Callable[[date, Money, bool], None], cantidad: Decimal | None = None) -> ft.Control:
    """Si se pasa `cantidad`, el monto ingresado es por unidad y se multiplica."""
    fila_fecha, fecha = mc.selector_fecha(page, "Fecha", date.today())
    monto_f = _numero(etiqueta_monto, autofocus=True)
    resultado = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    acreditar = _check("Sumar a la plata de la app")

    def total() -> Money:
        valor = parse_decimal(monto_f.value, etiqueta_monto)
        return Money.from_decimal(valor * cantidad if cantidad is not None else valor, moneda)

    def al_escribir(_e):
        try:
            recibido = total()
        except ValueError:
            resultado.value = ""
        else:
            dif = recibido - costo
            pct = (dif.amount / costo.amount * 100) if costo.cents else Decimal(0)
            signo = "+" if dif.cents >= 0 else ""
            pct_texto = f"{pct:.1f}".replace(".", ",")
            resultado.value = f"Recibís {recibido.formatted()} · Resultado: {signo}{dif.formatted()} ({signo}{pct_texto}%)"
            resultado.color = theme.INCOME_GREEN if dif.cents >= 0 else theme.EXPENSE_RED
        page.update()

    monto_f.on_change = al_escribir

    def guardar():
        al_confirmar(fecha() or date.today(), total(), bool(acreditar.value))

    return _formulario(
        page, nav,
        [ft.Text(f"Costo: {costo.formatted()} {moneda.value}", size=13, color=theme.TEXT_SECONDARY), fila_fecha, monto_f, resultado, acreditar],
        guardar, texto_boton="Confirmar", aviso="Listo",
    )


def confirmar_eliminar(page: ft.Page, descripcion: str, al_aceptar: Callable[[], None]) -> None:
    def aceptar(_e):
        page.pop_dialog()
        al_aceptar()

    page.show_dialog(theme.dialogo(
        "Eliminar",
        ft.Text(f"¿Seguro que querés eliminar {descripcion}? Si generó movimientos en la plata de la app, también se borran.",
                color=theme.TEXT_PRIMARY),
        [theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
         theme.primary_button("Eliminar", aceptar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED)],
        icono="delete_outline_rounded", color=theme.EXPENSE_RED, ancho=300,
    ))
