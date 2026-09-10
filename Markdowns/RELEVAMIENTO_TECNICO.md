Relevamiento Técnico — Gestión de Gastos del Hogar

1. Tecnología base
Python 3.x como lenguaje principal.

SQLite como base de datos local.

pytest para pruebas automatizadas.

Git para control de versiones.

2. Arquitectura
Separar presentación, casos de uso, dominio, servicios y persistencia.

La autenticación deberá quedar separada de la lógica financiera.

La interfaz no deberá contener reglas financieras complejas.

3. Autenticación

Android

Evaluar e implementar el mecanismo nativo de autenticación segura del dispositivo mediante
APIs/framework compatible con el framework multiplataforma seleccionado. La aplicación deberá solicitar
autenticación al sistema y no gestionar directamente PIN, patrón o contraseña del dispositivo.

Escritorio

Implementar login propio de la aplicación. Las credenciales deberán almacenarse mediante un mecanismo
seguro de hash/verificación y nunca como texto plano.

Deberá existir una sesión autenticada antes de permitir acceso a los módulos financieros.

4. Interfaz multiplataforma
Evaluar Kivy, Flet y PySide6 considerando que Android requiere acceso a autenticación del dispositivo.

La elección deberá priorizar la capacidad de compartir lógica y ofrecer una implementación segura de
autenticación en ambas plataformas.

5. Base de datos
SQLite local.

Tablas principales: usuarios/sesiones para escritorio, movimientos, categorías, tarjetas, compras, cuotas,
préstamos, cuotas de préstamos y gastos fijos.

Los importes monetarios deberán almacenarse sin utilizar float para cálculos financieros.

6. Seguridad de datos
No almacenar contraseñas en texto plano.

No almacenar PIN, patrón, contraseña ni credenciales biométricas del dispositivo Android.

No almacenar CVV ni credenciales bancarias.

Los datos financieros deberán permanecer locales durante V1.

7. Distribución
Windows: evaluar PyInstaller o Nuitka.

Android: evaluar Kivy + Buildozer o Flet con su mecanismo de empaquetado Android.

8. Estructura propuesta
home_budget/

app/ — domain, services, repositories, database, models, reports, auth

ui/ — desktop, mobile

tests/ — unit, integration, fixtures

migrations/

scripts/

main.py

9. Pendientes técnicos
Definir framework de interfaz.

Definir mecanismo concreto de autenticación Android.

Definir almacenamiento seguro de credenciales para Windows.

Definir timeout y duración de sesión.

Definir política de bloqueo después de inactividad.

Definir backup y restauración.

