TDD — Gestión de Gastos del Hogar

1. Autenticación

Android

Verificar que una sesión válida permita acceder a la aplicación.

Verificar que una autenticación inválida o cancelada no permita acceder.

Verificar el comportamiento cuando el dispositivo no dispone de biometría.

Verificar el fallback al método de seguridad del dispositivo cuando corresponda.

Verificar que la aplicación no almacene credenciales del sistema operativo.

Escritorio

Verificar login con credenciales válidas.

Verificar rechazo de credenciales inválidas.

Verificar que no se pueda acceder a las pantallas financieras sin autenticación.

Verificar cierre de sesión y posterior solicitud de login.

Verificar que las credenciales no se almacenen en texto plano.

2. Movimientos
Probar creación, edición y eliminación de ingresos y gastos.

Probar validación de monto, moneda, categoría, concepto y fecha.

3. Monedas
Probar que ARS y USD se acumulen por separado.

Probar que ningún cálculo mezcle ambas monedas.

4. Categorías
Probar totales por cada categoría y asociación correcta de movimientos.

5. Tarjetas y cuotas
Probar múltiples tarjetas independientes.

Probar compra de 1 pago.

Probar generación y seguimiento de cuotas.

Probar cuota actual, restantes y monto pendiente.

Probar que una cuota no pueda contabilizarse dos veces.

6. Préstamos
Probar cuotas pagadas, cuotas restantes, total pagado y total pendiente.

7. Dashboard y filtros

Probar que los totales coincidan con la base de datos y que los filtros devuelvan los movimientos esperados.

8. Persistencia
Crear datos, cerrar la aplicación, volver a abrir y verificar que los datos continúen disponibles.

