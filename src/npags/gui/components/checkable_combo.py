# src/npags/gui/components/checkable_combo.py
"""
Widget de ComboBox com checkboxes para seleção múltipla.

Componente reutilizável usado em:
- DecoderSelectorFrame (sidebar_params.py)
- HistoryFilterDialog (history_dialog.py)
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)

from npags.gui.styles import THEME_COLORS


class CheckableComboBox(QComboBox):
    """
    ComboBox com checkboxes para seleção múltipla.

    Usa QCheckBox reais para garantir consistência visual com o resto da UI.

    Signals:
        selectionChanged: Emitido quando a seleção muda (lista de itens selecionados).
    """

    selectionChanged = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        # Container para os checkboxes
        self._popup = QFrame()
        self._popup.setWindowFlags(Qt.WindowType.Popup)
        self._popup.setFrameShape(QFrame.Shape.StyledPanel)
        self._popup.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['background']};
                border: 1px solid {THEME_COLORS['accent']};
                border-radius: 4px;
            }}
            QCheckBox {{
                padding: 4px 6px;
                color: {THEME_COLORS['text']};
            }}
            QCheckBox:hover {{
                background-color: {THEME_COLORS['surface_secondary']};
            }}
        """)
        
        self._popup_layout = QVBoxLayout(self._popup)
        self._popup_layout.setContentsMargins(2, 2, 2, 2)
        self._popup_layout.setSpacing(0)
        
        # Armazena checkboxes e estado
        self._checkboxes: dict[str, QCheckBox] = {}
        self._has_all_option = False
        self._display_text = "Nenhum selecionado"

    def showPopup(self) -> None:
        """Mostra o popup customizado com checkboxes."""
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.setMinimumWidth(self.width())
        self._popup.move(pos)
        self._popup.show()

    def hidePopup(self) -> None:
        """Esconde o popup."""
        self._popup.hide()

    def addAllOption(self) -> None:
        """Adiciona opção 'Todos' no topo da lista."""
        if self._has_all_option:
            return

        checkbox = QCheckBox("Todos")
        checkbox.setChecked(False)
        checkbox.stateChanged.connect(lambda state: self._on_all_toggled(state))
        
        self._popup_layout.insertWidget(0, checkbox)
        self._checkboxes["__ALL__"] = checkbox
        self._has_all_option = True

    def addCheckableItem(self, text: str, checked: bool = False) -> None:
        """Adiciona item com checkbox."""
        checkbox = QCheckBox(text)
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(lambda: self._on_item_toggled())
        
        self._popup_layout.addWidget(checkbox)
        self._checkboxes[text] = checkbox
        self._update_display_text()

    def _on_all_toggled(self, state: int) -> None:
        """Handler quando 'Todos' é marcado/desmarcado."""
        is_checked = state == Qt.CheckState.Checked.value
        
        for key, checkbox in self._checkboxes.items():
            if key != "__ALL__":
                checkbox.blockSignals(True)
                checkbox.setChecked(is_checked)
                checkbox.blockSignals(False)
        
        self._update_display_text()
        self.selectionChanged.emit(self.getCheckedItems())

    def _on_item_toggled(self) -> None:
        """Handler quando um item individual é marcado/desmarcado."""
        self._update_all_checkbox_state()
        self._update_display_text()
        self.selectionChanged.emit(self.getCheckedItems())

    def _update_all_checkbox_state(self) -> None:
        """Atualiza o checkbox 'Todos' baseado no estado dos outros."""
        if "__ALL__" not in self._checkboxes:
            return

        all_checkbox = self._checkboxes["__ALL__"]
        regular_checkboxes = [cb for key, cb in self._checkboxes.items() if key != "__ALL__"]

        if not regular_checkboxes:
            return

        all_checked = all(cb.isChecked() for cb in regular_checkboxes)
        
        all_checkbox.blockSignals(True)
        all_checkbox.setChecked(all_checked)
        all_checkbox.blockSignals(False)

    def _update_display_text(self) -> None:
        """Atualiza texto exibido no combo fechado."""
        checked = self.getCheckedItems()
        total_regular = len([k for k in self._checkboxes.keys() if k != "__ALL__"])

        if not checked:
            self._display_text = "Nenhum selecionado"
        elif len(checked) == total_regular and total_regular > 0:
            self._display_text = f"Todos ({total_regular})"
        elif len(checked) == 1:
            self._display_text = checked[0]
        else:
            self._display_text = f"{len(checked)} selecionados"

        self.repaint()

    def getCheckedItems(self) -> list[str]:
        """Retorna lista de itens marcados (exceto __ALL__)."""
        checked = []
        for text, checkbox in self._checkboxes.items():
            if text == "__ALL__":
                continue
            if checkbox.isChecked():
                checked.append(text)
        return checked

    def setCheckedItems(self, items: list[str]) -> None:
        """Define quais itens estão marcados."""
        for text, checkbox in self._checkboxes.items():
            if text == "__ALL__":
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(text in items)
            checkbox.blockSignals(False)
        
        self._update_all_checkbox_state()
        self._update_display_text()

    def selectAll(self) -> None:
        """Seleciona todos os itens."""
        for checkbox in self._checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
        self._update_display_text()

    def clear(self) -> None:
        """Limpa todos os itens."""
        while self._popup_layout.count():
            item = self._popup_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._checkboxes.clear()
        self._has_all_option = False
        self._display_text = "Nenhum selecionado"

    def paintEvent(self, event: Any) -> None:
        """Override para mostrar texto customizado no combo fechado."""
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = self._display_text
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def mousePressEvent(self, event: Any) -> None:
        """Override para mostrar/esconder popup ao clicar."""
        if self._popup.isVisible():
            self.hidePopup()
        else:
            self.showPopup()
