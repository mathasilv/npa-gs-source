#!/usr/bin/env python3
"""
Plota graficos de telemetria a partir dos logs
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter


def load_timeseries_data(log_file, decoder_filter=None):
    """Carrega dados em serie temporal"""
    data = defaultdict(lambda: {'timestamps': [], 'values': []})
    
    with open(log_file, 'r') as f:
        for line in f:
            try:
                packet = json.loads(line)
                
                # Filtro de decoder
                if decoder_filter and packet['data'].get('decoder') != decoder_filter:
                    continue
                
                if 'error' in packet['data']:
                    continue
                
                timestamp = datetime.fromisoformat(packet['ts'])
                
                # Extrai campos numericos
                for section_name, section_data in packet['data'].items():
                    if section_name in ['decoder', 'version', 'header']:
                        continue
                    
                    if isinstance(section_data, dict):
                        for field_name, field_value in section_data.items():
                            try:
                                value = float(field_value)
                                key = f"{section_name}.{field_name}"
                                data[key]['timestamps'].append(timestamp)
                                data[key]['values'].append(value)
                            except (ValueError, TypeError):
                                pass
            
            except json.JSONDecodeError:
                continue
    
    return dict(data)


def plot_data(data, output_file=None):
    """Plota graficos"""
    if not data:
        print("Nenhum dado para plotar")
        return
    
    n_fields = len(data)
    
    # Cria subplots
    fig, axes = plt.subplots(n_fields, 1, figsize=(12, 4*n_fields))
    
    if n_fields == 1:
        axes = [axes]
    
    fig.suptitle('Telemetria ao longo do tempo', fontsize=16, y=0.995)
    
    for ax, (field_name, field_data) in zip(axes, sorted(data.items())):
        ax.plot(field_data['timestamps'], field_data['values'], 
                marker='o', markersize=3, linestyle='-', linewidth=1)
        ax.set_ylabel(field_name)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    axes[-1].set_xlabel('Tempo')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Grafico salvo em: {output_file}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description='Plota graficos de telemetria')
    parser.add_argument(
        'log_file',
        nargs='?',
        default='data/logs/station_data.jsonl',
        help='Arquivo de log'
    )
    parser.add_argument(
        '--decoder',
        help='Filtrar por decoder especifico'
    )
    parser.add_argument(
        '--output', '-o',
        help='Salvar grafico em arquivo (ex: telemetry.png)'
    )
    parser.add_argument(
        '--fields',
        nargs='+',
        help='Plotar apenas campos especificos (ex: sensor_data.temperature)'
    )
    
    args = parser.parse_args()
    
    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Erro: Arquivo nao encontrado: {log_path}")
        return 1
    
    # Carrega dados
    data = load_timeseries_data(log_path, args.decoder)
    
    # Filtro de campos
    if args.fields:
        data = {k: v for k, v in data.items() if k in args.fields}
    
    if not data:
        print("Nenhum dado encontrado")
        return 1
    
    print(f"Campos encontrados: {', '.join(sorted(data.keys()))}")
    
    # Plota
    plot_data(data, args.output)
    
    return 0


if __name__ == '__main__':
    exit(main())
