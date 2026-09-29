"""Escenas del manual: cada una lleva la app a un estado y saca capturas.
Cada marca es (control, titulo, explicacion): el manual numera las flechas en
ese orden y muestra el titulo y la explicacion debajo de la figura."""
from __future__ import annotations

import flet as ft

from motor import Motor

USUARIO, CLAVE = "ana", "ana12345"
TF, DD = ft.TextField, ft.Dropdown


def es_icono(icono):
    return lambda c: isinstance(c, ft.IconButton) and c.icon == icono


async def nav(m: Motor, seccion: str):
    await m.click(seccion, ft.Text, espera=1.5)


# ------------------------------------------------------------------ acceso
async def acceso(m: Motor):
    await m.click("¿Olvidaste tu contraseña?", espera=1.2)
    await m.escribir("Tu usuario", USUARIO)
    await m.captura("recuperar_1", [
        (m.control("Tu usuario", TF), "Tu usuario", "el nombre con el que entrás a Kakeibo."),
        (m.control("Continuar"), "Continuar", "pasa a la pregunta de seguridad que elegiste al crear el usuario."),
    ], pie="Recuperar la contraseña: paso 1.", recorte="marcas")
    await m.click("Continuar", espera=1.2)
    await m.escribir("Tu respuesta", "Toby")
    await m.escribir("Nueva contraseña", "nueva1234")
    await m.escribir("Confirmar nueva contraseña", "nueva1234")
    await m.captura("recuperar_2", [
        (m.control("Tu respuesta", TF), "Tu respuesta", "la respuesta a tu pregunta de seguridad (no importan mayúsculas ni espacios)."),
        (m.control("Nueva contraseña", TF), "Nueva contraseña", "escribila dos veces; tiene que tener al menos 6 caracteres."),
        (m.control("Restablecer contraseña"), "Restablecer contraseña", "guarda la contraseña nueva."),
    ], pie="Recuperar la contraseña: paso 2.", recorte="marcas")
    await m.click("Volver a iniciar sesión", espera=1.2)

    await m.click("Crear usuario nuevo", espera=1.2)
    await m.captura("crear_usuario", [
        (m.control("Usuario", TF), "Usuario y contraseña", "los datos con los que vas a entrar."),
        (m.control("Pregunta de seguridad"), "Pregunta de seguridad", "elegí una y escribí la respuesta: sirve para recuperar la contraseña si te la olvidás."),
        (m.control("Crear cuenta e ingresar"), "Crear cuenta e ingresar", "crea el usuario y entra a la app."),
    ], pie="Crear un usuario nuevo.", recorte="marcas")
    await m.click("Volver a iniciar sesión", espera=1.2)

    await m.click("Eliminar un usuario", espera=1.2)
    await m.captura("eliminar_usuario", [
        (m.control("Usuario a eliminar"), "Usuario a eliminar", "elegí de la lista qué usuario borrar."),
        (m.control("Contraseña de ese usuario", TF), "Contraseña", "hace falta la contraseña de ese usuario para borrarlo."),
    ], pie="Eliminar un usuario (los datos de gastos no se borran: son de la instalación).", recorte="marcas")
    await m.click("Cancelar", ft.TextButton, espera=1.2)

    await m.escribir("Usuario", USUARIO)
    await m.escribir("Contraseña", CLAVE)
    await m.captura("login", [
        (m.control("Usuario", TF), "Usuario", "tu nombre de usuario."),
        (m.control("Contraseña", TF), "Contraseña", "el ojo de la derecha muestra lo que escribiste."),
        (m.control("Ingresar"), "Ingresar", "entra a la app (también con Enter)."),
        (m.control("¿Olvidaste tu contraseña?"), "¿Olvidaste tu contraseña?", "para crear una nueva con tu pregunta de seguridad."),
        (m.control("Crear usuario nuevo"), "Crear usuario nuevo / Eliminar un usuario", "para manejar los usuarios de esta computadora."),
    ], pie="La pantalla para iniciar sesión.", recorte="marcas")
    await m.click("Ingresar", espera=3)


