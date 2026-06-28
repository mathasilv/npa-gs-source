# src/npags/radio/flowgraph.py
"""
Wrapper do GNU Radio para recepção LoRa e análise espectral.
Este módulo depende das bibliotecas 'gnuradio', 'osmosdr' e 'gr-lora'.

NOTA: Este módulo só funciona quando GNU Radio está instalado no SISTEMA.
      O executável compilado (PyInstaller) não inclui GNU Radio.
      Para usar SDR, execute a partir do código fonte.
"""

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Importações condicionais do GNU Radio
# GNU Radio é instalado no sistema (pacman/apt), não via pip
try:
    from gnuradio import blocks, gr
    _ = blocks  # Necessário para gr-lora
    import lora
    import osmosdr
    import pmt
    HAS_GNURADIO = True
except ImportError as e:
    logger.warning(f"GNU Radio não disponível: {e}")
    HAS_GNURADIO = False
    # Placeholders para evitar erros de sintaxe nas classes
    gr = None
    pmt = None
    lora = None
    osmosdr = None


def _check_gnuradio():
    """Verifica se GNU Radio está disponível."""
    if not HAS_GNURADIO:
        raise ImportError(
            "GNU Radio não está disponível.\n"
            "Para usar o modo SDR, instale GNU Radio no sistema:\n"
            "  Arch: sudo pacman -S gnuradio gr-osmosdr\n"
            "  Ubuntu: sudo apt install gnuradio gr-osmosdr\n"
            "\nOu use o modo UDP Network que não requer GNU Radio."
        )


