Requerimientos — Gestión de Gastos del Hogar

1. Objetivo
Desarrollar una aplicación de gestión financiera del hogar para registrar, consultar y analizar ingresos y
egresos, con versiones de escritorio Windows y Android APK.

Cada instalación deberá disponer de acceso protegido mediante login.

2. Acceso y autenticación
El sistema deberá requerir autenticación para acceder a los datos financieros.

Android

En Android, el acceso deberá utilizar el mecanismo de seguridad disponible en el dispositivo. Se deberá
permitir autenticación mediante los métodos compatibles con el dispositivo, por ejemplo huella dactilar,
reconocimiento biométrico, PIN, patrón o contraseña.

Si el método biométrico no está disponible o falla, deberá poder utilizarse el mecanismo de desbloqueo
alternativo configurado en el dispositivo.

La aplicación no deberá almacenar ni conocer la contraseña, PIN o patrón del dispositivo.

Escritorio

En Windows, la aplicación deberá mostrar una pantalla de login propia y solicitar credenciales para ingresar.

El usuario deberá poder iniciar sesión únicamente después de proporcionar credenciales válidas.

Las credenciales deberán almacenarse de forma segura y no en texto plano.

3. Gestión de movimientos
Registrar ingresos y gastos con fecha, concepto, detalle, monto, moneda, categoría y estado.

Permitir gastos fijos y variables.

Permitir editar, eliminar y consultar movimientos.

4. Monedas
Soportar ARS y USD.

No realizar conversión automática.

Mantener ingresos, gastos y totales separados por moneda.

5. Categorías
Préstamos; Comida; Farmacia; Mascotas; Salidas; Casa; Otros; Servicios esenciales; Servicios no
esenciales; Auto; Tarjeta de crédito.

6. Tarjetas de crédito
Permitir registrar múltiples tarjetas.

Cada tarjeta deberá tener sus propios movimientos.

Permitir compras de 1 pago y compras en cuotas.

Mostrar cuota actual, cantidad total, cuotas restantes, monto de cuota y monto pendiente.

7. Préstamos
Registrar monto original, moneda, cantidad de cuotas, monto de cuota, fechas, cuotas pagadas, cuotas
restantes, estado y detalle.

Calcular total pagado y total pendiente.

8. Dashboard
Mostrar ingresos y gastos separados por ARS/USD.

Mostrar totales por categoría y por tarjeta.

Mostrar información de cuotas y préstamos pendientes.

9. Historial y filtros
Filtrar por fecha, período, tipo, categoría, tarjeta, moneda, estado y concepto.

10. Persistencia
Utilizar SQLite local.

Los datos deberán conservarse al cerrar y volver a abrir la aplicación.

11. Plataformas
Windows 10/11 y Android mediante APK.

La lógica financiera deberá ser compartida entre plataformas cuando sea técnicamente posible.

