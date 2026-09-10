Requerimientos No Funcionales — Gestión de Gastos
del Hogar

1. Seguridad de acceso
La aplicación deberá requerir autenticación antes de mostrar información financiera.

Android

Deberá utilizar la seguridad del dispositivo siempre que sea posible: biometría y/o método alternativo
configurado por el usuario.

La aplicación no deberá almacenar la huella, rostro, PIN, patrón ni contraseña del dispositivo.

Escritorio

Deberá utilizar login propio con almacenamiento seguro de credenciales.

Las contraseñas no deberán almacenarse en texto plano.

2. Protección de sesión
La aplicación deberá impedir el acceso a las pantallas financieras cuando no exista una sesión autenticada.

Deberá poder bloquearse nuevamente después de un período de inactividad.

El cierre de sesión deberá invalidar la sesión actual.

3. Integridad
Las operaciones financieras deberán evitar duplicaciones y estados inconsistentes.

Las operaciones críticas deberán utilizar transacciones.

4. Precisión monetaria
Los importes deberán manejarse con representación exacta.

ARS y USD deberán permanecer completamente separados.

5. Funcionamiento offline
La aplicación deberá funcionar sin Internet para autenticación local, registro y consulta de datos en V1.

6. Rendimiento y usabilidad
El login y las operaciones habituales deberán responder rápidamente.

El registro de gastos deberá requerir pocos pasos.

La interfaz Android deberá ser adecuada para uso táctil y la de escritorio para teclado/mouse.

7. Persistencia y backup
Los datos deberán conservarse entre ejecuciones.

El backup no deberá modificar los datos originales.

La restauración deberá validar la integridad de la información.

8. Compatibilidad
Windows 10/11.

Android moderno, con versión mínima exacta a definir durante el relevamiento técnico.

9. Mantenibilidad y escalabilidad
La autenticación, lógica financiera y presentación deberán mantenerse desacopladas.

La arquitectura deberá permitir incorporar posteriormente sincronización en la nube, múltiples dispositivos y
usuarios.

10. Privacidad
No enviar información financiera a servicios externos en V1.

No almacenar credenciales bancarias ni información sensible innecesaria.

