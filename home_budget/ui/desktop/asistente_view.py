from __future__ import annotations

import asyncio
import os
from datetime import date

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.domain.money import Money, Moneda
from ...app.repositories.categorias import CategoriaRepository
from ...app.services.asistente import AsistenteError, AsistenteIAService, construir_contexto
from ...app.services.config import CLAVE_OLLAMA_HOST, CLAVE_OLLAMA_MODEL, ConfigService
from ...app.services.dashboard import DashboardService
from ...app.services.gastos_fijos import GastoFijoService
from ...app.services.logs import leer_log, ruta_log
from ...app.services.movimientos import MovimientoService
from ...app.services.prestamos import PrestamoService
from ...app.services.registro_intent import IntencionRegistro, detectar_intencion_registro
from ...app.services.tarjetas import TarjetaService
from .. import theme
from . import components

_SUGERENCIAS = [
    "¿Cuánto gasté este mes?",
    "¿Cuál es mi categoría con más gastos?",
    "¿Qué vencimientos tengo próximos?",
    "Compré una gaseosa de 800",
]


def build_asistente_view(
    page: ft.Page,
    asistente_service: AsistenteIAService,
    config_service: ConfigService,
    dashboard_service: DashboardService,
    movimiento_service: MovimientoService,
    gasto_fijo_service: GastoFijoService,
    prestamo_service: PrestamoService,
    tarjeta_service: TarjetaService,
    categoria_repo: CategoriaRepository,
) -> ft.Control:
    historial_ui: list[tuple[str, str]] = []  # (rol, texto) para mostrar en pantalla
    historial_api: list[tuple[str, str]] = []  # (rol, texto plano) enviado al modelo, sin el contexto ya usado
    estado = {"enviando": False, "form_pendiente": None}

    mensajes_col = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    input_f = ft.TextField(
        hint_text="Preguntale algo sobre tus finanzas...",
        filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        expand=True,
    )
    enviar_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=theme.ASISTENTE_COLOR)
    sugerencias_container = ft.Container()
    banner = ft.Container(padding=12, bgcolor=theme.ASISTENTE_BG, border_radius=theme.RADIUS_SM, border=theme.border_all(1, theme.BORDER))

    def _burbuja(rol: str, texto: str) -> ft.Control:
        es_usuario = rol == "user"
        return ft.Row(
            [
                ft.Container(
                    content=ft.Text(texto, size=13, color="#FFFFFF" if es_usuario else theme.TEXT_PRIMARY, selectable=True),
                    bgcolor=theme.ASISTENTE_COLOR if es_usuario else theme.SURFACE,
                    padding=12,
                    border_radius=theme.RADIUS_SM,
                    border=None if es_usuario else theme.border_all(1, theme.BORDER),
                    width=480,
                )
            ],
            alignment=ft.MainAxisAlignment.END if es_usuario else ft.MainAxisAlignment.START,
        )

    def _refrescar_banner():
        aviso = asistente_service.diagnostico()
        banner.visible = aviso is not None
        if aviso is not None:
            banner.content = ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=theme.ASISTENTE_COLOR, size=18),
                    ft.Text(aviso, size=12, color=theme.TEXT_SECONDARY, expand=True),
                    theme.secondary_button("Configurar", abrir_configuracion),
                ],
                spacing=8,
            )

    def _refrescar_mensajes():
        controles = [_burbuja(rol, texto) for rol, texto in historial_ui]
        if estado["form_pendiente"] is not None:
            controles.append(estado["form_pendiente"])
        if controles:
            mensajes_col.controls = controles
            sugerencias_container.visible = False
        else:
            mensajes_col.controls = [components.empty_state("Todavía no le preguntaste nada al asistente.", "smart_toy_rounded")]
            sugerencias_container.visible = True
        page.update()

    def _categorias_de(tipo: TipoMovimiento):
        return categoria_repo.listar(tipo)

    def _burbuja_registro(intencion: IntencionRegistro) -> ft.Control:
        categorias_tipo = _categorias_de(intencion.tipo)
        categoria_sugerida_id = next(
            (c.id for c in categorias_tipo if c.nombre == intencion.categoria_sugerida), None
        ) if intencion.categoria_sugerida else None

        tipo_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value=TipoMovimiento.EGRESO.value, label=ft.Text("Gasto"), icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED),
                ft.Segment(value=TipoMovimiento.INGRESO.value, label=ft.Text("Ingreso"), icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED),
            ],
            selected=[intencion.tipo.value],
            allow_multiple_selection=False, allow_empty_selection=False,
        )
        concepto_f = ft.TextField(
            label="Concepto", value=intencion.concepto, filled=True,
            bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        monto_f = ft.TextField(
            label="Monto", value=str(intencion.monto.amount) if intencion.monto else "", filled=True,
            bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        moneda_dd = ft.Dropdown(
            label="Moneda", value=(intencion.monto.moneda.value if intencion.monto else Moneda.ARS.value),
            options=[ft.dropdown.Option(m.value) for m in Moneda], filled=True,
            bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        categoria_dd = ft.Dropdown(
            label="Categoría",
            value=str(categoria_sugerida_id) if categoria_sugerida_id else (str(categorias_tipo[0].id) if categorias_tipo else None),
            options=[ft.dropdown.Option(str(c.id), c.nombre) for c in categorias_tipo],
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def on_tipo_change(_e=None):
            nuevas = _categorias_de(TipoMovimiento(next(iter(tipo_selector.selected))))
            categoria_dd.options = [ft.dropdown.Option(str(c.id), c.nombre) for c in nuevas]
            categoria_dd.value = str(nuevas[0].id) if nuevas else None
            page.update()

        tipo_selector.on_change = on_tipo_change

        def cancelar(_e=None):
            estado["form_pendiente"] = None
            historial_ui.append(("assistant", "Listo, no registré nada."))
            _refrescar_mensajes()

        def confirmar(_e=None):
            concepto = (concepto_f.value or "").strip()
            try:
                if not concepto:
                    raise ValueError("El concepto no puede estar vacío")
                if not categoria_dd.value:
                    raise ValueError("Elegí una categoría")
                monto = Money.from_decimal((monto_f.value or "0").replace(",", "."), moneda_dd.value)
                if monto.cents <= 0:
                    raise ValueError("El monto debe ser mayor a cero")
            except (ValueError, ArithmeticError) as exc:
                error_text.value = str(exc)
                error_text.visible = True
                page.update()
                return

            tipo = TipoMovimiento(next(iter(tipo_selector.selected)))
            movimiento_service.registrar(tipo, date.today(), concepto, "", monto, int(categoria_dd.value))

            nombre_categoria = next((c.nombre for c in _categorias_de(tipo) if c.id == int(categoria_dd.value)), "")
            etiqueta = "gasto" if tipo == TipoMovimiento.EGRESO else "ingreso"
            mensaje = f'Registré el {etiqueta} "{concepto}" de {monto.formatted()} en {nombre_categoria}.'
            estado["form_pendiente"] = None
            historial_ui.append(("assistant", mensaje))
            historial_api.append(("assistant", mensaje))
            _refrescar_mensajes()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("¿Registro esto? Revisá los datos y confirmá:", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                    tipo_selector,
                    concepto_f,
                    ft.Row([ft.Container(monto_f, expand=2), ft.Container(moneda_dd, expand=1)], spacing=8),
                    categoria_dd,
                    error_text,
                    ft.Row(
                        [
                            theme.secondary_button("Cancelar", cancelar),
                            theme.primary_button("Registrar", confirmar, color=theme.ASISTENTE_COLOR, icon=ft.Icons.CHECK_ROUNDED),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=theme.SURFACE, padding=14, border_radius=theme.RADIUS_SM,
            border=theme.border_all(1, theme.BORDER), width=460,
        )

    def abrir_logs(_e=None):
        contenido_f = ft.TextField(
            value="", read_only=True, multiline=True, min_lines=14, max_lines=14,
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
            text_style=ft.TextStyle(font_family="monospace", size=11),
        )
        estado_texto = ft.Text("", size=11, color=theme.TEXT_MUTED)

        def refrescar_log(_e2=None):
            contenido = leer_log()
            if contenido:
                contenido_f.value = contenido
                estado_texto.value = f"Archivo: {ruta_log()}"
            else:
                contenido_f.value = ""
                estado_texto.value = "Todavía no se registró ningún error. Buenas noticias."
            page.update()

        def abrir_carpeta(_e2=None):
            try:
                os.startfile(ruta_log().parent)  # noqa: S606 (accion explicita del usuario, solo Windows)
            except OSError as exc:
                estado_texto.value = f"No se pudo abrir la carpeta: {exc}"
                page.update()

        refrescar_log()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Registro de errores"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text(
                            "Si algo falló, acá vas a encontrar el detalle técnico para pasarle a un "
                            "administrador o soporte. Se guarda solo en tu PC, no se envía a ningún lado.",
                            size=12, color=theme.TEXT_SECONDARY,
                        ),
                        contenido_f,
                        estado_texto,
                    ],
                    spacing=10, tight=True,
                ),
                width=560,
            ),
            actions=[
                theme.secondary_button("Actualizar", refrescar_log),
                theme.secondary_button("Abrir carpeta", abrir_carpeta),
                theme.primary_button("Cerrar", lambda e: page.pop_dialog(), color=theme.ASISTENTE_COLOR),
            ],
        )
        page.show_dialog(dialog)

    def abrir_configuracion(_e=None):
        modelo_f = ft.TextField(
            label="Modelo de Ollama",
            value=config_service.obtener(CLAVE_OLLAMA_MODEL) or asistente_service.modelo(),
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        host_f = ft.TextField(
            label="Host de Ollama",
            value=config_service.obtener(CLAVE_OLLAMA_HOST) or asistente_service.host(),
            filled=True, bgcolor=theme.SURFACE_ALT, border_radius=theme.RADIUS_SM, border_color=theme.BORDER,
        )
        error_text = ft.Text("", color=theme.EXPENSE_RED, size=12, visible=False)

        def guardar(_e2):
            modelo = (modelo_f.value or "").strip()
            host = (host_f.value or "").strip()
            if not modelo or not host:
                error_text.value = "Completá el modelo y el host."
                error_text.visible = True
                page.update()
                return
            config_service.guardar(CLAVE_OLLAMA_MODEL, modelo)
            config_service.guardar(CLAVE_OLLAMA_HOST, host)
            page.pop_dialog()
            _refrescar_banner()
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configuración"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Asistente de IA", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                        ft.Text(
                            "El asistente corre 100% local con Ollama (sin costo, sin internet, tus datos nunca "
                            "salen de tu PC). Necesitás tener Ollama instalado y el modelo descargado "
                            "('ollama pull <modelo>') antes de usarlo.",
                            size=12, color=theme.TEXT_SECONDARY,
                        ),
                        modelo_f, host_f, error_text,
                        ft.Divider(height=1, color=theme.BORDER),
                        ft.Text("Registro de errores", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                        ft.Text(
                            "Si algo falla (acá o en cualquier otra parte de la app), quedan los detalles técnicos "
                            "acá para poder elevárselos a un administrador.",
                            size=12, color=theme.TEXT_SECONDARY,
                        ),
                        theme.secondary_button("Ver registro de errores", abrir_logs, icon=ft.Icons.DESCRIPTION_OUTLINED),
                    ],
                    spacing=12, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                width=420, height=460,
            ),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Guardar", guardar, color=theme.ASISTENTE_COLOR, icon=ft.Icons.CHECK_ROUNDED),
            ],
        )
        page.show_dialog(dialog)

    async def preguntar(pregunta: str):
        pregunta = pregunta.strip()
        if not pregunta or estado["enviando"]:
            return

        intencion = detectar_intencion_registro(pregunta)
        if intencion is not None:
            input_f.value = ""
            historial_ui.append(("user", pregunta))
            estado["form_pendiente"] = _burbuja_registro(intencion)
            _refrescar_mensajes()
            return

        aviso = asistente_service.diagnostico()
        if aviso is not None:
            _refrescar_banner()
            page.update()
            return

        estado["enviando"] = True
        input_f.value = ""
        input_f.disabled = True
        enviar_btn.disabled = True
        historial_ui.append(("user", pregunta))
        historial_ui.append(("assistant", "Pensando..."))
        _refrescar_mensajes()

        loop = asyncio.get_event_loop()
        try:
            contexto = construir_contexto(
                pregunta, dashboard_service, movimiento_service, gasto_fijo_service, prestamo_service, tarjeta_service,
            )
            # modelo/host se resuelven aca (hilo principal, donde vive la conexion
            # sqlite de ConfigService) antes de pasar al executor: sqlite3 no deja
            # usar la misma conexion desde otro hilo.
            modelo = asistente_service.modelo()
            host = asistente_service.host()
            respuesta = await loop.run_in_executor(
                None, asistente_service.responder, pregunta, contexto, list(historial_api), modelo, host,
            )
            historial_api.append(("user", pregunta))
            historial_api.append(("assistant", respuesta))
        except AsistenteError as exc:
            respuesta = f"No pude responder: {exc}"
        except Exception:
            import traceback
            with open("kakeibo_debug.log", "a", encoding="utf-8") as f:
                f.write("--- error inesperado en asistente.preguntar ---\n")
                f.write(traceback.format_exc())
                f.write("\n")
            respuesta = "Ocurrió un error inesperado al consultar al asistente."

        historial_ui[-1] = ("assistant", respuesta)
        estado["enviando"] = False
        input_f.disabled = False
        enviar_btn.disabled = False
        _refrescar_mensajes()
        try:
            await input_f.focus()
        except Exception:
            pass  # no es critico: el mensaje ya se mostro igual

    async def enviar(_e):
        await preguntar(input_f.value or "")

    enviar_btn.on_click = enviar
    input_f.on_submit = enviar

    sugerencias_container.content = ft.Row(
        [theme.secondary_button(s, (lambda texto: lambda e: page.run_task(preguntar, texto))(s)) for s in _SUGERENCIAS],
        spacing=8, wrap=True,
    )

    header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text("Asistente financiero", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Text("Preguntale sobre tus finanzas, o contale un gasto/ingreso (ej: \"compré una gaseosa\") para registrarlo.", size=12, color=theme.TEXT_SECONDARY),
                ],
                spacing=2,
            ),
            ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, icon_color=theme.TEXT_MUTED, on_click=abrir_configuracion),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    root = ft.Column(
        [
            header,
            banner,
            mensajes_col,
            sugerencias_container,
            ft.Row([input_f, enviar_btn], spacing=8),
        ],
        expand=True, spacing=12,
    )

    _refrescar_banner()
    _refrescar_mensajes()
    return root
