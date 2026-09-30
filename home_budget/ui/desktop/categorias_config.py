"""Configuracion -> Categorias: ver, agregar, quitar y volver a agregar categorias.

Quitar una categoria no borra nada: lo ya cargado con ella (movimientos,
compras, gastos fijos) la conserva, y solo deja de ofrecerse en los formularios.
"""
from __future__ import annotations

import flet as ft

from ...app.domain.models import TipoMovimiento
from ...app.repositories.categorias import CategoriaRepository
from .. import theme
from .movimientos_view import _COLORES_CATEGORIA_NUEVA


def build_categorias_seccion(page: ft.Page, categoria_repo: CategoriaRepository) -> ft.Control:
    cuerpo = ft.Column(spacing=16)
    error_texto = ft.Text("", size=12, color=theme.EXPENSE_RED, visible=False)

    def mostrar_error(mensaje: str):
        error_texto.value, error_texto.visible = mensaje, True
        page.update()

    def refrescar(actualizar: bool = True):
        cuerpo.controls = [
            ft.Text("Quitar una categoría no borra nada: lo que ya cargaste con ella la conserva. "
                    "Solo deja de aparecer para elegir.", size=12, color=theme.TEXT_SECONDARY),
            error_texto,
            _bloque(TipoMovimiento.EGRESO, "De egreso"),
            _bloque(TipoMovimiento.INGRESO, "De ingreso"),
        ]
        if actualizar:
            page.update()

    def _chip(c) -> ft.Control:
        motivo = categoria_repo.puede_quitarse(c)
        return ft.Container(
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=c.color, border_radius=5),
                    ft.Text(c.nombre, size=12, color=theme.TEXT_PRIMARY),
                    ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, size=14, color=theme.TEXT_MUTED, tooltip=motivo) if motivo else
                    ft.Container(
                        ft.Icon(ft.Icons.CLOSE_ROUNDED, size=15, color=theme.EXPENSE_RED),
                        on_click=lambda e, cat=c: confirmar_quitar(cat), tooltip="Quitar categoría",
                        border_radius=10, padding=1,
                    ),
                ],
                spacing=6, tight=True,
            ),
            padding=theme.pad(horizontal=10, vertical=5), border_radius=16,
            bgcolor=theme.SURFACE_ALT, border=theme.border_all(1, theme.BORDER),
        )

    def _bloque(tipo: TipoMovimiento, titulo: str) -> ft.Control:
        activas = categoria_repo.listar(tipo)
        quitadas = [c for c in categoria_repo.listar(tipo, incluir_quitadas=True) if not c.activa]
        nombre_f = ft.TextField(label="Nueva categoría", dense=True, width=240, filled=True, bgcolor=theme.SURFACE_ALT,
                                border_radius=theme.RADIUS_SM, border_color=theme.BORDER)

        def agregar(_e=None):
            nombre = (nombre_f.value or "").strip()
            if not nombre:
                return
            color = _COLORES_CATEGORIA_NUEVA[len(categoria_repo.listar(incluir_quitadas=True)) % len(_COLORES_CATEGORIA_NUEVA)]
            try:
                categoria_repo.crear(nombre, color, "label_rounded", tipo)
            except ValueError as exc:
                mostrar_error(str(exc))
                return
            error_texto.visible = False
            refrescar()

        nombre_f.on_submit = agregar
        controles = [
            ft.Text(titulo, size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
            ft.Row([_chip(c) for c in activas], wrap=True, spacing=8, run_spacing=8),
            ft.Row([nombre_f, ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, icon_color=theme.CONFIG_COLOR,
                                            tooltip="Agregar categoría", on_click=agregar)], spacing=4),
        ]
        if quitadas:
            controles.append(ft.Row(
                [ft.Text("Quitadas:", size=12, color=theme.TEXT_MUTED)] + [
                    ft.TextButton(c.nombre, icon=ft.Icons.UNDO_ROUNDED, tooltip="Volver a agregarla",
                                  style=ft.ButtonStyle(color=theme.TEXT_SECONDARY, padding=theme.pad(horizontal=6, vertical=2)),
                                  on_click=lambda e, cat=c: restaurar(cat))
                    for c in quitadas
                ],
                wrap=True, spacing=4, run_spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ))
        return ft.Column(controles, spacing=8)

    def restaurar(c):
        categoria_repo.crear(c.nombre, c.color, c.icono, c.tipo)
        error_texto.visible = False
        refrescar()

    def confirmar_quitar(c):
        detalle = ("Lo que ya está cargado con esta categoría la conserva: no queda sin categoría."
                   if categoria_repo.usos(c.id) else "No tiene nada cargado todavía.")

        def quitar(_e):
            page.pop_dialog()
            try:
                categoria_repo.quitar(c.id)
            except ValueError as exc:
                mostrar_error(str(exc))
                return
            error_texto.visible = False
            refrescar()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Quitar categoría"),
            content=ft.Container(ft.Text(
                f'¿Quitar "{c.nombre}"? Ya no va a aparecer para elegir.\n\n{detalle}', size=13,
            ), width=420),
            actions=[
                theme.secondary_button("Cancelar", lambda e: page.pop_dialog()),
                theme.primary_button("Quitar", quitar, color=theme.EXPENSE_RED, icon=ft.Icons.DELETE_OUTLINE_ROUNDED),
            ],
        ))

    refrescar(actualizar=False)
    return cuerpo
