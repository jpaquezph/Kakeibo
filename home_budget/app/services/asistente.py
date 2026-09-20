"""Asistente financiero conversacional (RAG sobre la base local de Kakeibo).

Corre 100% local: le habla por HTTP a Ollama (http://localhost:11434), un
motor de inferencia que el usuario instala una vez y que baja el modelo a su
PC. No hay API key, no hay costo por uso y los datos financieros nunca salen
de la maquina.

Al ser datos tabulares (movimientos, categorias, tarjetas) en vez de texto
libre, la "recuperacion" no usa embeddings/vector store: arma el contexto con
consultas SQL agregadas (totales por categoria/tarjeta, ya acotadas por la
cantidad de categorias, no de movimientos) mas un recorte de movimientos
crudos por rango de fechas, para que el tamano del contexto no crezca sin
limite a medida que el usuario acumula anios de historial.
"""
from __future__ import annotations

import calendar as calendar_mod
import json
import re
import urllib.error
import urllib.request
from datetime import date
from typing import Callable

from ..domain.dates import add_months
from ..repositories.movimientos import FiltroMovimientos
from .config import CLAVE_OLLAMA_HOST, CLAVE_OLLAMA_MODEL, ConfigService
from .dashboard import DashboardService
from .gastos_fijos import GastoFijoService
from .movimientos import MovimientoService
from .prestamos import PrestamoService
from .tarjetas import TarjetaService

HOST_DEFAULT = "http://localhost:11434"
MODEL_DEFAULT = "llama3.2:3b"
TIMEOUT_SEGUNDOS = 180
MOVIMIENTOS_MAX = 300

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

SYSTEM_PROMPT = (
    "Sos el asistente financiero de Kakeibo, una app de gestion de gastos "
    "personales/del hogar. Respondes preguntas del usuario sobre su propia "
    "plata usando EXCLUSIVAMENTE los datos que se te dan en el mensaje "
    "(resumen de movimientos, categorias, tarjetas, prestamos y gastos fijos "
    "de su base de datos local). No inventes montos, fechas ni movimientos "
    "que no esten en los datos provistos. Si la informacion no alcanza para "
    "responder con precision, decilo claramente y sugeri en que seccion de "
    "la app puede revisarlo (Movimientos, Historial, Tarjetas, Prestamos, "
    "Calendario). Respondes en espanol rioplatense, de forma breve y "
    "concreta, citando montos con el mismo formato que aparece en los datos."
)


class AsistenteError(Exception):
    """Error de configuracion o de comunicacion con Ollama."""


def _post_json(url: str, payload: dict, timeout: float = TIMEOUT_SEGUNDOS) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read().decode("utf-8", errors="ignore")
        try:
            mensaje = json.loads(cuerpo).get("error", cuerpo)
        except json.JSONDecodeError:
            mensaje = cuerpo
        if exc.code == 404 and "not found" in mensaje:
            raise AsistenteError(f"El modelo configurado no está descargado en Ollama. Ejecutá en una terminal: ollama pull <nombre-del-modelo>. Detalle: {mensaje}") from exc
        raise AsistenteError(f"Ollama respondió con un error: {mensaje}") from exc
    except urllib.error.URLError as exc:
        raise AsistenteError(
            "No se pudo conectar con Ollama en tu PC (http://localhost:11434). "
            "¿Está instalado y corriendo? Si no lo instalaste, bajalo de ollama.com; "
            "si ya lo tenés, abrilo o ejecutá 'ollama serve' en una terminal."
        ) from exc
    except TimeoutError as exc:
        raise AsistenteError("Ollama tardó demasiado en responder. Probá con un modelo más chico o de nuevo en un momento.") from exc


