from cerberus import Validator
from npags.core.field_types import FIELD_TYPES

class SchemaValidator:
    """Valida se o arquivo YAML de configuração segue o padrão esperado."""
    
    def __init__(self):
        self.validator = Validator(self._get_schema())
        self.validator.allow_unknown = True # Permite campos extras (ex: metadados do usuário)

    def _get_schema(self):
        """Define as regras de validação."""
        
        # Lista de tipos válidos vindos do field_types.py
        valid_types = list(FIELD_TYPES.keys())

        # Schema para um campo individual (field)
        field_schema = {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'type': {'type': 'string', 'required': True, 'allowed': valid_types},
                'description': {'type': 'string'},
                'unit': {'type': 'string'},
                'scale': {'type': 'float'},
                'offset_value': {'type': 'number'},
                'expected': {'type': 'integer'},
                'format': {'type': 'string'},
                'mapping': {'type': 'dict'}
            }
        }

        # Schema principal
        return {
            'name': {'type': 'string', 'required': True},
            'version': {'type': 'string', 'required': True},
            'description': {'type': 'string'},
            
            # Validação do Header
            'header': {
                'type': 'dict',
                'schema': {
                    'fields': {
                        'type': 'list',
                        'schema': field_schema
                    }
                }
            },
            
            # Validação do Payload (Lista de Seções)
            'payload': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'name': {'type': 'string', 'required': True},
                        'is_array': {'type': 'boolean'},
                        'count': {'type': 'integer'},
                        'count_field': {'type': 'string'},
                        'fields': {
                            'type': 'list',
                            'required': True,
                            'schema': field_schema
                        }
                    }
                }
            }
        }

    def validate(self, config_data):
        """
        Valida o dicionário de configuração.
        Raises:
            ValueError: Se houver erros no schema.
        """
        if not self.validator.validate(config_data):
            # Formata os erros para ficar legível
            raise ValueError(f"Erro no Schema YAML: {self.validator.errors}")
        return True