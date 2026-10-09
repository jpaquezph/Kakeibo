"""Préstamos en el celular: la lista con buscador y orden y, desde cada
préstamo, pagar la cuota que sigue, ver y cambiar sus cuotas, editarlo o
eliminarlo. El boton flotante carga uno nuevo. Los formularios piden lo
mismo y en el mismo orden que los de escritorio."""
from __future__ import annotations

from datetime import date

import flet as ft

from ...app.domain.models import EstadoPrestamo
from ...app.domain.money import Money, Moneda
from ...app.services.prestamos import vencimiento_cuota_prestamo
from .. import theme
from ..desktop import components
from . import componentes as mc

# Prestamos que el usuario dejo achicados (sus ids, separados por coma).
CLAVE_PRESTAMOS_PLEGADOS = "movil_prestamos_plegados"


def build_prestamos_view(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    plegadas = mc.Plegadas(servicios.config, CLAVE_PRESTAMOS_PLEGADOS)
    lista = ft.Column(spacing=12)
    # Primero los activos, por la cuota que vence antes; los ya pagados, al final.
    prestamos = sorted(servicios.prestamos.listar(), key=lambda p: (p.estado != EstadoPrestamo.ACTIVO, _proxima_fecha(p)))
    activos = sum(1 for p in prestamos if p.estado == EstadoPrestamo.ACTIVO)

    def abrir(titulo: str, constructor):
        nav.abrir(titulo, constructor, theme.PRESTAMOS_COLOR)

    def nuevo(_e=None):
        abrir("Nuevo préstamo", lambda: _formulario_nuevo(page, nav, servicios))

    def refrescar(busqueda: str = "", orden: str = "vencimiento"):
        elegidos = mc.filtrar_y_ordenar(prestamos, busqueda, orden, lambda p: f"{p.nombre} {p.detalle}", lambda p: p.total_pendiente)
        if not prestamos:
            lista.controls = [components.empty_state("Todavía no cargaste préstamos.", "account_balance_rounded"),
                              mc.boton_ancho("Cargar un préstamo", nuevo, theme.PRESTAMOS_COLOR, ft.Icons.ADD_ROUNDED)]
        else:
            lista.controls = [_tarjeta(p) for p in elegidos] or [mc.sin_resultados()]

    def al_buscar(busqueda: str, orden: str):
        refrescar(busqueda, orden)
        page.update()

    def _tarjeta(p) -> ft.Control:
        proxima = next((c for c in p.cuotas if not c.pagada), None)
        acciones = [
            ft.TextButton("Ver cuotas", icon=ft.Icons.LIST_ALT_ROUNDED, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                          on_click=lambda e: abrir(f"Cuotas de {p.nombre}", lambda: _pantalla_cuotas(page, servicios, p))),
            ft.TextButton("Editar", icon=ft.Icons.EDIT_ROUNDED, style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                          on_click=lambda e: abrir("Editar préstamo", lambda: _formulario_editar(page, nav, servicios, p))),
        ]
        return plegadas.tarjeta(
            str(p.id), p.nombre,
            [
                *([ft.Text(p.detalle, size=12, color=theme.TEXT_SECONDARY)] if p.detalle else []),
                ft.ProgressBar(value=p.cuotas_pagadas / p.cantidad_cuotas, color=theme.PRESTAMOS_COLOR, bgcolor=theme.PRESTAMOS_BG,
                               bar_height=8, border_radius=4),
                ft.Row(
                    [
                        ft.Text(f"{p.cuotas_pagadas} de {p.cantidad_cuotas} cuotas pagadas", size=12, color=theme.TEXT_SECONDARY, expand=True),
                        ft.Text(f"Falta {p.total_pendiente.formatted()}", size=13, weight=ft.FontWeight.BOLD, color=theme.PRESTAMOS_COLOR),
                    ],
                ),
                ft.Text(f"Monto total {p.monto_original.formatted()} · pagado {p.total_pagado.formatted()}", size=12,
                        color=theme.TEXT_SECONDARY),
                *([ft.Text(f"Próxima: cuota {proxima.numero_cuota} · vence el {proxima.fecha_vencimiento.strftime('%d/%m/%Y')}",
                           size=12, color=theme.TEXT_SECONDARY),
                   mc.boton_ancho(f"Pagar cuota {proxima.numero_cuota} ({proxima.monto.formatted()})",
                                  lambda e: abrir("Pagar cuota", lambda: _pantalla_pagar(page, nav, servicios, p, proxima)),
                                  theme.PRESTAMOS_COLOR, ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED)] if proxima else []),
                ft.Row(acciones, alignment=ft.MainAxisAlignment.SPACE_EVENLY),
            ],
            extra=components.category_chip(p.estado.value.capitalize(), theme.PRESTAMOS_COLOR if proxima else theme.TEXT_MUTED,
                                           "hourglass_top_rounded" if proxima else "check_circle_rounded"),
        )

    refrescar()
    return ft.Stack(
        [
            mc.pantalla([
                *([ft.Text(f"{activos} préstamo(s) pendiente(s) de {len(prestamos)} en total", size=12, color=theme.TEXT_SECONDARY)]
                  if prestamos else []),
                mc.barra_busqueda([("vencimiento", "Próximo vencimiento"), ("monto_mayor", "Falta pagar: mayor"),
                                   ("monto_menor", "Falta pagar: menor"), ("alfabetico", "Orden alfabético")], al_buscar, theme.PRESTAMOS_COLOR),
                lista,
            ]),
            mc.boton_flotante(ft.Icons.ADD_ROUNDED, theme.PRESTAMOS_COLOR, nuevo, "Nuevo préstamo"),
        ],
        expand=True,
    )


def _proxima_fecha(prestamo) -> date:
    return next((c.fecha_vencimiento for c in prestamo.cuotas if not c.pagada), date.max)


def _formulario_nuevo(page: ft.Page, nav: mc.Navegacion, servicios) -> ft.Control:
    nombre_f = mc.campo("Nombre del préstamo", autofocus=True)
    detalle_f = mc.campo("Detalle (opcional)")
    monto_f = mc.campo("Monto total", keyboard_type=ft.KeyboardType.NUMBER)
    moneda_dd = mc.desplegable("Moneda", Moneda.ARS.value, [ft.dropdown.Option(m.value) for m in Moneda])
    cuotas_f = mc.campo("Cantidad de cuotas", value="12", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    cuota_inicial_f = mc.campo("¿En qué cuota estás?", value="1", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    dia_f = mc.campo("Día de vencimiento de cada cuota", value=str(date.today().day), keyboard_type=ft.KeyboardType.NUMBER, max_length=2)
    vencimientos = ft.Text("", size=12, color=theme.TEXT_SECONDARY, italic=True)
    error, mostrar_error = mc.texto_error(page)

    def actualizar_vencimientos(_e=None):
        """Muestra cuando vence la proxima cuota a pagar, segun lo cargado."""
        try:
            cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas")
            actual = components.parse_entero(cuota_inicial_f.value, "Cuota", maximo=cantidad)
            dia = components.parse_entero(dia_f.value, "Día", maximo=31)
        except ValueError:
            vencimientos.value = ""
        else:
            vence = vencimiento_cuota_prestamo(fecha_elegida(), actual, dia)
            previas = f" Las cuotas 1 a {actual - 1} quedan como pagadas." if actual > 1 else ""
            vencimientos.value = f"La cuota {actual} vence el {vence.strftime('%d/%m/%Y')}.{previas}"
        if _e is not None:
            page.update()

    fila_fecha, fecha_elegida = mc.selector_fecha(page, "Fecha de inicio", date.today(), al_elegir=lambda: actualizar_vencimientos())
    cuotas_f.on_change = cuota_inicial_f.on_change = dia_f.on_change = actualizar_vencimientos
    actualizar_vencimientos()

    def guardar(_e):
        try:
            monto = components.parse_monto(monto_f.value, moneda_dd.value, "Monto total")
            cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas")
            cuota_inicial = components.parse_entero(cuota_inicial_f.value, "¿En qué cuota estás?", maximo=cantidad)
            dia = components.parse_entero(dia_f.value, "Día de vencimiento", maximo=31)
            if not (nombre_f.value or "").strip():
                raise ValueError("El nombre no puede estar vacío")
            servicios.prestamos.registrar_prestamo(nombre_f.value.strip(), detalle_f.value or "", monto, cantidad, fecha_elegida(),
                                                   cuota_inicial=cuota_inicial, dia_vencimiento=dia)
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar("Préstamo registrado")

    return mc.pantalla([
        fila_fecha,
        nombre_f,
        detalle_f,
        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
        ft.Row([cuotas_f, cuota_inicial_f], spacing=8),
        mc.nota("Si ya venías pagando, poné en qué cuota estás ahora: las anteriores quedan pagadas."),
        dia_f,
        vencimientos,
        error,
        mc.boton_ancho("Registrar préstamo", guardar, theme.PRESTAMOS_COLOR, ft.Icons.CHECK_ROUNDED),
    ])


def _formulario_editar(page: ft.Page, nav: mc.Navegacion, servicios, prestamo) -> ft.Control:
    """Edicion completa del prestamo. Muestra que cambia y pide confirmacion;
    las cuotas pagadas no se modifican. Suma eliminarlo."""
    dia_actual = servicios.prestamos.dia_vencimiento_de(prestamo)
    fila_fecha, fecha_elegida = mc.selector_fecha(page, "Fecha de inicio", prestamo.fecha_inicio)
    nombre_f = mc.campo("Nombre del préstamo", value=prestamo.nombre)
    detalle_f = mc.campo("Detalle (opcional)", value=prestamo.detalle)
    monto_f = mc.campo("Monto total", value=components.monto_editable(prestamo.monto_original), keyboard_type=ft.KeyboardType.NUMBER)
    moneda_dd = mc.desplegable("Moneda", prestamo.monto_original.moneda.value, [ft.dropdown.Option(m.value) for m in Moneda])
    cuotas_f = mc.campo("Cantidad de cuotas", value=str(prestamo.cantidad_cuotas), keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    pagadas_f = mc.campo("Cuotas ya pagadas", value=str(prestamo.cuotas_pagadas), keyboard_type=ft.KeyboardType.NUMBER, expand=True)
    dia_f = mc.campo("Día de vencimiento de cada cuota", value=str(dia_actual), keyboard_type=ft.KeyboardType.NUMBER, max_length=2)
    error, mostrar_error = mc.texto_error(page)

    def leer() -> dict:
        nombre = (nombre_f.value or "").strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío")
        cantidad = components.parse_entero(cuotas_f.value, "Cantidad de cuotas")
        return dict(
            nombre=nombre, detalle=detalle_f.value or "",
            monto_total=components.parse_monto(monto_f.value, moneda_dd.value, "Monto total"),
            cantidad_cuotas=cantidad,
            cuotas_pagadas=components.parse_entero(pagadas_f.value, "Cuotas ya pagadas", minimo=0, maximo=cantidad),
            fecha_inicio=fecha_elegida(),
            dia_vencimiento=components.parse_entero(dia_f.value, "Día de vencimiento", maximo=31),
        )

    def cambios(nuevo: dict) -> list[str]:
        pares = [
            ("Nombre", prestamo.nombre, nuevo["nombre"]),
            ("Detalle", prestamo.detalle or "(vacío)", nuevo["detalle"] or "(vacío)"),
            ("Monto total", prestamo.monto_original.formatted(), nuevo["monto_total"].formatted()),
            ("Cantidad de cuotas", str(prestamo.cantidad_cuotas), str(nuevo["cantidad_cuotas"])),
            ("Cuotas pagadas", str(prestamo.cuotas_pagadas), str(nuevo["cuotas_pagadas"])),
            ("Fecha de inicio", prestamo.fecha_inicio.strftime("%d/%m/%Y"), nuevo["fecha_inicio"].strftime("%d/%m/%Y")),
            ("Día de vencimiento", str(dia_actual), str(nuevo["dia_vencimiento"])),
        ]
        return [f"{que}: {antes}  →  {despues}" for que, antes, despues in pares if antes != despues]

    def guardar(_e):
        try:
            nuevo = leer()
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        lista = cambios(nuevo)
        if not lista:
            nav.volver()
            return

        def aplicar():
            try:
                servicios.prestamos.editar_prestamo(prestamo.id, **nuevo)
            except (ValueError, ArithmeticError) as exc:
                mostrar_error(exc)
                return
            nav.volver()
            nav.avisar("Préstamo guardado")

        lineas = [ft.Text("Se van a hacer estos cambios:", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY)]
        lineas += [ft.Text(f"•  {c}", size=13, color=theme.TEXT_PRIMARY) for c in lista]
        if not all(c.startswith(("Nombre", "Detalle")) for c in lista):
            conservadas = servicios.prestamos.cuotas_que_se_conservan(prestamo, nuevo["cuotas_pagadas"])
            moneda = nuevo["monto_total"].moneda
            ya_pagado = sum((c.monto.amount for c in conservadas), 0)
            restantes = nuevo["cantidad_cuotas"] - len(conservadas)
            if conservadas:
                lineas.append(ft.Text(f"Las {len(conservadas)} cuota(s) ya pagada(s) no se modifican "
                                      f"({Money.from_decimal(ya_pagado, moneda).formatted()} en total).",
                                      size=12, weight=ft.FontWeight.W_600, color=theme.INCOME_GREEN))
            if restantes:
                falta = nuevo["monto_total"].amount - ya_pagado
                lineas.append(ft.Text(
                    f"{'Lo que falta' if conservadas else 'El monto'} ({Money.from_decimal(falta, moneda).formatted()}) se reparte en "
                    f"{restantes} cuota(s) de {Money.from_decimal(falta / restantes, moneda).formatted()} aprox., "
                    f"que vencen el día {nuevo['dia_vencimiento']} de cada mes.", size=12, color=theme.TEXT_SECONDARY))
                lineas.append(mc.nota("Si cambiaste montos de cuotas a mano (en \"Ver cuotas\"), las pendientes vuelven a quedar iguales."))
        mc.confirmar(page, "¿Confirmás los cambios?", ft.Column(lineas, spacing=6, tight=True, scroll=ft.ScrollMode.AUTO), "Sí, guardar",
                     theme.PRESTAMOS_COLOR, "check_rounded", aplicar, cancelar="Volver")

    def eliminar(_e):
        def aceptar():
            servicios.prestamos.eliminar_prestamo(prestamo.id)
            nav.volver()
            nav.avisar("Préstamo eliminado")

        mc.confirmar(page, "Eliminar préstamo", f'¿Seguro que querés eliminar "{prestamo.nombre}" y todas sus cuotas?', "Eliminar",
                     theme.EXPENSE_RED, "delete_outline_rounded", aceptar)

    return mc.pantalla([
        fila_fecha,
        nombre_f,
        detalle_f,
        ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
        ft.Row([cuotas_f, pagadas_f], spacing=8),
        dia_f,
        mc.nota("Las cuotas ya pagadas no se modifican: se recalculan solo las que faltan."),
        error,
        mc.boton_ancho("Guardar", guardar, theme.PRESTAMOS_COLOR, ft.Icons.CHECK_ROUNDED),
        mc.boton_eliminar("Eliminar préstamo", eliminar),
    ])


def _pantalla_pagar(page: ft.Page, nav: mc.Navegacion, servicios, prestamo, cuota) -> ft.Control:
    """El monto de la cuota viene cargado y se puede corregir: hay prestamos
    cuya cuota cambia cada mes (UVA, sistema aleman, ajustes)."""
    monto_f = mc.campo(f"Monto de la cuota ({cuota.monto.moneda.value})", value=components.monto_editable(cuota.monto),
                       keyboard_type=ft.KeyboardType.NUMBER, text_size=20)
    error, mostrar_error = mc.texto_error(page)

    def pagar(_e):
        try:
            monto = components.parse_monto(monto_f.value, cuota.monto.moneda, "Monto de la cuota")
            servicios.prestamos.pagar_cuota(cuota.id, monto=monto if monto != cuota.monto else None)
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        nav.volver()
        nav.avisar(f"Cuota {cuota.numero_cuota} pagada")

    return mc.pantalla([
        ft.Text(prestamo.nombre, size=16, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
        ft.Text(f"Cuota {cuota.numero_cuota} de {prestamo.cantidad_cuotas} · vence el {cuota.fecha_vencimiento.strftime('%d/%m/%Y')}",
                size=13, color=theme.TEXT_SECONDARY),
        monto_f,
        mc.nota("Si este mes la cuota vino con otro monto, corregilo acá."),
        error,
        mc.boton_ancho("Sí, pagar", pagar, theme.PRESTAMOS_COLOR, ft.Icons.CHECK_ROUNDED),
    ])


def _pantalla_cuotas(page: ft.Page, servicios, prestamo) -> ft.Control:
    """Todas las cuotas del prestamo; en las que faltan pagar se puede
    cambiar el monto (y aplicarlo tambien a las siguientes)."""
    siguientes = ft.Checkbox(label="Aplicar el mismo monto a las cuotas siguientes", value=False, active_color=theme.PRESTAMOS_COLOR)
    total = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY)
    filas = ft.Column(spacing=4)
    error, mostrar_error = mc.texto_error(page)

    def armar(p):
        total.value = f"Monto total: {p.monto_original.formatted()}"
        filas.controls = [_fila(c) for c in p.cuotas]

    def _fila(c) -> ft.Control:
        vence = ft.Column(
            [ft.Text(f"Cuota {c.numero_cuota}", size=13, color=theme.TEXT_PRIMARY),
             ft.Text(f"vence {c.fecha_vencimiento.strftime('%d/%m/%Y')}", size=11, color=theme.TEXT_SECONDARY)],
            spacing=0, expand=True,
        )
        if c.pagada:
            pagada_el = f"pagada el {c.fecha_pago.strftime('%d/%m/%Y')}" if c.fecha_pago else "pagada"
            derecha = [ft.Column(
                [ft.Text(c.monto.formatted(), size=13, weight=ft.FontWeight.BOLD, color=theme.INCOME_GREEN),
                 ft.Text(pagada_el, size=11, color=theme.INCOME_GREEN)],
                spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END,
            )]
        else:
            monto_f = mc.campo("", value=components.monto_editable(c.monto), width=130, dense=True, text_size=13,
                               keyboard_type=ft.KeyboardType.NUMBER)
            derecha = [monto_f, ft.IconButton(icon=ft.Icons.CHECK_ROUNDED, icon_color=theme.PRESTAMOS_COLOR, tooltip="Guardar este monto",
                                              on_click=lambda e: guardar(c, monto_f))]
        return ft.Container(ft.Row([vence, *derecha], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=theme.pad(vertical=4))

    def guardar(cuota, campo_monto):
        try:
            monto = components.parse_monto(campo_monto.value, cuota.monto.moneda, f"Cuota {cuota.numero_cuota}")
            actualizado = servicios.prestamos.cambiar_monto_cuota(cuota.id, monto, bool(siguientes.value))
        except (ValueError, ArithmeticError) as exc:
            mostrar_error(exc)
            return
        error.visible = False
        armar(actualizado)
        page.update()

    armar(prestamo)
    return mc.pantalla([
        mc.nota("Cambiá el monto de una cuota pendiente y tocá el tilde para guardarlo. El monto total del préstamo pasa a ser "
                "la suma de todas las cuotas. Las cuotas pagadas no se modifican."),
        siguientes,
        total,
        error,
        mc.separador(),
        filas,
    ])
