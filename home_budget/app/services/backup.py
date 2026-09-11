"""Backup y restauracion de la base de datos local.

El backup se realiza con la API de respaldo online de SQLite (Connection.backup),
que no interfiere ni modifica la base de datos original mientras se usa.
La restauracion valida la integridad del archivo antes de reemplazar los datos.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


class BackupIntegrityError(Exception):
    """El archivo de backup a restaurar no es una base de datos SQLite valida."""


def crear_backup(db_path: Path, destino_dir: Path) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = destino_dir / f"kakeibo_backup_{timestamp}.db"

    origen_conn = sqlite3.connect(str(db_path))
    destino_conn = sqlite3.connect(str(destino))
    try:
        origen_conn.backup(destino_conn)
    finally:
        destino_conn.close()
        origen_conn.close()
    return destino


def validar_integridad(backup_path: Path) -> None:
    conn = sqlite3.connect(str(backup_path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            raise BackupIntegrityError("El archivo de backup no paso la verificacion de integridad")
        tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        requeridas = {"usuarios", "movimientos", "categorias", "tarjetas", "prestamos"}
        faltantes = requeridas - tablas
        if faltantes:
            raise BackupIntegrityError(f"Faltan tablas esperadas en el backup: {', '.join(sorted(faltantes))}")
    finally:
        conn.close()


def restaurar_backup(backup_path: Path, db_path: Path) -> None:
    validar_integridad(backup_path)
    seguridad = db_path.with_suffix(".pre_restore.db")
    if db_path.exists():
        shutil.copy2(db_path, seguridad)
    shutil.copy2(backup_path, db_path)
