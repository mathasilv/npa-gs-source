"""Módulo de comunicação por rádio (SDR/LoRa)

Importações condicionais para evitar erro quando gnuradio não está instalado.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

# GNU Radio é instalado no sistema (pacman/apt), não via pip.
# Adicionamos caminhos comuns do sistema ao sys.path para que o
# PyInstaller consiga encontrar o gnuradio quando instalado na máquina alvo.
_POSSIBLE_GNURADIO_PATHS = [
    "/usr/lib/python3/dist-packages",
    "/usr/local/lib/python3/dist-packages",
    "/usr/lib/python3.13/site-packages",
    "/usr/local/lib/python3.13/site-packages",
    "/usr/lib/python3.12/site-packages",
    "/usr/local/lib/python3.12/site-packages",
    "/usr/lib/python3.11/site-packages",
    "/usr/local/lib/python3.11/site-packages",
]
for _p in _POSSIBLE_GNURADIO_PATHS:
    _pp = Path(_p)
    if _pp.is_dir() and str(_pp) not in sys.path:
        sys.path.insert(0, str(_pp))

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
