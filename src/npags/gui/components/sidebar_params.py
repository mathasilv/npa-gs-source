# src/npags/gui/components/sidebar_params.py
"""
Componentes de parâmetros para a sidebar (Radio, UDP, Decoder).

Extraído de components.py para melhor organização.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from npags.gui.components.checkable_combo import CheckableComboBox
from npags.gui.translations import tr
from npags.gui.styles import THEME_COLORS


def create_styled_combobox() -> QComboBox:
    """
    Cria um QComboBox com estilo padronizado do tema.
    
    Usar esta função em vez de QComboBox() diretamente para garantir
    consistência visual em todo o projeto.
    
    Returns:
        QComboBox estilizado com dropdown de fundo preto e borda laranja.
    """
    cb = QComboBox()
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
    cb.setView(list_view)
    return cb


# Tentativa de importação dos drivers SDR
HAS_OSMOSDR = False
try:
    import osmosdr
    HAS_OSMOSDR = True
except ImportError:
    pass

# Tentativa de importação do SoapySDR (alternativa mais moderna)
HAS_SOAPYSDR = False
try:
    import SoapySDR
    HAS_SOAPYSDR = True
except ImportError:
    pass


def _scan_with_soapysdr() -> list[dict[str, Any]]:
    """
    Escaneia dispositivos SDR usando SoapySDR.

    Returns:
        Lista de dicionários com informações dos dispositivos.
    """
    if not HAS_SOAPYSDR:
        return []

    devices = []
    try:
        results = SoapySDR.Device.enumerate()
        for i, result in enumerate(results):
            device_info = {
                'index': i,
                'driver': result.get('driver', 'unknown'),
                'label': result.get('label', ''),
                'serial': result.get('serial', ''),
                'product': result.get('product', ''),
                'manufacturer': result.get('manufacturer', ''),
                'args': dict(result),
            }
            devices.append(device_info)
    except Exception:
        pass

    return devices


def _scan_with_osmosdr() -> list[dict[str, Any]]:
    """
    Escaneia dispositivos SDR usando gr-osmosdr.
    Usa apenas RTL-SDR por padrão (mais comum e rápido).

    Returns:
        Lista de dicionários com informações dos dispositivos.
    """
    if not HAS_OSMOSDR:
        return []

    devices = []

    # Escaneia apenas RTL-SDR (mais comum)
    for i in range(4):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            # Suprime output do osmosdr
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')

            src = osmosdr.source(args=f"rtl={i}")

            # Obtém informações do hardware
            try:
                hw_info = src.get_hardware_info()
            except Exception:
                hw_info = ''

            device_info = {
                'index': i,
                'driver': 'rtl',
                'name': 'RTL-SDR',
                'hw_info': hw_info,
                'freq_min': 24e6,
                'freq_max': 1766e6,
                'args': f"rtl={i}",
            }
            devices.append(device_info)

            del src

        except Exception:
            # Dispositivo não encontrado
            break
        finally:
            try:
                sys.stdout.close()
                sys.stderr.close()
            except Exception:
                pass
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    return devices


def scan_sdr_devices() -> list[str]:
    """
    Lista dispositivos SDR conectados.

    Detecta automaticamente RTL-SDR e outros dispositivos suportados.

    Returns:
        Lista de strings descrevendo os dispositivos encontrados.
    """

    # Se nenhum driver SDR está disponível, retorna lista simulada
    if not HAS_OSMOSDR and not HAS_SOAPYSDR:
        return [
            "[SIM] RTL-SDR v3",
            "[SIM] HackRF One",
            "[SIM] Airspy Mini",
            "[SIM] LimeSDR Mini",
        ]

    # Suprime output do osmosdr durante o scan
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

        detected = []
        seen_serials = set()

        # Primeiro tenta SoapySDR (mais moderno e abrangente)
        if HAS_SOAPYSDR:
            soapy_devices = _scan_with_soapysdr()
            for dev in soapy_devices:
                serial = dev.get('serial', '')
                if serial and serial in seen_serials:
                    continue
                if serial:
                    seen_serials.add(serial)

                driver = dev.get('driver', 'unknown').upper()
                label = dev.get('label', '') or dev.get('product', '')
                manufacturer = dev.get('manufacturer', '')

                if label:
                    display = f"{driver}: {label}"
                elif manufacturer:
                    display = f"{driver}: {manufacturer}"
                else:
                    display = f"{driver} #{dev['index']}"

                if serial:
                    display += f" [{serial[:8]}]"

                detected.append(display)

        # Depois tenta osmosdr (fallback ou complemento)
        if HAS_OSMOSDR:
            osmo_devices = _scan_with_osmosdr()
            for dev in osmo_devices:
                hw_info = dev.get('hw_info', '')

                serial = ''
                if 'serial' in hw_info.lower():
                    import re as regex
                    match = regex.search(r'serial[=:]?\s*([\w]+)', hw_info, regex.IGNORECASE)
                    if match:
                        serial = match.group(1)

                if serial and serial in seen_serials:
                    continue
                if serial:
                    seen_serials.add(serial)

                name = dev.get('name', 'SDR')
                idx = dev.get('index', 0)

                if hw_info:
                    display = f"{name} #{idx}: {hw_info}"
                else:
                    display = f"{name} #{idx}"

                detected.append(display)

        # Remove duplicatas mantendo ordem
        unique_detected = []
        seen_displays = set()
        for d in detected:
            normalized = d.lower().replace(' ', '')
            if normalized not in seen_displays:
                seen_displays.add(normalized)
                unique_detected.append(d)

        return unique_detected if unique_detected else [tr("Nenhum dispositivo SDR encontrado")]

    finally:
        try:
            sys.stdout.close()
            sys.stderr.close()
        except Exception:
            pass
        sys.stdout = old_stdout
        sys.stderr = old_stderr



def get_sdr_device_details() -> list[dict[str, Any]]:
    """
    Retorna informações detalhadas dos dispositivos SDR.

    Útil para configuração avançada e diagnóstico.

    Returns:
        Lista de dicionários com detalhes completos de cada dispositivo.
    """
    all_devices = []

    if HAS_SOAPYSDR:
        all_devices.extend(_scan_with_soapysdr())

    if HAS_OSMOSDR:
        all_devices.extend(_scan_with_osmosdr())

    return all_devices


class StyledLabel(QLabel):
    """Label padronizada para títulos de inputs na sidebar."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("class", "InfoLabel")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(f"""
            color: {THEME_COLORS['text_dim']};
            font-size: 11px;
            text-transform: uppercase;
            margin-top: 10px;
        """)


class RadioParamsFrame(QFrame):
    """Painel de configuração de parâmetros do Rádio LoRa (SDR)."""

    gainChanged = pyqtSignal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        radios: list[str] | None = None,
        on_gain_change: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.on_gain_change = on_gain_change
        self._setup_ui(radios)

    def _setup_ui(self, radios: list[str] | None) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        # Dispositivo SDR
        self._add_label(layout, tr("Dispositivo SDR:"))
        self.device_combo = self._create_combo(
            radios if radios else [tr("Nenhum detectado")], "device"
        )
        layout.addWidget(self.device_combo)

        # Frequência
        self._add_label(layout, tr("Frequência (MHz):"))
        self.freq_entry = QLineEdit("915.0")
        self.freq_entry.setPlaceholderText("Ex: 915.0")
        self._config_input_width(self.freq_entry)
        layout.addWidget(self.freq_entry)

        # SF e BW
        self._add_label(layout, tr("Spreading Factor (SF):"))
        self.sf_combo = self._create_combo([str(i) for i in range(7, 13)], "sf")
        self.sf_combo.setCurrentText("7")
        layout.addWidget(self.sf_combo)

        self._add_label(layout, tr("Bandwidth (Hz):"))
        self.bw_combo = self._create_combo(["125000", "250000", "500000"], "bw")
        self.bw_combo.setCurrentText("125000")
        layout.addWidget(self.bw_combo)

        layout.addSpacing(12)

        # Controle de Ganho
        gain_header = QHBoxLayout()
        lbl_gain = StyledLabel(tr("Ganho RF"))
        self.gain_label = QLabel("20 dB")
        self.gain_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        gain_header.addWidget(lbl_gain)
        gain_header.addStretch()
        gain_header.addWidget(self.gain_label)
        layout.addLayout(gain_header)

        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 49)
        self.gain_slider.setValue(20)
        self.gain_slider.valueChanged.connect(self._on_slider_change)
        layout.addWidget(self.gain_slider)

        # Bias Tee
        layout.addSpacing(6)
        self.bias_check = QCheckBox(tr("Bias Tee"))
        layout.addWidget(self.bias_check)

        layout.addStretch()

    def _add_label(self, layout: QVBoxLayout, text: str) -> None:
        layout.addWidget(StyledLabel(text))

    def _config_input_width(self, widget: QWidget) -> None:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _create_combo(self, items: list[str], obj_name: str) -> QComboBox:
        """Cria um ComboBox com dropdown estilizado."""
        cb = QComboBox()
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
        cb.setView(list_view)
        cb.addItems(items)
        cb.setObjectName(obj_name)
        self._config_input_width(cb)
        return cb

    def _on_slider_change(self, value: int) -> None:
        self.gain_label.setText(f"{value} dB")
        self.gainChanged.emit(value)
        if self.on_gain_change:
            self.on_gain_change(value)

    def get_config(self) -> dict[str, Any]:
        """Retorna a configuração atual do rádio."""
        try:
            freq = float(self.freq_entry.text().replace(',', '.')) * 1e6
        except ValueError:
            freq = 915.0e6

        return {
            'device': self.device_combo.currentText(),
            'freq': freq,
            'sf': int(self.sf_combo.currentText()),
            'bw': float(self.bw_combo.currentText()),
            'gain': self.gain_slider.value(),
            'bias': self.bias_check.isChecked()
        }

    def set_enabled(self, enabled: bool) -> None:
        """Habilita/desabilita os controles."""
        self.freq_entry.setEnabled(enabled)
        self.sf_combo.setEnabled(enabled)
        self.bw_combo.setEnabled(enabled)
        self.bias_check.setEnabled(enabled)
        self.device_combo.setEnabled(enabled)


class UDPParamsFrame(QFrame):
    """Painel de configuração UDP."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        self.host_entry = QLineEdit("0.0.0.0")
        self.host_entry.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(StyledLabel(tr("Host / IP:")))
        layout.addWidget(self.host_entry)

        self.port_entry = QLineEdit("5005")
        self.port_entry.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(StyledLabel(tr("Porta UDP:")))
        layout.addWidget(self.port_entry)

        layout.addStretch(1)

    def get_config(self) -> dict[str, Any]:
        """Retorna a configuração atual do UDP."""
        try:
            port = int(self.port_entry.text())
        except ValueError:
            port = 5005
        return {
            'host': self.host_entry.text().strip() or "0.0.0.0",
            'port': port
        }

    def set_enabled(self, enabled: bool) -> None:
        """Habilita/desabilita os controles."""
        self.host_entry.setEnabled(enabled)
        self.port_entry.setEnabled(enabled)



