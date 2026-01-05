"""
Pacote do Dashboard.

Contém componentes extraídos do dashboard_view.py para
melhor organização e manutenibilidade.
"""

from npags.gui.views.dashboard.data_manager import DashboardDataManager
from npags.gui.views.dashboard.layout_manager import DashboardLayoutManager

__all__ = [
    "DashboardDataManager",
    "DashboardLayoutManager",
]
