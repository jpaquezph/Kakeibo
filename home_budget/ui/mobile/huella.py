"""Lector de huella del telefono (o la biometria que tenga: cara, iris).

Envuelve el servicio de Flet (paquete flet-local-auth, solo en la version
movil). Donde no esta el paquete, o el dispositivo no tiene biometria
cargada, `disponible` queda en False y la app sigue pidiendo contrasena."""
from __future__ import annotations

import flet as ft

from ...app.services.logs import registrar_error


class Huella:
    def __init__(self):
        self.disponible = False
        self._servicio = None  # se guarda aca: Flet suelta los servicios que nadie referencia
        self._mensajes = None

    async def preparar(self, page: ft.Page) -> None:
        """Averigua si este dispositivo puede pedir la huella. En la
        computadora (ventana de prueba) no se usa."""
        if page.platform not in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
            return
        try:
            import flet_local_auth as fla

            self._servicio = fla.LocalAuthentication()
            self._mensajes = fla.AndroidAuthMessages(sign_in_title="Kakeibo", cancel_button="Usar contraseña")
            self.disponible = bool(await self._servicio.can_check_biometrics()) and bool(await self._servicio.get_available_biometrics())
        except Exception:
            # Sin huella la app funciona igual: se deja registrado y se sigue con contrasena.
            registrar_error("preparar el lector de huella")
            self.disponible = False

    async def pedir(self, motivo: str) -> bool:
        """Muestra el cartel del sistema para poner la huella. Devuelve si
        se comprobo; si se cancela o falla, False."""
        if not self.disponible:
            return False
        try:
            return bool(await self._servicio.authenticate(motivo, biometric_only=True, android_messages=self._mensajes))
        except Exception:
            return False