# ------------------------------------------------------------------ pantalla principal
async def principal(m: Motor):
    await m.captura("principal", [
        (m.control("Movimientos", ft.Text), "Menú de secciones", "cada opción abre una sección; la elegida queda resaltada."),
        (m.control("Vencimientos de septiembre", ft.Text), "Aviso de vencimientos", "lo que vence este mes y todavía no pagaste; aparece al entrar."),
        (m.por_tooltip("Minimizar"), "Minimizar", "deja solo el título del aviso, sin tapar la pantalla."),
        (m.por_tooltip("Cerrar"), "Cerrar", "cierra el aviso hasta la próxima vez que entres."),
        (m.control("Hacer backup"), "Hacer backup", "guarda una copia de todos tus datos (ver capítulo de copias de seguridad)."),
        (m.control("ana", ft.Text), "Tu usuario", "tocándolo podés pasar a otro usuario."),
        (m.control("Cerrar sesión"), "Cerrar sesión", "vuelve a la pantalla de inicio de sesión."),
    ], pie="La pantalla principal, con el aviso de vencimientos del mes.")
    await m.click(cond=lambda c: getattr(c, "tooltip", None) == "Cerrar", espera=1)


# ------------------------------------------------------------------ resumen
async def resumen(m: Motor):
    await m.captura("resumen_arriba", [
        (m.control("Ingresos", ft.Text), "Ingresos y egresos", "todo lo que entró y salió, separado en pesos (ARS) y dólares (USD)."),
        (m.control("Balance", ft.Text), "Balance", "ingresos menos egresos."),
        (m.control("Gastos por categoría", ft.Text), "Gastos por categoría", "la torta muestra en qué se va la plata; con ARS / USD elegís la moneda."),
        (m.control("Pendiente en tarjetas", ft.Text, exacto=False), "Pendiente en tarjetas", "lo que vence este mes en cada tarjeta (ver la figura siguiente)."),
    ], pie="Resumen general, parte de arriba.")
    await m.desplazar("Resumen general", 420)
    await m.captura("resumen_abajo", [
        (m.control("Pendiente en tarjetas", ft.Text, exacto=False), "Pendiente en tarjetas · mes",
         "solo lo que vence este mes: cuotas, compras en 1 pago y débitos automáticos, por tarjeta y por moneda. (Nuevo en 1.3)"),
        (m.control("Préstamos pendientes", ft.Text), "Préstamos pendientes", "lo que falta pagar en pesos y en dólares."),
        (m.control("Próximas cuotas", ft.Text), "Próximas cuotas", "cada préstamo activo con su próxima cuota, cuándo vence y el monto. (Nuevo en 1.3)"),
        (m.control("Nueva operación"), "Compra / venta de dólares", "registra una compra o venta de dólares."),
    ], pie="Resumen general, parte de abajo.")
    await m.desplazar("Resumen general", -1 if False else 900)
    await m.captura("resumen_pagado", [
        (m.control("Pagado este mes", ft.Text), "Pagado este mes", "gastos fijos, cuotas de tarjeta y de préstamos que ya pagaste este mes, con el total."),
    ], pie="Lo pagado en el mes.")
    await m.click("Nueva operación", espera=1)
    await m.escribir("Cantidad de USD", "200", dialogo=True)
    await m.escribir("Cotización (ARS por USD 1)", "1365", dialogo=True)
    await m.captura("dolares", [
        (m.control(tipo=ft.SegmentedButton, dialogo=True), "Comprar o vender", "elegí si comprás o vendés dólares."),
        (m.control("Cantidad de USD", TF, dialogo=True), "Cantidad de USD", "cuántos dólares."),
        (m.control("Cotización (ARS por USD 1)", TF, dialogo=True), "Cotización", "cuántos pesos vale cada dólar."),
        (m.control("Continuar", dialogo=True), "Continuar", "muestra qué se descuenta y qué se suma antes de confirmar."),
    ], pie="Compra o venta de dólares.", solo_dialogo=True)
    await m.click("Continuar", dialogo=True, espera=1)
    await m.captura("dolares_confirmar", [
        (m.control("Sí, confirmar", dialogo=True), "Sí, confirmar", "registra los dos movimientos: uno en cada moneda."),
    ], pie="Confirmación de la operación.", solo_dialogo=True)
    await m.cerrar_dialogos()


