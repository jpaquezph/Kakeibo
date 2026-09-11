"""Autenticacion de escritorio: login propio con hash seguro de contrasenas.

No se almacena texto plano en ningun momento. El hash usa PBKDF2-HMAC-SHA256
con una sal aleatoria por usuario (modulos estandar de Python, sin dependencias
externas).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass

PBKDF2_ITERATIONS = 260_000
DEFAULT_INACTIVITY_TIMEOUT_SECONDS = 5 * 60

PREGUNTAS_SECRETAS = [
    "¿Cuál es el nombre de tu primera mascota?",
    "¿Cuál es tu comida favorita?",
    "¿En qué ciudad naciste?",
    "¿Cómo se llamaba tu mejor amigo/a de la infancia?",
    "¿Cuál fue tu primer trabajo?",
]


class AuthError(Exception):
    """Credenciales invalidas o usuario inexistente."""


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return dk.hex()


def _normalizar_respuesta(respuesta: str) -> str:
    """Normaliza la respuesta secreta para que la comparacion no sea sensible
    a mayusculas ni espacios extra (una pregunta secreta no es una contrasena)."""
    return " ".join(respuesta.strip().lower().split())


@dataclass
class Session:
    usuario_id: int
    username: str
    started_at: float
    last_activity: float
    inactivity_timeout: int = DEFAULT_INACTIVITY_TIMEOUT_SECONDS
    locked: bool = False

    def touch(self) -> None:
        self.last_activity = time.monotonic()
        self.locked = False

    def check_inactivity(self) -> bool:
        """Devuelve True (y marca locked) si supero el timeout de inactividad."""
        if not self.locked and (time.monotonic() - self.last_activity) >= self.inactivity_timeout:
            self.locked = True
        return self.locked


class AuthService:
    """Gestiona alta de usuario, login y sesion activa para la app de escritorio."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self.session: Session | None = None

    def hay_usuarios(self) -> bool:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()
        return row["n"] > 0

    def crear_usuario(self, username: str, password: str, pregunta_secreta: str = "", respuesta_secreta: str = "") -> int:
        username = username.strip()
        if not username:
            raise ValueError("El usuario no puede estar vacio")
        if len(password) < 6:
            raise ValueError("La contrasena debe tener al menos 6 caracteres")
        salt = secrets.token_hex(16)
        password_hash = _hash_password(password, salt)

        respuesta_salt = secrets.token_hex(16)
        respuesta_hash = (
            _hash_password(_normalizar_respuesta(respuesta_secreta), respuesta_salt) if respuesta_secreta.strip() else ""
        )

        try:
            cur = self._conn.execute(
                """INSERT INTO usuarios
                   (username, password_hash, salt, pregunta_secreta, respuesta_hash, respuesta_salt)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, password_hash, salt, pregunta_secreta, respuesta_hash, respuesta_salt),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ese usuario ya existe") from exc
        return cur.lastrowid

    def obtener_pregunta_secreta(self, username: str) -> str | None:
        """Devuelve la pregunta secreta del usuario, o None si no existe o no la configuro."""
        row = self._conn.execute(
            "SELECT pregunta_secreta FROM usuarios WHERE username = ?", (username.strip(),)
        ).fetchone()
        if row is None or not row["pregunta_secreta"]:
            return None
        return row["pregunta_secreta"]

    def restablecer_password(self, username: str, respuesta_secreta: str, nueva_password: str) -> None:
        """Verifica la respuesta secreta y, si coincide, establece una nueva contrasena."""
        row = self._conn.execute(
            "SELECT id, respuesta_hash, respuesta_salt FROM usuarios WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row is None or not row["respuesta_hash"]:
            raise AuthError("No se pudo verificar la respuesta secreta")
        candidata = _hash_password(_normalizar_respuesta(respuesta_secreta), row["respuesta_salt"])
        if not hmac.compare_digest(candidata, row["respuesta_hash"]):
            raise AuthError("La respuesta no es correcta")
        if len(nueva_password) < 6:
            raise ValueError("La contrasena debe tener al menos 6 caracteres")

        nuevo_salt = secrets.token_hex(16)
        nuevo_hash = _hash_password(nueva_password, nuevo_salt)
        self._conn.execute(
            "UPDATE usuarios SET password_hash = ?, salt = ? WHERE id = ?",
            (nuevo_hash, nuevo_salt, row["id"]),
        )
        self._conn.commit()

    def login(self, username: str, password: str) -> Session:
        row = self._conn.execute(
            "SELECT id, username, password_hash, salt FROM usuarios WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row is None:
            raise AuthError("Usuario o contrasena incorrectos")
        candidate_hash = _hash_password(password, row["salt"])
        if not hmac.compare_digest(candidate_hash, row["password_hash"]):
            raise AuthError("Usuario o contrasena incorrectos")

        self._conn.execute("INSERT INTO sesiones (usuario_id) VALUES (?)", (row["id"],))
        self._conn.commit()

        now = time.monotonic()
        self.session = Session(usuario_id=row["id"], username=row["username"], started_at=now, last_activity=now)
        return self.session

    def logout(self) -> None:
        if self.session is not None:
            self._conn.execute(
                "UPDATE sesiones SET logout_at = datetime('now') "
                "WHERE id = ("
                "  SELECT id FROM sesiones WHERE usuario_id = ? AND logout_at IS NULL "
                "  ORDER BY id DESC LIMIT 1"
                ")",
                (self.session.usuario_id,),
            )
            self._conn.commit()
        self.session = None

    def is_authenticated(self) -> bool:
        return self.session is not None and not self.session.check_inactivity()
