"""Utilitários e correções de interface (Qt Hacks).
Extraído de main_window.py.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QEvent, QObject, Qt


class ComboPopupNoWhiteBorder(QObject):
    """
    Fix específico do Linux/Arch para QComboBox.
    Remove bordas brancas indesejadas e ajusta sombras em alguns temas GTK/Qt.
    """

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        """Filtra eventos para corrigir bordas de ComboBox."""
        if obj is None or event is None:
            return super().eventFilter(obj, event)

        if event.type() in (QEvent.Type.Polish, QEvent.Type.Show):
            try:
                cls: str = ""
                if hasattr(obj, "metaObject"):
                    meta = obj.metaObject()
                    if meta is not None:
                        cls = meta.className() or ""

                if "QComboBoxPrivateContainer" in cls:
                    # Type ignore necessário pois obj é QObject genérico
                    widget: Any = obj
                    widget.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                    widget.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
                    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    widget.setStyleSheet("""
                        QFrame { background-color: transparent; border: none; margin: 0px; padding: 0px; }
                    """)
            except Exception:
                pass  # Evento de popup ignorado
        return super().eventFilter(obj, event)
