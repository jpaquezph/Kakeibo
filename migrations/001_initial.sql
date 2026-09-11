-- Esquema inicial de Kakeibo. Los montos se guardan siempre en centavos (INTEGER).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    login_at TEXT NOT NULL DEFAULT (datetime('now')),
    logout_at TEXT
);

CREATE TABLE IF NOT EXISTS categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL,
    icono TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'egreso' CHECK (tipo IN ('ingreso', 'egreso'))
);

CREATE TABLE IF NOT EXISTS tarjetas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    banco TEXT NOT NULL DEFAULT '',
    ultimos_digitos TEXT NOT NULL DEFAULT '',
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    color TEXT NOT NULL DEFAULT '#D6467E',
    activa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('ingreso', 'egreso')),
    fecha TEXT NOT NULL,
    concepto TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '',
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    estado TEXT NOT NULL DEFAULT 'confirmado' CHECK (estado IN ('pendiente', 'confirmado')),
    fijo INTEGER NOT NULL DEFAULT 0,
    tarjeta_id INTEGER REFERENCES tarjetas(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos(fecha);
CREATE INDEX IF NOT EXISTS idx_movimientos_categoria ON movimientos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_moneda ON movimientos(moneda);

CREATE TABLE IF NOT EXISTS gastos_fijos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '',
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    dia_mes INTEGER NOT NULL CHECK (dia_mes BETWEEN 1 AND 28),
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarjeta_id INTEGER NOT NULL REFERENCES tarjetas(id),
    fecha TEXT NOT NULL,
    concepto TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '',
    monto_total_centavos INTEGER NOT NULL CHECK (monto_total_centavos > 0),
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    cantidad_cuotas INTEGER NOT NULL CHECK (cantidad_cuotas > 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cuotas_compra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id INTEGER NOT NULL REFERENCES compras(id) ON DELETE CASCADE,
    numero_cuota INTEGER NOT NULL,
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
    fecha_vencimiento TEXT NOT NULL,
    pagada INTEGER NOT NULL DEFAULT 0,
    fecha_pago TEXT,
    UNIQUE (compra_id, numero_cuota)
);

CREATE TABLE IF NOT EXISTS prestamos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '',
    monto_original_centavos INTEGER NOT NULL CHECK (monto_original_centavos > 0),
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    cantidad_cuotas INTEGER NOT NULL CHECK (cantidad_cuotas > 0),
    fecha_inicio TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'pagado', 'cancelado')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cuotas_prestamo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prestamo_id INTEGER NOT NULL REFERENCES prestamos(id) ON DELETE CASCADE,
    numero_cuota INTEGER NOT NULL,
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
    fecha_vencimiento TEXT NOT NULL,
    pagada INTEGER NOT NULL DEFAULT 0,
    fecha_pago TEXT,
    UNIQUE (prestamo_id, numero_cuota)
);
