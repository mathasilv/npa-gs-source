# src/npags/gui/dialogs/history_dialog.py
"""
Dialogo para filtragem e carga de dados historicos.
Com selecao de esquema de visualizacao.
"""

from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QDateTime, Qt
from npags.gui.components import create_styled_combobox
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from npags.decoders.loader import DecoderLoader
from npags.gui.components.checkable_combo import CheckableComboBox
from npags.gui.translations import tr


# Alias para compatibilidade (caso algum código externo use o nome antigo)
SchemaCheckableComboBox = CheckableComboBox


class HistoryFilterDialog(QDialog):
    """Dialogo de filtro de historico com selecao de schema."""

    def __init__(self, parent=None, current_schema: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Filtro de Historico")
        self.resize(550, 450)

        self._current_schema = current_schema

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # --- 1. SELECAO DE SCHEMAS ---
        dec_layout = QVBoxLayout()
        dec_layout.setSpacing(8)

        lbl_schema = QLabel("Esquema de Visualizacao:")
        dec_layout.addWidget(lbl_schema)

        self.combo_schema = create_styled_combobox()
        self.combo_schema.setFixedHeight(35)
        self._load_schemas(current_schema)
        dec_layout.addWidget(self.combo_schema)

        # Dica
        hint_label = QLabel("Selecione um ou mais esquemas para visualizar na dashboard")
        hint_label.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        dec_layout.addWidget(hint_label)

        main_layout.addLayout(dec_layout)

        # --- Linha divisoria ---
        line = QFrame()
        line.setObjectName("SeparatorLine")
        line.setFixedHeight(1)
        main_layout.addWidget(line)

        # --- 2. TEMPO ---
        time_section = QVBoxLayout()
        time_section.setSpacing(15)

        lbl_time = QLabel("Intervalo de Tempo:")
        time_section.addWidget(lbl_time)

        dates_grid = QGridLayout()
        dates_grid.setHorizontalSpacing(15)
        dates_grid.setVerticalSpacing(5)

        dates_grid.addWidget(QLabel("Inicio:"), 0, 0)
        self.dt_start = self._create_dt_edit()
        dates_grid.addWidget(self.dt_start, 1, 0)

        dates_grid.addWidget(QLabel("Fim:"), 0, 1)
        self.dt_end = self._create_dt_edit()
        self.dt_end.setDateTime(QDateTime.currentDateTime())
        dates_grid.addWidget(self.dt_end, 1, 1)
        time_section.addLayout(dates_grid)

        # Botoes Rapidos
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(10)
        self._add_quick_btn(quick_layout, "1h", 1)
        self._add_quick_btn(quick_layout, "6h", 6)
        self._add_quick_btn(quick_layout, "12h", 12)
        self._add_quick_btn(quick_layout, "24h", 24)
        self._add_quick_btn(quick_layout, "Tudo", 0)

        time_section.addLayout(quick_layout)
        main_layout.addLayout(time_section)

        # --- 3. LIMITE DE PACOTES ---
        limit_layout = QHBoxLayout()
        limit_layout.setSpacing(10)

        lbl_limit = QLabel("Limite de pacotes (0 = sem limite):")
        limit_layout.addWidget(lbl_limit)

        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(0, 1000000)
        self.spin_limit.setValue(10000)
        self.spin_limit.setSingleStep(1000)
        self.spin_limit.setFixedWidth(120)
        self.spin_limit.setFixedHeight(32)
        limit_layout.addWidget(self.spin_limit)
        limit_layout.addStretch()

        main_layout.addLayout(limit_layout)
        main_layout.addStretch()

        # --- 4. ACOES ---
        bottom_layout = QHBoxLayout()

        self.check_clear = QCheckBox("Limpar graficos atuais")
        self.check_clear.setChecked(True)
        bottom_layout.addWidget(self.check_clear)
        bottom_layout.addStretch()

        btn_cancel = QPushButton(tr("Cancelar"))
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.setFixedSize(100, 32)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)

        btn_load = QPushButton("Filtrar")
        btn_load.setObjectName("btn_filter")
        btn_load.setFixedSize(100, 32)
        btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_load.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_load)

        main_layout.addLayout(bottom_layout)

    def _create_dt_edit(self):
        dt = QDateTimeEdit(QDateTime.currentDateTime().addSecs(-3600))
        dt.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        dt.setCalendarPopup(True)
        dt.setFixedHeight(32)
        return dt

    def _add_quick_btn(self, layout, text, hours):
        btn = QPushButton(text)
        btn.setObjectName("btn_quick")
        btn.setFixedHeight(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _, h=hours: self._apply_quick_filter(h))
        layout.addWidget(btn)

    def _load_schemas(self, current: str | None):
        """Carrega schemas disponiveis."""
        try:
            loader = DecoderLoader()
            schemas = loader.scan_decoders()

            self.combo_schema.clear()
            self.combo_schema.addItems(schemas)

            # Seleciona o schema atual
            if current and current in schemas:
                self.combo_schema.setCurrentText(current)
            elif schemas:
                self.combo_schema.setCurrentIndex(0)

        except Exception as e:
            self.combo_schema.addItem(f"Erro: {e}")

    def _apply_quick_filter(self, hours):
        now = datetime.now()
        if hours == 0:
            start = now.replace(year=now.year-10)
        else:
            start = now - timedelta(hours=hours)
        self.dt_end.setDateTime(now)
        self.dt_start.setDateTime(start)

    def get_data(self) -> dict[str, Any]:
        """Retorna dados do filtro."""
        selected_schemas = [self.combo_schema.currentText()] if self.combo_schema.currentText() else []

        return {
            'start': self.dt_start.dateTime().toPyDateTime(),
            'end': self.dt_end.dateTime().toPyDateTime(),
            'limit': self.spin_limit.value(),
            'clear': self.check_clear.isChecked(),
            'schemas': selected_schemas,  # Lista de schemas
            'schema': selected_schemas[0] if selected_schemas else None  # Compatibilidade
        }
