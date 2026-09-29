"""Motor para sacar las capturas del manual: recorre los controles de la app,
dispara sus eventos como si el usuario tocara, y saca capturas marcando la
posicion de cada elemento senalado (se pinta de un color unico y se lo busca
en la imagen)."""
from __future__ import annotations

import asyncio
import dataclasses
import io
import json
from pathlib import Path

import flet as ft
from PIL import Image, ImageChops

try:  # tamanos reales de la ventana aunque Windows tenga zoom (125 %, 150 %...)
    import ctypes as _ct
    _ct.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

MARCA = "#FF00FF"
PIXEL_RATIO = 1.0  # las cajas y recortes estan en pixeles de la captura
TITULO_VENTANA = "Kakeibo - captura del manual"


def capturar_ventana(titulo: str) -> Image.Image:
    """Captura el area cliente de la ventana con PrintWindow
    (PW_CLIENTONLY | PW_RENDERFULLCONTENT): funciona aunque la ventana este
    tapada por otras, asi no se usa la pantalla del usuario."""
    import ctypes
    from ctypes import wintypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.FindWindowW.restype = wintypes.HWND
    hwnd = user32.FindWindowW(None, titulo)
    if not hwnd:
        raise RuntimeError(f"No encontre la ventana {titulo!r}")
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top

    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    hdc_ventana = user32.GetDC(wintypes.HWND(hwnd))
    hdc = gdi32.CreateCompatibleDC(hdc_ventana)
    bmp = gdi32.CreateCompatibleBitmap(hdc_ventana, w, h)
    gdi32.SelectObject(hdc, bmp)
    user32.PrintWindow(wintypes.HWND(hwnd), hdc, 3)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(hdc)
    user32.ReleaseDC(wintypes.HWND(hwnd), hdc_ventana)
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)
_BOTONES = (ft.ElevatedButton, ft.FilledButton, ft.OutlinedButton, ft.TextButton, ft.Button)


def hijos(c):
    if not dataclasses.is_dataclass(c):
        return
    for f in dataclasses.fields(c):
        if f.name.startswith("_") or f.name in ("parent", "page", "data"):
            continue
        try:
            v = getattr(c, f.name, None)
        except Exception:
            continue
        if isinstance(v, ft.BaseControl):
            yield v
        elif isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, ft.BaseControl):
                    yield x


def texto(c) -> str:
    if isinstance(c, ft.Text):
        return c.value or ""
    if isinstance(c, (ft.TextField, ft.Dropdown)):
        return c.label if isinstance(c.label, str) else ""
    if isinstance(c, (ft.Checkbox, ft.Switch)):
        return c.label if isinstance(c.label, str) else ""
    if isinstance(c, _BOTONES):
        if isinstance(c.content, str):
            return c.content
        if isinstance(c.content, ft.Text):
            return c.content.value or ""
    if isinstance(c, ft.Segment):
        return c.label.value if isinstance(c.label, ft.Text) else ""
    return ""


