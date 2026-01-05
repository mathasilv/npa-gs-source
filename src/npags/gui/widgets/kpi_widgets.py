# src/npags/gui/widgets/kpi_widgets.py
"""
Widgets de KPI (Key Performance Indicators) para dashboard.

Widgets disponíveis:
    - CardWidget: Exibe valor simples com unidade
    - GaugeWidget: Barra de progresso com valor
    - LedWidget: LED colorido com status mapeado
    - VarioWidget: Variômetro (velocidade vertical)
    - CompassWidget: Bússola / heading

Exemplo de uso:
    >>> from npags.gui.widgets import CardWidget, GaugeWidget
    >>>
    >>> card = CardWidget(config={'unit': '°C', 'format': '{:.1f}'})
    >>> card.set_value(25.5)
    >>>
    >>> gauge = GaugeWidget(config={'min': 0, 'max': 100, 'unit': '%'})
    >>> gauge.set_value(75)
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from npags.gui.styles import THEME_COLORS


class BaseKpiWidget(QWidget):
    """Classe base para widgets KPI."""

    def __init__(
        self,
        config: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configura a interface. Deve ser implementado nas subclasses."""
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        """Define o valor do widget. Deve ser implementado nas subclasses."""
        raise NotImplementedError

    def reset(self) -> None:
        """Reseta o widget para estado inicial."""
        raise NotImplementedError

    def _format_value(self, value: Any) -> str:
        """Formata o valor para exibição."""
        format_str = self.config.get('format', '{}')
        try:
            return format_str.format(value)
        except (ValueError, KeyError, TypeError):
            return str(value)


class CardWidget(BaseKpiWidget):
    """
    Widget de cartão simples que exibe um valor com unidade.

    Config:
        unit (str): Unidade do valor (ex: '°C', '%')
        format (str): String de formatação (ex: '{:.1f}')
    """

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.val_label = QLabel("--")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val_label.setProperty("class", "CardValue")
        layout.addWidget(self.val_label)

    def set_value(self, value: Any) -> None:
        unit = self.config.get('unit', '')
        display_text = self._format_value(value)
        self.val_label.setText(f"{display_text} {unit}".strip())

    def reset(self) -> None:
        self.val_label.setText("--")


