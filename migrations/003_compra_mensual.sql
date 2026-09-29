-- Compra mensual: una lista por mes para comparar precios entre locales.
-- Cada lista tiene sus locales y sus productos; la cantidad es del producto
-- (igual para todos los locales) y cada casilla producto x local guarda precio
-- unitario, descuento y detalle. precio NULL = el local no tiene el producto.

CREATE TABLE IF NOT EXISTS compra_listas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anio INTEGER NOT NULL,
    mes INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (anio, mes)
);

CREATE TABLE IF NOT EXISTS compra_locales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lista_id INTEGER NOT NULL REFERENCES compra_listas(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS compra_productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lista_id INTEGER NOT NULL REFERENCES compra_listas(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    cantidad TEXT NOT NULL DEFAULT '1',  -- decimal como texto (ej: 1,5 kg)
    orden INTEGER NOT NULL DEFAULT 0
);

-- Compras registradas desde la lista: como egreso (movimiento) o en una
-- tarjeta de credito (compra con cuotas). Una lista puede tener varias
-- (ej: una parte en efectivo y otra con tarjeta). referencia_id apunta al
-- movimiento o a la compra de tarjeta, segun el tipo.
CREATE TABLE IF NOT EXISTS compra_registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lista_id INTEGER NOT NULL REFERENCES compra_listas(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('egreso', 'tarjeta')),
    referencia_id INTEGER NOT NULL,
    monto_centavos INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compra_precios (
    producto_id INTEGER NOT NULL REFERENCES compra_productos(id) ON DELETE CASCADE,
    local_id INTEGER NOT NULL REFERENCES compra_locales(id) ON DELETE CASCADE,
    precio_centavos INTEGER,             -- precio unitario; NULL = no lo tiene
    descuento TEXT,                      -- porcentaje como texto decimal, NULL = sin descuento
    detalle TEXT NOT NULL DEFAULT '',    -- marca, tamaño, promo...
    PRIMARY KEY (producto_id, local_id)
);
