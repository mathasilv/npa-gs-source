"""Diálogo avançado de exportação de dados.

Permite ao usuário:
    - Selecionar decoder e período de dados
    - Carregar dados do histórico de forma independente
    - Selecionar campos para exportar via TreeWidget hierárquica
    - Escolher formato (CSV ou JSON)
    - Configurar opções avançadas

Design agnóstico: não assume tipos específicos de dados (satélites, nós, etc).
Independente: carrega dados do histórico sem depender do dashboard.
"""

import csv
import json
import logging
from datetime import datetime

from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from npags.gui.components import create_styled_combobox
from npags.gui.services import HistoryService
from npags.gui.services.history_service import HistoryFilter
from npags.gui.styles import THEME_COLORS
from npags.gui.translations import tr

logger = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """
    Diálogo avançado para exportação de dados de telemetria.
    Design agnóstico - funciona com qualquer tipo de dado.
    Independente - carrega dados do histórico sem depender do dashboard.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Inicializa o diálogo de exportação.

        Args:
            parent: Widget pai.
        """
        super().__init__(parent)
        
        # Serviço de histórico (elimina duplicação com report_dialog)
        self._history_service = HistoryService()
        
        # Dados carregados (referências aos buffers do serviço)
        self.loaded_data: dict[str, dict[str, list]] = {}
        self.loaded_timestamps: dict[str, dict[str, list]] = {}
        self.decoder_name = "Unknown"

        self.setWindowTitle(tr("Exportar Dados"))
        self.setMinimumSize(700, 600)
        self.setModal(True)

        self._setup_ui()
        self._load_decoders()

    def _setup_ui(self) -> None:
        """Configura a interface do diálogo."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title = QLabel(tr("Exportação de Dados"))
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME_COLORS['text']};")
        layout.addWidget(title)

        # Separador
        line = QFrame()
        line.setObjectName("SeparatorLine")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Resumo - criado antes das tabs para estar disponível em _update_summary
        self.summary_label = QLabel(tr("Selecione um decoder e carregue os dados"))
        self.summary_label.setStyleSheet(f"""
            background: {THEME_COLORS['surface_secondary']};
            padding: 10px;
            border-radius: 5px;
            color: {THEME_COLORS['text_dim']};
        """)

        # Inicializa radio_csv antes das tabs
        self.radio_csv = None

        # Tabs (3: Fonte de Dados, Dados, Formato)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_source_tab(), tr("Fonte de Dados"))
        self.tabs.addTab(self._create_data_tab(), tr("Dados"))
        self.tabs.addTab(self._create_format_tab(), tr("Formato"))
        layout.addWidget(self.tabs)

        # Adiciona resumo após tabs
        self._update_summary()
        layout.addWidget(self.summary_label)

        # Botões
        buttons = QHBoxLayout()
        buttons.addStretch()

        btn_cancel = QPushButton(tr("Cancelar"))
        btn_cancel.setFixedSize(100, 35)
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        self.btn_export = QPushButton(tr("Exportar"))
        self.btn_export.setFixedSize(100, 35)
        self.btn_export.clicked.connect(self._do_export)
        buttons.addWidget(self.btn_export)

        layout.addLayout(buttons)

    def _load_decoders(self) -> None:
        """Carrega lista de decoders disponíveis."""
        decoders = self._history_service.get_available_decoders()
        self.combo_decoder.clear()
        self.combo_decoder.addItem("-- " + tr("Selecione um decoder") + " --", None)
        for dec in decoders:
            self.combo_decoder.addItem(dec, dec)

    def _create_source_tab(self) -> QWidget:
        """Aba de seleção de fonte de dados (decoder e período)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Seleção de Decoder
        decoder_group = QGroupBox(tr("Decoder"))
        decoder_layout = QVBoxLayout(decoder_group)

        dec_row = QHBoxLayout()
        dec_row.addWidget(QLabel(tr("Decoder:")))
        self.combo_decoder = create_styled_combobox()
        self.combo_decoder.setMinimumHeight(36)
        self.combo_decoder.currentIndexChanged.connect(self._on_decoder_changed)
        dec_row.addWidget(self.combo_decoder, 1)
        decoder_layout.addLayout(dec_row)

        layout.addWidget(decoder_group)

        # Período
        period_group = QGroupBox(tr("Período de Dados"))
        period_layout = QVBoxLayout(period_group)

        dates_layout = QHBoxLayout()
        dates_layout.addWidget(QLabel(tr("De:")))
        self.dt_start = QDateTimeEdit(QDateTime.currentDateTime().addSecs(-86400))
        self.dt_start.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setMinimumHeight(36)
        dates_layout.addWidget(self.dt_start)

        dates_layout.addWidget(QLabel(tr("Até:")))
        self.dt_end = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_end.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setMinimumHeight(36)
        dates_layout.addWidget(self.dt_end)
        dates_layout.addStretch()
        period_layout.addLayout(dates_layout)

        # Botões rápidos de período
        quick_layout = QHBoxLayout()
        self.quick_period_buttons = {}
        for label, hours in [("1h", 1), ("6h", 6), ("12h", 12), ("24h", 24), ("7d", 168)]:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.setMinimumWidth(50)
            btn.setProperty("class", "secondary")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, h=hours, b=btn: self._set_quick_period(h, b))
            quick_layout.addWidget(btn)
            self.quick_period_buttons[hours] = btn
        quick_layout.addStretch()
        period_layout.addLayout(quick_layout)

        # Botão carregar
        load_layout = QHBoxLayout()
        load_layout.addStretch()
        self.btn_load = QPushButton(tr("Carregar Dados"))
        self.btn_load.setMinimumHeight(36)
        self.btn_load.setMinimumWidth(150)
        self.btn_load.clicked.connect(self._load_data)
        self.btn_load.setEnabled(False)
        load_layout.addWidget(self.btn_load)
        period_layout.addLayout(load_layout)

        layout.addWidget(period_group)

        # Status de carregamento
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {THEME_COLORS['text_dim']};")
        layout.addWidget(self.status_label)

        layout.addStretch()
        return widget

    def _set_quick_period(self, hours: int, _clicked_btn: QPushButton = None) -> None:
        """Define período rápido e atualiza visual dos botões."""
        now = QDateTime.currentDateTime()
        self.dt_end.setDateTime(now)
        self.dt_start.setDateTime(now.addSecs(-hours * 3600))

        # Atualiza visual dos botões
        for h, btn in self.quick_period_buttons.items():
            btn.setChecked(h == hours)

    def _on_decoder_changed(self, _index: int) -> None:
        """Handler para mudança de decoder."""
        decoder_name = self.combo_decoder.currentData()
        self.btn_load.setEnabled(decoder_name is not None)
        self._clear_loaded_data()

    def _clear_loaded_data(self) -> None:
        """Limpa dados carregados."""
        self.loaded_data.clear()
        self.loaded_timestamps.clear()
        self.data_tree.clear()
        self._update_summary()

    def _load_data(self) -> None:
        """Carrega dados do histórico baseado no decoder e período."""
        decoder_name = self.combo_decoder.currentData()
        if not decoder_name:
            return

        # Carrega o decoder via serviço
        success, error = self._history_service.load_decoder(decoder_name)
        if not success:
            QMessageBox.critical(self, tr("Erro"), f"{tr('Falha ao carregar decoder:')} {error}")
            return
        
        self.decoder_name = self._history_service.decoder_display_name

        # Verifica arquivo de log
        if not self._history_service.get_log_path():
            QMessageBox.warning(
                self, tr("Aviso"),
                tr("Arquivo de histórico não encontrado. Inicie uma sessão de captura primeiro.")
            )
            return

        # Prepara filtros
        filters = HistoryFilter(
            decoder_name=decoder_name,
            start_time=self.dt_start.dateTime().toPyDateTime(),
            end_time=self.dt_end.dateTime().toPyDateTime()
        )

        self.status_label.setText(tr("Carregando dados..."))

        # Carrega via serviço
        result = self._history_service.load_history(
            filters,
            progress_callback=lambda c: self.status_label.setText(f"{tr('Carregando:')} {c:,}")
        )

        if not result.success:
            self.status_label.setText("")
            QMessageBox.critical(self, tr("Erro"), f"{tr('Falha ao carregar dados:')} {result.error_message}")
            return

        # Copia referências dos buffers do extrator
        if result.extractor:
            self.loaded_data = result.extractor.get_data()
            self.loaded_timestamps = result.extractor.get_timestamps()

        self.status_label.setText(f"{tr('Carregados:')} {result.record_count:,} {tr('registros')}")
        self._populate_data_tree()
        self._update_summary()

        if result.record_count == 0:
            QMessageBox.information(
                self, tr("Info"),
                f"{tr('Nenhum dado encontrado para o decoder')} '{self.decoder_name}' {tr('no período selecionado.')}"
            )
        else:
            # Muda para a aba de dados
            self.tabs.setCurrentIndex(1)

    def _create_data_tab(self) -> QWidget:
        """Cria a aba de seleção de dados com TreeWidget hierárquica."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instruções
        instructions = QLabel(tr("Selecione os dados que deseja exportar:"))
        layout.addWidget(instructions)

        # Botões de seleção rápida
        quick_btns = QHBoxLayout()

        btn_expand = QPushButton(tr("Expandir Tudo"))
        btn_expand.setFixedHeight(35)
        btn_expand.setProperty("class", "secondary")
        btn_expand.clicked.connect(lambda: self.data_tree.expandAll())
        quick_btns.addWidget(btn_expand)

        btn_collapse = QPushButton(tr("Recolher"))
        btn_collapse.setFixedHeight(35)
        btn_collapse.setProperty("class", "secondary")
        btn_collapse.clicked.connect(lambda: self.data_tree.collapseAll())
        quick_btns.addWidget(btn_collapse)

        btn_all = QPushButton(tr("Selecionar Todos"))
        btn_all.setFixedHeight(35)
        btn_all.setProperty("class", "secondary")
        btn_all.clicked.connect(self._select_all)
        quick_btns.addWidget(btn_all)

        btn_none = QPushButton(tr("Limpar Seleção"))
        btn_none.setFixedHeight(35)
        btn_none.setProperty("class", "secondary")
        btn_none.clicked.connect(self._clear_selection)
        quick_btns.addWidget(btn_none)

        quick_btns.addStretch()
        layout.addLayout(quick_btns)

        # TreeWidget hierárquica
        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabels([tr("Campo"), tr("Pontos")])
        self.data_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.data_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.data_tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {THEME_COLORS['surface_secondary']};
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 5px;
            }}
            QTreeWidget::item {{
                padding: 4px;
            }}
            QTreeWidget::item:hover {{
                background: {THEME_COLORS['surface_tertiary']};
            }}
        """)

        self.data_tree.itemChanged.connect(self._on_tree_item_changed)
        layout.addWidget(self.data_tree)

        # Opções de limite
        limit_group = QGroupBox(tr("Limite de Exportação"))
        limit_layout = QVBoxLayout(limit_group)

        self.limit_group = QButtonGroup(self)

        self.radio_all = QRadioButton(tr("Todos os dados carregados"))
        self.radio_all.setChecked(True)
        self.limit_group.addButton(self.radio_all, 0)
        limit_layout.addWidget(self.radio_all)

        self.radio_last_n = QRadioButton(tr("Últimos N pontos por campo:"))
        self.limit_group.addButton(self.radio_last_n, 1)

        last_n_layout = QHBoxLayout()
        last_n_layout.addWidget(self.radio_last_n)
        self.spin_last_n = QSpinBox()
        self.spin_last_n.setRange(1, 100000)
        self.spin_last_n.setValue(1000)
        self.spin_last_n.setFixedWidth(100)
        last_n_layout.addWidget(self.spin_last_n)
        last_n_layout.addStretch()
        limit_layout.addLayout(last_n_layout)

        layout.addWidget(limit_group)

        return widget

    def _populate_data_tree(self) -> None:
        """Popula a árvore com dados organizados por fonte."""
        self.data_tree.clear()
        self.data_tree.blockSignals(True)

        # Obtém field_cache do serviço
        field_cache = self._history_service.get_field_cache()

        for source_id in sorted(self.loaded_data.keys()):
            source_data = self.loaded_data[source_id]
            if not source_data:
                continue

            # Nome amigável para a fonte
            if source_id == "_principal":
                display_name = tr("Principal")
            else:
                display_name = source_id

            # Conta campos e pontos
            field_count = 0
            total_points = 0

            # Item pai (fonte)
            source_item = QTreeWidgetItem([display_name, ""])
            source_item.setFlags(
                source_item.flags() | 
                Qt.ItemFlag.ItemIsUserCheckable | 
                Qt.ItemFlag.ItemIsAutoTristate
            )
            source_item.setCheckState(0, Qt.CheckState.Checked)
            source_item.setData(0, Qt.ItemDataRole.UserRole, source_id)

            for field_name, values in sorted(source_data.items()):
                if not isinstance(values, list) or len(values) == 0:
                    continue

                # Ignora campos internos/técnicos
                if field_name in ['sync_word']:
                    continue

                # Busca descrição do campo no field_cache
                field_desc = field_name
                unit = ""
                if field_name in field_cache:
                    cfg = field_cache[field_name]
                    field_desc = cfg.get('description', field_name)
                    unit = cfg.get('unit', '')

                points = len(values)
                total_points += points
                field_count += 1

                # Texto do item
                item_text = f"{field_desc} ({field_name})"
                if unit:
                    item_text += f" [{unit}]"

                field_item = QTreeWidgetItem([item_text, f"{points:,}"])
                field_item.setFlags(field_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                field_item.setCheckState(0, Qt.CheckState.Checked)
                field_item.setData(0, Qt.ItemDataRole.UserRole, f"{source_id}|{field_name}")
                source_item.addChild(field_item)

            # Atualiza contagem no item pai
            if field_count > 0:
                source_item.setText(1, f"{total_points:,}")
                self.data_tree.addTopLevelItem(source_item)

        self.data_tree.expandAll()
        self.data_tree.blockSignals(False)

    def _select_all(self) -> None:
        """Marca todos os itens."""
        self.data_tree.blockSignals(True)
        for i in range(self.data_tree.topLevelItemCount()):
            item = self.data_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)
        self.data_tree.blockSignals(False)
        self._update_summary()

    def _clear_selection(self) -> None:
        """Desmarca todos os itens."""
        self.data_tree.blockSignals(True)
        for i in range(self.data_tree.topLevelItemCount()):
            item = self.data_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)
        self.data_tree.blockSignals(False)
        self._update_summary()

    def _on_tree_item_changed(self, _item: QTreeWidgetItem, _column: int) -> None:
        """Handler para mudança de seleção na árvore."""
        self._update_summary()

    def _get_selected_data(self) -> dict[str, list[str]]:
        """
        Retorna os dados selecionados organizados por fonte.
        
        Returns:
            Dict {source_id: [field_names]}
        """
        selected: dict[str, list[str]] = {}

        for i in range(self.data_tree.topLevelItemCount()):
            source_item = self.data_tree.topLevelItem(i)

            for j in range(source_item.childCount()):
                field_item = source_item.child(j)
                if field_item.checkState(0) == Qt.CheckState.Checked:
                    data = field_item.data(0, Qt.ItemDataRole.UserRole)
                    if data and '|' in data:
                        src, field = data.split('|', 1)
                        if src not in selected:
                            selected[src] = []
                        selected[src].append(field)

        return selected

    def _create_format_tab(self) -> QWidget:
        """Cria a aba de formato de exportação."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Formato
        format_group = QGroupBox(tr("Formato de Saída"))
        format_layout = QVBoxLayout(format_group)

        self.format_group = QButtonGroup(self)

        self.radio_csv = QRadioButton(tr("CSV (Comma-Separated Values)"))
        self.radio_csv.setChecked(True)
        self.format_group.addButton(self.radio_csv, 0)
        format_layout.addWidget(self.radio_csv)

        csv_desc = QLabel("    " + tr("Ideal para Excel, Google Sheets e análise de dados"))
        csv_desc.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 12px;")
        format_layout.addWidget(csv_desc)

        self.radio_json = QRadioButton(tr("JSON (JavaScript Object Notation)"))
        self.format_group.addButton(self.radio_json, 1)
        format_layout.addWidget(self.radio_json)

        json_desc = QLabel("    " + tr("Ideal para programação e APIs"))
        json_desc.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 12px;")
        format_layout.addWidget(json_desc)

        layout.addWidget(format_group)

        # Opções CSV
        csv_options = QGroupBox(tr("Opções CSV"))
        csv_layout = QVBoxLayout(csv_options)

        self.check_header = QCheckBox(tr("Incluir cabeçalho com nomes dos campos"))
        self.check_header.setChecked(True)
        csv_layout.addWidget(self.check_header)

        self.check_metadata = QCheckBox(tr("Incluir metadados (decoder, data de exportação)"))
        self.check_metadata.setChecked(True)
        csv_layout.addWidget(self.check_metadata)

        self.check_timestamp = QCheckBox(tr("Incluir coluna de índice"))
        self.check_timestamp.setChecked(True)
        csv_layout.addWidget(self.check_timestamp)

        separator_layout = QHBoxLayout()
        separator_layout.addWidget(QLabel(tr("Separador:")))
        self.separator_input = QLineEdit(",")
        self.separator_input.setFixedWidth(50)
        separator_layout.addWidget(self.separator_input)
        separator_layout.addStretch()
        csv_layout.addLayout(separator_layout)

        layout.addWidget(csv_options)

        # Opções JSON
        json_options = QGroupBox(tr("Opções JSON"))
        json_layout = QVBoxLayout(json_options)

        self.check_pretty = QCheckBox(tr("Formatação legível (pretty print)"))
        self.check_pretty.setChecked(True)
        json_layout.addWidget(self.check_pretty)

        self.check_include_config = QCheckBox(tr("Incluir configuração dos campos"))
        self.check_include_config.setChecked(False)
        json_layout.addWidget(self.check_include_config)

        layout.addWidget(json_options)
        layout.addStretch()

        return widget

    def _update_summary(self) -> None:
        """Atualiza o resumo da exportação."""
        if not hasattr(self, 'summary_label') or self.summary_label is None:
            return

        if not self.loaded_data:
            self.summary_label.setText(tr("Selecione um decoder e carregue os dados"))
            return

        selected = self._get_selected_data()

        # Conta campos e fontes selecionados
        total_fields = sum(len(fields) for fields in selected.values())
        total_sources = len(selected)

        # Conta pontos de dados
        total_points = 0
        for source_id, fields in selected.items():
            if source_id in self.loaded_data:
                buffer = self.loaded_data[source_id]
                for field in fields:
                    if field in buffer and isinstance(buffer[field], list):
                        total_points += len(buffer[field])

        # Formato
        format_type = "CSV"
        if hasattr(self, 'radio_csv') and self.radio_csv is not None:
            format_type = "CSV" if self.radio_csv.isChecked() else "JSON"

        self.summary_label.setText(
            f"Decoder: {self.decoder_name} | "
            f"{total_fields} {tr('campos')} | "
            f"{total_sources} {tr('fontes')} | "
            f"{total_points:,} {tr('pontos')} | "
            f"{tr('Formato:')} {format_type}"
        )

    def _do_export(self) -> None:
        """Executa a exportação."""
        if not self.loaded_data:
            QMessageBox.warning(
                self,
                tr("Exportar"),
                tr("Carregue os dados primeiro na aba 'Fonte de Dados'.")
            )
            return

        selected = self._get_selected_data()

        if not selected:
            QMessageBox.warning(
                self, 
                tr("Exportar"), 
                tr("Selecione pelo menos um campo para exportar.")
            )
            return

        # Determina formato e extensão
        is_csv = self.radio_csv.isChecked()
        extension = "csv" if is_csv else "json"
        filter_str = "CSV Files (*.csv)" if is_csv else "JSON Files (*.json)"

        # Diálogo de arquivo
        default_name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Salvar Exportação"),
            default_name,
            f"{filter_str};;All Files (*)"
        )

        if not file_path:
            return

        if not file_path.endswith(f'.{extension}'):
            file_path += f'.{extension}'

        try:
            if is_csv:
                self._export_csv(file_path, selected)
            else:
                self._export_json(file_path, selected)

            QMessageBox.information(
                self,
                tr("Exportação Concluída"),
                f"{tr('Dados exportados com sucesso!')}\n\n{tr('Arquivo:')} {file_path}"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                tr("Erro na Exportação"),
                f"{tr('Falha ao exportar dados:')}\n{e!s}"
            )

    def _export_csv(self, file_path: str, selected: dict[str, list[str]]) -> None:
        """Exporta dados para CSV."""
        separator = self.separator_input.text() or ","

        # Aplica limite se selecionado
        limit = None
        if self.radio_last_n.isChecked():
            limit = self.spin_last_n.value()

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=separator)

            # Metadados
            if self.check_metadata.isChecked():
                writer.writerow([f"# Decoder: {self.decoder_name}"])
                writer.writerow([f"# {tr('Exportado em:')} {datetime.now().isoformat()}"])
                writer.writerow([f"# {tr('Período:')} {self.dt_start.dateTime().toString('dd/MM/yyyy HH:mm')} - {self.dt_end.dateTime().toString('dd/MM/yyyy HH:mm')}"])
                sources_list = ', '.join(selected.keys())
                writer.writerow([f"# {tr('Fontes:')} {sources_list}"])
                writer.writerow([])

            # Coleta dados
            all_data: dict[str, list] = {}
            max_len = 0

            for source_id, fields in selected.items():
                if source_id not in self.loaded_data:
                    continue

                buffer = self.loaded_data[source_id]
                source_prefix = source_id.replace(" ", "_").replace("-", "_")

                for field in fields:
                    if field in buffer and isinstance(buffer[field], list):
                        key = f"{source_prefix}_{field}"
                        data = buffer[field]

                        # Aplica limite
                        if limit and len(data) > limit:
                            data = data[-limit:]

                        all_data[key] = data
                        max_len = max(max_len, len(data))

            # Cabeçalho
            if self.check_header.isChecked():
                header = []
                if self.check_timestamp.isChecked():
                    header.append("index")
                header.extend(all_data.keys())
                writer.writerow(header)

            # Dados
            for i in range(max_len):
                row = []
                if self.check_timestamp.isChecked():
                    row.append(i)
                for key in all_data:
                    values = all_data[key]
                    if i < len(values):
                        row.append(values[i])
                    else:
                        row.append("")
                writer.writerow(row)

    def _export_json(self, file_path: str, selected: dict[str, list[str]]) -> None:
        """Exporta dados para JSON."""
        # Aplica limite se selecionado
        limit = None
        if self.radio_last_n.isChecked():
            limit = self.spin_last_n.value()

        export_data = {
            "metadata": {
                "decoder": self.decoder_name,
                "exported_at": datetime.now().isoformat(),
                "period": {
                    "start": self.dt_start.dateTime().toPyDateTime().isoformat(),
                    "end": self.dt_end.dateTime().toPyDateTime().isoformat()
                },
                "sources": list(selected.keys())
            },
            "data": {}
        }

        for source_id, fields in selected.items():
            if source_id not in self.loaded_data:
                continue

            buffer = self.loaded_data[source_id]
            export_data["data"][source_id] = {}

            for field in fields:
                if field in buffer:
                    if isinstance(buffer[field], list):
                        data = buffer[field]
                        # Aplica limite
                        if limit and len(data) > limit:
                            data = data[-limit:]
                        export_data["data"][source_id][field] = data

        # Configuração dos campos
        if self.check_include_config.isChecked():
            field_cache = self._history_service.get_field_cache()
            
            export_data["field_config"] = {}
            for fields in selected.values():
                for field in fields:
                    if field in field_cache:
                        export_data["field_config"][field] = field_cache[field]

        # Escreve arquivo
        indent = 2 if self.check_pretty.isChecked() else None
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=indent, ensure_ascii=False, default=str)
