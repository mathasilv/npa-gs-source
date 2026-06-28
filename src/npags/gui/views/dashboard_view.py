# src/npags/gui/views/dashboard_view.py
"""
View principal do Dashboard de telemetria.

Controlador que gerencia widgets de visualização de dados em tempo real.
Os widgets individuais foram extraídos para npags.gui.widgets.

Responsabilidades:
    - Gerenciar layout dos widgets na cena
    - Receber e distribuir dados para os widgets
    - Salvar/restaurar layouts
    - Filtrar por nó (multi-dispositivo)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QPushButton, QGraphicsView, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QSettings, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QShowEvent, QHideEvent

from npags.gui.styles import THEME_COLORS
from npags.gui.widgets import (
    MapWidget, PlotWidget, 
    CardWidget, GaugeWidget, LedWidget, VarioWidget, CompassWidget,
    SmartDashboardItem, BlueprintScene,
    AlertEngine, AlertNotificationManager
)
from npags.gui.dialogs import HistoryFilterDialog, ExportDialog, AlertConfigDialog, ReportDialog
from npags.core.decoder_engine import DecoderEngine
from npags.core.logger import get_current_log_path, get_log_directory
from npags.decoders.loader import DecoderLoader
from npags.gui.translations import tr
from npags.gui.views.dashboard import DashboardDataManager, DashboardLayoutManager


class HistoryLoaderWorker(QObject):
    """
    Worker para carregar dados históricos em background.
    Evita que a UI trave durante o carregamento de grandes volumes de dados.
    """
    progress = pyqtSignal(int, int)  # (current, total)
    data_loaded = pyqtSignal(dict, object)  # (data, timestamp)
    finished = pyqtSignal(int)  # total_count
    error = pyqtSignal(str)
    
    def __init__(self, path: Path, filters: Dict[str, Any]):
        super().__init__()
        self.path = path
        self.filters = filters
        self._is_cancelled = False
    
    def cancel(self):
        """Cancela o carregamento."""
        self._is_cancelled = True
    
    def run(self):
        """Executa o carregamento em background."""
        raw_limit = self.filters['limit']
        # Usa 0 como sentinela de "sem limite" para evitar int(float('inf'))
        has_limit = raw_limit > 0
        count = 0
        
        try:
            # Primeiro, conta o total de linhas para progresso
            total_lines = 0
            with open(self.path, 'r', encoding='utf-8') as f:
                for _ in f:
                    total_lines += 1
            
            progress_total = raw_limit if has_limit else total_lines
            
            # Agora processa os dados
            with open(self.path, 'r', encoding='utf-8') as f:
                for line in f:
                    if self._is_cancelled:
                        break
                    
                    try:
                        record = json.loads(line)
                        dt = None
                        if 'ts' in record:
                            dt = datetime.fromisoformat(record['ts'])
                            if dt < self.filters['start'] or dt > self.filters['end']:
                                continue
                        
                        if 'data' in record:
                            self.data_loaded.emit(record['data'], dt)
                            count += 1
                            
                            # Emite progresso a cada 100 registros
                            if count % 100 == 0:
                                self.progress.emit(count, progress_total)
                            
                            if has_limit and count >= raw_limit:
                                break
                    except Exception:
                        continue
            
            self.finished.emit(count)
            
        except Exception as e:
            self.error.emit(str(e))


class DashboardView(QWidget):
    """
    Controlador da Dashboard Multi-Nó.
    
    Attributes:
        data_buffer: Buffer de dados por nó.
        known_nodes: Conjunto de nós conhecidos.
        current_node_filter: Filtro de nó atual.
        widgets_data: Mapeamento campo -> widget.
    """
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None, 
        on_back: Optional[Callable[[], None]] = None
    ) -> None:
        super().__init__(parent)
        self.on_back = on_back
        
        # Configurações
        self.default_history_limit = 1000
        
        # Gerenciadores extraídos
        self._data_manager = DashboardDataManager(history_limit=self.default_history_limit)
        self._layout_manager = DashboardLayoutManager()
        
        # Estado (referências para compatibilidade)
        self.id_field_name: Optional[str] = None
        
        # Timer de heartbeat
        self.rx_timer = QTimer()
        self.rx_timer.timeout.connect(self._update_rx_heartbeat)
        
        # Engine e widgets
        self.last_engine: Optional[DecoderEngine] = None
        self.items_map: Dict[str, SmartDashboardItem] = {}
        self.widgets_data: Dict[str, Dict[str, Any]] = {}
        
        # Thread de carregamento
        self._loader_thread: Optional[QThread] = None
        self._loader_worker: Optional[HistoryLoaderWorker] = None
        
        # Sistema de alertas
        self.alert_engine = AlertEngine(self)
        self.alert_engine.alert_triggered.connect(self._on_alert_triggered)
        self.alert_engine.alert_cleared.connect(self._on_alert_cleared)
        
        self._setup_ui()

    def showEvent(self, event: QShowEvent) -> None:
        if not self.rx_timer.isActive():
            self.rx_timer.start(1000)
            self._update_rx_heartbeat()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        if self.rx_timer.isActive():
            self.rx_timer.stop()
        super().hideEvent(event)

    def _setup_ui(self) -> None:
        """Configura a interface do dashboard."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        main_layout.addWidget(self._create_header())
        
        # Viewport (cena de widgets)
        self.scene = BlueprintScene()
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.view)
        
        # Gerenciador de notificações (pop-ups no canto superior direito)
        self.notification_manager = AlertNotificationManager(self)

    def _create_header(self) -> QFrame:
        """Cria o cabeçalho do dashboard."""
        header = QFrame()
        header.setObjectName("DashboardHeader")
        header.setFixedHeight(60)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)
        
        # Botão Voltar
        btn_back = QPushButton(tr("Voltar"))
        btn_back.setFixedSize(80, 34)
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setProperty("class", "secondary")
        btn_back.clicked.connect(self._on_back_pressed)
        layout.addWidget(btn_back)
        
        layout.addWidget(self._create_separator())
        
        # Título
        self.lbl_title = QLabel(tr("Dashboard"))
        self.lbl_title.setStyleSheet(f"font-size: 14px; color: {THEME_COLORS['text']};")
        layout.addWidget(self.lbl_title)
        
        # Status
        self.lbl_last_rx = QLabel(tr("Aguardando dados..."))
        self.lbl_last_rx.setStyleSheet(
            f"color: {THEME_COLORS['text_dim']}; font-size: 12px; margin-left: 10px;"
        )
        layout.addWidget(self.lbl_last_rx)
        
        layout.addStretch()
        
        # Botões de controle
        btn_hist = QPushButton(tr("Filtro / Histórico"))
        btn_hist.setFixedSize(140, 34)
        btn_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_hist.setProperty("class", "secondary")
        btn_hist.clicked.connect(self._open_history_dialog)
        layout.addWidget(btn_hist)
        
        btn_save = QPushButton(tr("Salvar Layout"))
        btn_save.setFixedSize(120, 34)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setProperty("class", "secondary")
        btn_save.clicked.connect(self._save_layout)
        layout.addWidget(btn_save)
        
        btn_export = QPushButton(tr("Exportar"))
        btn_export.setFixedSize(100, 34)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setProperty("class", "secondary")
        btn_export.clicked.connect(self._open_export_dialog)
        layout.addWidget(btn_export)
        
        # Botão Relatório
        btn_report = QPushButton(tr("Relatório"))
        btn_report.setFixedSize(100, 34)
        btn_report.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_report.setProperty("class", "secondary")
        btn_report.clicked.connect(self._open_report_dialog)
        layout.addWidget(btn_report)
        
        # Botão Alertas
        self.btn_alerts = QPushButton(tr("Alertas"))
        self.btn_alerts.setFixedSize(100, 34)
        self.btn_alerts.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_alerts.setProperty("class", "secondary")
        self.btn_alerts.clicked.connect(self._open_alerts_config)
        layout.addWidget(self.btn_alerts)
        
        return header

    def _create_separator(self) -> QFrame:
        """Cria uma linha separadora vertical."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedWidth(1)
        line.setFixedHeight(24)
        line.setStyleSheet(
            f"background-color: {THEME_COLORS['border_subtle']}; border: none;"
        )
        return line

    def _update_rx_heartbeat(self) -> None:
        """Atualiza o indicador de último dado recebido."""
        # Sempre usa o timestamp do satélite
        target_time = self.node_timestamps.get("_satellite")

        if target_time is None:
            self.lbl_last_rx.setText(tr("Aguardando dados..."))
            return

        delta = int((datetime.now() - target_time).total_seconds())
        if delta < 0:
            delta = 0
        
        node_count = len([n for n in self.known_nodes if n != "_satellite"])
        suffix = f" | {node_count} nós" if node_count > 0 else ""
        if self.current_node_filter != "Todos":
            suffix = f" | Filtro: {self.current_node_filter}"
        
        self.lbl_last_rx.setText(f"{tr('Último dado:')} {delta}s {suffix}")

    # =========================================================================
    # GERENCIAMENTO DE DADOS
    # =========================================================================

    # =========================================================================
    # PROPRIEDADES DE COMPATIBILIDADE (delegam para _data_manager)
    # =========================================================================
    
    @property
    def data_buffer(self) -> Dict[str, Dict[str, List[Any]]]:
        return self._data_manager.data_buffer
    
    @property
    def timestamp_buffer(self) -> Dict[str, Dict[str, List[datetime]]]:
        return self._data_manager.timestamp_buffer
    
    @property
    def known_nodes(self) -> set:
        return self._data_manager.known_nodes
    
    @property
    def node_timestamps(self) -> Dict[str, datetime]:
        return self._data_manager.node_timestamps
    
    @property
    def current_node_filter(self) -> str:
        return self._data_manager.current_node_filter
    
    @current_node_filter.setter
    def current_node_filter(self, value: str) -> None:
        self._data_manager.current_node_filter = value
    
    @property
    def history_limit(self) -> int:
        return self._data_manager.history_limit
    
    @history_limit.setter
    def history_limit(self, value: int) -> None:
        self._data_manager.history_limit = value

    # =========================================================================
    # GERENCIAMENTO DE DADOS
    # =========================================================================

    def update_data(
        self, 
        data: Dict[str, Any], 
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Atualiza o dashboard com novos dados.
        
        Args:
            data: Dicionário com dados decodificados.
            timestamp: Timestamp do pacote (opcional).
        """
        # Delega para o data_manager
        self._data_manager.process_packet(data, timestamp)
        
        self._update_rx_heartbeat()
        self._refresh_widgets()
        
        # Verifica alertas
        self._check_alerts(data)
    
    def _refresh_widgets(self) -> None:
        """Atualiza todos os widgets com os dados do buffer."""
        target_data, target_timestamps = self._get_target_data()
        
        for field_name, widget_pkg in self.widgets_data.items():
            widget_type = widget_pkg['type']
            
            if widget_type == 'node_selector':
                # Atualiza o texto do botão com contagem de nós
                node_count = len(self.known_nodes)
                if self.current_node_filter == "Todos":
                    if node_count > 0:
                        widget_pkg['widget'].setText(f" {tr('Todos')} ({node_count} {tr('nós')}) ▼")
                    else:
                        widget_pkg['widget'].setText(f" {tr('Aguardando nós...')} ▼")
                else:
                    widget_pkg['widget'].setText(f" {self.current_node_filter} ▼")
                continue
            
            if widget_type == 'map':
                widget_pkg['widget'].update_from_buffer(target_data, force_update=True)
            
            elif widget_type == 'plot':
                data_list = target_data.get(field_name, [])
                ts_list = target_timestamps.get(field_name, [])
                widget_pkg['widget'].set_data(data_list, ts_list)
            
            elif widget_type in ['card', 'gauge', 'led', 'vario', 'compass']:
                last_key = f"{field_name}_last"
                if last_key in target_data:
                    widget_pkg['widget'].set_value(target_data[last_key])
                else:
                    widget_pkg['widget'].reset()

    def _get_target_data(self) -> tuple[Dict[str, Any], Dict[str, List[datetime]]]:
        """
        Obtém os dados combinados: satélite + nó selecionado.
        
        Returns:
            Tupla (dados, timestamps)
        """
        return self._data_manager.get_combined_data()

    # =========================================================================
    # CONSTRUÇÃO DA UI
    # =========================================================================

    def build_ui(self, engine: Optional[DecoderEngine], keep_data: bool = False) -> None:
        """
        Constrói a interface baseada no engine de decodificação.
        
        Args:
            engine: DecoderEngine com o schema carregado.
            keep_data: Se True, mantém os dados existentes.
        """
        # Limpa recursos antigos
        self._cleanup_widgets()
        
        self.last_engine = engine
        self.scene.clear()
        self.items_map.clear()
        self.widgets_data.clear()
        
        if not keep_data:
            self._clear_all_buffers()
        
        if not engine:
            return
        
        self.lbl_title.setText(f"{tr('Missão:')} {engine.config.get('name', 'Analys')}")
        
        # Detecta campo identificador
        self.id_field_name = None
        for name, cfg in engine.field_cache.items():
            if cfg.get('role') == 'identifier':
                self.id_field_name = name
                break
        
        # Cria widgets para cada campo
        for field_name, config in engine.field_cache.items():
            widget_type = config.get('widget', 'none').lower()
            if widget_type == 'none':
                continue
            
            widget_container = self._create_widget(widget_type, field_name, config)
            if widget_container:
                proxy = SmartDashboardItem(widget_container['frame'], field_name)
                self.scene.addItem(proxy)
                self.items_map[field_name] = proxy
                self.widgets_data[field_name] = widget_container
        
        # Restaura ou aplica layout
        if not self._restore_layout(engine.config.get('name')):
            self._apply_default_layout()
        
        self.view.ensureVisible(0, 0, 100, 100)

    def build_ui_multi(self, decoders: list, keep_data: bool = False) -> None:
        """
        Constrói a interface para múltiplos decoders (Multi-Decoder mode).
        Combina os field_cache de todos os decoders.
        
        Args:
            decoders: Lista de DecoderEngine carregados.
            keep_data: Se True, mantém os dados existentes.
        """
        # Limpa recursos antigos
        self._cleanup_widgets()
        
        self.scene.clear()
        self.items_map.clear()
        self.widgets_data.clear()
        
        if not keep_data:
            self._clear_all_buffers()
        
        if not decoders:
            return
        
        # Usa o primeiro decoder como referência principal
        self.last_engine = decoders[0] if decoders else None
        
        # Combina nomes dos decoders para o título
        decoder_names = [d.config.get('name', 'Unknown') for d in decoders]
        self.lbl_title.setText(f"{tr('Missão:')} {' + '.join(decoder_names)}")
        
        # Combina field_cache de todos os decoders
        combined_cache = {}
        for decoder in decoders:
            if hasattr(decoder, 'field_cache'):
                for field_name, config in decoder.field_cache.items():
                    # Se o campo já existe, não sobrescreve (prioridade ao primeiro)
                    if field_name not in combined_cache:
                        combined_cache[field_name] = config
        
        # Detecta campo identificador
        self.id_field_name = None
        for name, cfg in combined_cache.items():
            if cfg.get('role') == 'identifier':
                self.id_field_name = name
                break
        
        # Cria widgets para cada campo combinado
        for field_name, config in combined_cache.items():
            widget_type = config.get('widget', 'none').lower()
            if widget_type == 'none':
                continue
            
            widget_container = self._create_widget(widget_type, field_name, config)
            if widget_container:
                proxy = SmartDashboardItem(widget_container['frame'], field_name)
                self.scene.addItem(proxy)
                self.items_map[field_name] = proxy
                self.widgets_data[field_name] = widget_container
        
        # Tenta restaurar layout salvo, senão aplica padrão
        # Para multi-decoder, usa o nome do primeiro decoder como chave
        layout_name = decoders[0].config.get('name') if decoders else None
        if not self._restore_layout(layout_name):
            self._apply_default_layout()
        
        self.view.ensureVisible(0, 0, 100, 100)


    def _create_widget(
        self, 
        widget_type: str, 
        field_name: str, 
        config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Cria um widget baseado no tipo."""
        frame = QFrame()
        frame.setObjectName("DashboardFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Título
        title_lbl = QLabel(f"  {config.get('description', field_name).upper()}")
        title_lbl.setFixedHeight(25)
        title_lbl.setStyleSheet(f"""
            background: {THEME_COLORS['surface_tertiary']};
            color: {THEME_COLORS['text_dim']};
            font-size: 10px;
            font-weight: bold;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        """)
        layout.addWidget(title_lbl)
        
        # Área de conteúdo
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 5, 10, 5)
        layout.addWidget(content)
        
        result = {'frame': frame, 'type': widget_type, 'config': config}
        
        # Cria widget específico
        if widget_type == 'node_selector':
            # Texto inicial baseado no estado atual
            if self.known_nodes:
                initial_text = f" {self.current_node_filter} ({len(self.known_nodes)} {tr('nós')}) ▼"
            else:
                initial_text = f" {tr('Aguardando nós...')} ▼"
            btn = QPushButton(initial_text)
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "secondary")
            btn.clicked.connect(lambda: self._open_node_menu(btn))
            content_layout.addWidget(btn)
            result['widget'] = btn
            frame.resize(200, 80)
        
        elif widget_type == 'plot':
            plot = PlotWidget(field_name, config)
            # Conecta sinal para sincronização temporal (estilo Grafana)
            plot.time_cursor_changed.connect(self._on_time_cursor_changed)
            content_layout.addWidget(plot)
            result['widget'] = plot
            frame.resize(400, 320)
        
        elif widget_type == 'map':
            lat_source = config.get('lat_source', 'latitude')
            lon_source = config.get('lon_source', 'longitude')
            map_widget = MapWidget(lat_key=lat_source, lon_key=lon_source)
            content_layout.addWidget(map_widget)
            result['widget'] = map_widget
            frame.resize(500, 400)
        
        elif widget_type == 'card':
            widget = CardWidget(config)
            content_layout.addWidget(widget)
            result['widget'] = widget
            frame.resize(220, 100)
        
        elif widget_type == 'gauge':
            widget = GaugeWidget(config)
            content_layout.addWidget(widget)
            result['widget'] = widget
            frame.resize(220, 100)
        
        elif widget_type == 'led':
            widget = LedWidget(config)
            content_layout.addWidget(widget)
            result['widget'] = widget
            frame.resize(220, 100)
        
        elif widget_type == 'vario':
            widget = VarioWidget(config)
            content_layout.addWidget(widget)
            result['widget'] = widget
            frame.resize(120, 150)
        
        elif widget_type == 'compass':
            widget = CompassWidget(config)
            content_layout.addWidget(widget)
            result['widget'] = widget
            frame.resize(150, 150)
        
        else:
            return None
        
        return result

    def _cleanup_widgets(self) -> None:
        """Limpa recursos dos widgets."""
        for widget_pkg in self.widgets_data.values():
            widget = widget_pkg.get('widget')
            if widget and hasattr(widget, 'cleanup'):
                try:
                    widget.cleanup()
                except Exception:
                    pass  # Erro de cleanup ignorado

    # =========================================================================
    # FILTRO DE NÓS
    # =========================================================================

    def _open_node_menu(self, btn_sender: QPushButton) -> None:
        """Abre menu de seleção de nó."""
        menu = QMenu(self)
        action_all = menu.addAction(tr("Todos"))
        action_all.triggered.connect(lambda: self._on_node_filter_change("Todos"))
        menu.addSeparator()
        
        if not self.known_nodes:
            menu.addAction(tr("Nenhum nó detectado")).setEnabled(False)
        else:
            for node in sorted(list(self.known_nodes)):
                action = menu.addAction(str(node))
                action.triggered.connect(
                    lambda checked, n=node: self._on_node_filter_change(n)
                )
        
        menu.exec(btn_sender.mapToGlobal(btn_sender.rect().bottomLeft()))

    def _on_time_cursor_changed(self, index: int, timestamp: object) -> None:
        """
        Handler para sincronização temporal entre gráficos (estilo Grafana).
        
        Quando um ponto é clicado em qualquer gráfico, todos os outros
        gráficos e widgets são atualizados para mostrar o valor daquele
        momento específico.
        
        Args:
            index: Índice do ponto clicado.
            timestamp: Timestamp do ponto (datetime ou None).
        """
        # Atualiza todos os plots para mostrar o mesmo índice
        for field_name, widget_pkg in self.widgets_data.items():
            widget_type = widget_pkg['type']
            widget = widget_pkg.get('widget')
            
            if widget_type == 'plot' and widget:
                # Atualiza cursor em todos os plots (sem emitir sinal para evitar loop)
                widget.set_time_cursor(index, emit_signal=False)
            
            elif widget_type in ['card', 'gauge', 'led'] and widget:
                # Atualiza widgets de valor único com o dado do índice específico
                target_data, _ = self._get_target_data()
                data_list = target_data.get(field_name, [])
                
                if isinstance(data_list, list) and 0 <= index < len(data_list):
                    widget.set_value(data_list[index])
        
        # Atualiza label de status com informação do ponto selecionado
        if timestamp:
            self.lbl_last_rx.setText(f"Ponto #{index + 1} - {timestamp.strftime('%H:%M:%S')}")
        else:
            self.lbl_last_rx.setText(f"Ponto #{index + 1}")
        
    def _on_node_filter_change(self, text: str) -> None:
        """Handler para mudança de filtro de nó."""
        if not text:
            return
        
        self.current_node_filter = text
        
        # Atualiza botões de seletor
        for widget_pkg in self.widgets_data.values():
            if widget_pkg['type'] == 'node_selector':
                widget_pkg['widget'].setText(f" {text} ▼")
        
        self._update_rx_heartbeat()
        self._refresh_widgets()

    # =========================================================================
    # LAYOUT
    # =========================================================================

    def _save_layout(self) -> None:
        """Salva o layout atual."""
        if not self.last_engine:
            return
        
        name = self.last_engine.config.get('name', 'default')
        self._layout_manager.save_layout(name, self.items_map)

    def _restore_layout(self, name: Optional[str]) -> bool:
        """Restaura um layout salvo."""
        return self._layout_manager.restore_layout(name, self.items_map)

    def _apply_default_layout(self) -> None:
        """Aplica layout padrão em cascata."""
        self._layout_manager.apply_default_layout(self.items_map)



    # =========================================================================
    # HISTÓRICO
    # =========================================================================

    def _get_log_path(self) -> Path:
        """Retorna o caminho do arquivo de log."""
        central_path = get_current_log_path()
        if central_path and central_path.exists():
            return central_path
        
        log_dir = get_log_directory()
        return log_dir / "station_data.jsonl"

    def _open_export_dialog(self) -> None:
        """Abre diálogo avançado de exportação (independente)."""
        dialog = ExportDialog(parent=self)
        dialog.exec()
    
    
    def _open_report_dialog(self) -> None:
        """Abre diálogo de geração de relatório de missão."""
        dialog = ReportDialog(parent=self)
        dialog.exec()

    def _open_history_dialog(self) -> None:
        """Abre dialogo de filtro de historico."""
        log_path = self._get_log_path()
        curr_schema = self.last_engine.config.get('name') if self.last_engine else None
        
        dialog = HistoryFilterDialog(self, current_schema=curr_schema)
        if dialog.exec() == HistoryFilterDialog.DialogCode.Accepted:
            filters = dialog.get_data()
            
            # Verifica se ha schemas selecionados
            selected_schemas = filters.get('schemas', [])
            
            if not selected_schemas:
                QMessageBox.warning(self, tr("Aviso"), tr("Selecione pelo menos um esquema."))
                return
            
            if filters['clear']:
                self._clear_all_buffers()
            
            # Carrega o primeiro schema selecionado
            schema = selected_schemas[0]
            if not self.last_engine or schema != self.last_engine.config.get('name'):
                self._load_schema_and_build(schema, keep_data=not filters['clear'])
            
            if log_path.exists():
                self._load_history_data(log_path, filters)
            else:
                QMessageBox.warning(
                    self,
                    tr("Arquivo não encontrado"),
                    f"Arquivo de log nao encontrado:\n{log_path}\n\n"
                    "Inicie uma sessao de captura primeiro."
                )


    def _load_history_data(self, path: Path, filters: Dict[str, Any]) -> None:
        """Carrega dados históricos do arquivo de log em background."""
        if not self.last_engine:
            return
        
        if filters['clear']:
            self._clear_all_buffers()
        
        if filters['limit'] > self.history_limit:
            self.history_limit = filters['limit'] + 1000
        
        # Cancela carregamento anterior se existir
        self._cancel_loading()
        
        # Atualiza UI para mostrar que está carregando
        self.lbl_last_rx.setText(tr("Carregando dados..."))
        
        # Cria thread e worker
        self._loader_thread = QThread()
        self._loader_worker = HistoryLoaderWorker(path, filters)
        self._loader_worker.moveToThread(self._loader_thread)
        
        # Conecta sinais (Qt.ConnectionType.QueuedConnection garante execução na main thread)
        self._loader_thread.started.connect(self._loader_worker.run)
        self._loader_worker.data_loaded.connect(
            self._on_history_data_loaded, Qt.ConnectionType.QueuedConnection
        )
        self._loader_worker.progress.connect(
            self._on_loading_progress, Qt.ConnectionType.QueuedConnection
        )
        self._loader_worker.finished.connect(
            self._on_loading_finished, Qt.ConnectionType.QueuedConnection
        )
        self._loader_worker.error.connect(
            self._on_loading_error, Qt.ConnectionType.QueuedConnection
        )
        
        # Inicia carregamento
        self._loader_thread.start()
    
    def _cancel_loading(self) -> None:
        """Cancela o carregamento em andamento."""
        if self._loader_worker:
            self._loader_worker.cancel()
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait(1000)
        self._loader_thread = None
        self._loader_worker = None
    
    def _on_history_data_loaded(self, data: Dict[str, Any], timestamp) -> None:
        """Callback quando um registro é carregado."""
        self.update_data(data, timestamp=timestamp)
    
    def _on_loading_progress(self, current: int, total: int) -> None:
        """Callback de progresso do carregamento."""
        if total > 0:
            percent = int((current / total) * 100)
            self.lbl_last_rx.setText(f"Carregando... {current:,} registros ({percent}%)")
        else:
            self.lbl_last_rx.setText(f"Carregando... {current:,} registros")
    
    def _on_loading_finished(self, count: int) -> None:
        """Callback quando o carregamento termina."""
        # Limpa thread com timeout para evitar bloqueio indefinido
        if self._loader_thread:
            self._loader_thread.quit()
            if not self._loader_thread.wait(3000):  # Timeout de 3s
                self._loader_thread.terminate()
                self._loader_thread.wait(1000)
        self._loader_thread = None
        self._loader_worker = None
        
        # Atualiza UI
        self._update_rx_heartbeat()
        
        QMessageBox.information(
            self, tr("Análise Concluída"), 
            tr("Foram carregados %1 pacotes.").replace("%1", f"{count:,}")
        )
    
    def _on_loading_error(self, error_msg: str) -> None:
        """Callback quando ocorre erro no carregamento."""
        # Limpa thread com timeout para evitar bloqueio indefinido
        if self._loader_thread:
            self._loader_thread.quit()
            if not self._loader_thread.wait(3000):  # Timeout de 3s
                self._loader_thread.terminate()
                self._loader_thread.wait(1000)
        self._loader_thread = None
        self._loader_worker = None
        
        self.lbl_last_rx.setText(tr("Erro ao carregar dados"))
        QMessageBox.critical(
            self, tr("Erro"),
            f"{tr('Erro ao carregar histórico:')}\n{error_msg}"
        )

    def _load_schema_and_build(self, schema_name: str, keep_data: bool = False) -> None:
        """Carrega um schema e reconstrói a UI."""
        try:
            loader = DecoderLoader()
            path = loader.find_decoder_path(schema_name)
            if path is None:
                QMessageBox.critical(
                    self, tr("Erro"),
                    f"{tr('Falha ao carregar schema:')} arquivo '{schema_name}' não encontrado."
                )
                return
            # Instancia diretamente pelo path — evita double-open do YAML
            engine = DecoderEngine(path)
            self.build_ui(engine, keep_data=keep_data)
        except Exception as e:
            logging.getLogger(__name__).error("Erro fatal build_ui: %s", e)
            QMessageBox.critical(self, tr("Erro"), f"{tr('Falha ao carregar schema:')} {e}")



    def _clear_all_buffers(self) -> None:
        """Limpa todos os buffers de dados."""
        self._data_manager.clear()
        self.lbl_last_rx.setText(tr("Aguardando dados..."))
        
        for widget_pkg in self.widgets_data.values():
            if widget_pkg['type'] == 'node_selector':
                widget_pkg['widget'].setText(f" {tr('Todos')} ▼")
        
        # Limpa alertas ativos
        self.alert_engine.clear_all()
        self.notification_manager.clear_all()
        self._update_alerts_button()
        
        self._refresh_widgets()

    # =========================================================================
    # SISTEMA DE ALERTAS
    # =========================================================================
    
    def _check_alerts(self, data: Dict[str, Any]) -> None:
        """
        Verifica dados contra configurações de alerta.
        
        Args:
            data: Dados recebidos
        """
        # Extrai valores flat do dicionário
        flat_data = {}
        
        def extract_values(d: Dict[str, Any], prefix: str = "") -> None:
            for key, value in d.items():
                if isinstance(value, dict):
                    extract_values(value, f"{prefix}{key}_")
                elif isinstance(value, (int, float)):
                    flat_data[f"{prefix}{key}"] = value
                    flat_data[key] = value  # Também sem prefixo
        
        extract_values(data)
        
        # Verifica alertas
        self.alert_engine.check_all_values(flat_data)
    
    def _on_alert_triggered(self, alert) -> None:
        """Handler quando um alerta é disparado - mostra notificação."""
        self.notification_manager.show_alert(alert, auto_close=True, duration=6000)
        self._update_alerts_button()
    
    def _on_alert_cleared(self, field_name: str) -> None:
        """Handler quando um alerta é resolvido."""
        self._update_alerts_button()
    
    def _update_alerts_button(self) -> None:
        """Atualiza o visual do botão de alertas baseado no estado atual."""
        active_count = self.alert_engine.get_active_count()
        
        if active_count > 0:
            # Mantém texto simples, apenas muda a cor para indicar alertas ativos
            self.btn_alerts.setText(tr("Alertas"))
            self.btn_alerts.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME_COLORS['danger']};
                    border: 1px solid {THEME_COLORS['danger']};
                    color: #ffffff;
                }}
                QPushButton:hover {{
                    background-color: {THEME_COLORS['danger_hover']};
                    border-color: {THEME_COLORS['danger_hover']};
                }}
            """)
        else:
            self.btn_alerts.setText(tr("Alertas"))
            self.btn_alerts.setStyleSheet("")  # Volta ao estilo padrão
    
    def _open_alerts_config(self) -> None:
        """Abre diálogo de configuração de alertas."""
        if not self.last_engine:
            QMessageBox.warning(
                self,
                tr("Configurar Alertas"),
                tr("Carregue um decoder primeiro para configurar alertas.")
            )
            return
        
        available_fields = self.last_engine.field_cache
        
        dialog = AlertConfigDialog(
            alert_engine=self.alert_engine,
            available_fields=available_fields,
            parent=self
        )
        dialog.exec()

    # =========================================================================
    # NAVEGAÇÃO
    # =========================================================================

    def _on_back_pressed(self) -> None:
        """Handler para botão voltar."""
        self._cancel_loading()  # Cancela carregamento se estiver em andamento
        self._save_layout()
        self._cleanup_widgets()
        if self.on_back:
            self.on_back()
