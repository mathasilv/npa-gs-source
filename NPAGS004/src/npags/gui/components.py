# src/npags/gui/components.py

"""
Biblioteca de componentes reutilizáveis da interface (Widgets).
Versão Final: Log Híbrido (Logo HTML + Dados Texto Puro Monospace).
"""

from typing import List, Callable, Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QCheckBox, QSlider,
    QFrame, QPushButton, QTextBrowser, QListView, 
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QTextBlockFormat # Imports essenciais para formatação

from npags.gui.styles import THEME_COLORS

# Tentativa de importação do driver SDR
HAS_OSMOSDR = False
try:
    import osmosdr
    HAS_OSMOSDR = True
except ImportError:
    pass


def scan_sdr_devices() -> List[str]:
    """
    Lista dispositivos SDR conectados.
    Se não houver driver, retorna lista genérica para evitar UI quebrada.
    """
    if not HAS_OSMOSDR:
        # Retorna lista simulada para permitir testar a interface sem hardware
        return ["Simulated Device", "RTL-SDR (USB)", "HackRF One", "Airspy"]

    detected = []
    # Tenta escanear índices 0 a 3
    for i in range(4):
        try:
            src = osmosdr.source(args=f"rtl={i}")
            try:
                meta = src.get_hardware_info()
                label = f"{i}: RTL-SDR ({meta})"
            except Exception:
                label = f"{i}: Generic RTL-SDR"
            detected.append(label)
            del src
        except Exception:
            continue

    return detected if detected else ["Nenhum dispositivo encontrado"]


class StyledLabel(QLabel):
    """
    Label padronizada para títulos de inputs na sidebar.
    """
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "InfoLabel") 
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(f"""
            color: {THEME_COLORS['text_dim']};
            font-weight: bold;
            font-size: 11px;
            text-transform: uppercase;
            margin-top: 10px;
        """)


class RadioParamsFrame(QFrame):
    """Painel de configuração de parâmetros do Rádio LoRa (SDR)."""

    gainChanged = pyqtSignal(int)

    def __init__(self, parent=None, radios: List[str] = None, on_gain_change: Optional[Callable[[int], None]] = None):
        super().__init__(parent)
        self.on_gain_change = on_gain_change

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        # === Dispositivo SDR ===
        self._add_label(layout, "Dispositivo SDR:")
        self.device_combo = self._create_combo(radios if radios else ["Nenhum detectado"], "device")
        layout.addWidget(self.device_combo)

        # === Frequência ===
        self._add_label(layout, "Frequência (MHz):")
        self.freq_entry = QLineEdit("915.0")
        self.freq_entry.setPlaceholderText("Ex: 915.0")
        self._config_input_width(self.freq_entry)
        layout.addWidget(self.freq_entry)

        # === SF e BW ===
        self._add_label(layout, "Spreading Factor (SF):")
        self.sf_combo = self._create_combo([str(i) for i in range(7, 13)], "sf")
        self.sf_combo.setCurrentText("7")
        layout.addWidget(self.sf_combo)

        self._add_label(layout, "Bandwidth (Hz):")
        self.bw_combo = self._create_combo(["125000", "250000", "500000"], "bw")
        self.bw_combo.setCurrentText("125000")
        layout.addWidget(self.bw_combo)

        # === Espaço Vazio ===
        layout.addSpacing(12)

        # === Controle de Ganho ===
        gain_header = QHBoxLayout()
        lbl_gain = StyledLabel("Ganho RF")
        self.gain_label = QLabel("20 dB")
        self.gain_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        gain_header.addWidget(lbl_gain)
        gain_header.addStretch()
        gain_header.addWidget(self.gain_label)
        layout.addLayout(gain_header)

        # Slider
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 49)
        self.gain_slider.setValue(20)
        self.gain_slider.valueChanged.connect(self._on_slider_change)
        layout.addWidget(self.gain_slider)

        # === Bias Tee ===
        layout.addSpacing(6)
        self.bias_check = QCheckBox("Bias Tee")
        layout.addWidget(self.bias_check)

        layout.addStretch()

    def _add_label(self, layout, text):
        layout.addWidget(StyledLabel(text))

    def _config_input_width(self, widget):
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _create_combo(self, items, obj_name):
        cb = QComboBox()
        cb.setView(QListView())
        cb.addItems(items)
        cb.setObjectName(obj_name)
        self._config_input_width(cb)
        return cb

    def _on_slider_change(self, value: int):
        self.gain_label.setText(f"{value} dB")
        self.gainChanged.emit(value)
        if self.on_gain_change:
            self.on_gain_change(value)

    def get_config(self) -> Dict[str, Any]:
        try:
            freq = float(self.freq_entry.text().replace(',', '.')) * 1e6
        except ValueError:
            freq = 915.0e6

        return {
            'device': self.device_combo.currentText() if hasattr(self, 'device_combo') else "Auto",
            'freq': freq,
            'sf': int(self.sf_combo.currentText()),
            'bw': float(self.bw_combo.currentText()),
            'gain': self.gain_slider.value(),
            'bias': self.bias_check.isChecked()
        }

    def set_enabled(self, enabled: bool):
        self.freq_entry.setEnabled(enabled)
        self.sf_combo.setEnabled(enabled)
        self.bw_combo.setEnabled(enabled)
        self.bias_check.setEnabled(enabled)
        if hasattr(self, 'device_combo'): self.device_combo.setEnabled(enabled)


