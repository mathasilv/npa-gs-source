# src/npags/radio/backend.py
#!/usr/bin/env python3
"""Backend de Rádio (GNU Radio Headless)
Refatorado: Removeu Magic Bytes hardcoded. Adicionou suporte a filtro dinâmico via CLI.
"""

from __future__ import annotations

import argparse
import logging
import signal
import socket
import sys
from typing import Any

# Importações do GNU Radio
from gnuradio import blocks, gr

_ = blocks  # Necessário para gr-lora
import lora
import osmosdr
import pmt

logger = logging.getLogger(__name__)


class UDPForwarder(gr.basic_block):
    """
    Bloco para envio de dados via UDP com filtragem opcional.
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5005,
        filter_bytes: bytes | None = None,
    ) -> None:
        """
        Args:
            host (str): Endereço IP de destino.
            port (int): Porta UDP de destino.
            filter_bytes (bytes, optional): Sequência para filtrar/alinhar o pacote.
                                            Se None, encaminha tudo (modo Raw).
        """
        gr.basic_block.__init__(
            self,
            name="UDP Forwarder",
            in_sig=None,
            out_sig=None
        )
        self.target = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.filter_seq = filter_bytes
        
        # Registra a porta de entrada
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        
        filter_msg = f"Filtro: 0x{self.filter_seq.hex().upper()}" if self.filter_seq else "Filtro: Desativado (Modo Raw)"
        logger.info("Encaminhando para %s:%d | %s", host, port, filter_msg)
    
    def handle_msg(self, msg: Any) -> None:
        """Trata mensagens recebidas do bloco LoRa"""
        try:
            payload = msg
            # Extrai dados se for par (PDU)
            if pmt.is_pair(msg):
                payload = pmt.cdr(msg)
            
            if pmt.is_u8vector(payload):
                data = pmt.u8vector_elements(payload)
                data_bytes = bytes(data)
                
                # Lógica de Filtragem Dinâmica
                clean_data = None
                status_msg = ""
                
                if self.filter_seq:
                    # Modo Filtrado: Busca a sequência exata
                    magic_index = data_bytes.find(self.filter_seq)
                    if magic_index != -1:
                        # Encontrou: Alinha os dados removendo o lixo anterior
                        clean_data = data_bytes[magic_index:]
                        status_msg = f"Sync (Offset {magic_index})"
                    else:
                        # Não encontrou: Descarta (Ruído)
                        # print(f"[Debug] Ignorado: {len(data_bytes)}b sem magic bytes")
                        return 
                else:
                    # Modo Raw: Encaminha tudo
                    clean_data = data_bytes
                    status_msg = "Raw Pass-through"
                
                if clean_data:
                    hex_str = clean_data.hex().upper()
                    
                    # Log técnico simplificado
                    logger.debug("[RX] Total: %db | Payload: %db | %s", len(data_bytes), len(clean_data), status_msg)
                    # Limita o log do hex para não poluir se for muito grande
                    display_hex = hex_str if len(hex_str) < 100 else f"{hex_str[:50]}...{hex_str[-10:]}"
                    logger.debug("HEX: %s", display_hex)
                    
                    # Envio UDP
                    self.sock.sendto(clean_data, self.target)
        
        except Exception as e:
            logger.error("Erro no processamento UDP: %s", e)


class RadioBackend(gr.top_block):
    """Flowgraph principal do rádio"""

    def __init__(
        self,
        freq: float,
        sf: int,
        bw: float,
        gain: int,
        bias_tee: bool,
        host: str,
        port: int,
        filter_hex: str | None = None,
    ) -> None:
        gr.top_block.__init__(self, "LoRa Receiver Backend")
        
        # Prepara bytes de filtro se fornecidos
        filter_bytes = None
        if filter_hex:
            try:
                filter_bytes = bytes.fromhex(filter_hex)
            except ValueError:
                logger.warning("Filtro hexadecimal inválido '%s'. Iniciando sem filtro.", filter_hex)
        
        # Parâmetros
        samp_rate = 1000000
        if bw > 500000:
            samp_rate = 2000000
        
        logger.info("--- Configuração SDR ---")
        logger.info("Freq: %.1f MHz", freq / 1e6)
        logger.info("SF: %d | BW: %d Hz", sf, int(bw))
        logger.info("Gain: %d dB | Bias: %s", gain, bias_tee)
        logger.info("------------------------")
        
        # Configuração SDR Source (Osmocom)
        dev_args = "numchan=1"
        if bias_tee:
            dev_args += " bias=1"
        
        self.sdr_source = osmosdr.source(args=dev_args)
        self.sdr_source.set_sample_rate(samp_rate)
        self.sdr_source.set_center_freq(freq, 0)
        self.sdr_source.set_freq_corr(0, 0)
        self.sdr_source.set_dc_offset_mode(0, 0)
        self.sdr_source.set_iq_balance_mode(0, 0)
        self.sdr_source.set_gain_mode(False, 0)
        self.sdr_source.set_gain(gain, 0)
        self.sdr_source.set_if_gain(20, 0)
        self.sdr_source.set_bb_gain(20, 0)
        self.sdr_source.set_antenna('', 0)
        self.sdr_source.set_bandwidth(0, 0)
        
        # Configuração LoRa Receiver
        self.lora_receiver = lora.lora_receiver(
            samp_rate,
            freq,
            [freq],
            int(bw),
            int(sf),
            False, 4, True, False, False, 1, False, False
        )
        
        # Sink UDP Customizado
        self.udp_sink = UDPForwarder(host, port, filter_bytes=filter_bytes)
        
        # Conexões
        self.connect((self.sdr_source, 0), (self.lora_receiver, 0))
        self.msg_connect((self.lora_receiver, 'frames'), (self.udp_sink, 'in'))


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend de rádio LoRa - Genérico")
    parser.add_argument('-f', '--freq', type=float, default=915.0, help="Frequência em MHz")
    parser.add_argument('--sf', type=int, default=7, help="Spreading Factor")
    parser.add_argument('--bw', type=float, default=125000, help="Bandwidth em Hz")
    parser.add_argument('-g', '--gain', type=int, default=20, help="Ganho RF em dB")
    parser.add_argument('--bias', action='store_true', help="Habilitar Bias Tee")
    parser.add_argument('--host', default='localhost', help="Host UDP de destino")
    parser.add_argument('--port', type=int, default=5005, help="Porta UDP de destino")
    
    # Novo argumento para resolver o problema de hardcoding
    parser.add_argument('-x', '--filter', type=str, default=None, 
                        help="String Hexadecimal para filtrar pacotes (Ex: ABCD). Se omitido, encaminha tudo.")
    
    args = parser.parse_args()
    
    try:
        tb = RadioBackend(
            args.freq * 1e6,
            args.sf,
            args.bw,
            args.gain,
            args.bias,
            args.host,
            args.port,
            args.filter # Passa o filtro para a classe
        )
        
        def sig_handler(_sig: int | None = None, _frame: Any = None) -> None:
            logger.info("Encerrando rádio...")
            tb.stop()
            tb.wait()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
        
        logger.info("Capturando em %.1f MHz...", args.freq)
        tb.start()
        tb.wait()
    
    except Exception as e:
        logger.critical("Erro fatal no Backend: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
