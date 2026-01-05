#!/usr/bin/env python3
"""
Motor de decodificação de telemetria.
Responsável por interpretar bytes brutos baseados em arquivos de configuração YAML.
"""

import json
from pathlib import Path
from typing import Any

import yaml

# --- NOVAS EXCEÇÕES ---
from npags.core.exceptions import DecoderError, HeaderValidationError, SchemaValidationError
from npags.core.field_types import FIELD_TYPES
from npags.core.schema_validator import SchemaValidator


class DecoderEngine:
    """
    Processa pacotes binários transformando-os em dicionários Python.
    """

    config: dict[str, Any]
    field_cache: dict[str, dict[str, Any]]

    def __init__(self, config_file: str | Path) -> None:
        try:
            with open(config_file) as f:
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
        """Constrói cache de campos para acesso rápido e widgets."""
        self.field_cache = {}

        # Processa campos do header
        header = self.config.get('header', {})
        if header and isinstance(header, dict):
            for field in header.get('fields', []):
                self.field_cache[field['name']] = field.copy()

        # Processa campos do payload (incluindo seções aninhadas)
        payload = self.config.get('payload', [])
        if isinstance(payload, list):
            for section in payload:
                if not isinstance(section, dict):
                    continue
                for field in section.get('fields', []):
                    if isinstance(field, dict) and 'name' in field:
                        # Copia todas as propriedades do campo
                        self.field_cache[field['name']] = field.copy()


    def _find_sync_word(self, data: bytes) -> int:
        """
        Busca o sync_word no payload e retorna o offset onde comeca.
        Lida com pacotes que tem preambulo/padding no inicio (comum em SDR).
        """
        header_config = self.config.get('header', {})
        if not header_config:
            return 0

        for field in header_config.get('fields', []):
            if field.get('name') == 'sync_word' and 'expected' in field:
                expected = field['expected']
                if isinstance(expected, int):
                    sync_bytes = expected.to_bytes(2, byteorder='big')
                    idx = data.find(sync_bytes)
                    if idx >= 0:
                        return idx
        return 0

    def validate_header(self, data: bytes) -> tuple[dict[str, Any], int]:
        """
        Valida o header do payload.

        Returns:
            Tuple[Dict, int]: (Dados do header, Offset final)

        Raises:
            HeaderValidationError: Se o header for inválido ou incompleto.
        """
        header_config = self.config.get('header', {})
        offset = self._find_sync_word(data)
        header_data: dict[str, Any] = {}

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

    def decode_payload(self, payload: bytes) -> dict[str, Any]:
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
        payload_size = len(payload)

        result: dict[str, Any] = {
            'decoder': self.config.get('name', 'Unknown'),
            'version': self.config.get('version', '1.0'),
            'header': {},
            '_meta': {
                'payload_size': payload_size
            }
        }

        try:
            # 1. Validação do Header (agora lança exceção se falhar)
            header_data, offset = self.validate_header(data)
            result['header'] = header_data

            # Recalcula payload_size efetivo (desconta preambulo/padding e trailer)
            sync_offset = self._find_sync_word(data)
            trailer_size = self.config.get('meta', {}).get('trailer_size', 0)
            effective_payload_size = len(data) - sync_offset - trailer_size
            result['_meta']['payload_size'] = effective_payload_size
            result['_meta']['sync_offset'] = sync_offset
            result['_meta']['trailer_size'] = trailer_size

            # 2. Processamento do Payload
            payload_sections = self.config.get('payload', [])
            for section in payload_sections:
                section_name = section['name']

                # Verifica condição da seção (ex: "payload_size > 34")
                effective_size = result['_meta'].get('payload_size', payload_size)
                if not self._check_section_condition(section, effective_size, result):
                    continue

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

    def _check_section_condition(self, section: dict[str, Any], payload_size: int, result: dict[str, Any]) -> bool:
        """
        Verifica se uma seção deve ser processada baseado em sua condição.

        Suporta condições como:
            - "payload_size > 36"
            - "payload_size >= 44"
            - "payload_size == 36"

        Args:
            section: Configuração da seção
            payload_size: Tamanho do payload em bytes
            result: Resultado parcial da decodificação

        Returns:
            True se a seção deve ser processada, False caso contrário
        """
        condition = section.get('condition')

        if not condition:
            return True

        # Parse simples de condições
        try:
            # Substitui variáveis conhecidas
            expr = condition.replace('payload_size', str(payload_size))

            # Avalia a expressão de forma segura
            # Suporta apenas comparações simples
            if '>' in expr and '>=' not in expr:
                parts = expr.split('>')
                return int(parts[0].strip()) > int(parts[1].strip())
            elif '>=' in expr:
                parts = expr.split('>=')
                return int(parts[0].strip()) >= int(parts[1].strip())
            elif '<' in expr and '<=' not in expr:
                parts = expr.split('<')
                return int(parts[0].strip()) < int(parts[1].strip())
            elif '<=' in expr:
                parts = expr.split('<=')
                return int(parts[0].strip()) <= int(parts[1].strip())
            elif '==' in expr:
                parts = expr.split('==')
                return int(parts[0].strip()) == int(parts[1].strip())
            elif '!=' in expr:
                parts = expr.split('!=')
                return int(parts[0].strip()) != int(parts[1].strip())
            else:
                # Condição não reconhecida, assume True
                return True
        except (ValueError, IndexError):
            # Erro no parse, assume True
            return True

    def _resolve_count(self, section: dict[str, Any], current_result: dict[str, Any]) -> int:
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

    def _decode_field(self, data: bytes, field_config: dict[str, Any], offset: int) -> dict[str, Any]:
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

    def format_output(self, decoded_data: dict[str, Any], output_format: str = 'text') -> str:
        # (Mantém a mesma lógica de format_output anterior)
        # O código de impressão é longo, mas não muda a lógica.
        # Copie o método format_output da versão anterior (Step 3).
        if output_format == 'json':
            return json.dumps(decoded_data, indent=2)
        elif output_format == 'text':
            output: list[str] = []
            output.append("=" * 60)
            output.append(f"Decoder: {decoded_data.get('decoder', 'Unknown')}")
            output.append(f"Version: {decoded_data.get('version', '1.0')}")
            if 'error' in decoded_data:
                output.append("\n[ERRO DE DECODIFICAÇÃO]")
                output.append(f"  {decoded_data['error']}")
            output.append("=" * 60)

            def print_dict(d: dict[str, Any], indent: int = 0) -> None:
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
