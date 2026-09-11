# Kakeibo — Gestión de gastos del hogar

Aplicación de escritorio (Windows) para registrar y analizar ingresos y egresos
del hogar: movimientos, tarjetas de crédito con cuotas, préstamos, categorías y
un dashboard con totales separados por moneda (ARS/USD).

## Requisitos

- Python 3.11+

## Puesta en marcha

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

La primera vez que se ejecuta, la app pide crear un usuario y contraseña
(no hay usuarios por defecto). Las credenciales se guardan con hash
PBKDF2-HMAC-SHA256 + sal, nunca en texto plano.

## Tests

```bash
.venv\Scripts\python -m pytest
```

## Estructura

```
home_budget/
  app/
    domain/       -> Money (sin floats), modelos de dominio
    auth/         -> login de escritorio, sesion con bloqueo por inactividad
    repositories/ -> acceso a SQLite
    services/      -> logica de negocio (movimientos, tarjetas, prestamos, dashboard, backup)
    database.py    -> conexion y migraciones
  ui/
    theme.py       -> paleta de colores y componentes visuales compartidos
    desktop/       -> pantallas Flet (login, dashboard, movimientos, tarjetas, prestamos, historial)
migrations/        -> esquema SQL
tests/              -> pytest (unit + integration)
main.py             -> punto de entrada
```

## Empaquetado (generar un instalador para Windows)

Requiere `pyinstaller` (en el venv) e [Inno Setup 6](https://jrsoftware.org/isdl.php)
instalado en la máquina que compila.

```bash
.venv\Scripts\pip install pyinstaller

.venv\Scripts\flet pack main.py -n Kakeibo --product-name "Kakeibo" ^
  --company-name "Kakeibo" --add-data "migrations;migrations" ^
  --hidden-import tkinter --hidden-import tkinter.filedialog -y
```

Esto genera `dist\Kakeibo.exe` (un solo archivo, autocontenido — no necesita
Python ni internet en la máquina de destino). Después, compilar el instalador:

```bash
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\kakeibo.iss
```

Esto genera `installer\KakeiboSetup.exe`: ese es el único archivo que hay que
compartir. Al ejecutarlo, instala la app en `%LOCALAPPDATA%\Kakeibo`, crea un
ícono en el Escritorio (sin pedir elegir carpetas) y queda registrado como
programa desinstalable normal de Windows.

## Notas de diseño

- Los montos se guardan en SQLite como enteros (centavos) y se operan con
  `Decimal` en el dominio — nunca `float`.
- ARS y USD permanecen completamente separados: `Money` no permite sumar ni
  comparar montos de distinta moneda.
- La versión Android (biometría nativa) queda pendiente para una siguiente
  etapa; la capa `app/` no depende de la UI y se puede reutilizar tal cual.