def _get_json(url: str, timeout: float = 5.0) -> dict:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _rango_fechas_de_pregunta(pregunta: str, hoy: date) -> tuple[date, date]:
    """Interpreta menciones de fecha en la pregunta. Si no reconoce ninguna,
    usa por defecto los ultimos 3 meses (evita mandar todo el historico como
    contexto a medida que la base crece)."""
    texto = pregunta.lower()

    if "año pasado" in texto or "ano pasado" in texto:
        return date(hoy.year - 1, 1, 1), date(hoy.year - 1, 12, 31)
    if "este año" in texto or "este ano" in texto or "en el año" in texto:
        return date(hoy.year, 1, 1), hoy
    if "mes pasado" in texto:
        mes_pasado = add_months(hoy.replace(day=1), -1)
        ultimo_dia = calendar_mod.monthrange(mes_pasado.year, mes_pasado.month)[1]
        return mes_pasado, date(mes_pasado.year, mes_pasado.month, ultimo_dia)
    if "este mes" in texto or "mes actual" in texto:
        return date(hoy.year, hoy.month, 1), hoy

    match_n_meses = re.search(r"ultimos?\s+(\d+)\s+mes", texto)
    if match_n_meses:
        n = max(1, int(match_n_meses.group(1)))
        desde = add_months(hoy.replace(day=1), -(n - 1))
        return desde, hoy

    for nombre, numero in _MESES.items():
        if nombre in texto:
            match_anio = re.search(r"\b(20\d{2})\b", texto)
            anio = int(match_anio.group(1)) if match_anio else hoy.year
            ultimo_dia = calendar_mod.monthrange(anio, numero)[1]
            return date(anio, numero, 1), date(anio, numero, ultimo_dia)

    return add_months(hoy.replace(day=1), -2), hoy


def construir_contexto(
    pregunta: str,
    dashboard_service: DashboardService,
    movimiento_service: MovimientoService,
    gasto_fijo_service: GastoFijoService,
    prestamo_service: PrestamoService,
    tarjeta_service: TarjetaService,
    hoy: date | None = None,
) -> str:
    """Arma el bloque de contexto financiero para una pregunta puntual."""
    hoy = hoy or date.today()
    resumen = dashboard_service.resumen()
    desde, hasta = _rango_fechas_de_pregunta(pregunta, hoy)

    partes: list[str] = [f"Fecha de hoy: {hoy.isoformat()}.", ""]

    partes.append("== Balance historico total (todas las fechas) ==")
    for r in resumen.por_moneda:
        partes.append(f"{r.moneda.value}: ingresos {r.ingresos.formatted()}, egresos {r.egresos.formatted()}, balance {r.balance.formatted()}")

    if resumen.por_categoria:
        partes.append("")
        partes.append("== Total historico de egresos por categoria ==")
        for c in resumen.por_categoria:
            partes.append(f"- {c.nombre} ({c.moneda.value}): {c.total.formatted()}")

    if resumen.por_tarjeta:
        partes.append("")
        partes.append("== Deuda pendiente por tarjeta ==")
        for t in resumen.por_tarjeta:
            partes.append(f"- {t.nombre} ({t.moneda.value}): {t.total_pendiente.formatted()} pendiente")

    partes.append("")
    partes.append(f"== Prestamos activos: {resumen.prestamos_pendientes_cantidad} ==")
    partes.append(f"Pendiente total: {resumen.prestamos_pendientes_ars.formatted()} / {resumen.prestamos_pendientes_usd.formatted()}")
    for p in prestamo_service.listar():
        pendientes = [c for c in p.cuotas if not c.pagada]
        if pendientes:
            partes.append(f"- {p.nombre}: {len(pendientes)} cuotas pendientes de {len(p.cuotas)}, proximo vencimiento {min(c.fecha_vencimiento for c in pendientes).isoformat()}")

    gastos_fijos = gasto_fijo_service.listar(solo_activos=True)
    if gastos_fijos:
        partes.append("")
        partes.append("== Gastos fijos activos ==")
        for g in gastos_fijos:
            proximo = gasto_fijo_service.proximo_vencimiento(g, hoy)
            partes.append(f"- {g.concepto}: {g.monto.formatted()} (vence el dia {g.dia_mes} de cada mes, proximo {proximo.isoformat()})")

    movimientos = movimiento_service.listar(FiltroMovimientos(fecha_desde=desde, fecha_hasta=hasta))
    partes.append("")
    partes.append(f"== Movimientos entre {desde.isoformat()} y {hasta.isoformat()} ({len(movimientos)} en total) ==")
    for m in movimientos[:MOVIMIENTOS_MAX]:
        signo = "+" if m.tipo.value == "ingreso" else "-"
        detalle = f" ({m.detalle})" if m.detalle else ""
        partes.append(f"{m.fecha.isoformat()} {signo}{m.monto.formatted()} [{m.categoria_nombre}] {m.concepto}{detalle}")
    if len(movimientos) > MOVIMIENTOS_MAX:
        partes.append(f"(se muestran los primeros {MOVIMIENTOS_MAX} de {len(movimientos)}; para el detalle completo el usuario puede revisar la seccion Historial)")

    return "\n".join(partes)