# ------------------------------------------------------------------ movimientos
async def movimientos(m: Motor):
    await nav(m, "Movimientos")
    await m.captura("movimientos", [
        (m.control("Nuevo movimiento"), "Nuevo movimiento", "carga un ingreso o un egreso."),
        (m.control("Lámparas LED", ft.Text), "Detalle", "lo que escribiste en el detalle se ve debajo del concepto. (Nuevo en 1.3)"),
        (m.control(cond=es_icono(ft.Icons.EDIT_ROUNDED)), "Editar", "corrige el movimiento."),
        (m.control(cond=es_icono(ft.Icons.DELETE_OUTLINE_ROUNDED)), "Eliminar", "lo borra (pide confirmación)."),
    ], pie="La lista de movimientos.")
    await m.click("Nuevo movimiento", espera=1)
    await m.segmento("egreso")
    await m.escribir("Concepto", "Farmacia", dialogo=True)
    await m.escribir("Detalle (opcional)", "Remedios para la gripe", dialogo=True)
    await m.escribir("Monto", "23500,50", dialogo=True)
    await m.captura("movimiento_nuevo", [
        (m.control(tipo=ft.SegmentedButton, dialogo=True), "Ingreso o egreso", "qué tipo de movimiento es."),
        (m.control("Concepto", TF, dialogo=True), "Concepto y detalle", "qué fue; el detalle es opcional."),
        (m.control("Monto", TF, dialogo=True), "Monto", "con coma o con punto para los decimales (23500,50 o 23500.50)."),
        (m.control("Moneda", DD, dialogo=True), "Moneda", "pesos (ARS) o dólares (USD)."),
        (m.control("Categoría", DD, dialogo=True), "Categoría", "para ver en qué se va la plata; con + creás una nueva."),
        (m.control("Guardar", dialogo=True), "Guardar", "registra el movimiento."),
    ], pie="Cargar un movimiento.", solo_dialogo=True)
    await m.escribir("Monto", "doce mil", dialogo=True)
    await m.click("Guardar", dialogo=True, espera=1)
    await m.captura("movimiento_error", [
        (m.control("Monto: ", ft.Text, exacto=False, dialogo=True), "Aviso de error",
         "si algo está mal escrito, el aviso aparece debajo del título de la ventana, siempre a la vista. (Nuevo en 1.3)"),
    ], pie="Si el monto tiene letras, la app avisa qué corregir.", solo_dialogo=True)
    await m.click(cond=lambda c: getattr(c, "tooltip", None) == "Nueva categoría", dialogo=True, espera=0.8)
    await m.escribir("Nombre de la categoría nueva", "Regalos", dialogo=True)
    await m.captura("categoria_nueva", [
        (m.control("Nombre de la categoría nueva", TF, dialogo=True), "Categoría nueva", "escribí el nombre."),
        (m.por_tooltip("Crear categoría", dialogo=True), "Crear", "la crea y la deja elegida."),
    ], pie="Crear una categoría desde el formulario.", solo_dialogo=True)
    await m.cerrar_dialogos()


