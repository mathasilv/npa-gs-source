#!/usr/bin/env python3

"""
CLI para decodificação de payloads
Substitui o decode.py original
"""

import sys
import argparse
from pathlib import Path

from npags.core.decoder_engine import DecoderEngine
from npags.decoders.loader import DecoderLoader


def main():
    """Entry point para CLI de decodificação"""
    parser = argparse.ArgumentParser(
        description='Decodificador de payloads LoRa',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'payload',
        help='Payload em hexadecimal (ex: ABCD0001...)'
    )
    
    parser.add_argument(
        '-d', '--decoder',
        default='agrosat',
        help='Nome do decoder a usar (padrão: agrosat)'
    )
    
    parser.add_argument(
        '-f', '--format',
        choices=['text', 'json'],
        default='text',
        help='Formato de saída (padrão: text)'
    )
    
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='Lista decoders disponíveis'
    )
    
    args = parser.parse_args()
    
    # Listar decoders
    if args.list:
        loader = DecoderLoader()
        decoders = loader.scan_decoders()
        if decoders:
            print("Decoders disponíveis:")
            for dec in decoders:
                print(f"  - {dec}")
        else:
            print("Nenhum decoder encontrado")
        return 0
    
    # Decodificar payload
    try:
        loader = DecoderLoader()
        decoder_path = loader.get_decoder_path(args.decoder)
        
        if not decoder_path.exists():
            print(f"Erro: Decoder '{args.decoder}' não encontrado", file=sys.stderr)
            print("Use --list para ver decoders disponíveis", file=sys.stderr)
            return 1
        
        engine = DecoderEngine(decoder_path)
        decoded = engine.decode_payload(args.payload)
        
        if 'error' in decoded:
            print(f"Erro na decodificação: {decoded['error']}", file=sys.stderr)
            return 1
        
        print(engine.format_output(decoded, output_format=args.format))
        return 0
    
    except Exception as e:
        print(f"Erro fatal: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
