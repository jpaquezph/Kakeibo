# Manual de uso: capturas y PDF

Genera `Kakeibo - Manual de uso <versión>.pdf` con capturas reales de la app,
señaladas con recuadros, flechas y números, respetando el manual de marca
(ámbar solo sobre tinta, azul sobre papel, Segoe UI).

No usa datos reales: arma una base de ejemplo (`demo.db`) en esta carpeta.

## Requisitos

Además del entorno de la app (`.venv`), estas dos librerías solo para el manual:

```bash
.venv\Scripts\python -m pip install -r scripts\manual\requirements.txt
```

## Uso

```bash
cd scripts\manual
..\..\.venv\Scripts\python capturar.py          # abre la app y saca todas las capturas (~5 min)
..\..\.venv\Scripts\python armar_manual.py      # dibuja las flechas y arma el PDF
```

`capturar.py nombre ...` rehace solo algunas escenas (por ejemplo
`capturar.py tarjetas prestamos`); las demás capturas se conservan.

## Cómo funciona

- `datos_demo.py`: la base de ejemplo (una familia ficticia).
- `motor.py`: recorre los controles de Flet, dispara sus eventos como si el
  usuario tocara, y captura la ventana con `PrintWindow` (funciona aunque esté
  tapada). Para saber dónde va cada flecha, pinta el control de magenta, lo
  busca en la imagen y lo restaura.
- `escenas.py`: el recorrido de la app. Cada marca es
  `(control, título, explicación)`; el número de la flecha es su posición.
- `anotar.py`: dibuja recuadros, números y flechas sobre las capturas.
- `armar_manual.py`: el texto del manual y la maquetación del PDF.

Al cambiar la interfaz (textos de botones, campos), ajustar `escenas.py`: si
un control no se encuentra, la corrida lo informa con su nombre.