class DecoderSelectorFrame(QFrame):
    """Painel de selecao de decoder com suporte a multipla selecao via dropdown."""

    selectionChanged = pyqtSignal(list)

    def __init__(
        self,
        parent: QWidget | None,
        decoders: list[str],
        on_new: Callable[[], None],
        on_edit: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._decoders = decoders or []
        self._setup_ui(decoders, on_new, on_edit)

    def _setup_ui(
        self,
        decoders: list[str],
        on_new: Callable[[], None],
        on_edit: Callable[[], None],
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        lbl = StyledLabel(tr("Perfil de Decoder"))
        header.addWidget(lbl)
        header.addStretch()

        btn_new = QPushButton(tr("Novo"))
        btn_new.setFixedSize(70, 30)
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.clicked.connect(on_new)
        header.addWidget(btn_new)

        btn_edit = QPushButton(tr("Editar"))
        btn_edit.setFixedSize(70, 30)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(on_edit)
        header.addWidget(btn_edit)

        layout.addLayout(header)

        # Combo com checkboxes
        self.decoder_combo = CheckableComboBox()
        self.decoder_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.decoder_combo.selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.decoder_combo)

        # Popula com decoders
        self.update_decoders(decoders)

    def _on_selection_changed(self, selected: list[str]):
        """Emite sinal quando selecao muda."""
        self.selectionChanged.emit(selected)

    def get_selected(self) -> str:
        """Retorna o primeiro decoder selecionado (compatibilidade)."""
        selected = self.get_selected_decoders()
        return selected[0] if selected else "Nenhum"

    def get_selected_decoders(self) -> list[str]:
        """Retorna lista de decoders selecionados."""
        return self.decoder_combo.getCheckedItems()

    def is_multi_mode(self) -> bool:
        """Retorna True se mais de um decoder esta selecionado."""
        return len(self.get_selected_decoders()) > 1

    def update_decoders(self, decoders: list[str]) -> None:
        """Atualiza a lista de decoders."""
        self._decoders = decoders or []
        current_selection = self.decoder_combo.getCheckedItems()

        self.decoder_combo.clear()

        # Adiciona opcao tr("Todos") primeiro
        if len(decoders) > 1:
            self.decoder_combo.addAllOption()

        for decoder in decoders:
            checked = decoder in current_selection
            self.decoder_combo.addCheckableItem(decoder, checked)

        # Se nenhum estava selecionado, seleciona o primeiro
        if not current_selection and decoders:
            self.decoder_combo.setCheckedItems([decoders[0]])

    def set_enabled(self, enabled: bool) -> None:
        """Habilita/desabilita os controles."""
        self.decoder_combo.setEnabled(enabled)