class AsistenteIAService:
    def __init__(
        self,
        config_service: ConfigService,
        post_json: Callable[[str, dict], dict] = _post_json,
        get_json: Callable[[str], dict] = _get_json,
    ):
        self._config = config_service
        self._post_json = post_json
        self._get_json = get_json

    def modelo(self) -> str:
        return self._config.obtener(CLAVE_OLLAMA_MODEL) or MODEL_DEFAULT

    def host(self) -> str:
        return (self._config.obtener(CLAVE_OLLAMA_HOST) or HOST_DEFAULT).rstrip("/")

    def diagnostico(self) -> str | None:
        """Devuelve un mensaje de advertencia si Ollama no esta listo para
        responder, o None si todo esta en orden."""
        try:
            data = self._get_json(f"{self.host()}/api/tags")
        except Exception:
            return (
                "Ollama no está corriendo en tu PC. Instalalo desde ollama.com si todavía no lo hiciste, "
                "o abrilo (queda como servicio en segundo plano) y volvé a intentar."
            )
        modelos_instalados = {m.get("name") for m in data.get("models", [])}
        modelo = self.modelo()
        if modelo not in modelos_instalados and not any(m.startswith(modelo.split(":")[0] + ":") for m in modelos_instalados):
            return f"El modelo '{modelo}' todavía no está descargado. Ejecutá en una terminal: ollama pull {modelo}"
        return None

    def responder(
        self,
        pregunta: str,
        contexto: str,
        historial: list[tuple[str, str]] | None = None,
        modelo: str | None = None,
        host: str | None = None,
    ) -> str:
        """Envia la pregunta + contexto a Ollama. `historial` son pares
        (rol, texto plano) de turnos previos, sin el contexto ya usado en
        ellos, para no reenviar el mismo bloque de datos en cada turno.

        `modelo`/`host` se pueden pasar ya resueltos (por ejemplo, cuando
        este metodo corre en un hilo aparte via `run_in_executor`): la
        conexion sqlite de `ConfigService` solo se puede usar desde el hilo
        que la creo, asi que si no se pasan se resuelven aca, en el hilo que
        haya llamado a `responder`."""
        modelo = modelo or self.modelo()
        host = host or self.host()

        mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
        mensajes.extend({"role": rol, "content": texto} for rol, texto in (historial or []))
        mensajes.append({
            "role": "user",
            "content": f"Datos financieros disponibles:\n\n{contexto}\n\nPregunta del usuario: {pregunta}",
        })

        payload = {
            "model": modelo,
            "messages": mensajes,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        data = self._post_json(f"{host}/api/chat", payload)

        texto_respuesta = (data.get("message") or {}).get("content", "")
        return texto_respuesta.strip() or "No obtuve una respuesta del asistente."