# ------------------------------------------------------------------ gastos fijos
async def gastos_fijos(m: Motor):
    await nav(m, "Gastos fijos")
    await m.captura("gastos_fijos", [
        (m.control("Nuevo gasto fijo"), "Nuevo gasto fijo", "alquiler, servicios, suscripciones: se cargan una vez."),
        (m.control("Estado", DD), "Filtros", "por estado del mes, débito automático y categoría. (Nuevo en 1.3)"),
        (m.control("Ordenar por", DD), "Ordenar por", "vencimiento, monto mayor o menor, o alfabético. (Nuevo en 1.3)"),
        (m.control("Registrar pago"), "Registrar pago", "registra el pago de este mes (crea el egreso)."),
        (m.control("Pagado este mes", ft.Text), "Pagado este mes", "aparece cuando ya registraste el pago del mes."),
        (m.control("Débito · ", ft.Text, exacto=False), "Débito automático", "se paga con una tarjeta; tocando la etiqueta lo cambiás o lo quitás."),
        (m.control("Editar", ft.TextButton), "Editar", "cambia el monto, el vencimiento o el débito automático."),
    ], pie="Gastos fijos: fichas compactas, filtros y orden.")
    await m.click("Nuevo gasto fijo", espera=1)
    await m.escribir("Concepto (ej: Alquiler, Luz, Netflix)", "Gas", dialogo=True)
    await m.escribir("Detalle (opcional)", "Metrogas", dialogo=True)
    await m.escribir("Monto", "18000", dialogo=True)
    await m.escribir("Día de vencimiento (1-28)", "15", dialogo=True)
    await m.captura("gasto_fijo_nuevo", [
        (m.control("Concepto (ej: Alquiler, Luz, Netflix)", TF, dialogo=True), "Concepto y detalle", "qué gasto es."),
        (m.control("Monto", TF, dialogo=True), "Monto y moneda", "cuánto se paga por mes."),
        (m.control("Día de vencimiento (1-28)", TF, dialogo=True), "Día de vencimiento", "qué día del mes vence."),
        (m.control("Se paga con débito automático de tarjeta", ft.Checkbox, dialogo=True), "Débito automático", "tildalo si se paga solo con una tarjeta (ver la figura siguiente)."),
    ], pie="Nuevo gasto fijo, sin débito automático.", solo_dialogo=True)
    await m.tildar("Se paga con débito automático de tarjeta", True, dialogo=True)
    await m.elegir("¿A qué tarjeta se debita?", "Visa Galicia", dialogo=True)
    await m.captura("gasto_fijo_debito", [
        (m.control("¿A qué tarjeta se debita?", DD, dialogo=True), "Tarjeta", "a qué tarjeta se debita."),
        (m.control("El vencimiento es el de la tarjeta", ft.Text, exacto=False, dialogo=True), "Vencimiento",
         "ya no se carga el día: vence cuando vence la tarjeta, y lo informa. (Nuevo en 1.3)"),
        (m.control("Se paga con débito automático de tarjeta", ft.Checkbox, dialogo=True), "Quitar el débito", "destildando la casilla vuelve el campo del día."),
    ], pie="Con débito automático, el vencimiento es el de la tarjeta.", solo_dialogo=True)
    await m.cerrar_dialogos()
    await m.click("Registrar pago", espera=1)
    await m.captura("gasto_fijo_pago", [
        (m.control("Sí, registrar", dialogo=True), "Sí, registrar", "crea el egreso del mes."),
    ], pie="Confirmación del pago del mes.", solo_dialogo=True)
    await m.cerrar_dialogos()
    await m.elegir("Estado", "finalizados")
    await m.captura("gastos_fijos_filtro", [
        (m.control("Estado", DD), "Estado: Finalizados", "muestra solo los que ya pagaste este mes."),
        (m.control("Quitar filtros"), "Quitar filtros", "vuelve a mostrar todos."),
        (m.control("Mostrando", ft.Text, exacto=False), "Contador", "cuántos se ven de cuántos hay."),
    ], pie="Filtrar los gastos fijos.")
    await m.click("Quitar filtros", espera=1)


