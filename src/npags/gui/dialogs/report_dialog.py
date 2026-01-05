# src/npags/gui/dialogs/report_dialog.py
"""
Diálogo avançado de geração de relatórios de missão.
Independente - carrega dados do histórico baseado no decoder selecionado.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QDateTime, QObject, Qt, QThread, pyqtSignal
from npags.gui.components import create_styled_combobox
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from npags.gui.services import HistoryService
from npags.gui.services.history_service import HistoryFilter
from npags.gui.translations import tr
from npags.gui.styles import THEME_COLORS


class ReportGeneratorWorker(QObject):
    """Worker para gerar relatório em background."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, config, data_buffer, timestamp_buffer, field_configs, alerts_history, output_path):
        super().__init__()
        self.config = config
        self.data_buffer = data_buffer
        self.timestamp_buffer = timestamp_buffer
        self.field_configs = field_configs
        self.alerts_history = alerts_history
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit("Importando módulos...")
            from npags.reports.generator import ReportGenerator

            self.progress.emit("Inicializando gerador...")
            generator = ReportGenerator(
                config=self.config,
                data_buffer=self.data_buffer,
                timestamp_buffer=self.timestamp_buffer,
                field_configs=self.field_configs,
                alerts_history=self.alerts_history
            )

            self.progress.emit("Gerando relatório PDF...")
            success, message = generator.generate(self.output_path)
            self.finished.emit(success, message)

        except ImportError as e:
            self.finished.emit(False, f"Dependência não encontrada: {e}\n\nInstale com: pip install reportlab matplotlib")
        except Exception as e:
            self.finished.emit(False, f"Erro ao gerar relatório: {str(e)}")


