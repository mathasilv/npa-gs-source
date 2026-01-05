# src/npags/gui/views/__init__.py
"""Views principais da aplicação.

Views disponíveis:
    - DashboardView: Dashboard de telemetria com widgets
    - StationView: View principal da estação (controles, waterfall, log)
    - EditorView: Editor de schemas de decoder
"""

from npags.gui.views.dashboard_view import DashboardView
from npags.gui.views.editor_view import EditorView
from npags.gui.views.station_view import StationView

__all__ = [
    'DashboardView',
    'StationView',
    'EditorView',
]
