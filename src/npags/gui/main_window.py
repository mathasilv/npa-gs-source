
"""""
Interface principal da Ground Station.
Integração com Dashboard Data-Driven e navegação entre telas.
Refatorado para modularidade e limpeza.
"""

import json
import logging
import queue
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox,
    QStackedWidget
)
from PyQt6.QtCore import QTimer, Qt

# === Core Modules ===
from npags.core.decoder_engine import DecoderEngine
from npags.core.multi_decoder import MultiDecoderEngine
from npags.decoders.loader import DecoderLoader
from npags.core.logger import setup_telemetry_logger
from npags.core.telemetry_formatter import TelemetryFormatter, create_packet_info

# === GUI Modules (Modularizados) ===
from npags.gui.views import StationView, EditorView, DashboardView
from npags.gui.components import scan_sdr_devices
from npags.gui.styles import FLAT_DARK_STYLESHEET
from npags.gui.utils import ComboPopupNoWhiteBorder
from npags.gui.translations import init_language

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
        self.setMinimumSize(1080, 700)

        # --- Estado da Aplicação ---
        self.running = False
        self.backend = None   # Thread de Rádio ou UDP
        self.engine = None    # Motor de Decodificação
        self.mode = "RADIO"
        self.packet_count = 0
        
        # --- Formatador de Telemetria ---
        self.telemetry_formatter: TelemetryFormatter | None = None

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
            on_open_dashboard=self._open_dashboard
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

    def _on_gain_change(self, gain: int) -> None:
        """Callback para mudança de ganho do rádio."""
        if self.running and self.mode == "RADIO" and self.backend:
            try:
                if hasattr(self.backend, 'set_gain'):
                    self.backend.set_gain(gain)
                    logger.debug("Ganho ajustado para %d dB", gain)
            except Exception as e:
                logger.warning("Erro ao ajustar ganho: %s", e)
    


    def _toggle_system(self):
        if self.running:
            self._stop_system()
        else:
            self._start_system()

    def _start_system(self):
        """Inicializa threads de recepção e decodificação."""
        try:
            # 1. Configura Engine de Decodificação
            # Obtem lista de decoders selecionados
            selected_decoders = self.station_view.get_selected_decoders()
            
            if not selected_decoders:
                raise ValueError("Selecione pelo menos um decoder.")
            
            if len(selected_decoders) > 1:
                # Multiplos decoders -> usa MultiDecoderEngine
                self.engine = MultiDecoderEngine(filter_decoders=selected_decoders)
                count = len(self.engine.get_loaded_decoders())
                names = ", ".join(self.engine.get_loaded_decoder_names())
                self._system_log(f"Multi-Decoder ativo ({count} schemas: {names})")
                
                # Inicializa formatador para Multi-Decoder
                self.telemetry_formatter = TelemetryFormatter(decoder_name="multi")
                combined_cache = {}
                for dec in self.engine.get_loaded_decoders():
                    if hasattr(dec, 'field_cache'):
                        combined_cache.update(dec.field_cache)
                self.telemetry_formatter.set_field_cache(combined_cache)
                
                # Build dashboard com todos os decoders
                self.dashboard_view.build_ui_multi(self.engine.get_loaded_decoders())
            else:
                # Decoder unico
                name = selected_decoders[0]
                path = self.decoder_loader.get_decoder_path(name)
                self.engine = DecoderEngine(path)
                self._system_log(f"Decoder carregado: {name}")
                
                self.telemetry_formatter = TelemetryFormatter(decoder_name=name)
                self.telemetry_formatter.set_field_cache(self.engine.field_cache)
                
                # Build dashboard com decoder unico
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
        # --- EXIBE RESUMO DA SESSÃO ---
        if self.telemetry_formatter and self.telemetry_formatter.stats.total_packets > 0:
            summary = self.telemetry_formatter.format_session_summary()
            self.station_view.log(summary)
        
        if self.backend:
            try:
                self.backend.stop()
                if hasattr(self.backend, 'wait'):
                    self.backend.wait(timeout=2.0)
            except Exception as e:
                logger.warning("Erro ao parar backend: %s", e)
            finally:
                self.backend = None

        self.running = False
        self.packet_count = 0
        self.telemetry_formatter = None
        self.station_view.set_running_state(False)
        self._system_log("=== SISTEMA PARADO ===")

    def _system_log(self, msg: str) -> None:
        self.station_view.log(msg)
        logger.debug("[SYSTEM] %s", msg)

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
            pass  # Queue vazia, normal

    def _process_packet_logic(self, data: bytes):
        """Decodifica e exibe um pacote."""
        self.packet_count += 1
        ts = datetime.now()

        try:
            decoded = self.engine.decode_payload(data)
            
            # --- FORMATAÇÃO ---
            if self.telemetry_formatter:
                rssi = self._extract_rssi(decoded)
                packet_info = create_packet_info(
                    sequence=self.packet_count,
                    raw_data=data,
                    decoded=decoded,
                    rssi=rssi
                )
                log_msg = self.telemetry_formatter.format_packet(packet_info)
            else:
                ts_str = ts.strftime("%H:%M:%S")
                if 'error' in decoded:
                    log_msg = f"[{ts_str}] ERR: {decoded['error']} | RAW: {data.hex().upper()}"
                else:
                    log_msg = f"[{ts_str}] OK: {len(data)}B"
            
            # --- ATUALIZA A DASHBOARD (Gráficos/Cards) ---
            if 'error' not in decoded:
                self.dashboard_view.update_data(decoded)

            self.station_view.log(log_msg)
            self._save_log(data, decoded, ts.isoformat())

        except Exception as e:
            logger.exception("Erro no processamento de pacote")
            ts_str = ts.strftime("%H:%M:%S.%f")[:-3]
            self.station_view.log(f"[{ts_str}] ERRO INTERNO: {e}")
    
    def _extract_rssi(self, decoded: dict[str, Any]) -> int | None:
        """Extrai RSSI dos dados decodificados."""
        for section in decoded.values():
            if isinstance(section, dict):
                if 'rssi' in section:
                    return int(section['rssi'])
        return None

    def _save_log(self, raw: bytes, decoded: dict[str, Any], ts_iso: str) -> None:
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
    
    # Inicializa sistema de tradução (deve ser após QApplication)
    init_language()
    
    # Fix específico para Linux/Arch
    app._combo_popup_fix = ComboPopupNoWhiteBorder(app)
    app.installEventFilter(app._combo_popup_fix)

    window = GroundStationApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

if __name__ == '__main__':
    main()
