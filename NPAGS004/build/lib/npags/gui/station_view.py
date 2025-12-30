# src/npags/gui/station_view.py

"""
Visualização Principal (Station View).
Versão Final: Integração com Log Híbrido e Logo em Alta Definição (Base64).
"""

from typing import Callable, List, Optional, Dict, Any
import numpy as np
from pathlib import Path
import base64

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSplitter, QPushButton, QButtonGroup, QCheckBox,
    QSizePolicy, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QFont, QPixmap, QImage
import pyqtgraph as pg

from npags.gui.components import (
    RadioParamsFrame,
    UDPParamsFrame,
    DecoderSelectorFrame,
    LogTextbox,
    StyledLabel
)
from npags.gui.styles import THEME_COLORS

class StationView(QWidget):
    """View principal da estação."""

    def __init__(
        self,
        parent=None,
        radios: List[str] = None,
        decoders: List[str] = None,
        on_mode_change: Callable = None,
        on_toggle: Callable = None,
        on_new_decoder: Callable = None,
        on_edit_decoder: Callable = None,
        on_gain_change: Callable = None,
        on_open_dashboard: Callable = None 
    ):
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
        
        # --- EXIBE O LOGO (IMAGEM HD) AO INICIAR ---
        # Usa um Timer para garantir que a UI esteja carregada antes de inserir
        QTimer.singleShot(100, self._print_welcome_message)

    def _setup_ui(self, radios, decoders, on_new_decoder, on_edit_decoder):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === SIDEBAR ===
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setMaximumWidth(400)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(20)

        self._build_sidebar(sidebar_layout, radios, decoders, on_new_decoder, on_edit_decoder)
        layout.addWidget(self.sidebar)

        # === MAIN AREA ===
        self.main_area = QWidget()
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self._build_main_area(main_layout)
        layout.addWidget(self.main_area)

    def _build_sidebar(self, layout, radios, decoders, on_new_decoder, on_edit_decoder):
        layout.addWidget(StyledLabel("Modo de Operação"))
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

        def _lock_params_height():
            try:
                h = max(self.radio_params.sizeHint().height(), self.udp_params.sizeHint().height())
                if h > 0: self.params_stack.setFixedHeight(h)
            except Exception: pass
        QTimer.singleShot(0, _lock_params_height)

        layout.addSpacing(5)
        self.decoder_selector = DecoderSelectorFrame(self.sidebar, decoders, on_new_decoder, on_edit_decoder)
        layout.addWidget(self.decoder_selector)

        self.multi_decoder_check = QCheckBox("Auto-detect")
        self.multi_decoder_check.setStyleSheet("margin-top: 5px;") 
        layout.addWidget(self.multi_decoder_check)
        layout.addStretch()

        # Botões de Ação
        actions_container = QWidget()
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)
        action_font = QFont("Segoe UI", 11, QFont.Weight.Bold)

        self.btn_dashboard = QPushButton("DASHBOARD")
        self.btn_dashboard.setMinimumHeight(45)
        self.btn_dashboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dashboard.setFont(action_font)
        self.btn_dashboard.setObjectName("btn_dashboard_main")
        
        if self.on_open_dashboard:
            self.btn_dashboard.clicked.connect(self.on_open_dashboard)
        
        self.btn_dashboard.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions_layout.addWidget(self.btn_dashboard)

        self.btn_connect = QPushButton("INICIAR")
        self.btn_connect.setMinimumHeight(45)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.setFont(action_font)
        self.btn_connect.setObjectName("btn_connect_start")
        
        self.btn_connect.clicked.connect(self.on_toggle)
        self.btn_connect.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions_layout.addWidget(self.btn_connect)

        layout.addWidget(actions_container)

    def _create_mode_selector(self, layout):
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(1)

        self.btn_mode_sdr = QPushButton("SDR Radio")
        self.btn_mode_udp = QPushButton("UDP Network")
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

    def _build_main_area(self, layout):
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)
        
        # Seção Waterfall
        self.spectrum_container = self._create_section("Waterfall")
        self._setup_waterfall(self.spectrum_container.layout())
        splitter.addWidget(self.spectrum_container)

        # Seção Log
        self.log_container = self._create_section("Log de Telemetria")
        self.log_text = LogTextbox(max_lines=2000)
        # Borda removida pois LogTextbox já herda estilo
        self.log_text.setFrameShape(QFrame.Shape.NoFrame)
        self.log_container.layout().addWidget(self.log_text)
        splitter.addWidget(self.log_container)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter)

    def _create_section(self, title):
        w = QFrame()
        w.setProperty("class", "SectionContainer") 
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)

        lbl = QLabel(f"  {title}")
        lbl.setFixedHeight(32)
        lbl.setProperty("class", "SectionTitle") 
        l.addWidget(lbl)
        
        content = QWidget()
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(4, 4, 4, 4)
        l.addWidget(content)
        return w

    def _setup_waterfall(self, layout):
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

    # === MÉTODO CORRIGIDO: LOGO EM BASE64 + APPEND_HTML ===
    def _print_welcome_message(self):
        """
        Carrega o logo, converte para Base64 com redimensionamento SUAVE
        e insere no log como HTML, garantindo alta qualidade.
        """
        base_dir = Path(__file__).parent
        logo_path = (base_dir / "assets" / "logo.png").resolve().as_posix()
        
        img_tag = ""
        # Processamento de imagem para alta qualidade
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            # Redimensiona com filtro suave (SmoothTransformation)
            scaled = pixmap.scaledToWidth(150, Qt.TransformationMode.SmoothTransformation)
            
            # Converte para Base64
            ba = QByteArray()
            buff = QBuffer(ba)
            buff.open(QIODevice.OpenModeFlag.WriteOnly)
            scaled.save(buff, "PNG")
            hex_data = base64.b64encode(ba.data()).decode("utf-8")
            
            # Cria tag IMG com dados embutidos
            img_tag = f"<img src='data:image/png;base64,{hex_data}'>"
        else:
            img_tag = "<b>[LOGO NOT FOUND]</b>"

        # HTML do Banner
        # A div "align=left" vazia no final força o cursor a voltar para a esquerda
        html_content = f"""
        <div align='center' style='margin-bottom: 15px;'>
            {img_tag}
            <h3 style='color: {THEME_COLORS['accent']}; margin: 8px 0; font-family: Segoe UI, sans-serif;'>NPA AEROSPACE</h3>
            <span style='color: {THEME_COLORS['text_dim']}; font-style: italic; font-family: Segoe UI, sans-serif;'>Ground Station System v1.0</span>
            <div style='border-bottom: 1px solid {THEME_COLORS['border_subtle']}; margin-top: 15px; margin-bottom: 5px;'></div>
        </div>
        """
        
        # CHAMA O MÉTODO ESPECÍFICO PARA HTML
        self.log_text.append_html(html_content)

    def _on_mode_change_internal(self, btn_id):
        mode = "RADIO" if btn_id == 1 else "UDP"
        if mode == "RADIO": self.params_stack.setCurrentWidget(self.radio_params)
        else: self.params_stack.setCurrentWidget(self.udp_params)
        self.current_mode = mode
        if self.on_mode_change: self.on_mode_change(mode)

    def update_waterfall(self, data: np.ndarray):
        if data is None or data.size == 0: return
        try:
            if data.size != self.wf_cols:
                self.wf_cols = data.size
                self.wf_data = np.full((self.wf_rows, self.wf_cols), -100.0, dtype=np.float32)
            self.wf_data[:-1] = self.wf_data[1:]
            self.wf_data[-1] = data
            self.img_item.setImage(self.wf_data.T, autoLevels=False)
        except Exception: pass

    # === MÉTODO CORRIGIDO PARA LOGS ===
    def log(self, message: str): 
        # CHAMA O MÉTODO ESPECÍFICO PARA TEXTO PURO (Corrige alinhamento e formatação)
        self.log_text.append_log(message)

    def set_running_state(self, running: bool):
        self.btn_connect.setText("PARAR" if running else "INICIAR")
        new_id = "btn_connect_stop" if running else "btn_connect_start"
        self.btn_connect.setObjectName(new_id)
        
        self.btn_connect.style().unpolish(self.btn_connect)
        self.btn_connect.style().polish(self.btn_connect)

        self.enable_controls(not running)

    def enable_controls(self, enable):
        self.btn_mode_sdr.setEnabled(enable)
        self.btn_mode_udp.setEnabled(enable)
        self.decoder_selector.set_enabled(enable)
        self.multi_decoder_check.setEnabled(enable)
        if self.current_mode == "RADIO": self.radio_params.set_enabled(enable)
        else: self.udp_params.set_enabled(enable)

    def set_mode(self, mode: str):
        is_radio = (mode == "RADIO")
        self.btn_mode_sdr.setChecked(is_radio)
        self.btn_mode_udp.setChecked(not is_radio)
        self._on_mode_change_internal(1 if is_radio else 2)

    def get_radio_config(self): return self.radio_params.get_config()
    def get_udp_config(self): return self.udp_params.get_config()
    def get_selected_decoder(self): return self.decoder_selector.get_selected()
    def is_multi_decoder_enabled(self): return self.multi_decoder_check.isChecked()
    def update_decoders(self, decoders): self.decoder_selector.update_decoders(decoders)