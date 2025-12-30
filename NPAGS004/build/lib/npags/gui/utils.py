"""
Utilitários e correções de interface (Qt Hacks).
Extraído de main_window.py.
"""

from PyQt6.QtCore import QObject, QEvent, Qt

class ComboPopupNoWhiteBorder(QObject):
    """
    Fix específico do Linux/Arch para QComboBox.
    Remove bordas brancas indesejadas e ajusta sombras em alguns temas GTK/Qt.
    """
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Polish, QEvent.Type.Show):
            try:
                cls = obj.metaObject().className() if hasattr(obj, "metaObject") else ""
                if "QComboBoxPrivateContainer" in cls:
                    obj.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                    obj.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
                    obj.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    obj.setStyleSheet("""
                        QFrame { background-color: #2d2d2d; border: 1px solid #3d3d3d; margin: 0px; padding: 0px; }
                    """)
            except Exception:
                pass
        return super().eventFilter(obj, event)