# As classes só são definidas se GNU Radio estiver disponível
if HAS_GNURADIO:
    class WaterfallSniffer(gr.sync_block):
        """
        Bloco GNU Radio customizado para extração de dados FFT (Espectro).
        Reduz a taxa de dados antes de enviar para a GUI para evitar travamentos.
        """
        
        def __init__(self, callback: Callable[[NDArray[np.floating[Any]]], None], fft_size: int = 1024) -> None:
            gr.sync_block.__init__(
                self,
                name="Waterfall Sniffer",
                in_sig=[np.complex64],
                out_sig=None
            )
            self.callback = callback
            self.fft_size = fft_size
            self.num_chunks = 20  # Número de linhas FFT para acumular antes de processar
            self._needed = fft_size * self.num_chunks
            # Buffer pré-alocado de tamanho fixo: evita realocação a cada chunk de I/Q.
            # Usamos um array circular via índice de escrita.
            self._buf: NDArray[np.complexfloating[Any, Any]] = np.zeros(self._needed * 2, dtype=np.complex64)
            self._buf_len: int = 0
            self.window: NDArray[np.floating[Any]] = np.hanning(self.fft_size)
            self.counter = 0
        
        def work(self, input_items: list[NDArray[Any]], _output_items: list[NDArray[Any]]) -> int:
            in0: NDArray[np.complexfloating[Any, Any]] = input_items[0]
            n_in = len(in0)

            # Cresce o buffer interno apenas se necessário (acontece raramente)
            if self._buf_len + n_in > len(self._buf):
                new_size = max(len(self._buf) * 2, self._buf_len + n_in)
                new_buf = np.zeros(new_size, dtype=np.complex64)
                new_buf[:self._buf_len] = self._buf[:self._buf_len]
                self._buf = new_buf

            self._buf[self._buf_len:self._buf_len + n_in] = in0
            self._buf_len += n_in

            # Processa quadros completos
            while self._buf_len >= self._needed:
                proc = self._buf[:self._needed].copy()
                # Desloca o buffer restante para o início (sem realocar)
                remaining = self._buf_len - self._needed
                self._buf[:remaining] = self._buf[self._needed:self._needed + remaining]
                self._buf_len = remaining

                # Decimação temporal: processa 1 a cada 3 frames
                self.counter += 1
                if self.counter % 3 == 0:
                    mat: NDArray[np.complexfloating[Any, Any]] = proc.reshape(
                        (self.num_chunks, self.fft_size)
                    ) * self.window
                    fft_result = np.fft.fftshift(
                        np.fft.fft(mat, axis=1) / self.fft_size, axes=1
                    )
                    db: NDArray[np.floating[Any]] = 20 * np.log10(np.abs(fft_result) + 1e-12)
                    self.callback(np.max(db, axis=0))

            return n_in

    class BridgeBlock(gr.basic_block):
        """
        Bloco adaptador que converte mensagens assíncronas do GNU Radio (PMT)
        em chamadas de função Python puras.

        Args:
            callback: Função chamada com os bytes brutos de cada pacote.
            filter_bytes: Sequência de bytes usada para alinhar o pacote
                          (magic/sync word). Se None, encaminha tudo (modo raw).
        """
        
        def __init__(
            self,
            callback: Callable[[bytes], None],
            filter_bytes: bytes | None = None,
        ) -> None:
            gr.basic_block.__init__(
                self,
                name="Bridge Python",
                in_sig=None,
                out_sig=None
            )
            self.callback = callback
            self.filter_bytes = filter_bytes
            # Registra porta de entrada de mensagens
            self.message_port_register_in(pmt.intern("in"))
            self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        
        def handle_msg(self, msg: Any) -> None:
            """Trata PDUs recebidas do decodificador LoRa."""
            try:
                # Extrai payload do par (header, data)
                payload = pmt.cdr(msg) if pmt.is_pair(msg) else msg
                
                if pmt.is_u8vector(payload):
                    data = bytes(pmt.u8vector_elements(payload))
                    
                    if self.filter_bytes:
                        # Modo filtrado: alinha pelo sync word configurável
                        idx = data.find(self.filter_bytes)
                        if idx != -1:
                            self.callback(data[idx:])
                        # Se não encontrou, descarta (ruído)
                    else:
                        # Modo raw: encaminha tudo sem filtrar
                        self.callback(data)
                        
            except Exception as e:
                logger.warning("Erro ao converter pacote GNU Radio: %s", e)

    class RadioFlowgraph(gr.top_block):
        """
        Grafo de fluxo principal (Top Block).
        Conecta: SDR Source -> LoRa Receiver -> Python Bridge
                            -> Waterfall Sniffer
        """
        
        def __init__(
            self,
            pkt_cb: Callable[[bytes], None],
            wf_cb: Callable[[NDArray[np.floating[Any]]], None],
            freq: float,
            sf: int,
            bw: float,
            gain: int,
            bias: bool,
            device_str: str,
            filter_bytes: bytes | None = None,
        ) -> None:
            _check_gnuradio()  # Verifica disponibilidade
            gr.top_block.__init__(self, "AgroSat Receiver")
            
            # Ajuste de taxa de amostragem baseado na largura de banda LoRa
            samp_rate = 1000000 # 1 Msps padrão
            if bw > 500000:
                samp_rate = 2000000 # 2 Msps para bandas largas
            
            # Montagem dos argumentos do driver (RTL-SDR, HackRF, etc)
            try:
                # Tenta extrair o índice (ex: "0: RTL-SDR" -> 0)
                idx = device_str.split(":")[0]
                int(idx) # validação
                base_args = f"rtl={idx},numchan=1"
            except (ValueError, IndexError):
                base_args = "numchan=1" # Padrão genérico
            
            if bias:
                base_args += ",bias=1"
            
            # 1. Fonte SDR
            self.src = osmosdr.source(args=base_args)
            self.src.set_sample_rate(samp_rate)
            self.src.set_center_freq(freq, 0)
            self.src.set_freq_corr(0, 0)
            self.src.set_dc_offset_mode(0, 0)
            self.src.set_iq_balance_mode(0, 0)
            self.src.set_gain_mode(False, 0)
            self.src.set_gain(gain, 0)
            self.src.set_if_gain(20, 0)
            self.src.set_bb_gain(20, 0)
            self.src.set_antenna('', 0)
            self.src.set_bandwidth(0, 0)
            
            # 2. Receptor LoRa (gr-lora)
            self.lora = lora.lora_receiver(
                samp_rate, 
                freq, 
                [freq], 
                int(bw), 
                int(sf),
                False, # Implicit Header
                4,     # Coding Rate (4/8)
                True,  # CRC check
                False, # Low Data Rate Opt
                False, # Loopback
                1,     # Decimation
                False, # Verbose
                False  # Test mode
            )
            
            # 3. Blocos Auxiliares (Ponte e Espectro)
            self.bridge = BridgeBlock(pkt_cb, filter_bytes=filter_bytes)
            self.sniff = WaterfallSniffer(wf_cb, fft_size=1024)
            
            # 4. Conexões
            # Caminho de dados I/Q
            self.connect((self.src, 0), (self.lora, 0))
            self.connect((self.src, 0), (self.sniff, 0))
            
            # Caminho de mensagens (Pacotes decodificados)
            self.msg_connect((self.lora, 'frames'), (self.bridge, 'in'))
        
        def set_gain(self, gain: int) -> None:
            """Atualiza o ganho de RF em tempo de execução."""
            self.src.set_gain(gain, 0)

else:
    # Placeholders quando GNU Radio não está disponível
    class RadioFlowgraph:
        """Placeholder - GNU Radio não disponível."""
        def __init__(self, *args, **kwargs):
            _check_gnuradio()
    
    class WaterfallSniffer:
        """Placeholder - GNU Radio não disponível."""
        def __init__(self, *args, **kwargs):
            _check_gnuradio()
    
    class BridgeBlock:
        """Placeholder - GNU Radio não disponível."""
        def __init__(self, *args, **kwargs):
            _check_gnuradio()