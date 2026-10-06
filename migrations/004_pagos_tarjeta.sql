-- Pago del resumen de una tarjeta ("Pagar tarjeta" del mes): lo que se pago
-- de verdad y lo que daba la cuenta de la app (cuotas, compras en 1 pago y
-- debitos automaticos). Son distintos si el saldo se corrigio al pagar.
-- Una fila por moneda: ARS y USD nunca se suman.

CREATE TABLE IF NOT EXISTS pagos_tarjeta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarjeta_id INTEGER NOT NULL REFERENCES tarjetas(id) ON DELETE CASCADE,
    anio INTEGER NOT NULL,
    mes INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos >= 0),
    calculado_centavos INTEGER NOT NULL,
    fecha_pago TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