class ReportDialog(QDialog):
    """Diálogo para geração de relatórios de missão."""

    def __init__(self, parent: QWidget | None = None, **_kwargs) -> None:
        super().__init__(parent)

        self._worker_thread: QThread | None = None
        self._worker: ReportGeneratorWorker | None = None

        # Serviço de histórico (compartilhado com export_dialog)
        self._history_service = HistoryService()
        
        # Dados carregados (referências aos buffers do serviço)
        self.loaded_data: dict[str, dict[str, list]] = {}
        self.loaded_timestamps: dict[str, dict[str, list]] = {}

        self.setWindowTitle("Gerar Relatório de Missão")
        self.setMinimumSize(700, 600)
        self.setModal(True)

        self._setup_ui()
        self._load_decoders()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title = QLabel("Geração de Relatório de Missão")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME_COLORS['text']};")
        layout.addWidget(title)

        # Separador
        line = QFrame()
        line.setObjectName("SeparatorLine")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_source_tab(), "Fonte de Dados")
        self.tabs.addTab(self._create_general_tab(), "Informações")
        self.tabs.addTab(self._create_sections_tab(), "Seções")
        self.tabs.addTab(self._create_charts_tab(), "Gráficos")
        layout.addWidget(self.tabs)

        # Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {THEME_COLORS['text_dim']};")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Resumo
        self.summary_label = QLabel("Selecione um decoder e carregue os dados")
        self.summary_label.setStyleSheet(f"""
            background: {THEME_COLORS['surface_secondary']};
            padding: 10px;
            border-radius: 5px;
            color: {THEME_COLORS['text_dim']};
        """)
        layout.addWidget(self.summary_label)

        # Botões
        self._setup_buttons(layout)

    def _load_decoders(self) -> None:
        """Carrega lista de decoders disponíveis."""
        decoders = self._history_service.get_available_decoders()
        self.combo_decoder.clear()
        self.combo_decoder.addItem("-- Selecione um decoder --", None)
        for dec in decoders:
            self.combo_decoder.addItem(dec, dec)

    def _create_source_tab(self) -> QWidget:
        """Aba de seleção de fonte de dados."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Seleção de Decoder
        decoder_group = QGroupBox("Decoder")
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

        # Botões rápidos
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
        self.btn_load = QPushButton("Carregar Dados")
        self.btn_load.setMinimumHeight(36)
        self.btn_load.setMinimumWidth(150)
        self.btn_load.clicked.connect(self._load_data)
        self.btn_load.setEnabled(False)
        load_layout.addWidget(self.btn_load)
        period_layout.addLayout(load_layout)

        layout.addWidget(period_group)

        # Árvore de dados
        data_group = QGroupBox("Dados Disponíveis")
        data_layout = QVBoxLayout(data_group)

        # Botões de seleção
        tree_btns = QHBoxLayout()
        btn_expand = QPushButton("Expandir Tudo")
        btn_expand.setMinimumHeight(32)
        btn_expand.setProperty("class", "secondary")
        btn_expand.clicked.connect(lambda: self.data_tree.expandAll())
        tree_btns.addWidget(btn_expand)

        btn_collapse = QPushButton("Recolher")
        btn_collapse.setMinimumHeight(32)
        btn_collapse.setProperty("class", "secondary")
        btn_collapse.clicked.connect(lambda: self.data_tree.collapseAll())
        tree_btns.addWidget(btn_collapse)

        btn_select_all = QPushButton(tr("Selecionar Todos"))
        btn_select_all.setMinimumHeight(32)
        btn_select_all.setProperty("class", "secondary")
        btn_select_all.clicked.connect(self._select_all_tree)
        tree_btns.addWidget(btn_select_all)

        btn_clear = QPushButton(tr("Limpar"))
        btn_clear.setMinimumHeight(32)
        btn_clear.setProperty("class", "secondary")
        btn_clear.clicked.connect(self._clear_tree_selection)
        tree_btns.addWidget(btn_clear)
        tree_btns.addStretch()
        data_layout.addLayout(tree_btns)

        # Árvore
        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabels([tr("Campo"), "Pontos"])
        self.data_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.data_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.data_tree.itemChanged.connect(self._on_tree_item_changed)
        data_layout.addWidget(self.data_tree)

        layout.addWidget(data_group)
        return widget

    def _set_quick_period(self, hours: int, _clicked_btn: QPushButton = None) -> None:
        """Define período rápido e atualiza visual dos botões."""
        now = QDateTime.currentDateTime()
        self.dt_end.setDateTime(now)
        self.dt_start.setDateTime(now.addSecs(-hours * 3600))

        # Atualiza visual dos botões
        for h, btn in self.quick_period_buttons.items():
            btn.setChecked(h == hours)

    def _on_decoder_changed(self, index: int) -> None:
        decoder_name = self.combo_decoder.currentData()
        self.btn_load.setEnabled(decoder_name is not None)
        self._clear_loaded_data()

    def _clear_loaded_data(self) -> None:
        """Limpa dados carregados."""
        self.loaded_data.clear()
        self.loaded_timestamps.clear()
        self.data_tree.clear()
        self._update_charts_tree()
        self._update_summary()

    def _load_data(self) -> None:
        """Carrega dados do histórico baseado no decoder e período."""
        decoder_name = self.combo_decoder.currentData()
        if not decoder_name:
            return

        # Carrega o decoder via serviço
        success, error = self._history_service.load_decoder(decoder_name)
        if not success:
            QMessageBox.critical(self, tr("Erro"), f"Falha ao carregar decoder: {error}")
            return
        
        self.decoder_display_name = self._history_service.decoder_display_name

        # Verifica arquivo de log
        if not self._history_service.get_log_path():
            QMessageBox.warning(self, tr("Aviso"), "Arquivo de histórico não encontrado. Inicie uma sessão de captura primeiro.")
            return

        # Prepara filtros
        filters = HistoryFilter(
            decoder_name=decoder_name,
            start_time=self.dt_start.dateTime().toPyDateTime(),
            end_time=self.dt_end.dateTime().toPyDateTime()
        )

        self.status_label.setText(tr("Carregando dados..."))
        self.status_label.setVisible(True)

        # Carrega via serviço
        result = self._history_service.load_history(
            filters,
            progress_callback=lambda c: self.status_label.setText(f"{tr('Carregando:')} {c:,}")
        )

        self.status_label.setVisible(False)

        if not result.success:
            QMessageBox.critical(self, tr("Erro"), f"Falha ao carregar dados: {result.error_message}")
            return

        # Copia referências dos buffers do extrator
        if result.extractor:
            self.loaded_data = result.extractor.get_data()
            self.loaded_timestamps = result.extractor.get_timestamps()

        self._populate_data_tree()
        self._update_charts_tree()
        self._update_summary()

        if result.record_count == 0:
            QMessageBox.information(self, tr("Info"), f"Nenhum dado encontrado para o decoder '{self.decoder_display_name}' no período selecionado.")

    def _populate_data_tree(self) -> None:
        """Popula árvore com dados carregados."""
        self.data_tree.clear()
        self.data_tree.blockSignals(True)

        for source_id in sorted(self.loaded_data.keys()):
            source_data = self.loaded_data[source_id]
            if not source_data:
                continue

            # Nome amigável
            display_name = tr("Principal") if source_id == "_principal" else source_id

            # Item pai (fonte)
            source_item = QTreeWidgetItem([display_name, ""])
            source_item.setFlags(source_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            source_item.setCheckState(0, Qt.CheckState.Checked)
            source_item.setData(0, Qt.ItemDataRole.UserRole, source_id)

            total_points = 0

            for field_name, values in sorted(source_data.items()):
                if not isinstance(values, list):
                    continue

                # Descrição do campo
                field_desc = field_name
                field_cache = self._history_service.get_field_cache()
                if field_name in field_cache:
                    cfg = field_cache[field_name]
                    field_desc = cfg.get('description', field_name)

                points = len(values)
                total_points += points

                field_item = QTreeWidgetItem([f"{field_desc} ({field_name})", f"{points:,}"])
                field_item.setFlags(field_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                field_item.setCheckState(0, Qt.CheckState.Checked)
                field_item.setData(0, Qt.ItemDataRole.UserRole, f"{source_id}|{field_name}")
                source_item.addChild(field_item)

            source_item.setText(1, f"{total_points:,}")
            self.data_tree.addTopLevelItem(source_item)

        self.data_tree.expandAll()
        self.data_tree.blockSignals(False)

    def _select_all_tree(self) -> None:
        """Seleciona todos os itens da árvore."""
        self.data_tree.blockSignals(True)
        for i in range(self.data_tree.topLevelItemCount()):
            item = self.data_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)
        self.data_tree.blockSignals(False)
        self._update_summary()

    def _clear_tree_selection(self) -> None:
        """Limpa seleção da árvore."""
        self.data_tree.blockSignals(True)
        for i in range(self.data_tree.topLevelItemCount()):
            item = self.data_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)
        self.data_tree.blockSignals(False)
        self._update_summary()

    def _on_tree_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        """Handler para mudança de seleção na árvore."""
        self._update_summary()

    def _get_selected_fields(self) -> dict[str, list[str]]:
        """Retorna campos selecionados por fonte."""
        selected = {}

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

    def _create_general_tab(self) -> QWidget:
        """Aba de informações do relatório."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Informações da Missão
        mission_group = QGroupBox("Informações da Missão")
        mission_layout = QGridLayout(mission_group)
        mission_layout.setSpacing(10)

        mission_layout.addWidget(QLabel("Título do Relatório:"), 0, 0)
        self.edit_title = QLineEdit(tr("Relatório de Missão"))
        self.edit_title.setMinimumHeight(36)
        mission_layout.addWidget(self.edit_title, 0, 1)

        mission_layout.addWidget(QLabel("Nome da Missão:"), 1, 0)
        self.edit_mission = QLineEdit()
        self.edit_mission.setMinimumHeight(36)
        mission_layout.addWidget(self.edit_mission, 1, 1)

        mission_layout.addWidget(QLabel("Autor:"), 2, 0)
        self.edit_author = QLineEdit("NPA Ground Station")
        self.edit_author.setMinimumHeight(36)
        mission_layout.addWidget(self.edit_author, 2, 1)

        mission_layout.addWidget(QLabel("Organização:"), 3, 0)
        self.edit_organization = QLineEdit()
        self.edit_organization.setPlaceholderText("Opcional")
        self.edit_organization.setMinimumHeight(36)
        mission_layout.addWidget(self.edit_organization, 3, 1)

        layout.addWidget(mission_group)

        # Formato
        format_group = QGroupBox("Formato do Documento")
        format_layout = QGridLayout(format_group)

        format_layout.addWidget(QLabel(tr("Tamanho:")), 0, 0)
        self.combo_page_size = create_styled_combobox()
        self.combo_page_size.addItem("A4", "A4")
        self.combo_page_size.addItem(tr("Carta (Letter)"), "letter")
        self.combo_page_size.setMinimumHeight(36)
        format_layout.addWidget(self.combo_page_size, 0, 1)

        format_layout.addWidget(QLabel(tr("Orientação:")), 1, 0)
        self.combo_orientation = create_styled_combobox()
        self.combo_orientation.addItem(tr("Retrato"), "portrait")
        self.combo_orientation.addItem(tr("Paisagem"), "landscape")
        self.combo_orientation.setMinimumHeight(36)
        format_layout.addWidget(self.combo_orientation, 1, 1)

        layout.addWidget(format_group)
        layout.addStretch()
        return widget

    def _create_sections_tab(self) -> QWidget:
        """Aba de seções do relatório."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Seções
        sections_group = QGroupBox(tr("Seções do Relatório"))
        sections_layout = QVBoxLayout(sections_group)
        sections_layout.setSpacing(8)

        self.check_summary = QCheckBox(tr("Resumo Executivo"))
        self.check_summary.setChecked(True)
        sections_layout.addWidget(self.check_summary)

        self.check_statistics = QCheckBox(tr("Estatísticas de Telemetria"))
        self.check_statistics.setChecked(True)
        sections_layout.addWidget(self.check_statistics)

        self.check_charts = QCheckBox(tr("Gráficos Temporais"))
        self.check_charts.setChecked(True)
        sections_layout.addWidget(self.check_charts)

        self.check_alerts = QCheckBox(tr("Registro de Alertas"))
        self.check_alerts.setChecked(True)
        sections_layout.addWidget(self.check_alerts)


        self.check_gps = QCheckBox(tr("Trajetória GPS (Mapa)"))
        self.check_gps.setChecked(False)
        sections_layout.addWidget(self.check_gps)
        self.check_config = QCheckBox(tr("Configuração e Metadados"))
        self.check_config.setChecked(True)
        sections_layout.addWidget(self.check_config)

        layout.addWidget(sections_group)

        # Estatísticas
        stats_group = QGroupBox("Estatísticas a Incluir")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(8)

        self.check_stat_count = QCheckBox(tr("Contagem (N)"))
        self.check_stat_count.setChecked(True)
        stats_layout.addWidget(self.check_stat_count, 0, 0)

        self.check_stat_min = QCheckBox(tr("Mínimo"))
        self.check_stat_min.setChecked(True)
        stats_layout.addWidget(self.check_stat_min, 0, 1)

        self.check_stat_max = QCheckBox(tr("Máximo"))
        self.check_stat_max.setChecked(True)
        stats_layout.addWidget(self.check_stat_max, 0, 2)

        self.check_stat_mean = QCheckBox(tr("Média"))
        self.check_stat_mean.setChecked(True)
        stats_layout.addWidget(self.check_stat_mean, 1, 0)

        self.check_stat_std = QCheckBox(tr("Desvio Padrão"))
        self.check_stat_std.setChecked(True)
        stats_layout.addWidget(self.check_stat_std, 1, 1)

        self.check_stat_median = QCheckBox(tr("Mediana"))
        self.check_stat_median.setChecked(True)
        stats_layout.addWidget(self.check_stat_median, 1, 2)

        layout.addWidget(stats_group)
        layout.addStretch()
        return widget

    def _create_charts_tab(self) -> QWidget:
        """Aba de seleção de gráficos."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Seleção de gráficos
        charts_group = QGroupBox("Gráficos a Gerar")
        charts_layout = QVBoxLayout(charts_group)

        hint = QLabel("Selecione os campos que terão gráficos no relatório:")
        hint.setStyleSheet(f"color: {THEME_COLORS['text_dim']};")
        charts_layout.addWidget(hint)

        # Botões
        chart_btns = QHBoxLayout()
        btn_all_charts = QPushButton(tr("Selecionar Todos"))
        btn_all_charts.setMinimumHeight(32)
        btn_all_charts.setProperty("class", "secondary")
        btn_all_charts.clicked.connect(self._select_all_charts)
        chart_btns.addWidget(btn_all_charts)

        btn_clear_charts = QPushButton(tr("Limpar"))
        btn_clear_charts.setMinimumHeight(32)
        btn_clear_charts.setProperty("class", "secondary")
        btn_clear_charts.clicked.connect(self._clear_charts_selection)
        chart_btns.addWidget(btn_clear_charts)
        chart_btns.addStretch()
        charts_layout.addLayout(chart_btns)

        # Árvore de gráficos
        self.charts_tree = QTreeWidget()
        self.charts_tree.setHeaderLabels([tr("Campo"), "Pontos"])
        self.charts_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.charts_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        charts_layout.addWidget(self.charts_tree)

        layout.addWidget(charts_group)

        # Estilo
        style_group = QGroupBox("Estilo dos Gráficos")
        style_layout = QVBoxLayout(style_group)

        self.chart_style_group = QButtonGroup(self)

        self.radio_line = QRadioButton("Linha")
        self.radio_line.setChecked(True)
        self.chart_style_group.addButton(self.radio_line, 0)
        style_layout.addWidget(self.radio_line)

        self.radio_scatter = QRadioButton("Dispersão (Scatter)")
        self.chart_style_group.addButton(self.radio_scatter, 1)
        style_layout.addWidget(self.radio_scatter)

        self.radio_area = QRadioButton("Área")
        self.chart_style_group.addButton(self.radio_area, 2)
        style_layout.addWidget(self.radio_area)

        layout.addWidget(style_group)

        # Qualidade
        quality_group = QGroupBox("Qualidade")
        quality_layout = QHBoxLayout(quality_group)

        self.quality_group = QButtonGroup(self)

        self.radio_low = QRadioButton("Baixa")
        self.quality_group.addButton(self.radio_low, 0)
        quality_layout.addWidget(self.radio_low)

        self.radio_medium = QRadioButton(tr("Média"))
        self.radio_medium.setChecked(True)
        self.quality_group.addButton(self.radio_medium, 1)
        quality_layout.addWidget(self.radio_medium)

        self.radio_high = QRadioButton("Alta")
        self.quality_group.addButton(self.radio_high, 2)
        quality_layout.addWidget(self.radio_high)

        quality_layout.addStretch()
        layout.addWidget(quality_group)

        return widget

    def _update_charts_tree(self) -> None:
        """Atualiza árvore de gráficos baseado nos dados carregados."""
        self.charts_tree.clear()
        self.charts_tree.blockSignals(True)

        for source_id in sorted(self.loaded_data.keys()):
            source_data = self.loaded_data[source_id]
            if not source_data:
                continue

            display_name = tr("Principal") if source_id == "_principal" else source_id

            source_item = QTreeWidgetItem([display_name, ""])
            source_item.setFlags(source_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            source_item.setCheckState(0, Qt.CheckState.Checked)
            source_item.setData(0, Qt.ItemDataRole.UserRole, source_id)

            for field_name, values in sorted(source_data.items()):
                if not isinstance(values, list) or len(values) < 2:
                    continue

                field_desc = field_name
                field_cache = self._history_service.get_field_cache()
                if field_name in field_cache:
                    cfg = field_cache[field_name]
                    field_desc = cfg.get('description', field_name)

                points = len(values)

                field_item = QTreeWidgetItem([f"{field_desc}", f"{points:,}"])
                field_item.setFlags(field_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                field_item.setCheckState(0, Qt.CheckState.Checked)
                field_item.setData(0, Qt.ItemDataRole.UserRole, f"{source_id}|{field_name}")
                source_item.addChild(field_item)

            if source_item.childCount() > 0:
                self.charts_tree.addTopLevelItem(source_item)

        self.charts_tree.expandAll()
        self.charts_tree.blockSignals(False)

    def _select_all_charts(self) -> None:
        self.charts_tree.blockSignals(True)
        for i in range(self.charts_tree.topLevelItemCount()):
            item = self.charts_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)
        self.charts_tree.blockSignals(False)

    def _clear_charts_selection(self) -> None:
        self.charts_tree.blockSignals(True)
        for i in range(self.charts_tree.topLevelItemCount()):
            item = self.charts_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)
        self.charts_tree.blockSignals(False)

    def _get_selected_charts(self) -> list[str]:
        """Retorna lista de campos selecionados para gráficos."""
        selected = []

        for i in range(self.charts_tree.topLevelItemCount()):
            source_item = self.charts_tree.topLevelItem(i)

            for j in range(source_item.childCount()):
                field_item = source_item.child(j)
                if field_item.checkState(0) == Qt.CheckState.Checked:
                    data = field_item.data(0, Qt.ItemDataRole.UserRole)
                    if data:
                        selected.append(data)

        return selected

    def _setup_buttons(self, layout: QVBoxLayout) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.setFixedSize(100, 36)
        self.btn_cancel.setProperty("class", "secondary")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_generate = QPushButton(tr("Gerar Relatório"))
        self.btn_generate.setFixedSize(140, 36)
        self.btn_generate.clicked.connect(self._on_generate)
        btn_layout.addWidget(self.btn_generate)

        layout.addLayout(btn_layout)

    def _update_summary(self) -> None:
        if not hasattr(self, 'summary_label'):
            return

        if not self.loaded_data:
            self.summary_label.setText("Selecione um decoder e carregue os dados")
            return

        selected = self._get_selected_fields()
        total_fields = sum(len(fields) for fields in selected.values())
        total_sources = len(selected)

        total_points = 0
        for source_id, fields in selected.items():
            if source_id in self.loaded_data:
                for field in fields:
                    if field in self.loaded_data[source_id]:
                        values = self.loaded_data[source_id][field]
                        if isinstance(values, list):
                            total_points += len(values)

        decoder = self.combo_decoder.currentText() or "Nenhum"
        self.summary_label.setText(
            f"Decoder: {decoder} | "
            f"{total_fields} campos | "
            f"{total_sources} fontes | "
            f"{total_points:,} pontos"
        )

    def _on_generate(self) -> None:
        if not self.loaded_data:
            QMessageBox.warning(self, tr("Aviso"), "Carregue os dados primeiro.")
            return

        selected = self._get_selected_fields()
        if not selected:
            QMessageBox.warning(self, tr("Aviso"), "Selecione pelo menos um campo.")
            return

        default_name = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Relatório", default_name,
            "PDF Files (*.pdf);;All Files (*)"
        )

        if not file_path:
            return

        if not file_path.endswith('.pdf'):
            file_path += '.pdf'

        config = self._build_config()
        self._start_generation(config, file_path)

    def _build_config(self):
        from npags.reports.generator import ReportConfig

        chart_style = "line"
        if self.radio_scatter.isChecked():
            chart_style = "scatter"
        elif self.radio_area.isChecked():
            chart_style = "area"

        chart_resolution = "medium"
        if self.radio_low.isChecked():
            chart_resolution = "low"
        elif self.radio_high.isChecked():
            chart_resolution = "high"

        selected_fields = self._get_selected_fields()
        all_fields = []
        for fields in selected_fields.values():
            all_fields.extend(fields)

        # FUTURE: Usar selected_charts quando ReportConfig suportar seleção de gráficos
        _ = self._get_selected_charts()  # Reservado para uso futuro

        decoder_name = self.combo_decoder.currentData() or "Unknown"

        return ReportConfig(
            title=self.edit_title.text() or tr("Relatório de Missão"),
            mission_name=self.edit_mission.text() or decoder_name,
            author=self.edit_author.text() or "NPA Ground Station",
            organization=self.edit_organization.text(),
            start_time=self.dt_start.dateTime().toPyDateTime(),
            end_time=self.dt_end.dateTime().toPyDateTime(),
            selected_decoders=[decoder_name],
            selected_fields=list(set(all_fields)),
            selected_sources=list(selected_fields.keys()),
            include_summary=self.check_summary.isChecked(),
            include_statistics=self.check_statistics.isChecked(),
            include_charts=self.check_charts.isChecked(),
            include_alerts=self.check_alerts.isChecked(),
            include_gps_track=self.check_gps.isChecked(),
            include_raw_data=False,
            include_config=self.check_config.isChecked(),
            chart_style=chart_style,
            chart_resolution=chart_resolution,
            charts_per_page=2,
            stats_include_count=self.check_stat_count.isChecked(),
            stats_include_min=self.check_stat_min.isChecked(),
            stats_include_max=self.check_stat_max.isChecked(),
            stats_include_mean=self.check_stat_mean.isChecked(),
            stats_include_std=self.check_stat_std.isChecked(),
            stats_include_median=self.check_stat_median.isChecked(),
            page_size=self.combo_page_size.currentData(),
            orientation=self.combo_orientation.currentData(),
            max_data_points=100000,
            max_charts=100
        )

    def _start_generation(self, config, output_path: str) -> None:
        self.btn_generate.setEnabled(False)
        self.btn_cancel.setText("Aguarde...")
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Iniciando...")

        field_configs = self._history_service.get_field_cache()

        self._worker_thread = QThread()
        self._worker = ReportGeneratorWorker(
            config=config,
            data_buffer=self.loaded_data,
            timestamp_buffer=self.loaded_timestamps,
            field_configs=field_configs,
            alerts_history=[],
            output_path=output_path
        )
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)

        self._worker_thread.start()

    def _on_progress(self, message: str) -> None:
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str) -> None:
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
        self._worker_thread = None
        self._worker = None

        self.btn_generate.setEnabled(True)
        self.btn_cancel.setText(tr("Fechar"))
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        if success:
            QMessageBox.information(self, "Relatório Gerado", message)
            self.accept()
        else:
            QMessageBox.critical(self, tr("Erro"), message)

    def reject(self) -> None:
        if self._worker_thread and self._worker_thread.isRunning():
            reply = QMessageBox.question(
                self, tr("Cancelar"),
                "A geração está em andamento. Deseja cancelar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._worker_thread.quit()
            self._worker_thread.wait(1000)
        super().reject()
