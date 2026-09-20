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

## Asistente financiero (IA local, sin API ni costo)

La sección "Asistente" responde preguntas en lenguaje natural sobre los
propios datos del usuario (movimientos, categorías, tarjetas, préstamos,
gastos fijos). Corre 100% local con [Ollama](https://ollama.com/): no usa
ninguna API paga, no requiere API key y los datos financieros nunca salen
de la PC del usuario.

Requisitos (una sola vez, en la máquina donde se usa la app):

```bash
winget install --id Ollama.Ollama
ollama pull llama3.2:3b
```

Ollama queda corriendo en segundo plano en `http://localhost:11434`. La
sección Asistente muestra un aviso si no lo detecta corriendo o si el
modelo todavía no está descargado, con la solución sugerida. El modelo y
el host son configurables desde el ícono de engranaje (por si se quiere
usar un modelo más grande/mejor, como `llama3.1:8b` o `qwen2.5:7b`, a
costa de respuestas más lentas sin GPU).

- La recuperación de contexto (la parte "RAG") no usa embeddings/vector
  store: al ser datos tabulares, arma el contexto con agregados SQL
  (totales históricos por categoría/tarjeta) más los movimientos del
  período que la pregunta menciona, acotados a un máximo de filas para que
  no crezca sin límite con los años. Es de solo consulta: no crea, edita
  ni borra nada.
- Sin Ollama corriendo, el resto de la app funciona exactamente igual que
  antes (100% local, sin conexión).

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
            ".gitignore" "build"
```

(El `--exclude` es importante: sin él, `flet build` copia *toda* la carpeta
del proyecto tal cual, incluyendo `.venv` y `.git`.)

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
