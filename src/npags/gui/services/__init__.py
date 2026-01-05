"""
Serviços compartilhados da GUI.

Este módulo contém lógica de negócio extraída dos diálogos
para evitar duplicação e facilitar manutenção.
"""

from npags.gui.services.data_extractor import DataExtractor
from npags.gui.services.history_service import HistoryService

__all__ = [
    "DataExtractor",
    "HistoryService",
]