# ------------------------------------------------------------------ tarjetas
async def tarjetas(m: Motor):
    await nav(m, "Tarjetas")
    await m.click("Visa Galicia", ft.Text, espera=1.2)
    await m.captura("tarjetas", [
        (m.control("Visa Galicia", ft.Text), "La tarjeta", "tocándola se ven sus compras; la elegida tiene borde."),
        (m.control("Pendiente USD:", ft.Text, exacto=False), "Pendiente por moneda", "una tarjeta opera en pesos y en dólares; cada moneda por separado. (Nuevo en 1.3)"),
        (m.control("Cierra el", ft.Text, exacto=False, n=1), "Cierre y vencimiento", "los días de cierre y vencimiento del resumen. (Nuevo en 1.3)"),
        (m.por_tooltip("Editar tarjeta", n=2), "Editar tarjeta", "cambia sus datos o la elimina."),
        (m.control("Pagar tarjeta (mes)"), "Pagar tarjeta (mes)", "marca pagado todo lo que vence este mes."),
        (m.control("Nueva compra"), "Nueva compra", "carga una compra con tarjeta."),
        (m.control("Nueva tarjeta"), "Nueva tarjeta", "agrega una tarjeta."),
    ], pie="La sección Tarjetas.")
    await m.desplazar("Débitos automáticos de este mes", 520)
    await m.captura("tarjetas_compras", [
        (m.control("Heladera", ft.Text), "La compra", "concepto y monto total."),
        (m.control("Samsung no frost 360 L", ft.Text), "Detalle", "lo que escribiste al cargarla. (Nuevo en 1.3)"),
        (m.control("Cuota 4 de 6", ft.Text), "Cuota actual", "en qué cuota vas; abajo, el valor de la cuota, cuántas restan y el pendiente."),
        (m.en_ficha("Heladera", "Pagar cuota 4"), "Pagar cuota", "paga solo esa cuota."),
        (m.en_ficha("Heladera", "Editar", ft.TextButton), "Editar", "corrige cualquier dato de la compra (ver más adelante)."),
    ], pie="Las compras de la tarjeta, en fichas compactas.")
    await m.desplazar("Débitos automáticos de este mes", 0)

    await m.click("Nueva tarjeta", espera=1)
    await m.escribir("Nombre (ej: Visa Galicia)", "Visa Nación", dialogo=True)
    await m.escribir("Banco", "Banco Nación", dialogo=True)
    await m.escribir("Últimos 4 dígitos (opcional)", "5511", dialogo=True)
    await m.escribir("Día de cierre", "22", dialogo=True)
    await m.escribir("Día de vencimiento", "3", dialogo=True)
    await m.captura("tarjeta_nueva", [
        (m.control("Nombre (ej: Visa Galicia)", TF, dialogo=True), "Nombre y banco", "para reconocerla."),
        (m.control("Opera en pesos y en dólares", ft.Text, exacto=False, dialogo=True), "Pesos y dólares", "no se elige moneda: se elige en cada compra. (Nuevo en 1.3)"),
        (m.control("Día de cierre", TF, dialogo=True), "Día de cierre", "opcional. (Nuevo en 1.3)"),
        (m.control("Día de vencimiento", TF, dialogo=True), "Día de vencimiento", "opcional; lo usan los débitos automáticos. (Nuevo en 1.3)"),
        (m.control("Crear", dialogo=True), "Crear", "guarda la tarjeta."),
    ], pie="Nueva tarjeta.", solo_dialogo=True)
    await m.cerrar_dialogos()

    await m.click("Nueva compra", espera=1)
    await m.escribir("Concepto", "Auriculares", dialogo=True)
    await m.escribir("Detalle (opcional)", "Sony, compra online", dialogo=True)
    await m.escribir("Monto total", "85", dialogo=True)
    await m.elegir("Moneda", "USD", dialogo=True)
    await m.captura("compra_1pago", [
        (m.control("Tarjeta", DD, dialogo=True), "Tarjeta", "en qué tarjeta."),
        (m.control("Monto total", TF, dialogo=True), "Monto", "con coma o punto para los decimales."),
        (m.control("Moneda", DD, dialogo=True), "Moneda", "cada compra elige si es en pesos o en dólares. (Nuevo en 1.3)"),
        (m.control(tipo=ft.SegmentedButton, dialogo=True), "1 pago o en cuotas", "cómo la pagaste."),
        (m.control("La tarjeta ya cerró el resumen de este mes", ft.Checkbox, dialogo=True), "Resumen cerrado", "tildalo si compraste después del cierre: todo se corre un mes."),
    ], pie="Nueva compra en 1 pago, en dólares.", solo_dialogo=True)
    await m.elegir("Moneda", "ARS", dialogo=True)
    await m.segmento("cuotas", n=0)
    await m.segmento("cuota", n=0)
    await m.escribir("Valor de cada cuota", "50000", dialogo=True)
    await m.escribir("Cantidad de cuotas", "6", dialogo=True)
    await m.desplazar("Concepto", 400, dialogo=True, exacto=True)
    await m.captura("compra_cuotas", [
        (m.control(tipo=ft.SegmentedButton, dialogo=True, cond=lambda s: any(x.value == "cuota" for x in s.segments)),
         "Monto total o valor de la cuota", "elegí qué dato tenés a mano. (Nuevo en 1.3)"),
        (m.control("Cantidad de cuotas", TF, dialogo=True), "Cantidad de cuotas", "en cuántas cuotas."),
        (m.control("¿En qué cuota empezás?", TF, dialogo=True), "¿En qué cuota empezás?", "si ya venías pagando, las anteriores quedan pagadas."),
        (m.control("Total de la compra", ft.Text, exacto=False, dialogo=True), "La cuenta", "el total se calcula solo: cuota × cantidad."),
    ], pie="Compra en cuotas cargando el valor de la cuota.", solo_dialogo=True)
    await m.cerrar_dialogos()

    await m.click("Pagar tarjeta (mes)", espera=1)
    await m.captura("tarjeta_pagar_mes", [
        (m.control("Sí, pagar todo", dialogo=True), "Sí, pagar todo", "marca pagadas las cuotas y los débitos que vencen este mes."),
    ], pie="Pagar la tarjeta del mes.", solo_dialogo=True)
    await m.cerrar_dialogos()

    await m.desplazar("Débitos automáticos de este mes", 520)
    await m.click_en_ficha("Heladera", "Editar", ft.TextButton)
    await m.escribir("Monto total", "1260000", dialogo=True)
    await m.escribir("Cantidad de cuotas", "9", dialogo=True)
    await m.captura("compra_editar", [
        (m.control("Tarjeta", DD, dialogo=True), "Todo se puede cambiar", "tarjeta, fecha, concepto, detalle, monto, moneda y cuotas. (Nuevo en 1.3)"),
        (m.control("Cuotas ya pagadas", TF, dialogo=True), "Cuotas ya pagadas", "las pagadas no se modifican: se recalculan solo las que faltan."),
        (m.control("Guardar", dialogo=True), "Guardar", "antes de guardar muestra qué cambia."),
    ], pie="Editar una compra.", solo_dialogo=True)
    await m.click("Guardar", dialogo=True, espera=1)
    await m.captura("compra_editar_confirmar", [
        (m.control("Se van a hacer estos cambios:", ft.Text, dialogo=True), "Lo que cambia", "cada dato con su valor anterior y el nuevo."),
        (m.control("no se modifican", ft.Text, exacto=False, dialogo=True), "Cuotas pagadas", "quedan como estaban."),
        (m.control("se reparte en", ft.Text, exacto=False, dialogo=True), "Cuotas que faltan", "cómo se reparte lo que falta pagar."),
        (m.control("Sí, guardar", dialogo=True), "Sí, guardar", "aplica los cambios; con Volver a editar seguís corrigiendo."),
    ], pie="Confirmación antes de guardar los cambios.", solo_dialogo=True)
    await m.cerrar_dialogos()
    await m.desplazar("Débitos automáticos de este mes", 0)


