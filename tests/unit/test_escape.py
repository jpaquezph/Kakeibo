from home_budget.ui.desktop.components import cerrar_dialogo_con_escape


class _PaginaFalsa:
    """Imita la pila de dialogos de ft.Page (pop_dialog cierra el de arriba)."""

    def __init__(self, dialogos):
        self.dialogos = list(dialogos)

    def pop_dialog(self):
        return self.dialogos.pop() if self.dialogos else None


def test_escape_cierra_solo_el_dialogo_de_arriba():
    page = _PaginaFalsa(["Editar compra", "¿Confirmás los cambios?"])

    assert cerrar_dialogo_con_escape(page, "Escape")
    assert page.dialogos == ["Editar compra"]


def test_escape_sin_dialogos_no_hace_nada():
    page = _PaginaFalsa([])

    assert not cerrar_dialogo_con_escape(page, "Escape")


def test_otras_teclas_no_cierran():
    page = _PaginaFalsa(["Nueva compra"])

    assert not cerrar_dialogo_con_escape(page, "Enter")
    assert not cerrar_dialogo_con_escape(page, "A")
    assert page.dialogos == ["Nueva compra"]
