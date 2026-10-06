"""Conexion y esquema de la base de datos SQLite local."""
from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .domain.models import CATEGORIAS_BASE


def _migrations_dir() -> Path:
    """Ubicacion de las migraciones SQL (solo lectura).

    Cuando la app corre empaquetada (PyInstaller), los datos agregados con
    --add-data se extraen a `sys._MEIPASS`, no junto al ejecutable.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "migrations"
    return Path(__file__).resolve().parent.parent.parent / "migrations"


def _default_db_path() -> Path:
    """Ubicacion de la base de datos (debe persistir entre ejecuciones).

    Empaquetada como .exe de un solo archivo, `sys._MEIPASS` es una carpeta
    temporal que se borra al cerrar la app, asi que la base se guarda junto
    al ejecutable en su lugar.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "kakeibo.db"
    return Path(__file__).resolve().parent.parent.parent / "kakeibo.db"


MIGRATIONS_DIR = _migrations_dir()
DEFAULT_DB_PATH = _default_db_path()


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea el esquema (si no existe), aplica migraciones incrementales y siembra las categorias base."""
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text(encoding="utf-8"))
    _ensure_categoria_tipo_column(conn)
    _ensure_tarjeta_color_column(conn)
    _ensure_tarjeta_unica_por_moneda(conn)
    _ensure_tarjeta_dias_columnas(conn)
    _unir_tarjetas_duplicadas(conn)
    _ensure_prestamo_dia_vencimiento_column(conn)
    _ensure_usuario_recuperacion_columnas(conn)
    _ensure_usuario_perfil_columnas(conn)
    _ensure_movimiento_gasto_fijo_column(conn)
    _ensure_gasto_fijo_tarjeta_column(conn)
    _ensure_gasto_fijo_metodo_pago_column(conn)
    _ensure_categoria_activa_column(conn)
    _ensure_movimiento_metodo_pago_column(conn)
    _ensure_compra_lista_estado_columnas(conn)
    _ensure_compra_cuota_inicial(conn)
    _ensure_pago_tarjeta_movimiento(conn)
    _seed_categorias(conn)
    conn.commit()


def _ensure_categoria_tipo_column(conn: sqlite3.Connection) -> None:
    """Agrega la columna 'tipo' a categorias si la base es de una version anterior."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(categorias)")}
    if "tipo" not in columnas:
        conn.execute("ALTER TABLE categorias ADD COLUMN tipo TEXT NOT NULL DEFAULT 'egreso'")


def _ensure_tarjeta_color_column(conn: sqlite3.Connection) -> None:
    """Agrega la columna 'color' a tarjetas si la base es de una version anterior."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(tarjetas)")}
    if "color" not in columnas:
        conn.execute("ALTER TABLE tarjetas ADD COLUMN color TEXT NOT NULL DEFAULT '#D6467E'")


def _ensure_tarjeta_unica_por_moneda(conn: sqlite3.Connection) -> None:
    """Las bases anteriores tenian 'nombre' UNIQUE en tarjetas, lo que impedia
    cargar la misma tarjeta en ARS y en USD. SQLite no permite quitar un
    UNIQUE, asi que se reconstruye la tabla con UNIQUE (nombre, moneda)."""
    solo_nombre = False
    for idx in conn.execute("PRAGMA index_list(tarjetas)").fetchall():
        if not idx["unique"]:
            continue
        columnas = [c["name"] for c in conn.execute(f"PRAGMA index_info('{idx['name']}')")]
        if columnas == ["nombre"]:
            solo_nombre = True
    if not solo_nombre:
        return
    conn.commit()
    # Con foreign_keys activo, borrar la tabla vieja dispararia las referencias
    # de compras, movimientos y gastos_fijos; se desactiva durante el cambio.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            BEGIN;
            CREATE TABLE tarjetas_nueva (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                banco TEXT NOT NULL DEFAULT '',
                ultimos_digitos TEXT NOT NULL DEFAULT '',
                moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
                color TEXT NOT NULL DEFAULT '#D6467E',
                activa INTEGER NOT NULL DEFAULT 1,
                UNIQUE (nombre, moneda)
            );
            INSERT INTO tarjetas_nueva (id, nombre, banco, ultimos_digitos, moneda, color, activa)
                SELECT id, nombre, banco, ultimos_digitos, moneda, color, activa FROM tarjetas;
            DROP TABLE tarjetas;
            ALTER TABLE tarjetas_nueva RENAME TO tarjetas;
            COMMIT;
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _ensure_tarjeta_dias_columnas(conn: sqlite3.Connection) -> None:
    """Agrega el dia de cierre y el de vencimiento del resumen a tarjetas
    (opcionales: NULL si no se cargaron)."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(tarjetas)")}
    if "dia_cierre" not in columnas:
        conn.execute("ALTER TABLE tarjetas ADD COLUMN dia_cierre INTEGER CHECK (dia_cierre BETWEEN 1 AND 31)")
    if "dia_vencimiento" not in columnas:
        conn.execute("ALTER TABLE tarjetas ADD COLUMN dia_vencimiento INTEGER CHECK (dia_vencimiento BETWEEN 1 AND 31)")


