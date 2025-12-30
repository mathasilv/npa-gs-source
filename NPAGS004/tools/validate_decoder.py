#!/usr/bin/env python3
"""
Valida schemas de decoder YAML
"""

import yaml
import argparse
from pathlib import Path


VALID_TYPES = {
    'uint8', 'uint16be', 'uint32be',
    'int8', 'int16be', 'int32be',
    'string', 'hex', 'array'
}


def validate_field(field, path):
    """Valida um campo individual"""
    errors = []
    
    if 'name' not in field:
        errors.append(f"{path}: campo sem 'name'")
    
    if 'type' not in field:
        errors.append(f"{path}: campo sem 'type'")
    elif field['type'] not in VALID_TYPES:
        errors.append(f"{path}: tipo invalido '{field['type']}'")
    
    return errors


def validate_schema(schema_path):
    """Valida schema completo"""
    errors = []
    
    try:
        with open(schema_path, 'r') as f:
            schema = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"Erro de sintaxe YAML: {e}"]
    except Exception as e:
        return [f"Erro ao ler arquivo: {e}"]
    
    # Valida campos obrigatorios
    if 'name' not in schema:
        errors.append("Campo 'name' ausente")
    
    if 'version' not in schema:
        errors.append("Campo 'version' ausente")
    
    # Valida header
    if 'header' in schema:
        header = schema['header']
        if 'fields' in header:
            for i, field in enumerate(header['fields']):
                errors.extend(validate_field(field, f"header.fields[{i}]"))
    
    # Valida payload
    if 'payload' not in schema:
        errors.append("Campo 'payload' ausente")
    else:
        for i, section in enumerate(schema['payload']):
            if 'name' not in section:
                errors.append(f"payload[{i}]: secao sem 'name'")
            
            if 'fields' in section:
                for j, field in enumerate(section['fields']):
                    errors.extend(validate_field(field, f"payload[{i}].fields[{j}]"))
    
    return errors


def main():
    parser = argparse.ArgumentParser(description='Valida schemas de decoder')
    parser.add_argument(
        'decoder',
        nargs='?',
        help='Nome do decoder ou caminho do arquivo'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Valida todos os decoders disponiveis'
    )
    
    args = parser.parse_args()
    
    if args.all:
        decoder_dir = Path('config/decoder_schemas')
        files = list(decoder_dir.glob('*.yaml'))
        
        if not files:
            print("Nenhum decoder encontrado")
            return 1
        
        all_valid = True
        for file in sorted(files):
            errors = validate_schema(file)
            if errors:
                print(f"\n{file.stem}:")
                for error in errors:
                    print(f"  - {error}")
                all_valid = False
            else:
                print(f"{file.stem}: OK")
        
        return 0 if all_valid else 1
    
    elif args.decoder:
        # Tenta como arquivo primeiro
        decoder_path = Path(args.decoder)
        if not decoder_path.exists():
            # Tenta como nome
            decoder_path = Path(f'config/decoder_schemas/{args.decoder}.yaml')
        
        if not decoder_path.exists():
            print(f"Erro: Decoder nao encontrado: {args.decoder}")
            return 1
        
        errors = validate_schema(decoder_path)
        
        if errors:
            print(f"Erros em {decoder_path}:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print(f"{decoder_path}: Valido")
            return 0
    
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    exit(main())
