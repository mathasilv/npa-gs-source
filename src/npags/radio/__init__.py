"""Módulo de comunicação por rádio (SDR/LoRa)

Importações condicionais para evitar erro quando gnuradio não está instalado.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

# GNU Radio é instalado no sistema (pacman/apt), não via pip.
# O PyInstaller não inclui pacotes do sistema no bundle, então
# adicionamos dinamicamente diretórios site-packages do sistema ao
# sys.path para encontrar o gnuradio na máquina alvo.
import glob as _glob
for _p in _glob.glob("/usr/lib/python3*/site-packages"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
for _p in _glob.glob("/usr/local/lib/python3*/site-packages"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
for _p in _glob.glob("/usr/lib/python3*/dist-packages"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
for _p in _glob.glob("/usr/local/lib/python3*/dist-packages"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# UDP Receiver não depende de gnuradio
from npags.radio.udp_receiver import UDPReceiver

# Importações condicionais para módulos que dependem de gnuradio
RadioBackend: Any
RadioFlowgraph: Any

try:
    from npags.radio.backend import RadioBackend as _RadioBackend
    from npags.radio.flowgraph import RadioFlowgraph as _RadioFlowgraph
    RadioBackend = _RadioBackend
    RadioFlowgraph = _RadioFlowgraph
    HAS_GNURADIO = True
except ImportError:
    RadioBackend = None
    RadioFlowgraph = None
    HAS_GNURADIO = False

__all__ = ["UDPReceiver", "RadioBackend", "RadioFlowgraph", "HAS_GNURADIO"]
