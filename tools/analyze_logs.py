#!/usr/bin/env python3
"""
Analisa logs de telemetria com estatisticas detalhadas
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import statistics


def load_packets(log_file):
    """Carrega pacotes do arquivo JSONL"""
    packets = []
    with open(log_file, 'r') as f:
        for line in f:
            try:
                packets.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return packets


def analyze_general(packets):
    """Estatisticas gerais"""
    print("=" * 70)
    print("ESTATISTICAS GERAIS")
    print("=" * 70)
    print(f"Total de pacotes: {len(packets)}")
    
    if not packets:
        return
    
    # Decoders
    decoders = Counter(p['data'].get('decoder', 'unknown') for p in packets)
    print(f"\nDecoders utilizados:")
    for decoder, count in decoders.items():
        print(f"  {decoder}: {count} pacotes ({count/len(packets)*100:.1f}%)")
    
    # Range de tempo
    first = datetime.fromisoformat(packets[0]['ts'])
    last = datetime.fromisoformat(packets[-1]['ts'])
    duration = last - first
    print(f"\nPeriodo:")
    print(f"  Primeiro: {first.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Ultimo: {last.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Duracao: {duration}")
    
    if duration.total_seconds() > 0:
        rate = len(packets) / duration.total_seconds()
        print(f"  Taxa: {rate:.2f} pacotes/segundo")
    
    # Fontes
    sources = Counter(p['data'].get('matched_decoder', p['data'].get('decoder', 'unknown')) for p in packets)
    print(f"\nFontes:")
    for src, count in sources.items():
        print(f"  {src}: {count} pacotes")
    
    # Erros
    errors = [p for p in packets if 'error' in p['data']]
    if errors:
        print(f"\nPacotes com erro: {len(errors)} ({len(errors)/len(packets)*100:.1f}%)")
        error_types = Counter(p['data']['error'] for p in errors)
        for error, count in error_types.items():
            print(f"  {error}: {count}x")
    
    # Tamanho dos payloads
    sizes = [len(bytes.fromhex(p['raw'])) for p in packets]
    print(f"\nTamanho dos payloads:")
    print(f"  Min: {min(sizes)} bytes")
    print(f"  Max: {max(sizes)} bytes")
    print(f"  Media: {statistics.mean(sizes):.1f} bytes")
    print(f"  Mediana: {statistics.median(sizes)} bytes")


def analyze_sensor_data(packets):
    """Analisa dados de sensores"""
    print("\n" + "=" * 70)
    print("ANALISE DE DADOS DE SENSORES")
    print("=" * 70)
    
    # Coleta dados
    data_fields = defaultdict(list)
    
    for p in packets:
        if 'error' in p['data']:
            continue
        
        # Procura por dados em todas as secoes
        for key, value in p['data'].items():
            if key in ['decoder', 'version', 'header']:
                continue
            
            if isinstance(value, dict):
                for field_name, field_value in value.items():
                    try:
                        # Tenta converter para float
                        numeric_value = float(field_value)
                        data_fields[field_name].append(numeric_value)
                    except (ValueError, TypeError):
                        pass
    
    if not data_fields:
        print("Nenhum dado numerico encontrado")
        return
    
    # Estatisticas por campo
    for field_name, values in sorted(data_fields.items()):
        print(f"\n{field_name}:")
        print(f"  Amostras: {len(values)}")
        print(f"  Min: {min(values):.2f}")
        print(f"  Max: {max(values):.2f}")
        print(f"  Media: {statistics.mean(values):.2f}")
        print(f"  Mediana: {statistics.median(values):.2f}")
        if len(values) > 1:
            print(f"  Desvio padrao: {statistics.stdev(values):.2f}")


def export_csv(packets, output_file):
    """Exporta para CSV"""
    import csv
    
    if not packets:
        print("Nenhum pacote para exportar")
        return
    
    # Determina campos disponiveis
    all_fields = set()
    for p in packets:
        if 'error' not in p['data']:
            for key, value in p['data'].items():
                if isinstance(value, dict):
                    for field in value.keys():
                        all_fields.add(f"{key}.{field}")
    
    fieldnames = ['timestamp', 'seq', 'decoder'] + sorted(all_fields)
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for p in packets:
            if 'error' in p['data']:
                continue
            
            row = {
                'timestamp': p['ts'],
                'seq': p.get('id', 0),
                'decoder': p['data'].get('decoder', 'unknown')
            }
            
            for key, value in p['data'].items():
                if isinstance(value, dict):
                    for field, field_value in value.items():
                        row[f"{key}.{field}"] = field_value
            
            writer.writerow(row)
    
    print(f"\nExportado {len(packets)} pacotes para {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Analisa logs de telemetria')
    parser.add_argument(
        'log_file',
        nargs='?',
        default='data/logs/station_data.jsonl',
        help='Arquivo de log (padrao: data/logs/station_data.jsonl)'
    )
    parser.add_argument(
        '--export-csv',
        metavar='FILE',
        help='Exporta dados para CSV'
    )
    parser.add_argument(
        '--filter-decoder',
        metavar='NAME',
        help='Filtra por decoder especifico'
    )
    parser.add_argument(
        '--last',
        type=int,
        metavar='N',
        help='Analisa apenas os ultimos N pacotes'
    )
    
    args = parser.parse_args()
    
    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Erro: Arquivo nao encontrado: {log_path}")
        return 1
    
    # Carrega pacotes
    packets = load_packets(log_path)
    
    # Filtros
    if args.filter_decoder:
        packets = [p for p in packets if p['data'].get('decoder') == args.filter_decoder]
        print(f"Filtrado para decoder: {args.filter_decoder}")
    
    if args.last:
        packets = packets[-args.last:]
        print(f"Analisando ultimos {args.last} pacotes")
    
    if not packets:
        print("Nenhum pacote encontrado apos filtros")
        return 1
    
    # Analises
    analyze_general(packets)
    analyze_sensor_data(packets)
    
    # Export
    if args.export_csv:
        export_csv(packets, args.export_csv)
    
    return 0


if __name__ == '__main__':
    exit(main())
