# src/npags/gui/__init__.py
"""
Interface gráfica do NPA Ground Station.

Este módulo contém todos os componentes da interface gráfica:

    - views: Views principais (Dashboard, Station, Editor)
    - widgets: Widgets de visualização (MapWidget, PlotWidget, KPIs)
    - components: Componentes reutilizáveis de UI (LogTextbox, StatusBar)
    - dialogs: Diálogos modais (HistoryFilterDialog)
    - styles: Estilos e cores do tema

Uso básico:
    >>> from npags.gui import main
    >>> main()  # Inicia a aplicação

Ou importar componentes específicos:
    >>> from npags.gui.views import DashboardView, StationView
    >>> from npags.gui.widgets import MapWidget, PlotWidget
    >>> from npags.gui.components import LogTextbox
"""

from npags.gui.main_window import GroundStationApp, main

__all__ = [
    'GroundStationApp',
    'main',
]
