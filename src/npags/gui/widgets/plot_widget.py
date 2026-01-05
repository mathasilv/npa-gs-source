# src/npags/gui/widgets/plot_widget.py
"""
Widget de gráfico interativo com crosshair, tooltip e exportação.

Features:
    - Crosshair que segue o mouse
    - Tooltip com valor do ponto
    - Clique para fixar ponto (pin)
    - Clique direito para copiar valor
    - Zoom com scroll
    - Exportação para CSV
    - Botões de controle integrados

Exemplo de uso:
    >>> from npags.gui.widgets import PlotWidget
    >>>
    >>> plot = PlotWidget(
    ...     field_name='temperature',
    ...     config={'unit': '°C', 'plot_color': '#FF5555'}
    ... )
    >>> plot.set_data([23.5, 24.0, 24.5, 25.0])
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import Any

import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QFrame, QMessageBox, QVBoxLayout, QWidget

from npags.gui.styles import THEME_COLORS


class PlotWidget(QWidget):
    """
    Widget de gráfico com crosshair interativo e controles.

    Attributes:
        field_name: Nome do campo sendo plotado.
        config: Configuração do campo (unit, format, plot_color, etc).
        data: Lista de valores plotados.

    Signals:
        time_cursor_changed: Emitido quando o cursor temporal muda (index, timestamp).
    """

    # Sinal para sincronização temporal entre gráficos (padrão Qt)
    time_cursor_changed = pyqtSignal(int, object)  # (index, timestamp)

    def __init__(
        self,
        field_name: str,
        config: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        """
        Inicializa o widget de gráfico.

        Args:
            field_name: Nome do campo.
            config: Configuração com unit, format, plot_color, etc.
            parent: Widget pai.
        """
        super().__init__(parent)
        self.field_name = field_name
        self.config = config
        self.data: list[float] = []
        self.timestamps: list[datetime] = []  # Timestamps correspondentes aos dados

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configura a interface do widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Gráfico principal
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.getPlotItem().hideButtons()
        self.plot_widget.getPlotItem().getViewBox().setBorder(None)
        self.plot_widget.setFrameShape(QFrame.Shape.NoFrame)

        # Cor da linha
        color = self.config.get('plot_color', THEME_COLORS['accent'])
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color=color, width=2))

        # Configura crosshair
        self._setup_crosshair(color)

        # Configura zoom
        self._setup_zoom()

        layout.addWidget(self.plot_widget)

    def _setup_crosshair(self, color: str) -> None:
        """Configura o crosshair e tooltip."""
        pw = self.plot_widget

        # Linhas do crosshair
        self.vLine = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen(color='#888', width=1, style=Qt.PenStyle.DashLine)
        )
        self.hLine = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen(color='#888888', width=1, style=Qt.PenStyle.DashLine)
        )
        pw.addItem(self.vLine, ignoreBounds=True)
        pw.addItem(self.hLine, ignoreBounds=True)

        # Label para valor hover (com fundo para melhor visibilidade)
        self.value_label = pg.TextItem(
            color=THEME_COLORS['text'],
            anchor=(0, 1),
            fill=pg.mkBrush(THEME_COLORS['surface_secondary'] + 'E0'),  # Fundo semi-transparente
            border=pg.mkPen(THEME_COLORS['border_subtle'], width=1)
        )
        self.value_label.setFont(self.font())
        pw.addItem(self.value_label, ignoreBounds=True)
        self.value_label.hide()

        # Scatter para highlight do ponto (hover)
        self.scatter = pg.ScatterPlotItem(
            size=10,
            pen=pg.mkPen(color='white', width=2),
            brush=pg.mkBrush(color)
        )
        pw.addItem(self.scatter)

        # Label e scatter para ponto fixado (pinned)
        self.pinned_label = pg.TextItem(
            color='#ffcc00',
            anchor=(0, 0),
            fill=pg.mkBrush(THEME_COLORS['surface_secondary'] + 'E0'),
            border=pg.mkPen('#ffcc00', width=1)
        )
        self.pinned_label.setFont(self.font())
        pw.addItem(self.pinned_label, ignoreBounds=True)
        self.pinned_label.hide()

        self.pinned_scatter = pg.ScatterPlotItem(
            size=12,
            pen=pg.mkPen(color='#ffcc00', width=2),
            brush=pg.mkBrush('#ffcc00')
        )
        pw.addItem(self.pinned_scatter)

        self.pinned_data: dict[str, Any] | None = None

        # Conecta eventos
        self.mouse_proxy = pg.SignalProxy(
            pw.scene().sigMouseMoved,
            rateLimit=60,
            slot=self._on_mouse_moved
        )
        # Clique simples desabilitado para nao conflitar com arrastar e menu
        # Usar duplo clique para selecionar ponto



    def _setup_zoom(self) -> None:
        """Configura zoom e pan."""
        vb = self.plot_widget.getViewBox()

        # Habilita interacao com mouse
        vb.setMouseEnabled(x=True, y=True)
        self.plot_widget.setMouseEnabled(x=True, y=True)

        # PanMode: botao esquerdo arrasta, scroll faz zoom
        vb.setMouseMode(pg.ViewBox.PanMode)

        # Mantem auto-range inicial mas permite zoom manual
        vb.enableAutoRange(axis='xy', enable=True)

        # Adiciona opcoes customizadas ao menu de contexto
        self._setup_context_menu(vb)

    def _setup_context_menu(self, vb) -> None:
        """Configura menu de contexto com opcoes customizadas."""
        if vb.menu is None:
            return

        # Adiciona separador e opcoes customizadas
        vb.menu.addSeparator()

        # Reset Zoom
        reset_action = vb.menu.addAction("Reset Zoom")
        reset_action.triggered.connect(self._reset_zoom)

        # Limpar Selecao
        clear_action = vb.menu.addAction("Limpar Selecao")
        clear_action.triggered.connect(self._clear_pin)

    def _on_mouse_moved(self, evt: tuple) -> None:
        """Handler para movimento do mouse."""
        try:
            pos = evt[0]
            pw = self.plot_widget

            if pw.sceneBoundingRect().contains(pos):
                mouse_point = pw.getPlotItem().vb.mapSceneToView(pos)
                x_val = mouse_point.x()
                y_val = mouse_point.y()

                # Atualiza crosshair
                self.vLine.setPos(x_val)
                self.hLine.setPos(y_val)
                self.vLine.show()
                self.hLine.show()

                # Encontra ponto mais próximo
                if self.data:
                    idx = max(0, min(int(round(x_val)), len(self.data) - 1))
                    actual_y = self.data[idx]

                    # Formata valor
                    unit = self.config.get('unit', '')
                    format_str = self.config.get('format', '{:.2f}')
                    try:
                        formatted = format_str.format(actual_y)
                    except (ValueError, KeyError):
                        formatted = f"{actual_y:.2f}"

                    # Monta texto da tooltip com timestamp se disponível
                    tooltip_lines = [f"Pacote #{idx + 1}"]

                    # Adiciona timestamp se disponível
                    if idx < len(self.timestamps) and self.timestamps[idx]:
                        ts = self.timestamps[idx]
                        tooltip_lines.append(f"Hora: {ts.strftime('%H:%M:%S')}")

                    tooltip_lines.append(f"{formatted} {unit}".strip())

                    self.value_label.setText("\n".join(tooltip_lines))
                    self.value_label.setPos(x_val, actual_y)
                    self.value_label.show()
                    self.scatter.setData([idx], [actual_y])
                else:
                    self.value_label.hide()
                    self.scatter.setData([], [])
            else:
                self._hide_crosshair()
        except (RuntimeError, KeyError):
            pass  # Erro de formatação/runtime ignorado

    def _hide_crosshair(self) -> None:
        """Esconde o crosshair."""
        self.vLine.hide()
        self.hLine.hide()
        self.value_label.hide()
        self.scatter.setData([], [])

    def _clear_pin(self) -> None:
        """Remove o ponto fixado."""
        self.pinned_data = None
        self.pinned_scatter.setData([], [])
        self.pinned_label.hide()

    def _reset_zoom(self) -> None:
        """Reseta o zoom para auto-range."""
        self.plot_widget.autoRange()

    def _export_csv(self) -> None:
        """Exporta dados para CSV."""
        if not self.data:
            QMessageBox.warning(self, "Exportar CSV", "Não há dados para exportar.")
            return

        unit = self.config.get('unit', '')
        description = self.config.get('description', self.field_name)

        default_name = f"{self.field_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Dados do Gráfico",
            default_name,
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        if not file_path.endswith('.csv'):
            file_path += '.csv'

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['# Campo:', description])
                writer.writerow(['# Unidade:', unit])
                writer.writerow(['# Exportado em:', datetime.now().isoformat()])
                writer.writerow(['# Total de pontos:', len(self.data)])
                writer.writerow([])
                writer.writerow(['Índice', f'{self.field_name} ({unit})' if unit else self.field_name])

                for i, value in enumerate(self.data):
                    writer.writerow([i, value])

            QMessageBox.information(
                self,
                "Exportar CSV",
                f"Dados exportados com sucesso!\n\nArquivo: {file_path}\nTotal: {len(self.data)} pontos"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Exportar", f"Falha ao exportar dados:\n{str(e)}")

    def set_data(self, data: list[float], timestamps: list[datetime] | None = None) -> None:
        """
        Define os dados do gráfico.

        Args:
            data: Lista de valores a plotar.
            timestamps: Lista de timestamps correspondentes (opcional).
        """
        self.data = data
        self.timestamps = timestamps if timestamps else []
        self.curve.setData(data)

        self._hide_crosshair()

    def clear(self) -> None:
        """Limpa os dados do gráfico."""
        self.data = []
        self.timestamps = []
        self.curve.setData([])
        self._hide_crosshair()
        self._clear_pin()

    def set_time_cursor(self, index: int, emit_signal: bool = False) -> None:
        """
        Define a posição do cursor temporal (sincronização entre gráficos).

        Args:
            index: Índice do ponto a destacar.
            emit_signal: Se True, emite o sinal (evitar loops).
        """
        if not self.data or index < 0 or index >= len(self.data):
            return

        actual_y = self.data[index]
        unit = self.config.get('unit', '')
        format_str = self.config.get('format', '{:.2f}')

        try:
            formatted = format_str.format(actual_y)
        except (ValueError, KeyError):
            formatted = f"{actual_y:.2f}"

        # Atualiza visual do ponto fixado
        self.pinned_data = {
            'idx': index,
            'value': actual_y,
            'formatted': formatted,
            'unit': unit
        }
        self.pinned_scatter.setData([index], [actual_y])
        self.pinned_label.setText(f"#{index + 1}\n{formatted} {unit}")
        self.pinned_label.setPos(index, actual_y)
        self.pinned_label.show()

        # Move crosshair vertical para a posição
        self.vLine.setPos(index)
        self.vLine.show()

        if emit_signal:
            timestamp = self.timestamps[index] if index < len(self.timestamps) else None
            self.time_cursor_changed.emit(index, timestamp)

    def clear_time_cursor(self) -> None:
        """Remove o cursor temporal."""
        self._clear_pin()

    def mouseDoubleClickEvent(self, event) -> None:
        """
        Captura duplo clique para selecionar ponto temporal.
        Duplo clique funciona melhor dentro de QGraphicsProxyWidget.
        """
        # Mapeia posicao do clique para coordenadas do grafico
        pos = event.pos()

        # Verifica se o clique foi dentro do plot
        plot_geometry = self.plot_widget.geometry()
        if not plot_geometry.contains(pos):
            super().mouseDoubleClickEvent(event)
            return

        if not self.data:
            super().mouseDoubleClickEvent(event)
            return

        # Converte posicao do widget para posicao da cena do plot
        scene_pos = self.plot_widget.mapToScene(pos - self.plot_widget.pos())
        view_pos = self.plot_widget.getPlotItem().vb.mapSceneToView(scene_pos)

        x_val = view_pos.x()
        idx = max(0, min(int(round(x_val)), len(self.data) - 1))
        actual_y = self.data[idx]

        unit = self.config.get('unit', '')
        format_str = self.config.get('format', '{:.2f}')
        try:
            formatted = format_str.format(actual_y)
        except (ValueError, KeyError):
            formatted = f"{actual_y:.2f}"

        # Fixa o ponto
        self.pinned_data = {
            'idx': idx,
            'value': actual_y,
            'formatted': formatted,
            'unit': unit
        }
        self.pinned_scatter.setData([idx], [actual_y])
        self.pinned_label.setText(f"#{idx + 1}\n{formatted} {unit}")
        self.pinned_label.setPos(idx, actual_y)
        self.pinned_label.show()

        # Emite sinal para sincronizacao temporal
        timestamp = self.timestamps[idx] if idx < len(self.timestamps) else None
        self.time_cursor_changed.emit(idx, timestamp)

        event.accept()

    def cleanup(self) -> None:
        """Limpa recursos."""
        try:
            self.mouse_proxy.disconnect()
        except Exception:
            pass  # Erro de formatação/runtime ignorado