def _ensure_prestamo_dia_vencimiento_column(conn: sqlite3.Connection) -> None:
    """Dia del mes en que vencen las cuotas de un prestamo (opcional)."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(prestamos)")}
    if "dia_vencimiento" not in columnas:
        conn.execute("ALTER TABLE prestamos ADD COLUMN dia_vencimiento INTEGER CHECK (dia_vencimiento BETWEEN 1 AND 31)")


def _clave_tarjeta(nombre: str, banco: str, digitos: str) -> tuple[str, str, str]:
    return (nombre.strip().casefold(), banco.strip().casefold(), digitos.strip())


def _unir_tarjetas_duplicadas(conn: sqlite3.Connection) -> None:
    """Desde la 1.3 una tarjeta opera en ARS y en USD. Antes habia que cargar
    la misma tarjeta dos veces (una por moneda); esas copias (mismo nombre,
    banco y ultimos digitos) se unen en la mas antigua: sus compras, debitos
    automaticos y movimientos pasan a ella y la copia se borra. Antes de
    tocar nada se guarda un backup de la base junto a ella."""
    grupos: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
    for t in conn.execute("SELECT * FROM tarjetas ORDER BY id").fetchall():
        grupos.setdefault(_clave_tarjeta(t["nombre"], t["banco"], t["ultimos_digitos"]), []).append(t)
    duplicadas = [g for g in grupos.values() if len(g) > 1]
    if not duplicadas:
        return

    _backup_antes_de_migrar(conn, "antes-de-unir-tarjetas")
    try:
        for original, *copias in duplicadas:
            for copia in copias:
                for tabla in ("compras", "gastos_fijos", "movimientos"):
                    conn.execute(f"UPDATE {tabla} SET tarjeta_id = ? WHERE tarjeta_id = ?", (original["id"], copia["id"]))
                # Si la original no tenia dias de cierre/vencimiento, se toman de la copia.
                conn.execute(
                    "UPDATE tarjetas SET dia_cierre = COALESCE(dia_cierre, ?), dia_vencimiento = COALESCE(dia_vencimiento, ?) WHERE id = ?",
                    (copia["dia_cierre"], copia["dia_vencimiento"], original["id"]),
                )
                conn.execute("DELETE FROM tarjetas WHERE id = ?", (copia["id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _backup_antes_de_migrar(conn: sqlite3.Connection, motivo: str) -> None:
    """Copia completa de la base, junto a ella, antes de una migracion que
    modifica datos (no solo el esquema). Las bases en memoria no se copian."""
    archivo = conn.execute("PRAGMA database_list").fetchone()["file"]
    if not archivo:
        return
    origen = Path(archivo)
    destino = origen.with_name(f"{origen.stem}_{motivo}_{datetime.now():%Y%m%d-%H%M%S}{origen.suffix}")
    conn.commit()
    copia = sqlite3.connect(str(destino))
    try:
        conn.backup(copia)
    finally:
        copia.close()


def _ensure_usuario_recuperacion_columnas(conn: sqlite3.Connection) -> None:
    """Agrega las columnas de pregunta secreta (recuperacion de contrasena) si faltan."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(usuarios)")}
    if "pregunta_secreta" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN pregunta_secreta TEXT NOT NULL DEFAULT ''")
    if "respuesta_hash" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN respuesta_hash TEXT NOT NULL DEFAULT ''")
    if "respuesta_salt" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN respuesta_salt TEXT NOT NULL DEFAULT ''")


def _ensure_usuario_perfil_columnas(conn: sqlite3.Connection) -> None:
    """Agrega las columnas del perfil (avatar y PIN de desbloqueo) si faltan."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(usuarios)")}
    if "avatar_color" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN avatar_color TEXT NOT NULL DEFAULT ''")
    if "avatar_imagen" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN avatar_imagen BLOB")
    if "pin_hash" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN pin_hash TEXT NOT NULL DEFAULT ''")
    if "pin_salt" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN pin_salt TEXT NOT NULL DEFAULT ''")


def _ensure_movimiento_gasto_fijo_column(conn: sqlite3.Connection) -> None:
    """Agrega la columna 'gasto_fijo_id' a movimientos si la base es de una version anterior.
    Vincula un movimiento con el gasto fijo (plantilla recurrente) que lo genero."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(movimientos)")}
    if "gasto_fijo_id" not in columnas:
        conn.execute("ALTER TABLE movimientos ADD COLUMN gasto_fijo_id INTEGER REFERENCES gastos_fijos(id)")


