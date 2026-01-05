# src/npags/gui/components/__init__.py
"""
Componentes reutilizáveis da interface.

Componentes disponíveis:
    - CheckableComboBox: ComboBox com checkboxes para seleção múltipla
    - RadioParamsFrame: Configuração de rádio SDR/LoRa
    - UDPParamsFrame: Configuração de rede UDP
    - DecoderSelectorFrame: Seleção de decoder
    - LogTextbox: Widget de log híbrido (HTML + texto)
    - StyledLabel: Label estilizada para sidebar
    - scan_sdr_devices: Função para detectar dispositivos SDR
    - get_sdr_device_details: Função para obter detalhes dos dispositivos SDR
"""

from npags.gui.components.checkable_combo import CheckableComboBox
from npags.gui.components.log_textbox import LogTextbox
from npags.gui.components.sidebar_params import (
    DecoderSelectorFrame,
    RadioParamsFrame,
    StyledLabel,
    UDPParamsFrame,
    create_styled_combobox,
    get_sdr_device_details,
    scan_sdr_devices,
)

__all__ = [
    'CheckableComboBox',
    'create_styled_combobox',
    'RadioParamsFrame',
    'UDPParamsFrame',
    'DecoderSelectorFrame',
    'StyledLabel',
    'scan_sdr_devices',
    'get_sdr_device_details',
    'LogTextbox',
]