class Motor:
    def __init__(self, page: ft.Page, salida: Path):
        self.page = page
        self.salida = salida
        salida.mkdir(parents=True, exist_ok=True)
        previas = salida / "figuras.json"
        self.figuras: dict[str, dict] = json.loads(previas.read_text(encoding="utf-8")) if previas.exists() else {}

    # ---------- busqueda ----------
    def raices(self):
        p = self.page
        raices = list(p.controls) + list(p.overlay)
        try:
            raices += [d for d in p._dialogs.controls if d.open]
        except Exception:
            pass
        return raices

    def recorrer(self, solo_dialogo: bool = False):
        """(control, cadena de ancestros). Con solo_dialogo, solo el dialogo de arriba."""
        if solo_dialogo:
            abiertos = [d for d in self.page._dialogs.controls if d.open]
            raices = abiertos[-1:]
        else:
            raices = self.raices()
        pila = [(r, []) for r in reversed(raices)]
        while pila:
            c, anc = pila.pop()
            yield c, anc
            for h in reversed(list(hijos(c))):
                pila.append((h, anc + [c]))

    def buscar(self, que=None, tipo=None, n: int = 0, dialogo: bool = False, exacto: bool = True, cond=None):
        encontrados = []
        for c, anc in self.recorrer(dialogo):
            if tipo is not None and not isinstance(c, tipo):
                continue
            if que is not None:
                t = texto(c)
                if not (t == que if exacto else que in t):
                    continue
            if cond is not None and not cond(c):
                continue
            encontrados.append((c, anc))
        if len(encontrados) <= n:
            raise LookupError(f"No encontre {que!r} ({tipo}) n={n}; hay {len(encontrados)}")
        return encontrados[n]

    def control(self, *a, **k):
        return self.buscar(*a, **k)[0]

    def clickeable(self, *a, **k):
        """El control (o su ancestro mas cercano) que responde a click. Si
        hay varias coincidencias, la primera que se pueda tocar a partir de n."""
        n = k.pop("n", 0)
        while True:
            c, anc = self.buscar(*a, n=n, **k)  # LookupError si se terminan
            for x in [c] + list(reversed(anc)):
                if getattr(x, "on_click", None) and not getattr(x, "disabled", False):
                    return x
            n += 1

    def en_ficha(self, ancla: str, que: str, tipo=None):
        """El control `que` dentro de la ficha (celda de grilla con `col`) que
        contiene el texto `ancla`."""
        _, anc = self.buscar(ancla, ft.Text)
        ficha = next(x for x in reversed(anc) if isinstance(getattr(x, "col", None), dict))
        pila = [ficha]
        while pila:
            c = pila.pop()
            if texto(c) == que and (tipo is None or isinstance(c, tipo)):
                return c
            pila.extend(hijos(c))
        todos, pila = [], [ficha]
        while pila:
            c = pila.pop()
            todos.append((type(c).__name__, texto(c), getattr(c, "content", None) if not isinstance(getattr(c, "content", None), ft.BaseControl) else "ctrl"))
            pila.extend(hijos(c))
        raise LookupError(f"No hay {que!r} en la ficha de {ancla!r}: {todos}")

    async def click_en_ficha(self, ancla: str, que: str, tipo=None, espera: float = 1.0):
        c = self.en_ficha(ancla, que, tipo)
        await c._trigger_event("click", None)
        await self.esperar(espera)

    def por_tooltip(self, tooltip: str, n: int = 0, dialogo: bool = False):
        return self.control(n=n, dialogo=dialogo, cond=lambda c: getattr(c, "tooltip", None) == tooltip)

    # ---------- acciones ----------
    async def esperar(self, s: float = 0.6):
        await asyncio.sleep(s)

    async def click(self, *a, espera: float = 0.8, **k):
        c = self.clickeable(*a, **k)
        await c._trigger_event("click", None)
        await self.esperar(espera)
        return c

    async def escribir(self, label: str, valor: str, n: int = 0, dialogo: bool = False):
        c = self.control(label, ft.TextField, n=n, dialogo=dialogo)
        c.value = valor
        c.update()
        if c.on_change:
            await c._trigger_event("change", valor)
        await self.esperar(0.2)
        return c

    async def elegir(self, label: str, valor: str, n: int = 0, dialogo: bool = False):
        """`valor`: la clave de la opcion o su texto visible."""
        c = self.control(label, ft.Dropdown, n=n, dialogo=dialogo)
        for op in c.options or []:
            if op.text == valor and op.key is not None:
                valor = op.key
                break
        c.value = valor
        c.update()
        if c.on_select:
            await c._trigger_event("select", valor)
        await self.esperar(0.3)
        return c

    async def tildar(self, label: str, valor: bool = True, dialogo: bool = False):
        c = self.control(label, ft.Checkbox, dialogo=dialogo)
        c.value = valor
        c.update()
        if c.on_change:
            await c._trigger_event("change", str(valor).lower())
        await self.esperar(0.3)
        return c

    async def segmento(self, valor: str, dialogo: bool = True, n: int = 0):
        seg = self.control(tipo=ft.SegmentedButton, dialogo=dialogo, n=n,
                           cond=lambda s: any(x.value == valor for x in s.segments))
        seg.selected = [valor]
        seg.update()
        if seg.on_change:
            await seg._trigger_event("change", json.dumps([valor]))
        await self.esperar(0.4)
        return seg

    async def desplazar(self, ancla: str, offset: float, dialogo: bool = False, exacto: bool = True):
        """Scrollea el contenedor con scroll que contiene el texto `ancla`
        (offset en px logicos desde arriba; -1 = hasta el final)."""
        _, anc = self.buscar(ancla, dialogo=dialogo, exacto=exacto)
        for x in reversed(anc):
            if getattr(x, "scroll", None) is not None and hasattr(x, "scroll_to"):
                await x.scroll_to(offset=offset, duration=0)
                await self.esperar(0.6)
                return x
        raise LookupError(f"No hay scroll alrededor de {ancla!r}")

    async def cerrar_dialogos(self):
        while self.page.pop_dialog() is not None:
            await self.esperar(0.3)

    # ---------- capturas ----------
    async def _png(self) -> Image.Image:
        await asyncio.sleep(0.25)
        return capturar_ventana(TITULO_VENTANA)

    def _marcar(self, c):
        guardado = {}

        def poner(attr, valor):
            guardado[attr] = getattr(c, attr, None)
            setattr(c, attr, valor)

        if isinstance(c, (ft.TextField, ft.Dropdown)):
            poner("filled", True)
            poner("bgcolor", MARCA)
            poner("fill_color", MARCA)
        elif isinstance(c, ft.ElevatedButton):
            poner("bgcolor", MARCA)
        elif isinstance(c, (_BOTONES, ft.SegmentedButton)):
            poner("style", ft.ButtonStyle(bgcolor=MARCA))
        elif isinstance(c, ft.IconButton):
            poner("bgcolor", MARCA)
        elif isinstance(c, ft.Text):
            poner("bgcolor", MARCA)
            poner("color", MARCA)
            poner("style", ft.TextStyle(bgcolor=MARCA, color=MARCA))
        elif isinstance(c, ft.Checkbox):
            poner("fill_color", MARCA)
            poner("label_style", ft.TextStyle(bgcolor=MARCA, color=MARCA))
        elif isinstance(c, ft.Switch):
            poner("track_color", MARCA)
            poner("thumb_color", MARCA)
        elif isinstance(c, ft.Icon):
            poner("color", MARCA)
        else:  # Container y el resto
            poner("bgcolor", MARCA)

        def restaurar():
            for k, v in guardado.items():
                setattr(c, k, v)
        return restaurar

    def _marcar_dialogo(self, dlg):
        """Pinta el fondo del dialogo para ubicar su recuadro."""
        previo = dlg.bgcolor
        dlg.bgcolor = MARCA
        dlg.update()

        def restaurar():
            dlg.bgcolor = previo
            dlg.update()
        return restaurar

    @staticmethod
    def _bbox(im: Image.Image):
        r, g, b = im.split()
        m = ImageChops.multiply(
            ImageChops.multiply(r.point(lambda v: 255 if v > 215 else 0), g.point(lambda v: 255 if v < 60 else 0)),
            b.point(lambda v: 255 if v > 215 else 0),
        )
        return m.getbbox()

    async def captura(self, nombre: str, marcas: list | None = None, recorte: tuple | None = None, pie: str = "",
                      solo_dialogo: bool = False):
        """Guarda <nombre>.png y las cajas (en px de la imagen) de cada marca.
        `marcas`: lista de (control, titulo, explicacion), en orden (1, 2, 3...).
        `recorte`: (x0, y0, x1, y1) en px de la captura. `solo_dialogo`:
        recorta a la ventana (dialogo) abierta, con un margen."""
        marcas = marcas or []
        textos = [(t, e) for _, t, e in marcas]
        cajas = []
        if solo_dialogo:
            dlg = [d for d in self.page._dialogs.controls if d.open][-1]
            restaurar = self._marcar_dialogo(dlg)
            await self.esperar(0.4)
            caja_dlg = self._bbox(await self._png())
            restaurar()
            await self.esperar(0.4)
            if caja_dlg:
                m = 24
                recorte = (max(caja_dlg[0] - m, 0), max(caja_dlg[1] - m, 0), caja_dlg[2] + m, caja_dlg[3] + m)
        for c, _, _ in marcas:
            restaurar = self._marcar(c)
            c.update()
            await self.esperar(0.35)
            caja = self._bbox(await self._png())
            restaurar()
            c.update()
            if caja is None:
                print(f"  ! {nombre}: no se encontro la marca de {type(c).__name__} {texto(c)!r}")
            cajas.append(caja)
        await self.esperar(0.35)
        im = await self._png()
        if recorte == "marcas":  # alrededor de lo senalado, con aire
            validas = [cj for cj in cajas if cj]
            mx, my = 330, 260
            recorte = (max(min(c[0] for c in validas) - mx, 0), max(min(c[1] for c in validas) - my, 0),
                       max(c[2] for c in validas) + mx, max(c[3] for c in validas) + my)
        if recorte:
            x0, y0 = int(recorte[0]), int(recorte[1])
            x1, y1 = min(int(recorte[2]), im.size[0]), min(int(recorte[3]), im.size[1])
            im = im.crop((x0, y0, x1, y1))
            cajas = [None if cj is None else (cj[0] - x0, cj[1] - y0, cj[2] - x0, cj[3] - y0) for cj in cajas]
        im.save(self.salida / f"{nombre}.png")
        self.figuras[nombre] = {"tam": im.size, "cajas": cajas, "textos": textos, "pie": pie}
        (self.salida / "figuras.json").write_text(json.dumps(self.figuras, indent=1), encoding="utf-8")
        print(f"  captura {nombre} {im.size} marcas={len(cajas)}")