# ------------------------------------------------------------------ prestamos
async def prestamos(m: Motor):
    await nav(m, "Préstamos")
    await m.captura("prestamos", [
        (m.control("Monto total:", ft.Text, exacto=False), "Monto total", "el total del préstamo, lo pagado y lo pendiente."),
        (m.control("Próximo vencimiento", ft.Text, exacto=False), "Próximo vencimiento", "qué cuota sigue y cuándo vence. (Nuevo en 1.3)"),
        (m.control("Pagar cuota", ft.ElevatedButton, exacto=False), "Pagar cuota", "paga la próxima cuota; podés corregir el monto."),
        (m.control("Ver cuotas"), "Ver cuotas", "todas las cuotas; cambiá el monto de las que faltan. (Nuevo en 1.3)"),
        (m.control("Editar", ft.TextButton), "Editar", "cambia cualquier dato del préstamo. (Nuevo en 1.3)"),
        (m.control("Nuevo préstamo"), "Nuevo préstamo", "registra un préstamo."),
    ], pie="La sección Préstamos.")
    await m.click("Nuevo préstamo", espera=1)
    await m.escribir("Nombre del préstamo", "Préstamo refacción", dialogo=True)
    await m.escribir("Monto total", "900000", dialogo=True)
    await m.escribir("Cantidad de cuotas", "12", dialogo=True)
    await m.escribir("¿En qué cuota estás?", "4", dialogo=True)
    await m.escribir("Día de vencimiento de cada cuota", "10", dialogo=True)
    await m.captura("prestamo_nuevo", [
        (m.control("Monto total", TF, dialogo=True), "Monto total", "el total a devolver, en pesos o dólares."),
        (m.control("¿En qué cuota estás?", TF, dialogo=True), "¿En qué cuota estás?", "si ya venías pagando, las anteriores quedan pagadas. (Nuevo en 1.3)"),
        (m.control("Día de vencimiento de cada cuota", TF, dialogo=True), "Día de vencimiento", "qué día del mes vence cada cuota. (Nuevo en 1.3)"),
        (m.control("vence el", ft.Text, exacto=False, dialogo=True), "Aviso", "muestra cuándo vence la cuota en la que estás."),
    ], pie="Nuevo préstamo.", solo_dialogo=True)
    await m.cerrar_dialogos()
    await m.click("Pagar cuota", ft.ElevatedButton, exacto=False, espera=1)
    await m.captura("prestamo_pagar", [
        (m.control("Monto de la cuota", TF, exacto=False, dialogo=True), "Monto de la cuota", "si este mes vino distinta (UVA, ajustes), corregila antes de pagar. (Nuevo en 1.3)"),
        (m.control("Sí, pagar", dialogo=True), "Sí, pagar", "registra el pago."),
    ], pie="Pagar una cuota de un préstamo.", solo_dialogo=True)
    await m.cerrar_dialogos()
    await m.click("Ver cuotas", n=0, espera=1)
    await m.captura("prestamo_cuotas", [
        (m.control("Al cambiar una cuota", ft.Checkbox, exacto=False, dialogo=True), "Aplicar a las siguientes", "el monto nuevo se aplica también a las cuotas que vienen."),
        (m.control("Monto total:", ft.Text, exacto=False, dialogo=True), "Monto total", "es la suma de todas las cuotas."),
        (m.control(tipo=TF, dialogo=True), "Monto de una cuota pendiente", "cambialo y tocá ✓ para guardarlo."),
    ], pie="Ver y cambiar las cuotas de un préstamo.", solo_dialogo=True)
    await m.cerrar_dialogos()
    await m.click("Editar", ft.TextButton, espera=1)
    await m.escribir("Día de vencimiento de cada cuota", "12", dialogo=True)
    await m.captura("prestamo_editar", [
        (m.control("Monto total", TF, dialogo=True), "Todo se puede cambiar", "monto, moneda, cuotas, cuotas pagadas, fecha y día de vencimiento."),
        (m.control("Cuotas ya pagadas", TF, dialogo=True), "Cuotas ya pagadas", "no se modifican."),
        (m.control("Guardar", dialogo=True), "Guardar", "muestra los cambios y pide confirmación, como en las compras."),
    ], pie="Editar un préstamo.", solo_dialogo=True)
    await m.cerrar_dialogos()


