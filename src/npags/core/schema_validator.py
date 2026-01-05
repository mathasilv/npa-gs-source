"""Validador de schemas YAML para decoders."""

import logging
from typing import Any

from cerberus import Validator

from npags.core.field_types import FIELD_TYPES

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Valida se o arquivo YAML de configuração segue o padrão esperado.

    Utiliza Cerberus para validação estrutural do schema.
    """

    def __init__(self) -> None:
        self.validator = Validator(self._get_schema())
        self.validator.allow_unknown = True  # Permite campos extras

    def _get_schema(self) -> dict[str, Any]:
        """Define as regras de validação."""
        
        # Lista de tipos válidos vindos do field_types.py
        valid_types = list(FIELD_TYPES.keys())

        # Schema para um campo individual (field)
        field_schema = {
            'type': 'dict',
            'schema': {
                # Identificação
                'name': {'type': 'string', 'required': True},
                'type': {'type': 'string', 'required': True, 'allowed': valid_types},
                'description': {'type': 'string'},
                # Transformações numéricas
                'scale': {'type': 'float'},
                'offset': {'type': 'number'},  # Preferido
                'offset_value': {'type': 'number'},  # Alias (compatibilidade)
                'min': {'type': 'number'},
                'max': {'type': 'number'},
                # Validação
                'expected': {'type': 'integer'},
                # Apresentação
                'unit': {'type': 'string'},
                'format': {'type': 'string'},
                'mapping': {'type': 'dict'},
                'colors': {'type': 'dict'},
                # Widget
                'widget': {'type': 'string'},
                'plot_color': {'type': 'string'},
                'role': {'type': 'string'},
                # Campos especiais
                'length': {'type': 'integer'},  # Para string/hex
                'count': {'type': 'integer'},  # Para array
                'item_type': {'type': 'string'},  # Para array
                'item_config': {'type': 'dict'},  # Para array
                # Map widget
                'lat_source': {'type': 'string'},
                'lon_source': {'type': 'string'},
            },
        }

        # Schema para seção do payload
        section_schema = {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'is_array': {'type': 'boolean'},
                'count': {'type': 'integer'},
                'count_field': {'type': 'string'},
                'optional': {'type': 'boolean'},
                'condition': {'type': 'string'},
                'fields': {
                    'type': 'list',
                    'required': True,
                    'schema': field_schema,
                },
            },
        }

        # Schema principal
        return {
            # Metadados obrigatórios
            'name': {'type': 'string', 'required': True},
            'version': {'type': 'string', 'required': True},
            # Metadados opcionais
            'description': {'type': 'string'},
            'author': {'type': 'string'},
            # Configuração de protocolo
            'meta': {
                'type': 'dict',
                'schema': {
                    'endian': {'type': 'string', 'allowed': ['big', 'little']},
                    'min_size': {'type': 'integer'},
                    'max_size': {'type': 'integer'},
                    'has_crc': {'type': 'boolean'},
                    'trailer_size': {'type': 'integer'},
                },
            },
            # Header
            'header': {
                'type': 'dict',
                'schema': {
                    'fields': {
                        'type': 'list',
                        'schema': field_schema,
                    },
                },
            },
            # Payload (obrigatório)
            'payload': {
                'type': 'list',
                'required': True,
                'schema': section_schema,
            },
        }

    def validate(self, config_data: dict[str, Any]) -> bool:
        """
        Valida o dicionário de configuração.
        
        Args:
            config_data: Dicionário com a configuração do decoder.
            
        Returns:
            True se válido.
            
        Raises:
            ValueError: Se houver erros no schema.
        """
        if not self.validator.validate(config_data):
            logger.error("Erro de validação do schema: %s", self.validator.errors)
            raise ValueError(f"Erro no Schema YAML: {self.validator.errors}")

        logger.debug("Schema validado com sucesso: %s", config_data.get('name'))
        return True