def _ensure_gasto_fijo_tarjeta_column(conn: sqlite3.Connection) -> None:
    """Agrega 'tarjeta_id' a gastos_fijos: la tarjeta a la que se debita
    automaticamente (NULL = se paga por fuera de las tarjetas)."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(gastos_fijos)")}
    if "tarjeta_id" not in columnas:
        conn.execute("ALTER TABLE gastos_fijos ADD COLUMN tarjeta_id INTEGER REFERENCES tarjetas(id)")


def _ensure_gasto_fijo_metodo_pago_column(conn: sqlite3.Connection) -> None:
    """Agrega 'metodo_pago' a gastos_fijos (efectivo, transferencia, etc.).
    Los gastos ya cargados quedan "sin especificar"."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(gastos_fijos)")}
    if "metodo_pago" not in columnas:
        conn.execute("ALTER TABLE gastos_fijos ADD COLUMN metodo_pago TEXT NOT NULL DEFAULT ''")


def _ensure_categoria_activa_column(conn: sqlite3.Connection) -> None:
    """Agrega 'activa' a categorias. Una categoria quitada no se borra (los
    movimientos, compras y gastos fijos ya cargados la siguen mostrando):
    queda con activa = 0 y deja de ofrecerse en los formularios."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(categorias)")}
    if "activa" not in columnas:
        conn.execute("ALTER TABLE categorias ADD COLUMN activa INTEGER NOT NULL DEFAULT 1")


def _ensure_movimiento_metodo_pago_column(conn: sqlite3.Connection) -> None:
    """Agrega 'metodo_pago' a movimientos (efectivo, transferencia, etc.).
    Los movimientos ya cargados quedan "sin especificar"."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(movimientos)")}
    if "metodo_pago" not in columnas:
        conn.execute("ALTER TABLE movimientos ADD COLUMN metodo_pago TEXT NOT NULL DEFAULT ''")


