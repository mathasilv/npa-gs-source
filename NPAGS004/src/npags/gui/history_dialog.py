# src/npags/gui/history_dialog.py

"""
Diálogo para filtragem e carga de dados históricos.
Refatorado: Sem estilos manuais.
"""

from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QFrame, 
    QDateTimeEdit, QCheckBox, QPushButton, QLabel, QGridLayout
)
from PyQt6.QtCore import QDateTime, Qt
from npags.decoders.loader import DecoderLoader

class HistoryFilterDialog(QDialog):
    def __init__(self, parent=None, current_schema: str = None):
        super().__init__(parent)
        self.setWindowTitle("Filtro de Histórico")
        self.resize(550, 420)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # --- 1. SELEÇÃO ---
        dec_layout = QVBoxLayout()
        dec_layout.setSpacing(8)
        
        lbl_schema = QLabel("Esquema de Visualização:")
        dec_layout.addWidget(lbl_schema)
        
        self.combo_schema = QComboBox()
        self.combo_schema.setFixedHeight(35)
        self._load_schemas(current_schema)
        dec_layout.addWidget(self.combo_schema)
        
        main_layout.addLayout(dec_layout)

        # --- CORREÇÃO: Linha divisória usando styles.py ---
        line = QFrame()
        line.setObjectName("SeparatorLine") # Definido no CSS global
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
        
        dates_grid.addWidget(QLabel("Início:"), 0, 0)
        self.dt_start = self._create_dt_edit()
        dates_grid.addWidget(self.dt_start, 1, 0)
        
        dates_grid.addWidget(QLabel("Fim:"), 0, 1)
        self.dt_end = self._create_dt_edit()
        self.dt_end.setDateTime(QDateTime.currentDateTime())
        dates_grid.addWidget(self.dt_end, 1, 1)
        time_section.addLayout(dates_grid)
        
        # Botões Rápidos
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(10)
        self._add_quick_btn(quick_layout, "1h", 1)
        self._add_quick_btn(quick_layout, "6h", 6)
        self._add_quick_btn(quick_layout, "12h", 12)
        self._add_quick_btn(quick_layout, "24h", 24)
        self._add_quick_btn(quick_layout, "Tudo", 0)
        
        time_section.addLayout(quick_layout)
        main_layout.addLayout(time_section)
        main_layout.addStretch()

        # --- 3. AÇÕES ---
        bottom_layout = QHBoxLayout()
        
        self.check_clear = QCheckBox("Limpar gráficos atuais")
        self.check_clear.setChecked(True)
        bottom_layout.addWidget(self.check_clear)
        bottom_layout.addStretch()
        
        # Botão Cancelar (Vermelho)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btn_cancel") 
        btn_cancel.setFixedSize(100, 32)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)
        
        # Botão Filtrar (Verde)
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

    def _load_schemas(self, current):
        try:
            loader = DecoderLoader()
            schemas = loader.scan_decoders()
            for s in schemas: 
                self.combo_schema.addItem(s)
            if current:
                self.combo_schema.setCurrentText(current)
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

    def get_data(self) -> dict:
        return {
            'start': self.dt_start.dateTime().toPyDateTime(),
            'end': self.dt_end.dateTime().toPyDateTime(),
            'limit': 0,
            'clear': self.check_clear.isChecked(),
            'schema': self.combo_schema.currentText()
        }