class UDPParamsFrame(QFrame):
    """Painel UDP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        self.host_entry = QLineEdit("0.0.0.0")
        self.host_entry.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(StyledLabel("Host / IP:"))
        layout.addWidget(self.host_entry)

        self.port_entry = QLineEdit("5005")
        self.port_entry.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(StyledLabel("Porta UDP:"))
        layout.addWidget(self.port_entry)

        layout.addStretch(1)

    def get_config(self) -> Dict[str, Any]:
        try:
            port = int(self.port_entry.text())
        except ValueError:
            port = 5005
        return {'host': self.host_entry.text().strip() or "0.0.0.0", 'port': port}

    def set_enabled(self, enabled: bool):
        self.host_entry.setEnabled(enabled)
        self.port_entry.setEnabled(enabled)


class DecoderSelectorFrame(QFrame):
    """Painel de seleção de decoder."""

    def __init__(self, parent, decoders: List[str], on_new: Callable, on_edit: Callable):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        lbl = StyledLabel("Perfil de Decoder")
        header.addWidget(lbl)
        header.addStretch()

        # Botões
        btn_new = QPushButton("Novo")
        btn_new.setFixedSize(70, 30)  
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.clicked.connect(on_new)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setFixedSize(70, 30)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(on_edit)
        header.addWidget(btn_edit)

        layout.addLayout(header)

        # Combo
        self.decoder_combo = QComboBox()
        self.decoder_combo.setView(QListView())
        self.decoder_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.update_decoders(decoders)
        layout.addWidget(self.decoder_combo)

    def get_selected(self) -> str:
        return self.decoder_combo.currentText()

    def update_decoders(self, decoders: List[str]):
        curr = self.decoder_combo.currentText()
        self.decoder_combo.clear()
        if decoders:
            self.decoder_combo.addItems(decoders)
            if curr in decoders: self.decoder_combo.setCurrentText(curr)
        else:
            self.decoder_combo.addItem("Nenhum")

    def set_enabled(self, enabled: bool):
        self.decoder_combo.setEnabled(enabled)


class LogTextbox(QTextBrowser):
    """
    Log Híbrido: Suporta HTML (para o logo) e Texto Puro (para o log de dados).
    Usa fonte Monospace para garantir alinhamento correto das tabelas.
    """
    def __init__(self, parent=None, max_lines: int = 1000):
        super().__init__(parent)
        self.max_lines = max_lines
        self.setObjectName("LogConsole") # Vincula ao styles.py
        
        self.setOpenExternalLinks(True)
        self.setPlaceholderText("Aguardando telemetria...")
        
        # 1. FORÇA FONTE DE TERMINAL (Monospace)
        # Isso garante que a tabela de dados não fique torta
        font = QFont("Consolas") 
        font.setStyleHint(QFont.StyleHint.Monospace)
        if not font.exactMatch():
            font = QFont("Monospace") # Fallback para Linux/Mac
        font.setPointSize(10)
        self.setFont(font)

    def append_html(self, html: str):
        """
        Insere conteúdo HTML (como o Logo).
        Move o cursor para o fim antes de inserir.
        """
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.insertHtml(html)
        self.insertPlainText("\n") # Garante uma quebra de linha limpa após o HTML
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def append_log(self, text: str):
        """
        Insere texto de log como TEXTO PURO (PlainText).
        Corrige automaticamente o alinhamento para esquerda e remove formatação herdada.
        """
        self.moveCursor(QTextCursor.MoveOperation.End)
        cursor = self.textCursor()

        # 1. Força Alinhamento à Esquerda (evita herdar o 'center' do logo)
        block_fmt = cursor.blockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)
        cursor.setBlockFormat(block_fmt)

        # 2. Reseta estilos de fonte (evita herdar negrito/itálico)
        char_fmt = cursor.charFormat()
        char_fmt.setFontWeight(QFont.Weight.Normal)
        char_fmt.setFontItalic(False)
        cursor.setCharFormat(char_fmt)
        
        # 3. Insere o texto limpo
        self.insertPlainText(text + "\n")
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def append(self, text: str):
        """
        Sobrescreve o método padrão para usar a inserção segura de log.
        Isso mantém compatibilidade com o resto do código que chama .append()
        """
        self.append_log(text)
        
    def clear_log(self):
        self.clear()