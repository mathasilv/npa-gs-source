
"""
Interface principal da Ground Station.
Integração com Dashboard Data-Driven e navegação entre telas.
Refatorado para modularidade e limpeza.
"""

import sys
import queue
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox,
    QStackedWidget, QWidget
)
from PyQt6.QtCore import QTimer, Qt, QObject, QEvent

# === Core Modules ===
from npags.core.decoder_engine import DecoderEngine
from npags.core.multi_decoder import MultiDecoderEngine
from npags.decoders.loader import DecoderLoader
from npags.core.logger import setup_telemetry_logger

# === GUI Modules (Modularizados) ===
from npags.gui.station_view import StationView
from npags.gui.editor_view import EditorView
from npags.gui.dashboard_view import DashboardView 
from npags.gui.components import scan_sdr_devices
from npags.gui.styles import FLAT_DARK_STYLESHEET
from npags.gui.utils import ComboPopupNoWhiteBorder

# === Hardware/Network Modules ===
HAS_RADIO = False
try:
    from npags.radio.flowgraph import RadioFlowgraph
    HAS_RADIO = True
except ImportError:
    RadioFlowgraph = None

from npags.radio.udp_receiver import UDPReceiver

class GroundStationApp(QMainWindow):
    """Janela principal da aplicação."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("NPA Ground Station v5.6 (Dashboard)")
        self.resize(1200, 800)
        self.setMinimumSize(1024, 700)

        # --- Estado da Aplicação ---
        self.running = False
        self.backend = None   # Thread de Rádio ou UDP
        self.engine = None    # Motor de Decodificação
        self.mode = "RADIO"
        self.packet_count = 0

        # --- Recursos ---
        self.decoder_loader = DecoderLoader()
        self.data_logger = setup_telemetry_logger('TelemetryData_GUI')

        # Filas Thread-Safe
        self.q_pkt = queue.Queue()
        self.q_wf = queue.Queue()

        # --- Inicialização UI ---
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._init_views()

        # --- Timer de Loop Principal (60 Hz aprox) ---
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_loop)
        self.timer.start(16)

    def _init_views(self):
        """Inicializa e empilha as visualizações."""
        decoders = self.decoder_loader.scan_decoders()
        radios = scan_sdr_devices()

        # 1. View Principal (Station)
        self.station_view = StationView(
            parent=self.stack,
            radios=radios,
            decoders=decoders,
            on_mode_change=self._on_mode_change,
            on_toggle=self._toggle_system,
            on_new_decoder=self._on_new_decoder_req,
            on_edit_decoder=self._on_edit_decoder_req,
            on_gain_change=self._on_gain_change,
            on_open_dashboard=self._open_dashboard # <--- Callback do Dashboard
        )
        self.stack.addWidget(self.station_view)

        # 2. View Editor
        self.editor_view = EditorView(
            parent=self.stack,
            on_back=self._back_to_station
        )
        self.stack.addWidget(self.editor_view)

        # 3. View Dashboard (NOVO)
        self.dashboard_view = DashboardView(
            parent=self.stack,
            on_back=self._back_to_station
        )
        self.stack.addWidget(self.dashboard_view)

        # Mostra inicial
        self.stack.setCurrentWidget(self.station_view)

    # === Navegação ===

    def _open_dashboard(self):
        """Alterna para a tela de gráficos."""
        self.stack.setCurrentWidget(self.dashboard_view)

    def _back_to_station(self):
        """Retorna à tela principal."""
        # Se veio do editor, recarrega decoders
        decoders = self.decoder_loader.scan_decoders()
        self.station_view.update_decoders(decoders)
        self.stack.setCurrentWidget(self.station_view)

    def _on_new_decoder_req(self):
        self.editor_view.open_new_decoder()
        self.stack.setCurrentWidget(self.editor_view)

    def _on_edit_decoder_req(self):
        current = self.station_view.get_selected_decoder()
        if not current or current == "Nenhum":
            QMessageBox.warning(self, "Seleção Inválida", "Selecione um decoder para editar.")
            return
        if self.editor_view.open_edit_decoder(current):
            self.stack.setCurrentWidget(self.editor_view)

    # === Controle do Sistema ===

    def _on_mode_change(self, mode: str):
        if self.running:
            QMessageBox.warning(self, "Sistema em Execução", "Pare o sistema antes de mudar o modo.")
            self.station_view.set_mode(self.mode)
            return
        self.mode = mode
        self.station_view.log(f"--- Modo alterado para {mode} ---")

    def _on_gain_change(self, gain: int):
        if self.running and self.mode == "RADIO" and self.backend:
            try:
                if hasattr(self.backend, 'set_gain'):
                    self.backend.set_gain(gain)
            except Exception as e:
                print(f"Erro ao ajustar ganho: {e}")

    def _toggle_system(self):
        if self.running:
            self._stop_system()
        else:
            self._start_system()

    def _start_system(self):
        """Inicializa threads de recepção e decodificação."""
        try:
            # 1. Configura Engine de Decodificação
            if self.station_view.is_multi_decoder_enabled():
                self.engine = MultiDecoderEngine()
                count = len(self.engine.get_loaded_decoders())
                self._system_log(f"Iniciando Multi-Decoder ({count} schemas)")
                # Nota: MultiDecoder não suporta build_ui automático ainda, 
                # a menos que peguemos o primeiro decoder como base.
            else:
                name = self.station_view.get_selected_decoder()
                if not name or name == "Nenhum":
                    raise ValueError("Selecione um decoder ou ative o modo auto-detect.")

                path = self.decoder_loader.get_decoder_path(name)
                self.engine = DecoderEngine(path)
                self._system_log(f"Decoder carregado: {name}")
                
                # --- CONSTRÓI A DASHBOARD COM BASE NO DECODER ---
                self.dashboard_view.build_ui(self.engine)

            # 2. Configura Backend (Radio ou UDP)
            if self.mode == "RADIO":
                self._start_radio()
            else:
                self._start_udp()

            # 3. Atualiza Estado UI
            self.running = True
            self.station_view.set_running_state(True)
            self._system_log("=== SISTEMA INICIADO ===")

        except Exception as e:
            self._system_log(f"ERRO FATAL: {str(e)}")
            QMessageBox.critical(self, "Erro ao Iniciar", str(e))
            self._stop_system()

    def _start_radio(self):
        if not HAS_RADIO:
            raise ImportError("Módulo GNU Radio/SDR não encontrado no ambiente Python.")

        cfg = self.station_view.get_radio_config()
        self._system_log(f"Configurando Rádio: {cfg['freq']/1e6} MHz, SF{cfg['sf']}, BW{cfg['bw']/1e3}k")

        self.backend = RadioFlowgraph(
            pkt_cb=self._on_packet_received,
            wf_cb=self._on_waterfall_data,
            freq=cfg['freq'],
            sf=cfg['sf'],
            bw=cfg['bw'],
            gain=cfg['gain'],
            bias=cfg['bias'],
            device_str=cfg['device']
        )
        self.backend.start()

    def _start_udp(self):
        cfg = self.station_view.get_udp_config()
        self._system_log(f"Ouvindo UDP: {cfg['host']}:{cfg['port']}")
        self.backend = UDPReceiver(
            ip=cfg['host'],
            port=cfg['port'],
            callback_packet=self._on_packet_received
        )
        self.backend.start()

    def _stop_system(self):
        """Para threads de forma graciosa."""
        if self.backend:
            try:
                self.backend.stop()
                if hasattr(self.backend, 'wait'):
                    self.backend.wait()
            except Exception as e:
                print(f"Erro ao parar backend: {e}")
            finally:
                self.backend = None

        self.running = False
        self.station_view.set_running_state(False)
        self._system_log("=== SISTEMA PARADO ===")

    def _system_log(self, msg: str):
        self.station_view.log(msg)
        print(f"[SYSTEM] {msg}")

    # === Callbacks de Dados ===

    def _on_packet_received(self, data: bytes):
        if data:
            self.q_pkt.put(data)

    def _on_waterfall_data(self, data: Any):
        if self.q_wf.qsize() < 2:
            self.q_wf.put(data)

    # === Loop de Atualização ===

    def _update_loop(self):
        if not self.running:
            return

        # 1. Processa Pacotes
        for _ in range(5):
            try:
                pkt = self.q_pkt.get_nowait()
                self._process_packet_logic(pkt)
            except queue.Empty:
                break

        # 2. Atualiza Waterfall
        try:
            latest_wf = None
            while not self.q_wf.empty():
                latest_wf = self.q_wf.get_nowait()
            if latest_wf is not None:
                self.station_view.update_waterfall(latest_wf)
        except queue.Empty:
            pass

    def _process_packet_logic(self, data: bytes):
        """Decodifica e exibe um pacote."""
        ts = datetime.now()
        ts_str = ts.strftime("%H:%M:%S.%f")[:-3]

        try:
            decoded = self.engine.decode_payload(data)

            if 'error' in decoded:
                log_msg = f"[{ts_str}] FALHA: {decoded['error']} | RAW: {data.hex().upper()}"
            else:
                formatted = self.engine.format_output(decoded, output_format='text')
                log_msg = f"\n[{ts_str}] PACOTE RECEBIDO ({len(data)}b):\n{formatted}"
                
                # --- ATUALIZA A DASHBOARD (Gráficos/Cards) ---
                self.dashboard_view.update_data(decoded)

            self.station_view.log(log_msg)
            self._save_log(data, decoded, ts.isoformat())

        except Exception as e:
            print(f"Erro no processamento de pacote: {e}")
            self.station_view.log(f"[{ts_str}] ERRO INTERNO: {e}")

    def _save_log(self, raw: bytes, decoded: Dict, ts_iso: str):
        self.packet_count += 1
        entry = {
            'ts': ts_iso,
            'id': self.packet_count,
            'raw': raw.hex().upper(),
            'data': decoded
        }
        self.data_logger.info(json.dumps(entry))

    def closeEvent(self, event):
        if self.running:
            reply = QMessageBox.question(
                self, 'Sair',
                'O sistema está rodando. Deseja parar e sair?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_system()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(FLAT_DARK_STYLESHEET)
    
    # Fix específico para Linux/Arch
    app._combo_popup_fix = ComboPopupNoWhiteBorder(app)
    app.installEventFilter(app._combo_popup_fix)

    window = GroundStationApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()