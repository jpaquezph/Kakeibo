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

Se usa `flet build windows` (no `flet pack`): `flet pack` empaqueta con
PyInstaller el cliente de escritorio "full" de Flet, que incluye soporte de
video (media_kit) y depende de Windows Media Foundation
(`MFReadWrite.dll`) — ausente por defecto en ediciones "N"/"KN" de Windows y
en algunas instalaciones tipo Server, lo que rompe la app con el error
`"no se encontró MFReadWrite.dll"`. `flet build windows` compila un cliente
propio con Flutter que no incluye esa dependencia.

Requiere, en la máquina que compila:

- [Flutter SDK](https://docs.flutter.dev/get-started/install/windows) (canal stable) en el PATH.
- Visual Studio Build Tools 2022 con el workload "Desktop development with C++"
  (`winget install --id Microsoft.VisualStudio.2022.BuildTools --override "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`).
- Modo de desarrollador de Windows activado (Configuración → Privacidad y
  seguridad → Para desarrolladores → Modo de desarrollador), necesario para
  que Flutter pueda crear symlinks al compilar los plugins.
- [Inno Setup 6](https://jrsoftware.org/isdl.php).

```bash
flutter doctor          # verificar que Visual Studio se detecta OK

.venv\Scripts\flet build windows --product "Kakeibo" --org "com.kakeibo" ^
  --company "Kakeibo" --yes --no-rich-output ^
  --exclude .venv .git .claude .pytest_cache backups dist installer packaging ^
            Markdowns tests "Kakeibo-Windows.zip" "Kakeibo.spec" "kakeibo.db" ^
            "kakeibo_debug.log" "README.md" "requirements.txt" "pytest.ini" ^
            ".gitignore" "build" "Logo-Kakeibo.png" "Logo-Kakeibo-claro.png" ^
            "Relevamiento tecnico.txt" docs scripts "Documentacion usuario" "kakeibo_run.log"
```

(El `--exclude` es importante: sin él, `flet build` copia *toda* la carpeta
del proyecto tal cual, incluyendo `.venv` y `.git`, y también la base
`kakeibo.db` con tus datos. El instalador nunca debe llevar una base: cada
instalación arranca vacía y la app crea la base al abrirse por primera vez.
Antes de compilar el instalador, verificar que `build\windows` no tenga
ningún `.db`, `.log` ni backup; y no abrir `build\windows\Kakeibo.exe` antes
de compilarlo, porque eso crea una base ahí adentro.)

Esto genera `build\windows\` (una carpeta, no un único .exe — son varias DLLs
de Flutter + el ejecutable). Después, compilar el instalador:

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
