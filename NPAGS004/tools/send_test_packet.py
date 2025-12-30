#!/usr/bin/env python3
"""
Envia pacotes de teste via UDP para testar a ground station
"""

import socket
import argparse
import time
from pathlib import Path
import yaml


def load_decoder_schema(decoder_name):
    """Carrega schema do decoder"""
    schema_path = Path(f"config/decoder_schemas/{decoder_name}.yaml")
    if not schema_path.exists():
        raise FileNotFoundError(f"Decoder '{decoder_name}' nao encontrado")
    
    with open(schema_path, 'r') as f:
        return yaml.safe_load(f)


def build_test_packet(decoder_name):
    """Constroi pacote de teste baseado no schema"""
    schema = load_decoder_schema(decoder_name)
    
    packet = bytearray()
    
    # Header
    header = schema.get('header', {})
    for field in header.get('fields', []):
        field_type = field['type']
        
        if 'expected' in field:
            value = field['expected']
        else:
            value = 0
        
        if field_type == 'uint8':
            packet.append(value & 0xFF)
        elif field_type == 'uint16be':
            packet.extend([(value >> 8) & 0xFF, value & 0xFF])
    
    # Payload de exemplo (valores dummy)
    # Temperatura: 25.5°C
    packet.extend([0x00, 0xFF])  # int16be scaled
    # Umidade: 65%
    packet.append(65)
    # Bateria: 87%
    packet.append(87)
    
    return bytes(packet)


def send_packet(host, port, data, repeat=1, interval=1.0):
    """Envia pacote via UDP"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    for i in range(repeat):
        sock.sendto(data, (host, port))
        print(f"[{i+1}/{repeat}] Enviado {len(data)} bytes para {host}:{port}")
        print(f"  Hex: {data.hex().upper()}")
        
        if i < repeat - 1:
            time.sleep(interval)
    
    sock.close()


def main():
    parser = argparse.ArgumentParser(description='Envia pacotes de teste via UDP')
    parser.add_argument(
        '--host',
        default='localhost',
        help='Host destino (padrao: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5005,
        help='Porta destino (padrao: 5005)'
    )
    parser.add_argument(
        '--decoder',
        default='agrosat',
        help='Nome do decoder para gerar pacote (padrao: agrosat)'
    )
    parser.add_argument(
        '--hex',
        help='Enviar payload hexadecimal customizado'
    )
    parser.add_argument(
        '--repeat',
        type=int,
        default=1,
        help='Numero de vezes para enviar (padrao: 1)'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='Intervalo entre envios em segundos (padrao: 1.0)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.hex:
            data = bytes.fromhex(args.hex)
        else:
            data = build_test_packet(args.decoder)
        
        send_packet(args.host, args.port, data, args.repeat, args.interval)
        
    except Exception as e:
        print(f"Erro: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
