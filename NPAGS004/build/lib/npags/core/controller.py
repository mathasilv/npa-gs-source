import queue
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Union

# Módulos Core
from npags.core.decoder_engine import DecoderEngine
from npags.core.multi_decoder import MultiDecoderEngine
from npags.core.logger import setup_telemetry_logger
from npags.radio.udp_receiver import UDPReceiver

# Tenta importar Rádio (pode não existir)
try:
    from npags.radio.flowgraph import RadioFlowgraph # type: ignore
    HAS_RADIO = True
except ImportError:
    HAS_RADIO = False
    RadioFlowgraph = None

class StationController:
    """
    Gerencia a lógica de negócio da estação terrestre.
    Independente de Interface Gráfica (pode rodar em CLI ou GUI).
    """

    def __init__(self) -> None:
        self.running = False
        self.backend: Any = None # Pode ser UDPReceiver ou RadioFlowgraph
        self.engine: Union[DecoderEngine, MultiDecoderEngine, None] = None
        self.packet_count = 0
        
        # Logger
        self.data_logger = setup_telemetry_logger('TelemetryData_Controller')
        
        # Filas de saída (thread-safe) para a UI consumir
        self.q_packets: queue.Queue = queue.Queue()
        self.q_waterfall: queue.Queue = queue.Queue()
        
        # Callback para logs de sistema (ex: "Iniciando rádio...")
        self.log_callback: Optional[Callable[[str], None]] = None

    def set_system_logger(self, callback: Callable[[str], None]) -> None:
        """Define uma função para receber logs de texto do sistema."""
        self.log_callback = callback

    def _log(self, msg: str) -> None:
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(f"[CONTROLLER] {msg}")

    def start_udp(self, host: str, port: int, decoder_engine: Any) -> None:
        """Inicia modo UDP."""
        if self.running:
            raise RuntimeError("Sistema já está rodando.")
            
        self.engine = decoder_engine
        self._log(f"Iniciando UDP em {host}:{port}")
        
        self.backend = UDPReceiver(
            ip=host,
            port=port,
            callback_packet=self._on_packet_received
        )
        self.backend.start()
        self.running = True

    def start_radio(self, config: Dict[str, Any], decoder_engine: Any) -> None:
        """Inicia modo Rádio (SDR)."""
        if not HAS_RADIO:
            raise ImportError("Módulo de Rádio não instalado.")
        
        if self.running:
            raise RuntimeError("Sistema já está rodando.")

        self.engine = decoder_engine
        freq_mhz = config['freq'] / 1e6
        self._log(f"Iniciando Rádio: {freq_mhz} MHz, SF{config['sf']}")

        self.backend = RadioFlowgraph(
            pkt_cb=self._on_packet_received,
            wf_cb=self._on_waterfall_data,
            freq=config['freq'],
            sf=config['sf'],
            bw=config['bw'],
            gain=config['gain'],
            bias=config['bias'],
            device_str=config['device']
        )
        self.backend.start()
        self.running = True

    def stop(self) -> None:
        """Para todos os processos."""
        if self.backend:
            self._log("Parando backend...")
            try:
                self.backend.stop()
                if hasattr(self.backend, 'wait'):
                    self.backend.wait() 
            except Exception as e:
                self._log(f"Erro ao parar backend: {e}")
            finally:
                self.backend = None

        self.running = False
        self._log("Sistema parado.")

    def set_gain(self, gain: int) -> None:
        """Ajusta ganho em tempo real (apenas rádio)."""
        if self.running and HAS_RADIO and isinstance(self.backend, RadioFlowgraph):
            try:
                self.backend.set_gain(gain)
            except Exception as e:
                self._log(f"Erro ao ajustar ganho: {e}")

    # --- Callbacks Internos (Vêm da Thread do Backend) ---

    def _on_packet_received(self, raw_data: bytes) -> None:
        """
        Chamado pela thread de rádio/udp. 
        Decodifica, salva e coloca na fila para a UI.
        """
        if not raw_data or not self.engine:
            return

        ts = datetime.now()
        self.packet_count += 1
        
        # 1. Decodificação
        decoded = self.engine.decode_payload(raw_data)
        
        # 2. Formatação para Log/Display
        # A formatação bonita (Pretty Print) pode ser feita aqui ou na UI.
        # Vamos mandar o objeto decodificado e deixar a UI formatar o texto se quiser.
        
        packet_info = {
            'id': self.packet_count,
            'timestamp': ts.isoformat(),
            'timestamp_str': ts.strftime("%H:%M:%S.%f")[:-3],
            'raw_hex': raw_data.hex().upper(),
            'size': len(raw_data),
            'decoded': decoded
        }

        # 3. Persistência (Salvar em disco imediatamente)
        self._save_to_disk(packet_info)

        # 4. Envia para UI
        self.q_packets.put(packet_info)

    def _on_waterfall_data(self, data: Any) -> None:
        # Limita tamanho da fila para não travar a UI se ela ficar lenta
        if self.q_waterfall.qsize() < 2:
            self.q_waterfall.put(data)

    def _save_to_disk(self, packet_info: Dict) -> None:
        """Persiste o pacote decodificado."""
        try:
            log_entry = json.dumps(packet_info)
            self.data_logger.info(log_entry)
        except Exception as e:
            print(f"Erro ao salvar log: {e}")

    # --- Métodos para UI Consumir ---

    def get_pending_packets(self) -> list:
        """Retorna todos os pacotes acumulados na fila."""
        packets = []
        try:
            while True:
                packets.append(self.q_packets.get_nowait())
        except queue.Empty:
            pass
        return packets

    def get_latest_waterfall(self) -> Any:
        """Retorna o dado de waterfall mais recente (descarta antigos)."""
        latest = None
        try:
            while True:
                latest = self.q_waterfall.get_nowait()
        except queue.Empty:
            pass
        return latest