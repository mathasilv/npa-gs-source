# src/npags/gui/views/station_view.py

"""
Visualização Principal (Station View).

View principal da estação com:
    - Sidebar de configuração (modo, parâmetros, decoder)
    - Waterfall de espectro
    - Log de telemetria
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSplitter, QPushButton, QButtonGroup, QSizePolicy,
    QStackedWidget, QComboBox, QMessageBox, QListView
)
from PyQt6.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QFont, QPixmap
import pyqtgraph as pg

from npags.gui.components import (
    RadioParamsFrame,
    UDPParamsFrame,
    DecoderSelectorFrame,
    LogTextbox,
    StyledLabel,
)
from npags.gui.styles import THEME_COLORS
from npags.gui.translations import (
    tr, set_language, get_current_language, get_available_languages
)

logger = logging.getLogger(__name__)


class StationView(QWidget):
    """View principal da estação."""

    def __init__(
        self,
        parent: QWidget | None = None,
        radios: list[str] | None = None,
        decoders: list[str] | None = None,
        on_mode_change: Callable[[str], None] | None = None,
        on_toggle: Callable[[], None] | None = None,
        on_new_decoder: Callable[[], None] | None = None,
        on_edit_decoder: Callable[[], None] | None = None,
        on_gain_change: Callable[[float], None] | None = None,
        on_open_dashboard: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)

        self.on_mode_change = on_mode_change
        self.on_toggle = on_toggle
        self.on_gain_change = on_gain_change
        self.on_open_dashboard = on_open_dashboard
        self.current_mode = "RADIO"

        # Buffer de Waterfall
        self.wf_rows = 150
        self.wf_cols = 1024
        self.wf_data = np.full((self.wf_rows, self.wf_cols), -100.0, dtype=np.float32)

        self._setup_ui(radios, decoders, on_new_decoder, on_edit_decoder)

        QTimer.singleShot(100, self._print_welcome_message)

    def _setup_ui(
        self,
        radios: list[str] | None,
        decoders: list[str] | None,
        on_new_decoder: Callable[[], None] | None,
        on_edit_decoder: Callable[[], None] | None,
    ) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === SIDEBAR ===
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(400)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 8)
        sidebar_layout.setSpacing(20)

        self._build_sidebar(sidebar_layout, radios, decoders, on_new_decoder, on_edit_decoder)
        layout.addWidget(self.sidebar)

        # === MAIN AREA ===
        self.main_area = QWidget()
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self._build_main_area(main_layout)
        layout.addWidget(self.main_area)

    def _build_sidebar(
        self,
        layout: QVBoxLayout,
        radios: list[str] | None,
        decoders: list[str] | None,
        on_new_decoder: Callable[[], None] | None,
        on_edit_decoder: Callable[[], None] | None,
    ) -> None:
        layout.addWidget(StyledLabel(tr("Modo de Operação")))
        self._create_mode_selector(layout)
        layout.addSpacing(10)

        self.params_stack = QStackedWidget()
        self.params_stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.radio_params = RadioParamsFrame(radios=radios, on_gain_change=self.on_gain_change)
        self.udp_params = UDPParamsFrame()

        self.params_stack.addWidget(self.radio_params)
        self.params_stack.addWidget(self.udp_params)
        self.params_stack.setCurrentWidget(self.radio_params)

        layout.addWidget(self.params_stack)

        QTimer.singleShot(0, self._lock_params_height)

        layout.addSpacing(5)
        self.decoder_selector = DecoderSelectorFrame(
            self.sidebar,
            decoders or [],
            on_new_decoder or (lambda: None),
            on_edit_decoder or (lambda: None),
        )
        layout.addWidget(self.decoder_selector)


        layout.addStretch()

        # Botões de Ação
        actions_container = QWidget()
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)
        action_font = QFont("Segoe UI", 11, QFont.Weight.Bold)

        self.btn_dashboard = QPushButton(tr("DASHBOARD"))
        self.btn_dashboard.setMinimumHeight(30)
        self.btn_dashboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dashboard.setFont(action_font)
        self.btn_dashboard.setObjectName("btn_dashboard_main")

        if self.on_open_dashboard:
            self.btn_dashboard.clicked.connect(self.on_open_dashboard)

        self.btn_dashboard.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions_layout.addWidget(self.btn_dashboard)

        self.btn_connect = QPushButton(tr("INICIAR"))
        self.btn_connect.setMinimumHeight(30)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.setFont(action_font)
        self.btn_connect.setObjectName("btn_connect_start")

        if self.on_toggle:
            self.btn_connect.clicked.connect(self.on_toggle)
        self.btn_connect.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions_layout.addWidget(self.btn_connect)

        layout.addWidget(actions_container)

        # Seletor de idioma (discreto no rodapé)
        self._build_language_selector(layout)

    def _build_language_selector(self, layout: QVBoxLayout) -> None:
        """Cria seletor de idioma discreto no canto inferior esquerdo."""
        # Container para alinhar à esquerda e manter pequeno
        lang_container = QWidget()
        lang_layout = QHBoxLayout(lang_container)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.setSpacing(0)

        # ComboBox pequeno com fonte menor
        self.lang_combo = QComboBox()
        self.lang_combo.setMaximumWidth(130)
        self.lang_combo.setStyleSheet("QComboBox { font-size: 9px; }")
        
        # ListView com estilo igual aos outros combos (borda laranja)
        list_view = QListView()
        list_view.setStyleSheet(f"""
            QListView {{
                background-color: {THEME_COLORS['background']};
                border: 1px solid {THEME_COLORS['accent']};
                border-radius: 4px;
                color: {THEME_COLORS['text']};
                outline: none;
                padding: 2px;
            }}
            QListView::item {{
                padding: 4px 6px;
                min-height: 18px;
                background-color: {THEME_COLORS['background']};
            }}
            QListView::item:selected {{
                background-color: {THEME_COLORS['accent']};
                color: #ffffff;
            }}
            QListView::item:hover:!selected {{
                background-color: {THEME_COLORS['surface_secondary']};
            }}
        """)
        self.lang_combo.setView(list_view)
        self.lang_combo.setObjectName("lang")

        # Popula com idiomas disponíveis
        languages = get_available_languages()
        current_lang = get_current_language()
        current_index = 0

        for i, (code, name) in enumerate(languages.items()):
            self.lang_combo.addItem(name, code)
            if code == current_lang:
                current_index = i

        self.lang_combo.setCurrentIndex(current_index)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)

        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()  # Empurra para a esquerda

        layout.addWidget(lang_container)

    def _on_language_changed(self, index: int) -> None:
        """Handler para mudança de idioma."""
        lang_code = self.lang_combo.itemData(index)
        if lang_code and lang_code != get_current_language():
            if set_language(lang_code):
                QMessageBox.information(
                    self,
                    tr("Idioma"),
                    tr("Idioma alterado. Reinicie a aplicação para aplicar completamente.")
                )

    def _create_mode_selector(self, layout: QVBoxLayout) -> None:
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(1)

        self.btn_mode_sdr = QPushButton(tr("SDR Radio"))
        self.btn_mode_udp = QPushButton(tr("UDP Network"))
        self.btn_mode_sdr.setCheckable(True)
        self.btn_mode_udp.setCheckable(True)
        self.btn_mode_sdr.setChecked(True)

        self.btn_mode_sdr.setProperty("class", "ModeToggle")
        self.btn_mode_udp.setProperty("class", "ModeToggle")

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_mode_sdr, 1)
        self.mode_group.addButton(self.btn_mode_udp, 2)
        self.mode_group.idClicked.connect(self._on_mode_change_internal)

        h_layout.addWidget(self.btn_mode_sdr)
        h_layout.addWidget(self.btn_mode_udp)
        layout.addWidget(container)

    def _build_main_area(self, layout: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)

        # Seção Waterfall
        self.spectrum_container, spectrum_layout = self._create_section(tr("Waterfall"))
        self._setup_waterfall(spectrum_layout)
        splitter.addWidget(self.spectrum_container)

        # Seção Log
        self.log_container, log_layout = self._create_section(tr("Log de Telemetria"))
        self.log_text = LogTextbox(max_lines=2000)
        self.log_text.setFrameShape(QFrame.Shape.NoFrame)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(self.log_container)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter)

    def _create_section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Cria uma seção com título e retorna (container, content_layout)."""
        container = QFrame()
        container.setProperty("class", "SectionContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        title_label = QLabel(f"  {title}")
        title_label.setFixedHeight(32)
        title_label.setProperty("class", "SectionTitle")
        container_layout.addWidget(title_label)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.addWidget(content_widget)

        return container, content_layout

    def _setup_waterfall(self, layout: QVBoxLayout) -> None:
        pg.setConfigOptions(background=THEME_COLORS['background'], foreground=THEME_COLORS['text'])
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideAxis('left')
        self.plot_widget.hideAxis('bottom')
        self.plot_widget.getPlotItem().hideButtons()
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.getPlotItem().getViewBox().setBorder(None)
        self.plot_widget.setFrameShape(QFrame.Shape.NoFrame)

        self.img_item = pg.ImageItem()
        self.plot_widget.addItem(self.img_item)

        pos = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
        colors = np.array([
            [0, 0, 0, 255],
            [30, 15, 5, 255],
            [174, 85, 22, 255],
            [255, 140, 0, 255],
            [255, 255, 255, 255]
        ], dtype=np.ubyte)
        self.img_item.setLookupTable(pg.ColorMap(pos, colors).getLookupTable())
        self.img_item.setLevels([-90, -30])

        layout.addWidget(self.plot_widget)

    def _print_welcome_message(self) -> None:
        """Carrega o logo e insere no log como HTML com alta qualidade."""
        base_dir = Path(__file__).parent.parent
        logo_path = (base_dir / "assets" / "logo.png").resolve().as_posix()

        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            scaled = pixmap.scaledToWidth(150, Qt.TransformationMode.SmoothTransformation)
            ba = QByteArray()
            buff = QBuffer(ba)
            buff.open(QIODevice.OpenModeFlag.WriteOnly)
            scaled.save(buff, "PNG")
            b64_data = base64.b64encode(ba.data()).decode("utf-8")
            img_tag = f"<img src='data:image/png;base64,{b64_data}'>"
        else:
            img_tag = "<b>[LOGO NOT FOUND]</b>"

        accent = THEME_COLORS['accent']
        text_dim = THEME_COLORS['text_dim']
        border = THEME_COLORS['border_subtle']
        html_content = f"""
        <div align='center' style='margin-bottom: 15px;'>
            {img_tag}
            <h3 style='color: {accent}; margin: 8px 0;'>NPA-UFG</h3>
            <span style='color: {text_dim}; font-style: italic;'>
                {tr('Ground Station System')} v5.6
            </span>
            <div style='border-bottom: 1px solid {border}; margin-top: 15px;'></div>
        </div>
        """
        self.log_text.append_html(html_content)

    def _on_mode_change_internal(self, btn_id: int) -> None:
        """Handler interno para mudança de modo."""
        mode = "RADIO" if btn_id == 1 else "UDP"
        if mode == "RADIO":
            self.params_stack.setCurrentWidget(self.radio_params)
        else:
            self.params_stack.setCurrentWidget(self.udp_params)
        self.current_mode = mode
        if self.on_mode_change:
            self.on_mode_change(mode)

    def update_waterfall(self, data: np.ndarray) -> None:
        """Atualiza o waterfall com nova linha de dados FFT."""
        if data is None or data.size == 0 or data.ndim != 1:
            return
        try:
            if data.size != self.wf_cols:
                self.wf_cols = data.size
                self.wf_data = np.full((self.wf_rows, self.wf_cols), -100.0, dtype=np.float32)
            self.wf_data[:-1] = self.wf_data[1:]
            self.wf_data[-1] = data
            self.img_item.setImage(self.wf_data.T, autoLevels=False)
        except Exception as e:
            logger.debug("Erro ao atualizar waterfall: %s", e)

    def log(self, message: str) -> None:
        """Adiciona mensagem ao log de telemetria."""
        self.log_text.append_log(message)

    def set_running_state(self, running: bool) -> None:
        """Atualiza estado visual do botão de conexão."""
        self.btn_connect.setText(tr("PARAR") if running else tr("INICIAR"))
        new_id = "btn_connect_stop" if running else "btn_connect_start"
        self.btn_connect.setObjectName(new_id)

        style = self.btn_connect.style()
        if style:
            style.unpolish(self.btn_connect)
            style.polish(self.btn_connect)

        self.enable_controls(not running)

    def _lock_params_height(self) -> None:
        """Trava a altura do stack de parâmetros para evitar saltos de layout."""
        try:
            height = max(
                self.radio_params.sizeHint().height(),
                self.udp_params.sizeHint().height()
            )
            if height > 0:
                self.params_stack.setFixedHeight(height)
        except RuntimeError as e:
            logger.debug("Erro ao travar altura dos parâmetros: %s", e)

    def enable_controls(self, enable: bool) -> None:
        """Habilita ou desabilita controles da sidebar."""
        self.btn_mode_sdr.setEnabled(enable)
        self.btn_mode_udp.setEnabled(enable)
        self.decoder_selector.set_enabled(enable)
        if self.current_mode == "RADIO":
            self.radio_params.set_enabled(enable)
        else:
            self.udp_params.set_enabled(enable)

    def set_mode(self, mode: str) -> None:
        """Define o modo de operação (RADIO ou UDP)."""
        is_radio = (mode == "RADIO")
        self.btn_mode_sdr.setChecked(is_radio)
        self.btn_mode_udp.setChecked(not is_radio)
        self._on_mode_change_internal(1 if is_radio else 2)

    def get_radio_config(self) -> dict:
        """Retorna configuração atual do rádio."""
        return self.radio_params.get_config()

    def get_udp_config(self) -> dict:
        """Retorna configuração atual do UDP."""
        return self.udp_params.get_config()

    def get_selected_decoder(self) -> str | None:
        """Retorna o decoder selecionado."""
        return self.decoder_selector.get_selected()

    def update_decoders(self, decoders: list[str]) -> None:
        """Atualiza lista de decoders disponíveis."""
        self.decoder_selector.update_decoders(decoders)

    def get_selected_decoders(self) -> list[str]:
        """Retorna lista de decoders selecionados (modo multi)."""
        return self.decoder_selector.get_selected_decoders()
