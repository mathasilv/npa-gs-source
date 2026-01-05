# src/npags/gui/dialogs/alerts_config_dialog.py
"""
Diálogo de configuração de alertas.

Permite ao usuário:
    - Adicionar/editar/remover alertas
    - Configurar thresholds (min/max) por campo
    - Definir severidade e som
    - Salvar/carregar configurações

Design agnóstico: lista campos disponíveis dinamicamente.
"""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from npags.gui.components import create_styled_combobox
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from npags.gui.translations import tr
from npags.gui.styles import THEME_COLORS
from npags.gui.widgets.alerts_widget import AlertConfig, AlertEngine, AlertSeverity


class AlertConfigDialog(QDialog):
    """
    Diálogo para configurar alertas de campos.
    """

    def __init__(
        self,
        alert_engine: AlertEngine,
        available_fields: dict[str, dict[str, Any]],
        parent: QWidget | None = None
    ) -> None:
        """
        Inicializa o diálogo.

        Args:
            alert_engine: Motor de alertas
            available_fields: Campos disponíveis {nome: config}
            parent: Widget pai
        """
        super().__init__(parent)
        self.alert_engine = alert_engine
        self.available_fields = available_fields

        self.setWindowTitle(tr("Configurar Alertas"))
        self.setMinimumSize(700, 500)
        self.setModal(True)

        self._setup_ui()
        self._load_existing_configs()

    def _setup_ui(self) -> None:
        """Configura a interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title = QLabel(tr("Configuração de Alertas"))
        title.setStyleSheet(f"font-size: 14px; color: {THEME_COLORS['text']};")
        layout.addWidget(title)

        # Tabs: Configuração e Histórico
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_config_tab(), tr("Configuração"))
        self.tabs.addTab(self._create_history_tab(), tr("Histórico"))
        layout.addWidget(self.tabs)

        # Botões de diálogo
        self._setup_dialog_buttons(layout)

    def _create_config_tab(self) -> QWidget:
        """Cria a aba de configuração de alertas."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Descrição
        desc = QLabel("Configure limites mínimos e máximos para cada campo. "
                     "Alertas serão disparados quando os valores ultrapassarem os limites.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 12px;")
        layout.addWidget(desc)

        # Tabela de alertas
        self._setup_table(layout)

        # Formulário de edição
        self._setup_edit_form(layout)

        # Botões de ação
        self._setup_action_buttons(layout)

        return widget

    def _create_history_tab(self) -> QWidget:
        """Cria a aba de histórico de alertas."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Descrição
        desc = QLabel(tr("Histórico de alertas disparados durante a sessão."))
        desc.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 12px;")
        layout.addWidget(desc)

        # Tabela de histórico
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            tr("Campo"), tr("Valor"), tr("Limite"), tr("Severidade"), tr("Horário")
        ])

        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {THEME_COLORS['surface_secondary']};
                alternate-background-color: {THEME_COLORS['surface_tertiary']};
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 4px;
                gridline-color: {THEME_COLORS['border_subtle']};
                color: {THEME_COLORS['text']};
            }}
            QTableWidget::item {{
                padding: 6px;
                color: {THEME_COLORS['text']};
            }}
            QTableWidget::item:selected {{
                background-color: {THEME_COLORS['accent']}40;
                color: {THEME_COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: {THEME_COLORS['surface_tertiary']};
                color: {THEME_COLORS['text']};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {THEME_COLORS['border_subtle']};
                font-size: 11px;
            }}
        """)

        layout.addWidget(self.history_table)

        # Botões
        btn_layout = QHBoxLayout()

        btn_clear = QPushButton(tr("Limpar Histórico"))
        btn_clear.setFixedHeight(32)
        btn_clear.setObjectName("btn_delete")
        btn_clear.clicked.connect(self._clear_history)
        btn_layout.addWidget(btn_clear)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Carrega histórico inicial
        self._refresh_history()

        return widget

    def _refresh_history(self) -> None:
        """Atualiza a tabela de histórico."""
        self.history_table.setRowCount(0)

        history = self.alert_engine.get_history()

        for entry in history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            # Campo
            item_field = QTableWidgetItem(entry.description or entry.field_name)
            self.history_table.setItem(row, 0, item_field)

            # Valor
            item_value = QTableWidgetItem(f"{entry.value:.2f}")
            item_value.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row, 1, item_value)

            # Limite
            limit_text = f"{'<' if entry.violation_type == 'min' else '>'} {entry.threshold:.2f}"
            item_limit = QTableWidgetItem(limit_text)
            item_limit.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row, 2, item_limit)

            # Severidade
            severity_map = {
                AlertSeverity.INFO: (tr("Info"), THEME_COLORS['accent']),
                AlertSeverity.WARNING: (tr("Aviso"), "#FFA500"),
                AlertSeverity.CRITICAL: (tr("Crítico"), "#FF4444")
            }
            sev_text, sev_color = severity_map.get(entry.severity, ("?", "#888"))
            item_sev = QTableWidgetItem(sev_text)
            item_sev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_sev.setForeground(QColor(sev_color))
            self.history_table.setItem(row, 3, item_sev)

            # Horário
            item_triggered = QTableWidgetItem(entry.triggered_at.strftime("%H:%M:%S"))
            item_triggered.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row, 4, item_triggered)

    def _clear_history(self) -> None:
        """Limpa o histórico de alertas."""
        reply = QMessageBox.question(
            self, tr("Confirmar"),
            "Limpar todo o histórico de alertas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.alert_engine.clear_history()
            self._refresh_history()

    def _setup_table(self, layout: QVBoxLayout) -> None:
        """Configura a tabela de alertas."""
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            tr("Campo"), tr("Descrição"), tr("Mínimo"), tr("Máximo"), tr("Severidade"), tr("Ativo")
        ])

        # Configurações da tabela
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        # Ajusta colunas
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # Estilo
        self.table.setStyleSheet(f"""
            QTableWidget {{
                alternate-background-color: {THEME_COLORS['surface_tertiary']};
                color: {THEME_COLORS['text']};
                background-color: {THEME_COLORS['surface_secondary']};
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 4px;
                gridline-color: {THEME_COLORS['border_subtle']};
            }}
            QTableWidget::item {{
                padding: 8px;
                color: {THEME_COLORS['text']};
            }}
            QTableWidget::item:selected {{
                background-color: {THEME_COLORS['accent']}40;
                color: {THEME_COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: {THEME_COLORS['surface_tertiary']};
                color: {THEME_COLORS['text']};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {THEME_COLORS['border_subtle']};
            }}
        """)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.table)

    def _setup_edit_form(self, layout: QVBoxLayout) -> None:
        """Configura o formulário de edição."""
        group = QGroupBox(tr("Adicionar / Editar Alerta"))
        group.setStyleSheet(f"""
            QGroupBox {{
                font-size: 12px;
                color: {THEME_COLORS['text']};
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)

        form_layout = QHBoxLayout(group)
        form_layout.setSpacing(15)

        # Coluna 1: Campo e Descrição
        col1 = QVBoxLayout()
        col1.setSpacing(8)

        col1.addWidget(QLabel(tr("Campo:")))
        self.combo_field = create_styled_combobox()
        self.combo_field.setFixedHeight(32)
        self._populate_fields_combo()
        self.combo_field.currentTextChanged.connect(self._on_field_changed)
        col1.addWidget(self.combo_field)

        col1.addWidget(QLabel(tr("Descrição:")))
        self.edit_description = QLineEdit()
        self.edit_description.setFixedHeight(32)
        self.edit_description.setPlaceholderText(tr("Descrição do alerta"))
        col1.addWidget(self.edit_description)

        form_layout.addLayout(col1)

        # Coluna 2: Min e Max
        col2 = QVBoxLayout()
        col2.setSpacing(8)

        col2.addWidget(QLabel(tr("Valor Mínimo:")))
        min_layout = QHBoxLayout()
        self.check_min = QCheckBox()
        self.check_min.setChecked(False)
        self.check_min.toggled.connect(lambda c: self.spin_min.setEnabled(c))
        min_layout.addWidget(self.check_min)
        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(-999999, 999999)
        self.spin_min.setDecimals(2)
        self.spin_min.setFixedHeight(32)
        self.spin_min.setEnabled(False)
        self.spin_min.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {THEME_COLORS['background']};
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 4px;
                padding: 4px 8px;
                color: {THEME_COLORS['text']};
            }}
            QDoubleSpinBox:focus {{
                border: 1px solid {THEME_COLORS['accent']};
            }}
            QDoubleSpinBox:disabled {{
                color: {THEME_COLORS['text_dim']};
                background-color: {THEME_COLORS['surface_secondary']};
            }}
        """)
        min_layout.addWidget(self.spin_min)
        col2.addLayout(min_layout)

        col2.addWidget(QLabel(tr("Valor Máximo:")))
        max_layout = QHBoxLayout()
        self.check_max = QCheckBox()
        self.check_max.setChecked(False)
        self.check_max.toggled.connect(lambda c: self.spin_max.setEnabled(c))
        max_layout.addWidget(self.check_max)
        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(-999999, 999999)
        self.spin_max.setDecimals(2)
        self.spin_max.setFixedHeight(32)
        self.spin_max.setEnabled(False)
        self.spin_max.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {THEME_COLORS['background']};
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 4px;
                padding: 4px 8px;
                color: {THEME_COLORS['text']};
            }}
            QDoubleSpinBox:focus {{
                border: 1px solid {THEME_COLORS['accent']};
            }}
            QDoubleSpinBox:disabled {{
                color: {THEME_COLORS['text_dim']};
                background-color: {THEME_COLORS['surface_secondary']};
            }}
        """)
        max_layout.addWidget(self.spin_max)
        col2.addLayout(max_layout)

        form_layout.addLayout(col2)

        # Coluna 3: Severidade e Som
        col3 = QVBoxLayout()
        col3.setSpacing(8)

        col3.addWidget(QLabel(tr("Severidade:")))
        self.combo_severity = create_styled_combobox()
        self.combo_severity.setFixedHeight(32)
        self.combo_severity.addItem(tr("Informação"), AlertSeverity.INFO)
        self.combo_severity.addItem(tr("Aviso"), AlertSeverity.WARNING)
        self.combo_severity.addItem(tr("Crítico"), AlertSeverity.CRITICAL)
        self.combo_severity.setCurrentIndex(1)  # Warning por padrão
        col3.addWidget(self.combo_severity)

        col3.addSpacing(10)
        self.check_sound = QCheckBox(tr("Tocar som"))
        self.check_sound.setChecked(True)
        col3.addWidget(self.check_sound)

        self.check_enabled = QCheckBox(tr("Alerta ativo"))
        self.check_enabled.setChecked(True)
        col3.addWidget(self.check_enabled)

        form_layout.addLayout(col3)

        layout.addWidget(group)

    def _setup_action_buttons(self, layout: QVBoxLayout) -> None:
        """Configura botões de ação."""
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_add = QPushButton(tr("Adicionar"))
        self.btn_add.setFixedHeight(32)
        self.btn_add.clicked.connect(self._add_alert)
        btn_layout.addWidget(self.btn_add)

        self.btn_update = QPushButton(tr("Atualizar"))
        self.btn_update.setFixedHeight(32)
        self.btn_update.setProperty("class", "secondary")
        self.btn_update.clicked.connect(self._update_alert)
        self.btn_update.setEnabled(False)
        btn_layout.addWidget(self.btn_update)

        self.btn_remove = QPushButton(tr("Remover"))
        self.btn_remove.setFixedHeight(32)
        self.btn_remove.setObjectName("btn_delete")
        self.btn_remove.clicked.connect(self._remove_alert)
        self.btn_remove.setEnabled(False)
        btn_layout.addWidget(self.btn_remove)

        btn_layout.addStretch()

        # Importar/Exportar
        btn_import = QPushButton(tr("Importar"))
        btn_import.setFixedHeight(32)
        btn_import.setProperty("class", "secondary")
        btn_import.clicked.connect(self._import_configs)
        btn_layout.addWidget(btn_import)

        btn_export = QPushButton(tr("Exportar"))
        btn_export.setFixedHeight(32)
        btn_export.setProperty("class", "secondary")
        btn_export.clicked.connect(self._export_configs)
        btn_layout.addWidget(btn_export)

        layout.addLayout(btn_layout)

    def _setup_dialog_buttons(self, layout: QVBoxLayout) -> None:
        """Configura botões do diálogo."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_close = QPushButton(tr("Fechar"))
        btn_close.setFixedSize(100, 35)
        btn_close.setProperty("class", "secondary")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _populate_fields_combo(self) -> None:
        """Popula combo de campos disponíveis."""
        self.combo_field.clear()

        for field_name, config in self.available_fields.items():
            # Ignora campos sem widget ou internos
            widget_type = config.get('widget', 'none')
            if widget_type == 'none' or field_name in ['sync_word']:
                continue

            description = config.get('description', field_name)
            unit = config.get('unit', '')

            display = f"{description} ({field_name})"
            if unit:
                display += f" [{unit}]"

            self.combo_field.addItem(display, field_name)

    def _on_field_changed(self, text: str) -> None:
        """Handler para mudança de campo selecionado."""
        field_name = self.combo_field.currentData()
        if not field_name:
            return

        # Preenche descrição padrão
        config = self.available_fields.get(field_name, {})
        description = config.get('description', field_name)
        self.edit_description.setText(description)

        # Verifica se já existe config
        existing = self.alert_engine.get_config(field_name)
        if existing:
            self._load_config_to_form(existing)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handler para mudança de item na tabela (checkbox Ativo)."""
        # Verifica se é a coluna tr("Ativo") (índice 5)
        if item.column() != 5:
            return
        
        row = item.row()
        field_item = self.table.item(row, 0)
        if not field_item:
            return
        
        field_name = field_item.data(Qt.ItemDataRole.UserRole)
        config = self.alert_engine.get_config(field_name)
        if not config:
            return
        
        # Atualiza o estado enabled
        new_enabled = item.checkState() == Qt.CheckState.Checked
        if config.enabled != new_enabled:
            config.enabled = new_enabled
            self.alert_engine.add_config(config)

    def _on_selection_changed(self) -> None:
        """Handler para mudança de seleção na tabela."""
        selected = self.table.selectedItems()
        has_selection = len(selected) > 0

        self.btn_update.setEnabled(has_selection)
        self.btn_remove.setEnabled(has_selection)

        if has_selection:
            row = self.table.currentRow()
            field_name = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            config = self.alert_engine.get_config(field_name)
            if config:
                self._load_config_to_form(config)
                # Seleciona no combo
                for i in range(self.combo_field.count()):
                    if self.combo_field.itemData(i) == field_name:
                        self.combo_field.setCurrentIndex(i)
                        break

    def _load_config_to_form(self, config: AlertConfig) -> None:
        """Carrega configuração no formulário."""
        self.edit_description.setText(config.description)

        # Min
        if config.min_value is not None:
            self.check_min.setChecked(True)
            self.spin_min.setValue(config.min_value)
        else:
            self.check_min.setChecked(False)
            self.spin_min.setValue(0)

        # Max
        if config.max_value is not None:
            self.check_max.setChecked(True)
            self.spin_max.setValue(config.max_value)
        else:
            self.check_max.setChecked(False)
            self.spin_max.setValue(0)

        # Severidade
        for i in range(self.combo_severity.count()):
            if self.combo_severity.itemData(i) == config.severity:
                self.combo_severity.setCurrentIndex(i)
                break

        self.check_sound.setChecked(config.sound_enabled)
        self.check_enabled.setChecked(config.enabled)

    def _get_config_from_form(self) -> AlertConfig | None:
        """Obtém configuração do formulário."""
        field_name = self.combo_field.currentData()
        if not field_name:
            QMessageBox.warning(self, tr("Erro"), "Selecione um campo.")
            return None

        min_val = self.spin_min.value() if self.check_min.isChecked() else None
        max_val = self.spin_max.value() if self.check_max.isChecked() else None

        if min_val is None and max_val is None:
            QMessageBox.warning(
                self, tr("Erro"),
                tr("Configure pelo menos um limite (mínimo ou máximo).")
            )
            return None

        if min_val is not None and max_val is not None and min_val >= max_val:
            QMessageBox.warning(
                self, tr("Erro"),
                tr("O valor mínimo deve ser menor que o máximo.")
            )
            return None

        return AlertConfig(
            field_name=field_name,
            description=self.edit_description.text() or field_name,
            min_value=min_val,
            max_value=max_val,
            severity=self.combo_severity.currentData(),
            sound_enabled=self.check_sound.isChecked(),
            enabled=self.check_enabled.isChecked()
        )

    def _add_alert(self) -> None:
        """Adiciona novo alerta."""
        config = self._get_config_from_form()
        if not config:
            return

        # Verifica se já existe
        if self.alert_engine.get_config(config.field_name):
            reply = QMessageBox.question(
                self, tr("Substituir"),
                f"Já existe um alerta para '{config.field_name}'.\nDeseja substituir?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.alert_engine.add_config(config)
        self._refresh_table()
        self._clear_form()

    def _update_alert(self) -> None:
        """Atualiza alerta selecionado."""
        config = self._get_config_from_form()
        if not config:
            return

        self.alert_engine.add_config(config)
        self._refresh_table()

    def _remove_alert(self) -> None:
        """Remove alerta selecionado."""
        row = self.table.currentRow()
        if row < 0:
            return

        field_name = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self, tr("Confirmar"),
            f"Remover alerta para '{field_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.alert_engine.remove_config(field_name)
            self._refresh_table()
            self._clear_form()

    def _clear_form(self) -> None:
        """Limpa o formulário."""
        self.combo_field.setCurrentIndex(0)
        self.edit_description.clear()
        self.check_min.setChecked(False)
        self.check_max.setChecked(False)
        self.spin_min.setValue(0)
        self.spin_max.setValue(0)
        self.combo_severity.setCurrentIndex(1)
        self.check_sound.setChecked(True)
        self.check_enabled.setChecked(True)

    def _load_existing_configs(self) -> None:
        """Carrega configurações existentes na tabela."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Atualiza a tabela com configurações atuais."""
        self.table.setRowCount(0)

        for config in self.alert_engine.get_all_configs():
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Campo
            item_field = QTableWidgetItem(config.field_name)
            item_field.setData(Qt.ItemDataRole.UserRole, config.field_name)
            item_field.setFlags(item_field.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item_field)

            # Descrição
            item_desc = QTableWidgetItem(config.description)
            item_desc.setFlags(item_desc.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item_desc)

            # Mínimo
            min_text = f"{config.min_value:.2f}" if config.min_value is not None else "-"
            item_min = QTableWidgetItem(min_text)
            item_min.setFlags(item_min.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_min.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, item_min)

            # Máximo
            max_text = f"{config.max_value:.2f}" if config.max_value is not None else "-"
            item_max = QTableWidgetItem(max_text)
            item_max.setFlags(item_max.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_max.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, item_max)

            # Severidade
            severity_map = {
                AlertSeverity.INFO: tr("Info"),
                AlertSeverity.WARNING: tr("Aviso"),
                AlertSeverity.CRITICAL: tr("Crítico")
            }
            item_sev = QTableWidgetItem(severity_map.get(config.severity, "?"))
            item_sev.setFlags(item_sev.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_sev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, item_sev)

            # Ativo (checkbox)
            item_active = QTableWidgetItem()
            item_active.setFlags(item_active.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item_active.setCheckState(Qt.CheckState.Checked if config.enabled else Qt.CheckState.Unchecked)
            item_active.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, item_active)

    def _import_configs(self) -> None:
        """Importa configurações de arquivo."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            tr("Importar Configurações de Alertas"),
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if filepath:
            try:
                self.alert_engine.load_configs(filepath)
                self._refresh_table()
                QMessageBox.information(
                    self, "Importado",
                    tr("Configurações importadas com sucesso!")
                )
            except Exception as e:
                QMessageBox.critical(
                    self, tr("Erro"),
                    f"Falha ao importar:\n{str(e)}"
                )

    def _export_configs(self) -> None:
        """Exporta configurações para arquivo."""
        if not self.alert_engine.get_all_configs():
            QMessageBox.warning(
                self, tr("Exportar"),
                tr("Não há configurações para exportar.")
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            tr("Exportar Configurações de Alertas"),
            "alert_configs.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if filepath:
            if not filepath.endswith('.json'):
                filepath += '.json'

            try:
                self.alert_engine.save_configs(filepath)
                QMessageBox.information(
                    self, "Exportado",
                    f"Configurações exportadas para:\n{filepath}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, tr("Erro"),
                    f"Falha ao exportar:\n{str(e)}"
                )
