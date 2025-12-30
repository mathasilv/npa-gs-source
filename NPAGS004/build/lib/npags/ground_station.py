#!/usr/bin/env python3

"""
Estacao Terrestre - Recebe e decodifica payloads via UDP
Versao Refatorada: Polimorfismo corrigido e Logging centralizado
"""

import sys
import socket
import json
from datetime import datetime

from npags.core.decoder_engine import DecoderEngine
from npags.core.multi_decoder import MultiDecoderEngine
from npags.decoders.loader import DecoderLoader
from npags.core.logger import setup_telemetry_logger

class GroundStation:
    """Estacao Terrestre Robusta"""
    
    def __init__(self, host='localhost', port=5005, decoder_name=None, decoder_engine=None):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.payload_count = 0
        
        # Configuracao do Decoder
        if decoder_engine:
            self.engine = decoder_engine
            print("Multi-decoder carregado")
        elif decoder_name:
            loader = DecoderLoader()
            decoder_file = loader.get_decoder_path(decoder_name)
            
            if not decoder_file.exists():
                raise FileNotFoundError(f"Decoder '{decoder_name}' nao encontrado")
            
            self.engine = DecoderEngine(decoder_file)
            print(f"Decoder '{decoder_name}' carregado")
        else:
            raise ValueError("Especifique decoder_name ou decoder_engine")
        
        # Configuracao de Logging Centralizada
        self.data_logger = setup_telemetry_logger('TelemetryData_CLI')
    
    def start(self):
        """Inicia estacao terrestre"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        self.running = True
        
        print(f"Estacao Terrestre (Modo Raw Binary)")
        print(f"Host: {self.host}")
        print(f"Porta: {self.port}")
        print(f"Aguardando payloads...\n")
        
        try:
            while self.running:
                try:
                    data, addr = self.socket.recvfrom(4096)
                    self.handle_payload(data, addr)
                except socket.timeout:
                    pass
                except Exception as e:
                    if self.running:
                        print(f"Erro de Socket: {e}")
        
        except KeyboardInterrupt:
            print("\nEstacao parada")
        finally:
            self.stop()
    
    def handle_payload(self, data, addr):
        """Processa payload recebido"""
        self.payload_count += 1
        timestamp = datetime.now().isoformat()
        
        try:
            # Decodifica diretamente (o engine lida com bytes)
            decoded = self.engine.decode_payload(data)
            
            # Exibicao e Persistencia
            self.display_decoded(decoded, timestamp, addr, data)
            self.save_telemetry(decoded, data, timestamp, addr)
        
        except Exception as e:
            print(f"[{timestamp}] Erro Critico no processamento: {e}")
    
    def display_decoded(self, decoded, timestamp, addr, raw_bytes):
        """Exibe dados na tela"""
        mode = "RAW-BIN"
        
        # Identifica decoder usado (compativel com single e multi)
        decoder_used = decoded.get('matched_decoder', decoded.get('decoder', 'unknown'))
        
        print(f"[{timestamp}] Payload #{self.payload_count} de {addr[0]}:{addr[1]} [{mode}] - Decoder: {decoder_used}")
        
        if 'error' in decoded:
            print(f"Erro: {decoded['error']}")
            if 'decoder_errors' in decoded:
                print(f"Tentados: {', '.join(decoded['tried_decoders'])}")
            print(f"Dump: {raw_bytes.hex().upper()}")
            return
        
        # CORREÇÃO: Chamada polimórfica limpa.
        # Não importa se self.engine é Single ou Multi, ambos respondem a format_output.
        print(self.engine.format_output(decoded))
        
        print(f"Tamanho Fisico: {len(raw_bytes)} bytes\n")
    
    def save_telemetry(self, decoded, raw_bytes, timestamp, addr):
        """Salva telemetria"""
        entry = {
            'ts': timestamp,
            'seq': self.payload_count,
            'src': f"{addr[0]}:{addr[1]}",
            'raw': raw_bytes.hex().upper(),
            'data': decoded
        }
        self.data_logger.info(json.dumps(entry))
    
    def stop(self):
        """Para estacao"""
        self.running = False
        if self.socket:
            self.socket.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Estacao Terrestre Avancada')
    parser.add_argument('-d', '--decoder', default='agrosat', help='Nome do decoder')
    parser.add_argument('--multi-decoder', action='store_true', help='Usar todos os decoders')
    parser.add_argument('--host', default='localhost', help='Host')
    parser.add_argument('--port', type=int, default=5005, help='Porta')
    
    args = parser.parse_args()
    
    try:
        if args.multi_decoder:
            station = GroundStation(
                host=args.host,
                port=args.port,
                decoder_engine=MultiDecoderEngine()
            )
        else:
            station = GroundStation(
                host=args.host,
                port=args.port,
                decoder_name=args.decoder
            )
        
        station.start()
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()