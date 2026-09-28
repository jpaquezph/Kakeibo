-- Seccion Inversiones. Los montos van en centavos (como el resto de la app);
-- cantidades, precios unitarios de crypto y TNA van como texto decimal para
-- no perder precision (una crypto puede tener 8 decimales).
-- estado: 'vigente' | 'finalizada'. Los *_mov_id apuntan al movimiento que se
-- genero si el usuario eligio operar con la plata de la app (NULL si no).

CREATE TABLE IF NOT EXISTS ahorros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monto_centavos INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    fecha TEXT NOT NULL,
    ubicacion TEXT NOT NULL DEFAULT '',
    observaciones TEXT NOT NULL DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'vigente',
    fecha_salida TEXT,
    monto_salida_centavos INTEGER,
    entrada_mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    salida_mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Acciones y Bonos/Lecap comparten estructura (tipo = 'accion' | 'bono').
-- meses_pago: meses de dividendos (acciones) o renta (bonos), ej "3,6,9,12".
CREATE TABLE IF NOT EXISTS titulos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'vigente',
    simbolo TEXT NOT NULL,
    nombre TEXT NOT NULL DEFAULT '',
    tipo_empresa TEXT NOT NULL DEFAULT '',
    plazo TEXT NOT NULL DEFAULT 'largo',
    broker TEXT NOT NULL DEFAULT '',
    transaccion TEXT NOT NULL DEFAULT '',
    fecha_suscripcion TEXT NOT NULL,
    cantidad TEXT NOT NULL,
    precio_compra_centavos INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    meses_pago TEXT NOT NULL DEFAULT '',
    observaciones TEXT NOT NULL DEFAULT '',
    fecha_salida TEXT,
    monto_salida_centavos INTEGER,
    entrada_mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    salida_mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fcis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estado TEXT NOT NULL DEFAULT 'vigente',
    simbolo TEXT NOT NULL DEFAULT '',
    nombre TEXT NOT NULL,
    plazo TEXT NOT NULL DEFAULT 'corto',
    broker TEXT NOT NULL DEFAULT '',
    transaccion TEXT NOT NULL DEFAULT '',
    fecha_suscripcion TEXT NOT NULL,
    monto_centavos INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    fecha_rescate TEXT,
    tna TEXT,
    observaciones TEXT NOT NULL DEFAULT '',
    fecha_salida TEXT,
    monto_salida_centavos INTEGER,
    entrada_mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    salida_mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Crypto se registra como operaciones sueltas (compra/venta); la tenencia de
-- cada activo se calcula sumando compras y restando ventas.
CREATE TABLE IF NOT EXISTS crypto_operaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    operacion TEXT NOT NULL,
    activo TEXT NOT NULL,
    monto_centavos INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    precio_unitario TEXT NOT NULL,
    cantidad TEXT NOT NULL,
    observaciones TEXT NOT NULL DEFAULT '',
    mov_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