# ------------------------------------------------------------------ compra mensual
async def compra_mensual(m: Motor):
    await nav(m, "Compra mensual")
    await m.captura("compra_mensual", [
        (m.control("Agregar local"), "Agregar local", "cada supermercado o negocio es una columna."),
        (m.control("Agregar producto"), "Agregar producto", "cada producto es una fila, con su cantidad."),
        (m.control(cond=lambda c: isinstance(c, TF) and c.value == "Leche"), "Producto", "nombre y cantidad; se repiten todos los meses."),
        (m.control("Mostrar marca / detalle", ft.Switch), "Marca / detalle", "muestra u oculta la marca y el descuento de cada precio."),
    ], pie="La planilla de la compra mensual.")
    await m.desplazar("Agregar producto", 700)
    await m.captura("compra_mensual_registrar", [
        (m.control("Registrar la compra", ft.Text), "Registrar la compra", "pasa lo que gastaste a tus cuentas: como egreso o en una tarjeta."),
        (m.control("Registrar compra"), "Registrar compra", "abre el formulario para registrarla."),
    ], pie="Totales y registro de la compra.")
    await m.desplazar("Agregar producto", 0)


# ------------------------------------------------------------------ inversiones
async def inversiones(m: Motor):
    await nav(m, "Inversiones")
    await m.captura("inversiones", [
        (m.control("Resumen", ft.Text, n=1), "Apartados", "Resumen, Calendario, Ahorro, Acciones, Bonos / Lecap, FCI y Crypto."),
    ], pie="Inversiones: el resumen.")
    for apartado, nombre, pie in [("Ahorro", "inv_ahorro", "Inversiones: Ahorro."), ("Acciones", "inv_acciones", "Inversiones: Acciones."),
                                  ("Calendario", "inv_calendario", "Inversiones: calendario de dividendos y renta.")]:
        await m.click(apartado, ft.Text, n=1 if apartado == "Calendario" else 0, espera=1.2)
        await m.captura(nombre, [], pie=pie)


