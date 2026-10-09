"""Compra / venta de dólares en el celular: se descuenta de una moneda y se
acredita en la otra. Se abre desde el Resumen y pide lo mismo que en
escritorio: operación, fecha, cantidad y cotización."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.money import Money, Moneda
from .. import theme
from ..desktop import components
from . import componentes as mc


def formulario_cambio(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    operacion_sel = mc.selector([("comprar", "Comprar USD"), ("vender", "Vender USD")], "comprar")
    fila_fecha, fecha_elegida = mc.selector_fecha(page, "Fecha", date.today())
    cantidad_f = mc.campo("Cantidad de USD", keyboard_type=ft.KeyboardType.NUMBER, text_size=20, autofocus=True)
    cotizacion_f = mc.campo("Cotización (ARS por USD 1)", keyboard_type=ft.KeyboardType.NUMBER)
    cuenta = ft.Text("", size=13, weight=ft.FontWeight.W_600, color=theme.CAMBIO_COLOR, visible=False)
    error, mostrar_error = mc.texto_error(page)

    def leer() -> tuple[Money, Money]:
        """La cantidad de dolares y la cotizacion (en pesos por dolar)."""
        cantidad = components.parse_monto(cantidad_f.value, Moneda.USD, "Cantidad de dólares")
        cotizacion = components.parse_monto(cotizacion_f.value, Moneda.ARS, "Cotización")
        if cantidad.cents <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if cotizacion.cents <= 0:
            raise ValueError("La cotización debe ser mayor a cero")
        return cantidad, cotizacion

    def movimiento(cantidad: Money, cotizacion: Money) -> str:
        total = Money.from_decimal(cantidad.amount * cotizacion.amount, Moneda.ARS)
        if mc.elegido(operacion_sel) == "comprar":
            return f"Se van a descontar {total.formatted()} y se van a sumar {cantidad.formatted()}."
        return f"Se van a descontar {cantidad.formatted()} y se van a sumar {total.formatted()}."

    def actualizar_cuenta(_e=None):
        try:
            cuenta.value = movimiento(*leer())
        except (ValueError, ArithmeticError):
            cuenta.value = ""
        cuenta.visible = bool(cuenta.value)
        page.update()

    cantidad_f.on_change = cotizacion_f.on_change = operacion_sel.on_change = actualizar_cuenta

    def continuar(_e):
        try:
            cantidad, cotizacion = leer()
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        comprar = mc.elegido(operacion_sel) == "comprar"

        def aceptar():
            operar = servicios.cambio.comprar_dolares if comprar else servicios.cambio.vender_dolares
            try:
                operar(fecha_elegida(), cantidad, cotizacion.amount)
            except (ValueError, ArithmeticError) as exc:
                mostrar_error(exc)
                return
            nav.volver()
            nav.avisar("Compra de dólares registrada" if comprar else "Venta de dólares registrada")

        mc.confirmar(page, "Confirmar operación",
                     f"¿Confirmás {'comprar' if comprar else 'vender'} {cantidad.formatted()} a {cotizacion.formatted()} cada uno?\n\n"
                     f"{movimiento(cantidad, cotizacion)}", "Sí, confirmar", theme.CAMBIO_COLOR, "check_rounded", aceptar)

    return mc.pantalla([
        ft.Row([operacion_sel]),
        fila_fecha,
        cantidad_f,
        cotizacion_f,
        cuenta,
        mc.nota("Queda registrado como dos movimientos: lo que entregás y lo que recibís."),
        error,
        mc.boton_ancho("Continuar", continuar, theme.CAMBIO_COLOR, ft.Icons.ARROW_FORWARD_ROUNDED),
    ])
