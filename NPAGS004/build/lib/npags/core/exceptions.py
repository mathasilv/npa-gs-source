class DecoderError(Exception):
    """Exceção base para erros de decodificação."""
    pass

class HeaderValidationError(DecoderError):
    """Levantada quando o header é inválido (Magic Bytes errados, etc)."""
    pass

class SchemaValidationError(DecoderError):
    """Levantada quando o arquivo YAML tem formato inválido."""
    pass