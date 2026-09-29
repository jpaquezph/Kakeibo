"""Dibuja sobre cada captura los recuadros, numeros y flechas del manual."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

AZUL = (0, 60, 151)
BLANCO = (255, 255, 255)
R = 23  # radio del numero (se agranda en capturas grandes)
GROSOR = 5


def recortar_negro(im: Image.Image) -> Image.Image:
    """Saca la franja negra que a veces queda abajo o a la derecha (zona de
    la ventana que no se dibuja)."""
    gris = im.convert("L")
    w, h = im.size
    fondo = h
    while fondo > h // 2 and max(gris.crop((0, fondo - 1, w, fondo)).getextrema()) < 40:
        fondo -= 1
    # filas con un tramo negro (la franja puede ocupar solo una esquina)
    while fondo > h // 2:
        fila = list(gris.crop((0, fondo - 1, w, fondo)).get_flattened_data())
        if sum(1 for v in fila if v < 12) > w * 0.02:
            fondo -= 1
        else:
            break
    derecha = w
    while derecha > w // 2 and max(gris.crop((derecha - 1, 0, derecha, fondo)).getextrema()) < 40:
        derecha -= 1
    return im.crop((0, 0, derecha, fondo))


def _solapa(a, b, margen=6):
    return not (a[2] + margen < b[0] or b[2] + margen < a[0] or a[3] + margen < b[1] or b[3] + margen < a[1])


def _flecha(d: ImageDraw.ImageDraw, p0, p1):
    d.line([p0, p1], fill=AZUL, width=GROSOR)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    largo, abre = 18, 0.45
    pts = [p1,
           (p1[0] - largo * math.cos(ang - abre), p1[1] - largo * math.sin(ang - abre)),
           (p1[0] - largo * math.cos(ang + abre), p1[1] - largo * math.sin(ang + abre))]
    d.polygon(pts, fill=AZUL)


def _numero(d: ImageDraw.ImageDraw, c, n: int):
    x, y = c
    fuente = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", int(R * 1.3))
    d.ellipse((x - R, y - R, x + R, y + R), fill=AZUL, outline=BLANCO, width=3)
    d.text((x, y - 1), str(n), fill=BLANCO, font=fuente, anchor="mm")


def anotar(origen: Path, destino: Path, cajas: list) -> None:
    global R
    im = recortar_negro(Image.open(origen).convert("RGB"))
    w, h = im.size
    R = 29 if w > 1500 else 23
    d = ImageDraw.Draw(im)
    ocupados = [tuple(c) for c in cajas if c]
    badges = []
    for n, caja in enumerate(cajas, start=1):
        if not caja:
            continue
        x0, y0, x1, y1 = caja
        x0, y0, x1, y1 = max(x0 - 7, 2), max(y0 - 7, 2), min(x1 + 7, w - 3), min(y1 + 7, h - 3)
        d.rounded_rectangle((x0, y0, x1, y1), radius=12, outline=AZUL, width=GROSOR)
        grande = (x1 - x0) > w * 0.45 or (y1 - y0) > h * 0.45
        cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
        dist = 70
        if grande:
            candidatos = [((x0 + R + 6, y0 + R + 6), None)]
        else:
            candidatos = [
                ((x0 - dist, cy), (x0 - 2, cy)), ((x1 + dist, cy), (x1 + 2, cy)),
                ((cx, y0 - dist + 10), (cx, y0 - 2)), ((cx, y1 + dist - 10), (cx, y1 + 2)),
                ((x0 - dist, y0 - dist + 20), (x0 + 4, y0 + 4)), ((x1 + dist, y0 - dist + 20), (x1 - 4, y0 + 4)),
            ]
        elegido = None
        for centro, punta in candidatos:
            bx = (centro[0] - R, centro[1] - R, centro[0] + R, centro[1] + R)
            if bx[0] < 2 or bx[1] < 2 or bx[2] > w - 2 or bx[3] > h - 2:
                continue
            if any(_solapa(bx, b) for b in badges) or any(_solapa(bx, o, 2) for o in ocupados if o != tuple(caja)):
                continue
            elegido = (centro, punta)
            break
        if elegido is None:  # sin lugar libre: sobre la esquina del recuadro
            elegido = ((min(max(x0, R + 4), w - R - 4), min(max(y0, R + 4), h - R - 4)), None)
        centro, punta = elegido
        if punta:
            ang = math.atan2(punta[1] - centro[1], punta[0] - centro[0])
            inicio = (centro[0] + R * math.cos(ang), centro[1] + R * math.sin(ang))
            _flecha(d, inicio, punta)
        _numero(d, centro, n)
        badges.append((centro[0] - R, centro[1] - R, centro[0] + R, centro[1] + R))
    im.save(destino)


def anotar_todo(capturas: Path, salida: Path) -> dict:
    salida.mkdir(exist_ok=True)
    figuras = json.loads((capturas / "figuras.json").read_text(encoding="utf-8"))
    for nombre, info in figuras.items():
        anotar(capturas / f"{nombre}.png", salida / f"{nombre}.png", info["cajas"])
    return figuras


if __name__ == "__main__":
    anotar_todo(AQUI / "capturas", AQUI / "anotadas")
    print("ok")
