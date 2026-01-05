class DecoderError(Exception):
    """Exceção base para erros de decodificação."""

class HeaderValidationError(DecoderError):
    """Levantada quando o header é inválido (Magic Bytes errados, etc)."""

class SchemaValidationError(DecoderError):
    """Levantada quando o arquivo YAML tem formato inválido."""