def _ensure_compra_lista_estado_columnas(conn: sqlite3.Connection) -> None:
    """Estado de cada compra mensual (abierta / cerrada) y el resumen que se
    guarda al cerrarla. Una compra cerrada no se borra: se muestra solo su
    resumen y el detalle se carga al pedirlo. Las listas ya cargadas quedan abiertas."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(compra_listas)")}
    nuevas = {
        "estado": "TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'cerrada'))",
        "cerrada_at": "TEXT",
        "total_optimo_centavos": "INTEGER",
        "total_registrado_centavos": "INTEGER",
        "cantidad_productos": "INTEGER",
        "cantidad_locales": "INTEGER",
    }
    for nombre, tipo in nuevas.items():
        if nombre not in columnas:
            conn.execute(f"ALTER TABLE compra_listas ADD COLUMN {nombre} {tipo}")


def _ensure_compra_cuota_inicial(conn: sqlite3.Connection) -> None:
    """Agrega 'cuota_inicial' a compras: en que cuota se estaba al cargarla.

    Hasta la 1.5, una compra cargada ya empezada (ej: "estoy en la cuota 4")
    con la fecha del dia dejaba las cuotas anteriores como pagadas pero con
    vencimiento en los meses siguientes, y la cuota que tocaba pagar quedaba
    varios meses adelante: no entraba en el resumen del mes ni en "Pagar
    tarjeta". Esas compras se reconocen porque sus primeras cuotas figuran
    pagadas en una fecha posterior a la carga; se les corrige el calendario
    para que la cuota en la que se estaba venza el mes siguiente a la compra.
    Antes de tocar nada se guarda un backup de la base junto a ella."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(compras)")}
    if "cuota_inicial" in columnas:
        return
    conn.execute("ALTER TABLE compras ADD COLUMN cuota_inicial INTEGER NOT NULL DEFAULT 1")

    from datetime import date

    from .services.tarjetas import vencimiento_cuota

    corregir = []
    for compra in conn.execute("SELECT * FROM compras WHERE cantidad_cuotas > 1").fetchall():
        cuotas = conn.execute("SELECT * FROM cuotas_compra WHERE compra_id = ? ORDER BY numero_cuota", (compra["id"],)).fetchall()
        cargada = compra["created_at"][:10]
        adelantadas = 0
        for c in cuotas:
            if not (c["pagada"] and c["fecha_pago"] == c["fecha_vencimiento"] and c["fecha_vencimiento"] > cargada):
                break
            adelantadas += 1
        if 0 < adelantadas < len(cuotas):
            corregir.append((compra, cuotas, adelantadas))
    if not corregir:
        return

    _backup_antes_de_migrar(conn, "antes-de-corregir-cuotas")
    try:
        for compra, cuotas, adelantadas in corregir:
            fecha = date.fromisoformat(compra["fecha"])
            cantidad, inicial = compra["cantidad_cuotas"], adelantadas + 1
            cerrada = cuotas[0]["fecha_vencimiento"] != vencimiento_cuota(fecha, 1, cantidad).isoformat()
            conn.execute("UPDATE compras SET cuota_inicial = ? WHERE id = ?", (inicial, compra["id"]))
            for c in cuotas:
                vence = vencimiento_cuota(fecha, c["numero_cuota"], cantidad, cerrada, inicial).isoformat()
                # Las que ya se habian pagado de verdad conservan su fecha de pago.
                pago = vence if c["numero_cuota"] <= adelantadas else c["fecha_pago"]
                conn.execute("UPDATE cuotas_compra SET fecha_vencimiento = ?, fecha_pago = ? WHERE id = ?", (vence, pago, c["id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _ensure_pago_tarjeta_movimiento(conn: sqlite3.Connection) -> None:
    """Agrega 'movimiento_id' a pagos_tarjeta: el egreso que genera cada pago
    del resumen. Los pagos hechos antes de que existiera (primer armado de la
    1.6) no habian registrado egreso: se les crea ahora, por lo pagado menos
    los debitos automaticos (que ya tenian el suyo como gastos fijos). Antes
    de tocar nada se guarda un backup de la base junto a ella."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(pagos_tarjeta)")}
    if "movimiento_id" in columnas:
        return
    conn.execute("ALTER TABLE pagos_tarjeta ADD COLUMN movimiento_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL")
    pagos = conn.execute(
        "SELECT pt.*, t.nombre AS tarjeta_nombre FROM pagos_tarjeta pt JOIN tarjetas t ON t.id = pt.tarjeta_id"
    ).fetchall()
    categoria = conn.execute("SELECT id FROM categorias WHERE nombre = 'Tarjeta de crédito' AND tipo = 'egreso'").fetchone()
    if not pagos or categoria is None:
        return

    _backup_antes_de_migrar(conn, "antes-de-sumar-pagos-de-tarjeta")
    try:
        for p in pagos:
            # Lo pagado en cuotas y compras en 1 pago ese dia, mas la correccion del saldo.
            cuotas = conn.execute(
                """SELECT COALESCE(SUM(cc.monto_centavos), 0) AS total
                   FROM cuotas_compra cc JOIN compras co ON co.id = cc.compra_id
                   WHERE co.tarjeta_id = ? AND co.moneda = ? AND cc.pagada = 1 AND cc.fecha_pago = ?""",
                (p["tarjeta_id"], p["moneda"], p["fecha_pago"]),
            ).fetchone()["total"]
            monto = cuotas + p["monto_centavos"] - p["calculado_centavos"]
            if monto <= 0:
                continue
            cur = conn.execute(
                """INSERT INTO movimientos (tipo, fecha, concepto, detalle, monto_centavos, moneda, categoria_id, tarjeta_id)
                   VALUES ('egreso', ?, ?, ?, ?, ?, ?, ?)""",
                (p["fecha_pago"], f"Pago tarjeta {p['tarjeta_nombre']}", f"Resumen {p['mes']:02d}/{p['anio']}", monto,
                 p["moneda"], categoria["id"], p["tarjeta_id"]),
            )
            conn.execute("UPDATE pagos_tarjeta SET movimiento_id = ? WHERE id = ?", (cur.lastrowid, p["id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _seed_categorias(conn: sqlite3.Connection) -> None:
    # Una categoria base quitada sigue existiendo (inactiva): no se vuelve a crear.
    existentes = {row["nombre"] for row in conn.execute("SELECT nombre FROM categorias")}
    for cat in CATEGORIAS_BASE:
        if cat["nombre"] not in existentes:
            conn.execute(
                "INSERT INTO categorias (nombre, color, icono, tipo) VALUES (?, ?, ?, ?)",
                (cat["nombre"], cat["color"], cat["icono"], cat["tipo"]),
            )


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Agrupa operaciones en una transaccion: commit al salir, rollback ante error."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
