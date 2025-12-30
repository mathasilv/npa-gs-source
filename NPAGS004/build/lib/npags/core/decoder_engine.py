#!/usr/bin/env python3
"""
Motor de decodificação de telemetria.
Responsável por interpretar bytes brutos baseados em arquivos de configuração YAML.
"""

import yaml
import json
from typing import Dict, Any, Tuple, List, Union, Optional
from pathlib import Path

from npags.core.field_types import FIELD_TYPES
from npags.core.schema_validator import SchemaValidator
# --- NOVAS EXCEÇÕES ---
from npags.core.exceptions import HeaderValidationError, DecoderError, SchemaValidationError

class DecoderEngine:
    """
    Processa pacotes binários transformando-os em dicionários Python.
    """
    
    config: Dict[str, Any]
    field_cache: Dict[str, Dict[str, Any]]

    def __init__(self, config_file: Union[str, Path]) -> None:
        try:
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)  # type: ignore
            
            # Validação Automática
            validator = SchemaValidator()
            try:
                validator.validate(self.config)
            except ValueError as e:
                # Converte erro do Cerberus para nossa exceção personalizada
                raise SchemaValidationError(str(e)) from e
                
            self._build_field_cache()
            
        except Exception as e:
            # Se falhar no init, propagamos o erro limpo
            raise DecoderError(f"Falha ao carregar decoder '{config_file}': {e}") from e
    
    def _build_field_cache(self) -> None:
        self.field_cache = {}
        header = self.config.get('header', {})
        if header and isinstance(header, dict):
            for field in header.get('fields', []):
                self.field_cache[field['name']] = field
        payload = self.config.get('payload', [])
        if isinstance(payload, list):
            for section in payload:
                for field in section.get('fields', []):
                    self.field_cache[field['name']] = field

    def validate_header(self, data: bytes) -> Tuple[Dict[str, Any], int]:
        """
        Valida o header do payload.
        
        Returns:
            Tuple[Dict, int]: (Dados do header, Offset final)
        
        Raises:
            HeaderValidationError: Se o header for inválido ou incompleto.
        """
        header_config = self.config.get('header', {})
        offset = 0
        header_data: Dict[str, Any] = {}
        
        if not header_config:
            return {}, 0
        
        try:
            for field in header_config.get('fields', []):
                field_name = field['name']
                field_type = field['type']
                
                decoder = FIELD_TYPES.get(field_type)
                if not decoder:
                    raise HeaderValidationError(f"Tipo de campo desconhecido: {field_type}")
                
                # Tenta decodificar
                value, offset = decoder.decode(data, offset, field)
                header_data[field_name] = value
                
                # Validação de valor esperado
                if 'expected' in field:
                    expected = field['expected']
                    if value != expected:
                        val_str = f"0x{value:X}" if isinstance(value, int) else str(value)
                        exp_str = f"0x{expected:X}" if isinstance(expected, int) else str(expected)
                        raise HeaderValidationError(
                            f"Valor incorreto em '{field_name}'. Esperado: {exp_str}, Recebido: {val_str}"
                        )
        
        except IndexError:
            raise HeaderValidationError("Payload muito curto (Buffer Underflow)")
        except Exception as e:
            # Se já for nossa exceção, apenas repassa
            if isinstance(e, HeaderValidationError):
                raise
            raise HeaderValidationError(f"Erro genérico no header: {str(e)}")
            
        return header_data, offset
    
    def decode_payload(self, payload: bytes) -> Dict[str, Any]:
        """
        Decodifica o payload completo.
        Captura exceções internas e retorna um dicionário de erro amigável para a GUI.
        """
        if not isinstance(payload, (bytes, bytearray)):
            return {
                'error': f'Tipo de entrada inválido: {type(payload).__name__}. Esperado: bytes.',
                'dump': str(payload)
            }
        
        data = payload
        result: Dict[str, Any] = {
            'decoder': self.config.get('name', 'Unknown'),
            'version': self.config.get('version', '1.0'),
            'header': {}
        }
        
        try:
            # 1. Validação do Header (agora lança exceção se falhar)
            header_data, offset = self.validate_header(data)
            result['header'] = header_data
            
            # 2. Processamento do Payload
            payload_sections = self.config.get('payload', [])
            for section in payload_sections:
                section_name = section['name']
                
                if section.get('is_array', False):
                    count = self._resolve_count(section, result)
                    array_items = []
                    for _ in range(count):
                        item_data = {}
                        for field in section['fields']:
                            value_info = self._decode_field(data, field, offset)
                            item_data[field['name']] = value_info['value']
                            offset = value_info['new_offset']
                        array_items.append(item_data)
                    result[section_name] = array_items
                else:
                    section_data = {}
                    for field in section['fields']:
                        value_info = self._decode_field(data, field, offset)
                        section_data[field['name']] = value_info['value']
                        offset = value_info['new_offset']
                    result[section_name] = section_data

        except HeaderValidationError as e:
            # Erros de header são esperados (ruído, pacote de outro satélite)
            result['error'] = f"Header Inválido: {str(e)}"
            return result
            
        except IndexError:
            # Buffer underflow durante o payload
            return {'error': 'Payload incompleto (Buffer Underflow)', 'partial': result}
            
        except Exception as e:
            # Outros erros
            return {'error': f'Erro de decodificação: {str(e)}', 'partial': result}
        
        return result

    def _resolve_count(self, section: Dict[str, Any], current_result: Dict[str, Any]) -> int:
        count_field = section.get('count_field')
        if count_field:
            count_parts = count_field.split('.')
            count_value: Any = current_result
            try:
                for part in count_parts:
                    if isinstance(count_value, dict):
                        count_value = count_value.get(part, 0)
                    else:
                        return 0
                return int(count_value)
            except (AttributeError, ValueError, TypeError):
                return 0
        return int(section.get('count', 1))

    def _decode_field(self, data: bytes, field_config: Dict[str, Any], offset: int) -> Dict[str, Any]:
        field_type = field_config['type']
        decoder = FIELD_TYPES.get(field_type)
        if not decoder:
            raise ValueError(f"Tipo de campo desconhecido: {field_type}")
        
        value, new_offset = decoder.decode(data, offset, field_config)
        return {'value': value, 'new_offset': new_offset}

    def _apply_visual_format(self, key: str, value: Any) -> Any:
        # (Mantém a mesma lógica de formatação visual)
        if key not in self.field_cache:
            return value
        field_config = self.field_cache[key]
        if 'mapping' in field_config:
            return field_config['mapping'].get(value, value)
        if 'format' in field_config and isinstance(value, (int, float)):
            try:
                return field_config['format'].format(value)
            except (ValueError, TypeError):
                pass
        return value

    def format_output(self, decoded_data: Dict[str, Any], output_format: str = 'text') -> str:
        # (Mantém a mesma lógica de format_output anterior)
        # O código de impressão é longo, mas não muda a lógica.
        # Copie o método format_output da versão anterior (Step 3).
        if output_format == 'json':
            return json.dumps(decoded_data, indent=2)
        elif output_format == 'text':
            output: List[str] = []
            output.append("=" * 60)
            output.append(f"Decoder: {decoded_data.get('decoder', 'Unknown')}")
            output.append(f"Version: {decoded_data.get('version', '1.0')}")
            if 'error' in decoded_data:
                output.append(f"\n[ERRO DE DECODIFICAÇÃO]")
                output.append(f"  {decoded_data['error']}")
            output.append("=" * 60)
            
            def print_dict(d: Dict[str, Any], indent: int = 0) -> None:
                prefix = "  " * indent
                for k, v in d.items():
                    if k in ['decoder', 'version', 'header', 'error', 'partial', 'matched_decoder']:
                        continue
                    if isinstance(v, list):
                        output.append(f"\n{prefix}[{k.upper()}]")
                        for i, item in enumerate(v, 1):
                            output.append(f"{prefix}  Item {i}:")
                            if isinstance(item, dict):
                                for sub_k, sub_v in item.items():
                                    formatted_v = self._apply_visual_format(sub_k, sub_v)
                                    output.append(f"{prefix}    {sub_k}: {formatted_v}")
                            else:
                                output.append(f"{prefix}    {item}")
                    elif isinstance(v, dict):
                        if indent == 0 and k == 'header': continue 
                        output.append(f"{prefix}{k}:")
                        print_dict(v, indent + 1)
                    else:
                        display_value = self._apply_visual_format(k, v)
                        output.append(f"{prefix}{k}: {display_value}")

            if 'header' in decoded_data and isinstance(decoded_data['header'], dict):
                output.append("\n[HEADER]")
                for k, v in decoded_data['header'].items():
                    val = self._apply_visual_format(k, v)
                    output.append(f"  {k}: {val}")
            
            print_dict(decoded_data)
            return '\n'.join(output)
        return str(decoded_data)