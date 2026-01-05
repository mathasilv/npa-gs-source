# src/npags/gui/widgets/__init__.py
"""
Widgets reutilizáveis para a interface gráfica.

Widgets disponíveis:
    - MapWidget: Mapa GPS interativo com Leaflet.js
    - PlotWidget: Gráfico com crosshair e exportação
    - CardWidget: Cartão simples com valor
    - GaugeWidget: Medidor com barra de progresso
    - LedWidget: LED colorido com status
    - VarioWidget: Variômetro (velocidade vertical)
    - CompassWidget: Bússola / heading
    - SmartDashboardItem: Item arrastável para canvas
    - BlueprintScene: Cena com grade de fundo
    - AlertEngine: Motor de alertas
    - AlertsPanelWidget: Painel de alertas ativos
    - AlertConfig: Configuração de alerta
"""

from npags.gui.canvas_items import BlueprintScene, SmartDashboardItem
from npags.gui.widgets.alerts_widget import (
    ActiveAlert,
    AlertConfig,
    AlertEngine,
    AlertHistoryEntry,
    AlertNotificationManager,
    AlertSeverity,
)
from npags.gui.widgets.kpi_widgets import (
    CardWidget,
    CompassWidget,
    GaugeWidget,
    LedWidget,
    VarioWidget,
    create_kpi_widget,
)
from npags.gui.widgets.map_widget import MapWidget
from npags.gui.widgets.plot_widget import PlotWidget

__all__ = [
    'MapWidget',
    'PlotWidget',
    'CardWidget',
    'GaugeWidget',
    'LedWidget',
    'VarioWidget',
    'CompassWidget',
    'create_kpi_widget',
    'SmartDashboardItem',
    'BlueprintScene',
    'AlertEngine',
    'AlertNotificationManager',
    'AlertConfig',
    'AlertSeverity',
    'ActiveAlert',
    'AlertHistoryEntry',
]
