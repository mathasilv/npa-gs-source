# src/npags/radio/flowgraph.py
"""
Wrapper do GNU Radio para recepção LoRa e análise espectral.
Este módulo depende das bibliotecas 'gnuradio', 'osmosdr' e 'gr-lora'.
"""

import numpy as np
from gnuradio import gr
import pmt
import osmosdr
import lora

class WaterfallSniffer(gr.sync_block):
    """
    Bloco GNU Radio customizado para extração de dados FFT (Espectro).
    Reduz a taxa de dados antes de enviar para a GUI para evitar travamentos.
    """
    
    def __init__(self, callback, fft_size=1024):
        gr.sync_block.__init__(
            self,
            name="Waterfall Sniffer",
            in_sig=[np.complex64],
            out_sig=None
        )
        self.callback = callback
        self.fft_size = fft_size
        self.num_chunks = 20  # Número de linhas FFT para acumular antes de processar
        self.buffer = np.empty((0,), dtype=np.complex64)
        self.window = np.hanning(self.fft_size)
        self.counter = 0
    
    def work(self, input_items, output_items):
        in0 = input_items[0]
        self.buffer = np.append(self.buffer, in0)
        
        needed = self.fft_size * self.num_chunks
        
        # Se temos dados suficientes para processar um quadro
        if len(self.buffer) >= needed:
            proc = self.buffer[:needed]
            self.buffer = self.buffer[needed:]
            
            # Decimação temporal: Processa apenas 1 a cada 3 frames para aliviar a CPU/GUI
            self.counter += 1
            if self.counter % 3 == 0:
                # Transforma tempo -> frequência (FFT)
                mat = proc.reshape((self.num_chunks, self.fft_size)) * self.window
                fft = np.fft.fftshift(np.fft.fft(mat, axis=1) / self.fft_size, axes=1)
                # Converte para dB
                db = 20 * np.log10(np.abs(fft) + 1e-12)
                # Envia o pico (max hold) ou média para a GUI
                self.callback(np.max(db, axis=0))
        
        return len(in0)

class BridgeBlock(gr.basic_block):
    """
    Bloco adaptador que converte mensagens assíncronas do GNU Radio (PMT)
    em chamadas de função Python puras.
    """
    
    def __init__(self, callback):
        gr.basic_block.__init__(
            self,
            name="Bridge Python",
            in_sig=None,
            out_sig=None
        )
        self.callback = callback
        # Registra porta de entrada de mensagens
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
    
    def handle_msg(self, msg):
        """Trata PDUs recebidas do decodificador LoRa."""
        try:
            # Extrai payload do par (header, data)
            payload = pmt.cdr(msg) if pmt.is_pair(msg) else msg
            
            if pmt.is_u8vector(payload):
                data = bytes(pmt.u8vector_elements(payload))
                
                # Sincronização opcional: Busca por magic bytes (0xAB 0xCD)
                # Se seu protocolo não usa isso no início, remova esta lógica.
                magic = data.find(b'\xAB\xCD')
                if magic != -1:
                    self.callback(data[magic:])
                else:
                    self.callback(data)
                    
        except Exception as e:
            print(f"Erro ao converter pacote GNU Radio: {e}")

class RadioFlowgraph(gr.top_block):
    """
    Grafo de fluxo principal (Top Block).
    Conecta: SDR Source -> LoRa Receiver -> Python Bridge
                        -> Waterfall Sniffer
    """
    
    def __init__(self, pkt_cb, wf_cb, freq, sf, bw, gain, bias, device_str):
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
        except:
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
        self.bridge = BridgeBlock(pkt_cb)
        self.sniff = WaterfallSniffer(wf_cb, fft_size=1024)
        
        # 4. Conexões
        # Caminho de dados I/Q
        self.connect((self.src, 0), (self.lora, 0))
        self.connect((self.src, 0), (self.sniff, 0))
        
        # Caminho de mensagens (Pacotes decodificados)
        self.msg_connect((self.lora, 'frames'), (self.bridge, 'in'))
    
    def set_gain(self, gain):
        """Atualiza o ganho de RF em tempo de execução."""
        self.src.set_gain(gain, 0)