class GaugeWidget(BaseKpiWidget):
    """
    Widget de medidor com barra de progresso.

    Config:
        min (float): Valor mínimo (default: 0)
        max (float): Valor máximo (default: 100)
        unit (str): Unidade do valor
        format (str): String de formatação
    """

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.val_label = QLabel("--")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val_label.setStyleSheet(
            f"color: {THEME_COLORS['accent']}; font-size: 16px;"
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setProperty("class", "DashboardGauge")
        self.progress_bar.setRange(0, 1000)

        layout.addWidget(self.val_label)
        layout.addWidget(self.progress_bar)

    def set_value(self, value: Any) -> None:
        try:
            val = float(value)
            min_v = self.config.get('min', 0)
            max_v = self.config.get('max', 100)

            clamped = max(min_v, min(val, max_v))
            progress = int(((clamped - min_v) / (max_v - min_v)) * 1000)
            self.progress_bar.setValue(progress)

            unit = self.config.get('unit', '')
            display_text = self._format_value(value)
            self.val_label.setText(f"{display_text} {unit}".strip())
        except (ValueError, TypeError, ZeroDivisionError):
            pass  # Valor inválido ignorado

    def reset(self) -> None:
        self.val_label.setText("--")
        self.progress_bar.setValue(0)


class LedWidget(BaseKpiWidget):
    """
    Widget de LED colorido com status mapeado.

    Config:
        mapping (dict): Mapeamento valor -> texto (ex: {0: 'OFF', 1: 'ON'})
        colors (dict): Mapeamento valor -> cor (ex: {0: '#555', 1: '#0F0'})
    """

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        led_row = QHBoxLayout()

        self.led_bulb = QLabel()
        self.led_bulb.setFixedSize(16, 16)
        self.led_bulb.setProperty("class", "LedBulb")
        self.led_bulb.setStyleSheet(
            f"background-color: {THEME_COLORS['border_subtle']}; border-radius: 8px;"
        )

        self.val_label = QLabel("--")
        self.val_label.setProperty("class", "InfoLabel")

        led_row.addStretch()
        led_row.addWidget(self.led_bulb)
        led_row.addWidget(self.val_label)
        led_row.addStretch()

        layout.addLayout(led_row)

    def set_value(self, value: Any) -> None:
        colors_map = self.config.get('colors', {})
        mapping = self.config.get('mapping', {})

        # Tenta encontrar cor (valor direto, string, ou int)
        bulb_color = (
            colors_map.get(value) or
            colors_map.get(str(value)) or
            colors_map.get(int(value) if isinstance(value, (int, float)) else 0) or
            "#444"
        )
        self.led_bulb.setStyleSheet(
            f"background-color: {bulb_color}; border-radius: 8px;"
        )

        # Tenta encontrar texto mapeado
        mapped_text = (
            mapping.get(value) or
            mapping.get(str(value)) or
            mapping.get(int(value) if isinstance(value, (int, float)) else 0) or
            value
        )
        self.val_label.setText(str(mapped_text).upper())

    def reset(self) -> None:
        self.led_bulb.setStyleSheet(
            f"background-color: {THEME_COLORS['border_subtle']}; border-radius: 8px;"
        )
        self.val_label.setText("--")


class VarioWidget(BaseKpiWidget):
    """
    Widget de variômetro (velocidade vertical).

    Mostra setas coloridas indicando subida/descida.

    Config:
        unit (str): Unidade (default: 'm/s')
    """

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)

        # Seta para cima
        self.arrow_up = QLabel("▲")
        self.arrow_up.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arrow_up.setStyleSheet(
            f"color: {THEME_COLORS['border_subtle']}; font-size: 18px;"
        )

        # Valor
        self.val_label = QLabel("0.0")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val_label.setStyleSheet(
            f"color: {THEME_COLORS['text']}; font-size: 16px;"
        )

        # Unidade
        unit = self.config.get('unit', 'm/s')
        self.unit_label = QLabel(unit)
        self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_label.setStyleSheet(
            f"color: {THEME_COLORS['text_dim']}; font-size: 11px;"
        )

        # Seta para baixo
        self.arrow_down = QLabel("▼")
        self.arrow_down.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arrow_down.setStyleSheet(
            f"color: {THEME_COLORS['border_subtle']}; font-size: 18px;"
        )

        layout.addWidget(self.arrow_up)
        layout.addWidget(self.val_label)
        layout.addWidget(self.unit_label)
        layout.addWidget(self.arrow_down)

    def set_value(self, value: Any) -> None:
        try:
            val = float(value)
            self.val_label.setText(f"{val:+.1f}")

            dim_color = THEME_COLORS['border_subtle']

            if val > 0.5:  # Subindo
                self.arrow_up.setStyleSheet("color: #00FF00; font-size: 18px;")
                self.arrow_down.setStyleSheet(f"color: {dim_color}; font-size: 18px;")
            elif val < -0.5:  # Descendo
                self.arrow_up.setStyleSheet(f"color: {dim_color}; font-size: 18px;")
                self.arrow_down.setStyleSheet("color: #FF4444; font-size: 18px;")
            else:  # Estável
                self.arrow_up.setStyleSheet(f"color: {dim_color}; font-size: 18px;")
                self.arrow_down.setStyleSheet(f"color: {dim_color}; font-size: 18px;")
        except (ValueError, TypeError):
            pass  # Valor inválido ignorado

    def reset(self) -> None:
        dim_color = THEME_COLORS['border_subtle']
        self.val_label.setText("0.0")
        self.arrow_up.setStyleSheet(f"color: {dim_color}; font-size: 18px;")
        self.arrow_down.setStyleSheet(f"color: {dim_color}; font-size: 18px;")


class CompassWidget(BaseKpiWidget):
    """
    Widget de bússola / heading.

    Mostra direção cardinal e graus.
    """

    DIRECTIONS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.compass_label = QLabel("N")
        self.compass_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compass_label.setStyleSheet(f"""
            color: {THEME_COLORS['accent']};
            font-size: 22px;
            border: 2px solid {THEME_COLORS['border_subtle']};
            border-radius: 40px;
            min-width: 80px;
            min-height: 80px;
        """)

        self.val_label = QLabel("0°")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val_label.setStyleSheet(
            f"color: {THEME_COLORS['text']}; font-size: 12px;"
        )

        layout.addWidget(self.compass_label)
        layout.addWidget(self.val_label)

    def set_value(self, value: Any) -> None:
        try:
            heading = float(value) % 360
            self.val_label.setText(f"{heading:.0f}°")

            # Determina direção cardinal
            idx = int((heading + 22.5) / 45) % 8
            cardinal = self.DIRECTIONS[idx]
            self.compass_label.setText(cardinal)
        except (ValueError, TypeError):
            pass  # Valor inválido ignorado

    def reset(self) -> None:
        self.compass_label.setText("N")
        self.val_label.setText("0°")


# Factory function para criar widgets por tipo
def create_kpi_widget(
    widget_type: str,
    config: dict[str, Any],
    parent: QWidget | None = None,
) -> BaseKpiWidget | None:
    """
    Cria um widget KPI pelo tipo.

    Args:
        widget_type: Tipo do widget ('card', 'gauge', 'led', 'vario', 'compass')
        config: Configuração do widget
        parent: Widget pai

    Returns:
        Instância do widget ou None se tipo inválido.
    """
    widgets = {
        'card': CardWidget,
        'gauge': GaugeWidget,
        'led': LedWidget,
        'vario': VarioWidget,
        'compass': CompassWidget,
    }

    widget_class = widgets.get(widget_type.lower())
    if widget_class:
        return widget_class(config, parent)
    return None