# ------------------------------------------------------------------ calendario / historial
async def calendario(m: Motor):
    await nav(m, "Calendario")
    await m.captura("calendario", [], pie="El calendario de vencimientos del mes.")
    await m.click(cond=lambda c: isinstance(c, ft.Container) and c.height == 92 and bool(c.on_click), n=4, espera=1)
    await m.captura("calendario_dia", [
        (m.control(dialogo=True, cond=lambda c: isinstance(c, ft.OutlinedButton) and c.content in ("Pagar", "Registrar pago")),
         "Pagar / Registrar pago", "paga ese vencimiento desde el calendario (pide confirmación)."),
    ], pie="Los vencimientos de un día.", solo_dialogo=True)
    await m.cerrar_dialogos()


async def historial(m: Motor):
    await nav(m, "Historial")
    await m.escribir("Buscar por concepto o detalle", "Super")
    await m.click("Aplicar filtros", espera=1)
    await m.captura("historial", [
        (m.control("Tipo", DD), "Filtros", "tipo, categoría, moneda y estado; Desde / Hasta para las fechas."),
        (m.control("Buscar por concepto o detalle", TF), "Buscar", "busca en el concepto y en el detalle."),
        (m.control("Aplicar filtros"), "Aplicar filtros", "muestra los movimientos que coinciden."),
        (m.control("Limpiar"), "Limpiar", "borra los filtros."),
    ], pie="Historial: buscar movimientos.")


# ------------------------------------------------------------------ configuracion
async def configuracion(m: Motor):
    await nav(m, "Configuración")
    for seccion in ("Usuario", "Apariencia", "General"):
        await m.click(seccion, ft.Text, espera=0.8)
    await m.captura("config_usuario", [
        (m.control("Subir imagen"), "Imagen de perfil", "una foto (PNG o JPG) o un color para tu avatar."),
        (m.control("Cambiar contraseña"), "Cambiar contraseña", "pide la actual y la nueva."),
        (m.control("Configurar PIN"), "PIN", "un PIN de 4 números para desbloquear la app."),
    ], pie="Configuración: tu usuario.")
    await m.desplazar("Registro de errores", 600)
    await m.captura("config_general", [
        (m.control("Modo oscuro", ft.Text), "Modo oscuro", "cambia los colores de toda la app."),
        (m.control("Iniciar con Windows", ft.Text), "Iniciar con Windows", "Kakeibo se abre solo al prender la computadora. (Nuevo en 1.3)"),
    ], pie="Configuración: apariencia y general.")
    await m.desplazar("Registro de errores", 0)


ESCENAS = [
    ("acceso", acceso),
    ("principal", principal),
    ("resumen", resumen),
    ("movimientos", movimientos),
    ("gastos_fijos", gastos_fijos),
    ("tarjetas", tarjetas),
    ("prestamos", prestamos),
    ("compra_mensual", compra_mensual),
    ("inversiones", inversiones),
    ("calendario", calendario),
    ("historial", historial),
    ("configuracion", configuracion),
]


async def entrar_rapido(m: Motor, cerrar_aviso: bool = True):
    await m.escribir("Usuario", USUARIO)
    await m.escribir("Contraseña", CLAVE)
    await m.click("Ingresar", espera=3)
    if cerrar_aviso:
        await m.click(cond=lambda c: getattr(c, "tooltip", None) == "Cerrar", espera=1)
