# src/npags/gui/dashboard_view.py

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, 
    QCheckBox, QGraphicsView, QProgressBar, QMessageBox, QMenu,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QPainter, QShowEvent, QHideEvent, QColor
import pyqtgraph as pg

# Imports do Core e GUI
from npags.decoders.loader import DecoderLoader
from npags.core.decoder_engine import DecoderEngine 
from npags.gui.canvas_items import BlueprintScene, SmartDashboardItem
from npags.gui.history_dialog import HistoryFilterDialog
from npags.gui.styles import THEME_COLORS 

class DashboardView(QWidget):
    """
    Controlador da Dashboard Multi-Nó.
    Visual limpo: Bordas e cores gerenciadas automaticamente pelo styles.py.
    """
    def __init__(self, parent=None, on_back: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_back = on_back
        
        # Configurações
        self.default_history_limit = 1000 
        self.history_limit = self.default_history_limit
        self.settings = QSettings("NPA_Aerospace", "GroundStation_Dashboard")
        
        self.data_buffer: Dict[str, Dict[str, List[Any]]] = {} 
        self.known_nodes = set()
        self.current_node_filter = "Todos"
        self.id_field_name = None 
        self.node_timestamps: Dict[str, datetime] = {}
        
        self.rx_timer = QTimer()
        self.rx_timer.timeout.connect(self._update_rx_heartbeat)
        
        self.last_engine = None 
        self.items_map = {}       
        self.widgets_data = {}   
        
        # === CONFIGURAÇÃO GLOBAL DOS GRÁFICOS ===
        pg.setConfigOptions(
            antialias=True, 
            background=THEME_COLORS['background'], 
            foreground=THEME_COLORS['text']
        )
        
        self._setup_ui()

    def showEvent(self, event: QShowEvent):
        if not self.rx_timer.isActive():
            self.rx_timer.start(1000)
            self._update_rx_heartbeat()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent):
        if self.rx_timer.isActive():
            self.rx_timer.stop()
        super().hideEvent(event)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- CABEÇALHO (HEADER) ---
        header = QFrame()
        header.setObjectName("DashboardHeader") # Estilo do styles.py
        header.setFixedHeight(60) # Altura confortável
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0) # Margens laterais
        header_layout.setSpacing(12) # Espaçamento consistente
        
        # === BLOCO ESQUERDO: Navegação e Identidade ===
        
        # 1. Botão Voltar
        btn_back = QPushButton("Voltar")
        self._style_secondary_btn(btn_back, 80)
        btn_back.clicked.connect(self._on_back_pressed)
        header_layout.addWidget(btn_back)
        
        # 2. Separador Vertical
        header_layout.addWidget(self._create_separator())
        
        # 3. Título
        self.lbl_title = QLabel("Dashboard")
        # Ajuste de fonte local ou via styles.py
        font = self.lbl_title.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lbl_title.setFont(font)
        header_layout.addWidget(self.lbl_title)
        
        # 4. Status (Heartbeat) - Agora ao lado do título, discreto
        self.lbl_last_rx = QLabel("Aguardando dados...")
        self.lbl_last_rx.setObjectName("HeartbeatLabel")
        self.lbl_last_rx.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 12px; margin-left: 10px;")
        header_layout.addWidget(self.lbl_last_rx)
        
        # === ESPAÇADOR FLEXÍVEL (Empurra ferramentas para a direita) ===
        header_layout.addStretch() 
        
        # === BLOCO DIREITO: Ferramentas ===
        
        # 5. Botão Grade (Substitui o Checkbox)
        self.btn_snap = QPushButton("Grade: ON")
        self._style_secondary_btn(self.btn_snap, 100)
        self.btn_snap.setCheckable(True)
        self.btn_snap.setChecked(True)
        self.btn_snap.toggled.connect(self._toggle_snap)
        header_layout.addWidget(self.btn_snap)
        
        # 6. Botão Histórico
        btn_hist = QPushButton("Filtro / Histórico")
        self._style_secondary_btn(btn_hist, 130)
        btn_hist.clicked.connect(self._open_history_dialog)
        header_layout.addWidget(btn_hist)
        
        # 7. Botão Salvar
        btn_save = QPushButton("Salvar Layout")
        self._style_secondary_btn(btn_save, 110)
        btn_save.clicked.connect(self._save_layout)
        header_layout.addWidget(btn_save)
        
        main_layout.addWidget(header)
        
        # --- VIEWPORT (Gráficos) ---
        self.scene = BlueprintScene()
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Remove bordas nativas da View
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setStyleSheet("background: transparent; border: none;")
        
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.view)

    def _create_separator(self):
        """Cria uma linha vertical sutil para separar grupos."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedWidth(1)
        line.setFixedHeight(24) 
        line.setStyleSheet(f"background-color: {THEME_COLORS['border_subtle']}; border: none;")
        return line

    def _style_secondary_btn(self, btn, width):
        """Define botão como secundário (outline) para o styles.py processar."""
        btn.setFixedSize(width, 30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("class", "secondary")

    def _update_rx_heartbeat(self):
        target_time = None
        if self.current_node_filter == "Todos":
            if self.node_timestamps:
                target_time = max(self.node_timestamps.values())
        else:
            target_time = self.node_timestamps.get(self.current_node_filter)

        if target_time is None:
            self.lbl_last_rx.setText("Aguardando dados...")
            return

        delta = int((datetime.now() - target_time).total_seconds())
        if delta < 0: delta = 0
        
        suffix = f" (Nó: {self.current_node_filter})" if self.current_node_filter != "Todos" else ""
        self.lbl_last_rx.setText(f"Último dado: {delta} s atrás{suffix}")

    def update_data(self, data: Dict[str, Any], timestamp: Optional[datetime] = None):
        node_id = self._get_node_id(data)
        if node_id not in self.known_nodes:
            self.known_nodes.add(node_id)
        pkt_time = timestamp if timestamp else datetime.now()
        self.node_timestamps[node_id] = pkt_time
        self._update_rx_heartbeat()
        self._store_data_in_buffer(node_id, data)
        if self.current_node_filter == "Todos" or self.current_node_filter == node_id:
            self._refresh_widgets()

    def _load_history_data(self, path: Path, filters: dict):
        if not self.last_engine: return
        if filters['clear']: self._clear_all_buffers()
        limit = filters['limit'] if filters['limit'] > 0 else float('inf')
        count = 0
        try:
            if filters['limit'] > self.history_limit:
                self.history_limit = filters['limit'] + 1000
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        dt = None
                        if 'ts' in record:
                            dt = datetime.fromisoformat(record['ts'])
                            if dt < filters['start'] or dt > filters['end']: continue
                        if 'data' in record:
                            self.update_data(record['data'], timestamp=dt)
                            count += 1
                            if count >= limit: break
                    except: continue
            QMessageBox.information(self, "Análise Concluída", f"Foram carregados {count} pacotes.")
        except Exception as e: print(f"Erro histórico: {e}")

    def _find_value_recursive(self, data: Dict, key: str) -> Optional[Any]:
        if key in data: return data[key]
        for v in data.values():
            if isinstance(v, dict):
                res = self._find_value_recursive(v, key)
                if res is not None: return res
        return None

    def _get_node_id(self, data: Dict) -> str:
        if self.id_field_name:
            val = self._find_value_recursive(data, self.id_field_name)
            if val is not None: return str(val)
        candidates = ['node_id', 'device_id', 'id', 'serial', 'dev_id', 'address']
        for cand in candidates:
            val = self._find_value_recursive(data, cand)
            if val is not None:
                self.id_field_name = cand
                return str(val)
        return "Desconhecido"

    def _open_node_menu(self, btn_sender):
        menu = QMenu(self)
        
        action_all = menu.addAction("Todos")
        action_all.triggered.connect(lambda: self._on_node_filter_change("Todos"))
        menu.addSeparator()
        if not self.known_nodes:
             menu.addAction("Nenhum nó detectado").setEnabled(False)
        else:
            for node in sorted(list(self.known_nodes)):
                action = menu.addAction(str(node))
                action.triggered.connect(lambda checked, n=node: self._on_node_filter_change(n))
        menu.exec(btn_sender.mapToGlobal(btn_sender.rect().bottomLeft()))

    def _on_node_filter_change(self, text):
        if not text: return
        self.current_node_filter = text
        for widget_pkg in self.widgets_data.values():
            if widget_pkg['type'] == 'node_selector':
                btn = widget_pkg['extra']
                btn.setText(f" {text} ▼")
        self._update_rx_heartbeat()
        self._refresh_widgets()

    def _store_data_in_buffer(self, node_id, data):
        if node_id not in self.data_buffer:
            self.data_buffer[node_id] = {}
        target_buffer = self.data_buffer[node_id]
        def recursive_extract(d):
            for key, value in d.items():
                if isinstance(value, dict):
                    recursive_extract(value)
                elif isinstance(value, (int, float)):
                    if key not in target_buffer: target_buffer[key] = []
                    target_buffer[key].append(value)
                    if len(target_buffer[key]) > self.history_limit:
                        target_buffer[key].pop(0)
                target_buffer[f"{key}_last"] = value
        recursive_extract(data)

    def _refresh_widgets(self):
        target_data = {}
        if self.current_node_filter != "Todos" and self.current_node_filter in self.data_buffer:
            target_data = self.data_buffer[self.current_node_filter]
        elif self.current_node_filter == "Todos":
             if self.data_buffer:
                 first_node = list(self.data_buffer.keys())[0]
                 target_data = self.data_buffer[first_node]

        for field_name, widget_pkg in self.widgets_data.items():
            if widget_pkg['type'] == 'node_selector': continue

            if widget_pkg['type'] == 'plot':
                if field_name in target_data:
                    widget_pkg['curve'].setData(target_data[field_name])
                else:
                    widget_pkg['curve'].setData([])
            elif f"{field_name}_last" in target_data:
                self._update_kpi_visual(widget_pkg, target_data[f"{field_name}_last"])
            else:
                 if widget_pkg['type'] == 'card': widget_pkg['val_label'].setText("--")

    def _create_widget_container(self, wt, name, cfg):
        # Frame recebe o ID "DashboardFrame" para o styles.py aplicar a borda correta
        frame = QFrame()
        frame.setObjectName("DashboardFrame") 
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Título
        title_lbl = QLabel(f"  {cfg.get('description', name).upper()}")
        title_lbl.setFixedHeight(25)
        title_lbl.setProperty("class", "WidgetTitle") 
        layout.addWidget(title_lbl)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 5, 10, 5)
        
        result_pkg = {'frame': frame, 'type': wt, 'config': cfg}
        
        if wt == 'node_selector':
            btn = QPushButton(f" {self.current_node_filter} ▼")
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "secondary") 
            btn.clicked.connect(lambda: self._open_node_menu(btn))
            content_layout.addWidget(btn)
            result_pkg['extra'] = btn
            frame.resize(200, 80)
            
        elif wt == 'plot':
            pw = pg.PlotWidget()
            # Fundo transparente para herdar a cor do DashboardFrame ou usar a global
            pw.setBackground(None) 
            pw.showGrid(x=True, y=True, alpha=0.2)
            pw.getPlotItem().hideButtons()
            pw.getPlotItem().getViewBox().setBorder(None)
            pw.setFrameShape(QFrame.Shape.NoFrame)
            
            color = cfg.get('plot_color', THEME_COLORS['accent']) 
            result_pkg['curve'] = pw.plot(pen=pg.mkPen(color=color, width=2))
            content_layout.addWidget(pw)
            frame.resize(400, 300)
            
        elif wt in ['card', 'led', 'gauge']:
            val_label = QLabel("--")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            result_pkg['val_label'] = val_label
            
            if wt == 'card':
                val_label.setProperty("class", "CardValue") 
                content_layout.addWidget(val_label)
                
            elif wt == 'led':
                led_row = QHBoxLayout()
                led_bulb = QLabel()
                led_bulb.setFixedSize(16, 16)
                
                # Aplica classe CSS para forma (redonda) e borda removida
                led_bulb.setProperty("class", "LedBulb")
                # Cor inicial (desligado)
                led_bulb.setStyleSheet(f"background-color: {THEME_COLORS['border_subtle']};")
                
                val_label.setProperty("class", "InfoLabel")
                
                led_row.addStretch()
                led_row.addWidget(led_bulb)
                led_row.addWidget(val_label)
                led_row.addStretch()
                content_layout.addLayout(led_row)
                result_pkg['extra'] = led_bulb
                
            elif wt == 'gauge':
                val_label.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-size: 14px; font-weight: bold;")
                bar = QProgressBar()
                bar.setFixedHeight(6)
                bar.setTextVisible(False)
                # Aplica classe CSS para cores da barra
                bar.setProperty("class", "DashboardGauge")
                
                bar.setRange(0, 1000)
                content_layout.addWidget(val_label)
                content_layout.addWidget(bar)
                result_pkg['extra'] = bar
                
            frame.resize(220, 100)
            
        layout.addWidget(content_widget)
        return result_pkg

    def _update_kpi_visual(self, widget_pkg, value):
        config = widget_pkg['config']
        format_str = config.get('format', '{}')
        unit = config.get('unit', '')
        
        try: display_text = format_str.format(value)
        except: display_text = str(value)
        
        if widget_pkg['type'] == 'card':
            widget_pkg['val_label'].setText(f"{display_text} {unit}")
            
        elif widget_pkg['type'] == 'led':
            colors_map = config.get('colors', {})
            bulb_color = colors_map.get(value, colors_map.get(str(value), "#444"))
            # Atualiza apenas a cor de fundo, mantendo a classe .LedBulb
            widget_pkg['extra'].setStyleSheet(f"background-color: {bulb_color};")
            
            mapping = config.get('mapping', {})
            widget_pkg['val_label'].setText(str(mapping.get(value, value)).upper())
            
        elif widget_pkg['type'] == 'gauge':
            try:
                min_v = config.get('min', 0)
                max_v = config.get('max', 100)
                clamped = max(min_v, min(float(value), max_v))
                progress = int(((clamped - min_v) / (max_v - min_v)) * 1000)
                widget_pkg['extra'].setValue(progress)
                widget_pkg['val_label'].setText(f"{display_text} {unit}")
            except: pass

    def _save_layout(self):
        if not self.last_engine: return
        name = self.last_engine.config.get('name', 'default')
        self.settings.beginGroup(f"ProLayouts/{name}")
        self.settings.remove("")
        for field, item in self.items_map.items():
            self.settings.setValue(f"{field}/x", item.pos().x())
            self.settings.setValue(f"{field}/y", item.pos().y())
            self.settings.setValue(f"{field}/w", item.widget().size().width())
            self.settings.setValue(f"{field}/h", item.widget().size().height())
        self.settings.endGroup()
        self.settings.sync()

    def _restore_layout(self, name) -> bool:
        self.settings.beginGroup(f"ProLayouts/{name}")
        if not self.settings.childGroups():
            self.settings.endGroup()
            return False
        restored = 0
        for field, item in self.items_map.items():
            x = self.settings.value(f"{field}/x", type=float)
            y = self.settings.value(f"{field}/y", type=float)
            w = self.settings.value(f"{field}/w", type=float)
            h = self.settings.value(f"{field}/h", type=float)
            if x is not None and w is not None and w > 10:
                item.setPos(x, y)
                item.widget().resize(int(w), int(h))
                item.resize(w, h)
                restored += 1
        self.settings.endGroup()
        return restored > 0

    def _apply_default_layout(self):
        cx, cy = 20, 20
        for item in self.items_map.values():
            item.setPos(cx, cy)
            cx += 40; cy += 40
            if cy > 500: cy = 20; cx += 300

    def _toggle_snap(self, checked):
        # Atualiza o texto para dar feedback visual do estado
        self.btn_snap.setText("Grade: ON" if checked else "Grade: OFF")
        
        self.scene.grid_visible = checked
        self.scene.update()
        for item in self.items_map.values(): item.snap_enabled = checked

    def _on_back_pressed(self):
        self._save_layout()
        if self.on_back: self.on_back()
    
    def _open_history_dialog(self):
        log_path = Path("data/logs/station_data.jsonl")
        curr_schema = self.last_engine.config.get('name') if self.last_engine else None
        dialog = HistoryFilterDialog(self, current_schema=curr_schema)
        if dialog.exec() == HistoryFilterDialog.DialogCode.Accepted:
            filters = dialog.get_data()
            if filters.get('schema') and (not self.last_engine or filters['schema'] != self.last_engine.config.get('name')):
                self._load_schema_and_build(filters['schema'], keep_data=False)
            if log_path.exists():
                self._load_history_data(log_path, filters)
            else:
                 if filters['clear']:
                    self._clear_all_buffers()

    def _clear_all_buffers(self):
        self.data_buffer.clear()
        self.known_nodes.clear()
        self.node_timestamps.clear()
        self.history_limit = self.default_history_limit
        self.lbl_last_rx.setText("Aguardando dados...")
        for widget_pkg in self.widgets_data.values():
             if widget_pkg['type'] == 'node_selector':
                widget_pkg['extra'].setText(" Todos ▼")
        self._refresh_widgets()

    def _load_schema_and_build(self, schema_name, keep_data=False):
        try:
            loader = DecoderLoader()
            success, _, error = loader.load_decoder(schema_name)
            if success:
                engine = DecoderEngine(loader.get_decoder_path(schema_name))
                self.build_ui(engine, keep_data=keep_data)
            else:
                QMessageBox.critical(self, "Erro", f"Falha ao carregar schema: {error}")
        except Exception as e:
            print(f"Erro fatal build_ui: {e}")

    def build_ui(self, engine, keep_data=False):
        self.last_engine = engine
        self.scene.clear()
        self.items_map.clear()
        self.widgets_data.clear()
        
        if not keep_data: self._clear_all_buffers()
        if not engine: return
        self.lbl_title.setText(f"Missão: {engine.config.get('name', 'Analys')}")
        
        self.id_field_name = None
        for name, cfg in engine.field_cache.items():
            if cfg.get('role') == 'identifier':
                self.id_field_name = name
                break

        for field_name, config in engine.field_cache.items():
            widget_type = config.get('widget', 'none').lower()
            if widget_type == 'none': continue
            container = self._create_widget_container(widget_type, field_name, config)
            proxy = SmartDashboardItem(container['frame'], field_name)
            self.scene.addItem(proxy)
            self.items_map[field_name] = proxy
            self.widgets_data[field_name] = container
            
        if not self._restore_layout(engine.config.get('name')):
            self._apply_default_layout()
        self.view.ensureVisible(0, 0, 100, 100)