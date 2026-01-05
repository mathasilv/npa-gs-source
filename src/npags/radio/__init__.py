"""Módulo de comunicação por rádio (SDR/LoRa)

Importações condicionais para evitar erro quando gnuradio não está instalado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
