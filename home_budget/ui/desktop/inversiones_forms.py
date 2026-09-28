"""Dialogos de alta/edicion/finalizacion de la seccion Inversiones."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Callable

import flet as ft

from ...app.domain.money import Money, Moneda
from ...app.services.inversiones import (
    Ahorro, EstadoInversion, Fci, InversionService, fmt_cantidad as fmt_decimal, OperacionCrypto, OperacionCryptoRegistro, Plazo, TipoTitulo, Titulo,
)
from .. import theme

MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
PLAZOS = {Plazo.CORTO: "Corto plazo", Plazo.MEDIANO: "Mediano plazo", Plazo.LARGO: "Largo plazo"}
_ANCHO_DIALOGO = 520


# --- helpers de campos ---

def parse_decimal(texto: str | None, campo: str) -> Decimal:
    """Acepta "1500", "1500.5", "1500,5" y "1.500,50" (formato argentino)."""
    s = (texto or "").strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"{campo}: ingresá un número válido") from None
    if not valor.is_finite():
        raise ValueError(f"{campo}: ingresá un número válido")
    return valor


def _texto(label: str, value: str = "", **kwargs) -> ft.TextField:
    return ft.TextField(
        label=label, value=value, filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM,
        border_color=theme.BORDER, focused_border_color=theme.INVERSIONES_COLOR, **kwargs,
    )


def _dropdown(label: str, opciones: list[tuple[str, str]], value: str, **kwargs) -> ft.Dropdown:
    return ft.Dropdown(
        label=label, value=value, options=[ft.dropdown.Option(v, t) for v, t in opciones],
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER, **kwargs,
    )


def _dropdown_moneda(value: Moneda) -> ft.Dropdown:
    return _dropdown("Moneda", [(Moneda.ARS.value, "Pesos (ARS)"), (Moneda.USD.value, "Dólares (USD)")], value.value, expand=True)


def _dropdown_plazo(value: Plazo) -> ft.Dropdown:
    return _dropdown("Plazo", [(p.value, t) for p, t in PLAZOS.items()], value.value, expand=True)


class _CampoFecha:
    def __init__(self, page: ft.Page, label: str, valor: date | None, opcional: bool = False):
        self.valor = valor
        self._texto = ft.Text(self._formato(), size=14, color=theme.TEXT_PRIMARY)

        def on_change(_e):
            if self._picker.value:
                v = self._picker.value
                self.valor = v.date() if isinstance(v, datetime) else v
                self._texto.value = self._formato()
                page.update()

        def limpiar(_e):
            self.valor = None
            self._texto.value = self._formato()
            page.update()

        self._picker = ft.DatePicker(value=valor, on_change=on_change)
        page.overlay.append(self._picker)
        self.control = ft.Container(
            ft.Row(
                [
                    ft.Column([ft.Text(label, size=11, color=theme.TEXT_MUTED), self._texto], spacing=0, expand=True),
                    ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: (setattr(self._picker, "open", True), page.update())),
                    *([ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, tooltip="Quitar fecha", on_click=limpiar)] if opcional else []),
                ],
                spacing=0,
            ),
            bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=theme.pad_only(left=12, top=4, bottom=4), expand=True,
        )

    def _formato(self) -> str:
        return self.valor.strftime("%d/%m/%Y") if self.valor else "Sin definir"


class _SelectorMeses:
    """Los 12 meses como botones que se prenden/apagan (se puede dejar vacio)."""
    def __init__(self, page: ft.Page, seleccionados: list[int]):
        self.seleccionados = set(seleccionados)
        self._page = page
        self.control = ft.Row(spacing=6, run_spacing=6, wrap=True)
        self._dibujar()

    def _dibujar(self):
        self.control.controls = [self._boton(i + 1, nombre) for i, nombre in enumerate(MESES_CORTOS)]

    def _boton(self, mes: int, nombre: str) -> ft.Control:
        activo = mes in self.seleccionados

        def alternar(_e):
            self.seleccionados.symmetric_difference_update({mes})
            self._dibujar()
            self._page.update()

        return ft.Container(
            ft.Text(nombre, size=12, weight=ft.FontWeight.W_600, color="#FFFFFF" if activo else theme.TEXT_SECONDARY),
            width=52, height=32, alignment=ft.Alignment.CENTER, border_radius=theme.RADIUS_SM,
            bgcolor=theme.INVERSIONES_COLOR if activo else theme.SURFACE_ALT,
            border=None if activo else theme.border_all(1, theme.BORDER),
            on_click=alternar,
        )


def _subtitulo(texto: str) -> ft.Text:
    return ft.Text(texto, size=12, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY)


def _dialogo(page: ft.Page, titulo: str, controles: list[ft.Control], guardar: Callable[[], None], texto_boton: str = "Guardar"):
    """Muestra un formulario; `guardar` lanza ValueError con el mensaje a mostrar si algo esta mal."""
    error = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

    def on_guardar(_e=None):
        try:
            guardar()
        except ValueError as exc:
            error.value, error.visible = str(exc), True
            page.update()
            return
        page.pop_dialog()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Text(titulo),
        content=ft.Container(ft.Column([*controles, error], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO), width=_ANCHO_DIALOGO),
        actions=[
            theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
            theme.primary_button(texto_boton, on_guardar, color=theme.INVERSIONES_COLOR),
        ],
    ))


def _check_cuenta(label: str, valor: bool = True) -> ft.Checkbox:
    return ft.Checkbox(label=label, value=valor, active_color=theme.INVERSIONES_COLOR)


# --- Ahorro ---

def form_ahorro(page: ft.Page, service: InversionService, moneda: Moneda, on_listo: Callable[[], None], existente: Ahorro | None = None):
    a = existente
    monto_f = _texto("Monto", fmt_decimal(a.monto.amount) if a else "", expand=True, autofocus=True)
    moneda_dd = _dropdown_moneda(a.monto.moneda if a else moneda)
    fecha = _CampoFecha(page, "Fecha", a.fecha if a else date.today())
    ubicacion_f = _texto("Dónde está guardado", a.ubicacion if a else "", hint_text="Ej: Banco Galicia, Mercado Pago, Ualá, efectivo")
    obs_f = _texto("Observaciones", a.observaciones if a else "", multiline=True, min_lines=2, max_lines=4)
    debitar = _check_cuenta("Descontar de la plata de la app")

    def guardar():
        monto = Money.from_decimal(parse_decimal(monto_f.value, "Monto"), moneda_dd.value)
        datos = Ahorro(a.id if a else None, monto, fecha.valor or date.today(), ubicacion_f.value or "", obs_f.value or "")
        if a:
            datos.entrada_mov_id, datos.estado = a.entrada_mov_id, a.estado
            service.editar_ahorro(datos)
        else:
            service.registrar_ahorro(datos, debitar=bool(debitar.value))
        on_listo()

    controles = [ft.Row([monto_f, moneda_dd], spacing=10), fecha.control, ubicacion_f, obs_f]
    if not a:
        controles.append(debitar)
    _dialogo(page, "Editar ahorro" if a else "Nuevo ahorro", controles, guardar)


# --- Acciones y Bonos/Lecap ---

def form_titulo(page: ft.Page, service: InversionService, tipo: TipoTitulo, moneda: Moneda, on_listo: Callable[[], None], existente: Titulo | None = None):
    t = existente
    es_accion = tipo == TipoTitulo.ACCION
    etiqueta_pagos = "Meses en que paga dividendos" if es_accion else "Meses en que paga renta"

    estado_dd = _dropdown("Estado", [(EstadoInversion.VIGENTE.value, "En posesión"), (EstadoInversion.FINALIZADA.value, "Finalizada")],
                          EstadoInversion.VIGENTE.value, expand=True)
    simbolo_f = _texto("Símbolo", t.simbolo if t else "", hint_text="Ej: NVDA" if es_accion else "Ej: AL30, S31O5", capitalization=ft.TextCapitalization.CHARACTERS, expand=True, autofocus=True)
    nombre_f = _texto("Nombre", t.nombre if t else "", hint_text="Ej: Nvidia Corp." if es_accion else "Ej: Bono Rep. Argentina 2030")
    tipo_empresa_f = _texto("Tipo de empresa", t.tipo_empresa if t else "", hint_text="Ej: Tecnología", expand=True)
    plazo_dd = _dropdown_plazo(t.plazo if t else Plazo.LARGO)
    broker_f = _texto("Broker", t.broker if t else "", hint_text="Ej: IOL", expand=True)
    transaccion_f = _texto("Transacción", t.transaccion if t else "", hint_text="Ej: 129861459", expand=True)
    fecha = _CampoFecha(page, "Fecha de suscripción", t.fecha_suscripcion if t else date.today())
    cantidad_f = _texto("Cantidad", fmt_decimal(t.cantidad) if t else "", hint_text="Ej: 1", expand=True)
    precio_f = _texto("Precio de compra (por unidad)", fmt_decimal(t.precio_compra.amount) if t else "", hint_text="Ej: 1500", expand=True)
    moneda_dd = _dropdown_moneda(t.precio_compra.moneda if t else moneda)
    meses = _SelectorMeses(page, t.meses_pago if t else [])
    obs_f = _texto("Observaciones", t.observaciones if t else "", multiline=True, min_lines=2, max_lines=4)
    debitar = _check_cuenta("Descontar la compra de la plata de la app")

    # Si se carga como finalizada, se piden los datos de la venta.
    fecha_venta = _CampoFecha(page, "Fecha de venta", date.today())
    precio_venta_f = _texto("Precio de venta (por unidad)", expand=True)
    acreditar = _check_cuenta("Sumar la venta a la plata de la app")
    bloque_venta = ft.Column([_subtitulo("Venta"), ft.Row([fecha_venta.control, precio_venta_f], spacing=10), acreditar], spacing=10, visible=False)

    def on_estado(_e):
        bloque_venta.visible = estado_dd.value == EstadoInversion.FINALIZADA.value
        page.update()

    estado_dd.on_select = on_estado

    def guardar():
        cantidad = parse_decimal(cantidad_f.value, "Cantidad")
        precio = Money.from_decimal(parse_decimal(precio_f.value, "Precio de compra"), moneda_dd.value)
        datos = Titulo(
            id=t.id if t else None, tipo=tipo, simbolo=simbolo_f.value or "", fecha_suscripcion=fecha.valor or date.today(),
            cantidad=cantidad, precio_compra=precio, nombre=nombre_f.value or "", tipo_empresa=tipo_empresa_f.value or "",
            plazo=Plazo(plazo_dd.value), broker=broker_f.value or "", transaccion=transaccion_f.value or "",
            meses_pago=sorted(meses.seleccionados), observaciones=obs_f.value or "",
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
                service.finalizar_titulo(creado.id, fecha_venta.valor or date.today(), venta, acreditar=bool(acreditar.value))
        on_listo()

    controles = []
    if not t:
        controles.append(estado_dd)
    controles += [
        ft.Row([simbolo_f, plazo_dd], spacing=10),
        nombre_f,
        ft.Row([tipo_empresa_f, broker_f], spacing=10),
        ft.Row([transaccion_f, fecha.control], spacing=10),
        ft.Row([cantidad_f, precio_f, moneda_dd], spacing=10),
        _subtitulo(etiqueta_pagos + " (opcional)"),
        meses.control,
        obs_f,
    ]
    if not t:
        controles += [debitar, bloque_venta]
    nombre_tipo = "acción" if es_accion else "bono / Lecap"
    _dialogo(page, f"Editar {nombre_tipo}" if t else f"Nueva {nombre_tipo}" if es_accion else f"Nuevo {nombre_tipo}", controles, guardar)


# --- FCI ---

def form_fci(page: ft.Page, service: InversionService, moneda: Moneda, on_listo: Callable[[], None], existente: Fci | None = None):
    f = existente
    estado_dd = _dropdown("Estado", [(EstadoInversion.VIGENTE.value, "Vigente"), (EstadoInversion.FINALIZADA.value, "Rescatado")],
                          EstadoInversion.VIGENTE.value, expand=True)
    simbolo_f = _texto("Símbolo", f.simbolo if f else "", capitalization=ft.TextCapitalization.CHARACTERS, expand=True)
    nombre_f = _texto("Nombre del fondo", f.nombre if f else "", autofocus=True)
    plazo_dd = _dropdown_plazo(f.plazo if f else Plazo.CORTO)
    broker_f = _texto("Broker", f.broker if f else "", expand=True)
    transaccion_f = _texto("Transacción", f.transaccion if f else "", expand=True)
    fecha = _CampoFecha(page, "Fecha de suscripción", f.fecha_suscripcion if f else date.today())
    fecha_rescate = _CampoFecha(page, "Fecha de rescate", f.fecha_rescate if f else None, opcional=True)
    monto_f = _texto("Monto", fmt_decimal(f.monto.amount) if f else "", expand=True)
    moneda_dd = _dropdown_moneda(f.monto.moneda if f else moneda)
    tna_f = _texto("TNA (%)", fmt_decimal(f.tna) if f and f.tna is not None else "", hint_text="Ej: 35,5", expand=True)
    obs_f = _texto("Observaciones", f.observaciones if f else "", multiline=True, min_lines=2, max_lines=4)
    debitar = _check_cuenta("Descontar de la plata de la app")

    monto_rescate_f = _texto("Monto rescatado", expand=True)
    acreditar = _check_cuenta("Sumar el rescate a la plata de la app")
    bloque_rescate = ft.Column([_subtitulo("Rescate (se usa la fecha de rescate de arriba)"), monto_rescate_f, acreditar], spacing=10, visible=False)

    def on_estado(_e):
        bloque_rescate.visible = estado_dd.value == EstadoInversion.FINALIZADA.value
        page.update()

    estado_dd.on_select = on_estado

    def guardar():
        tna = parse_decimal(tna_f.value, "TNA") if (tna_f.value or "").strip() else None
        datos = Fci(
            id=f.id if f else None, nombre=nombre_f.value or "", fecha_suscripcion=fecha.valor or date.today(),
            monto=Money.from_decimal(parse_decimal(monto_f.value, "Monto"), moneda_dd.value), simbolo=simbolo_f.value or "",
            plazo=Plazo(plazo_dd.value), broker=broker_f.value or "", transaccion=transaccion_f.value or "",
            fecha_rescate=fecha_rescate.valor, tna=tna, observaciones=obs_f.value or "",
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
                service.rescatar_fci(creado.id, fecha_rescate.valor or date.today(), rescate, acreditar=bool(acreditar.value))
        on_listo()

    controles = [estado_dd] if not f else []
    controles += [
        nombre_f,
        ft.Row([simbolo_f, plazo_dd], spacing=10),
        ft.Row([broker_f, transaccion_f], spacing=10),
        ft.Row([fecha.control, fecha_rescate.control], spacing=10),
        ft.Row([monto_f, moneda_dd, tna_f], spacing=10),
        obs_f,
    ]
    if not f:
        controles += [debitar, bloque_rescate]
    _dialogo(page, "Editar FCI" if f else "Nuevo FCI", controles, guardar)


# --- Crypto ---

def form_crypto(page: ft.Page, service: InversionService, moneda: Moneda, on_listo: Callable[[], None], existente: OperacionCryptoRegistro | None = None):
    op = existente
    fecha = _CampoFecha(page, "Fecha", op.fecha if op else date.today())
    operacion_dd = _dropdown("Operación", [(OperacionCrypto.COMPRA.value, "Compra"), (OperacionCrypto.VENTA.value, "Venta")],
                             (op.operacion if op else OperacionCrypto.COMPRA).value, expand=True)
    activo_f = _texto("Criptomoneda", op.activo if op else "", hint_text="Ej: USDT, BTC", capitalization=ft.TextCapitalization.CHARACTERS, expand=True, autofocus=True)
    monto_f = _texto("Monto", fmt_decimal(op.monto.amount) if op else "", expand=True)
    moneda_dd = _dropdown_moneda(op.monto.moneda if op else moneda)
    precio_f = _texto("Precio unitario", fmt_decimal(op.precio_unitario) if op else "", hint_text="Precio de 1 unidad", expand=True)
    cantidad_f = _texto("Cantidad", fmt_decimal(op.cantidad) if op else "", expand=True)
    obs_f = _texto("Observaciones", op.observaciones if op else "", multiline=True, min_lines=2, max_lines=4)
    cuenta = _check_cuenta("Descontar de la plata de la app")

    def on_operacion(_e):
        es_compra = operacion_dd.value == OperacionCrypto.COMPRA.value
        cuenta.label = "Descontar de la plata de la app" if es_compra else "Sumar a la plata de la app"
        page.update()

    operacion_dd.on_select = on_operacion

    def guardar():
        datos = OperacionCryptoRegistro(
            id=op.id if op else None, fecha=fecha.valor or date.today(), operacion=OperacionCrypto(operacion_dd.value),
            activo=activo_f.value or "", monto=Money.from_decimal(parse_decimal(monto_f.value, "Monto"), moneda_dd.value),
            precio_unitario=parse_decimal(precio_f.value, "Precio unitario"), cantidad=parse_decimal(cantidad_f.value, "Cantidad"),
            observaciones=obs_f.value or "",
        )
        if op:
            datos.mov_id = op.mov_id
            service.editar_crypto(datos)
        else:
            service.registrar_crypto(datos, operar_con_cuenta=bool(cuenta.value))
        on_listo()

    controles = [
        ft.Row([operacion_dd, fecha.control], spacing=10),
        ft.Row([activo_f, moneda_dd], spacing=10),
        ft.Row([monto_f, precio_f, cantidad_f], spacing=10),
        obs_f,
    ]
    if not op:
        controles.append(cuenta)
    _dialogo(page, "Editar operación crypto" if op else "Nueva operación crypto", controles, guardar)


# --- Finalizar / rescatar / retirar ---

def form_salida(
    page: ft.Page, titulo: str, etiqueta_monto: str, moneda: Moneda, costo: Money,
    on_confirmar: Callable[[date, Money, bool], None], cantidad: Decimal | None = None,
):
    """Si se pasa `cantidad`, el monto ingresado es por unidad y se multiplica."""
    fecha = _CampoFecha(page, "Fecha", date.today())
    monto_f = _texto(etiqueta_monto, autofocus=True)
    resultado = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    acreditar = _check_cuenta("Sumar a la plata de la app")

    def total() -> Money:
        valor = parse_decimal(monto_f.value, etiqueta_monto)
        return Money.from_decimal(valor * cantidad if cantidad is not None else valor, moneda)

    def on_change(_e):
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

    monto_f.on_change = on_change

    def guardar():
        on_confirmar(fecha.valor or date.today(), total(), bool(acreditar.value))

    _dialogo(
        page, titulo,
        [ft.Text(f"Costo: {costo.formatted()} {moneda.value}", size=12, color=theme.TEXT_SECONDARY), ft.Row([fecha.control, monto_f], spacing=10), resultado, acreditar],
        guardar, texto_boton="Confirmar",
    )


def confirmar_eliminar(page: ft.Page, descripcion: str, on_ok: Callable[[], None]):
    def ok(_e):
        page.pop_dialog()
        on_ok()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Text("Eliminar"),
        content=ft.Text(f"¿Seguro que querés eliminar {descripcion}? Si generó movimientos en la plata de la app, también se borran."),
        actions=[
            theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
            theme.primary_button("Eliminar", ok, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
        ],
    ))
