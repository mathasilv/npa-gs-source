# src/npags/core/field_types.py
"""
Definição dos tipos de dados binários suportados pelos decoders.
Utiliza o módulo 'struct' para parsing eficiente e seguro.

Refatorado: Usa factory pattern para eliminar duplicação de código.
"""

from __future__ import annotations

import logging
import struct
from typing import Any

logger = logging.getLogger(__name__)


class FieldDecoder:
    """Classe base abstrata para decodificadores de campo."""
    
    @staticmethod
    def decode(data: bytes, offset: int, config: dict[str, Any]) -> tuple[Any, int]:
        """
        Lê bytes do buffer e retorna o valor interpretado.
        
        Args:
            data: Buffer completo.
            offset: Posição atual do cursor.
            config: Metadados do campo (ex: scale, offset).

        Returns:
            Tupla (valor_processado, novo_offset)
        """
        raise NotImplementedError
    
    @staticmethod
    def _apply_transform(value: float, config: dict[str, Any]) -> float:
        """Aplica pós-processamento numérico (escala, offset, limites)."""
        if 'scale' in config:
            value = value * config['scale']
        # Suporta tanto 'offset' quanto 'offset_value' para compatibilidade
        if 'offset' in config:
            value = value + config['offset']
        elif 'offset_value' in config:
            value = value + config['offset_value']
        if 'max' in config:
            value = min(value, config['max'])
        if 'min' in config:
            value = max(value, config['min'])
        return value
    
    @staticmethod
    def _has_decimal_transform(config: dict[str, Any]) -> bool:
        """Verifica se a transformação produz valores decimais."""
        if 'scale' in config:
            scale = config['scale']
            if scale != int(scale):
                return True
        
        offset = config.get('offset', config.get('offset_value'))
        if offset is not None and offset != int(offset):
            return True
        
        return False


# =============================================================================
# FACTORY: Gera classes de decoder para tipos inteiros
# =============================================================================

def _create_int_decoder(
    fmt: str,
    size: int,
    type_name: str
) -> type[FieldDecoder]:
    """
    Factory que cria classes de decoder para tipos inteiros.

    Args:
        fmt: Formato struct (ex: '>H' para uint16 big-endian)
        size: Tamanho em bytes
        type_name: Nome do tipo para mensagens de erro

    Returns:
        Classe de decoder configurada
    """

    class IntDecoder(FieldDecoder):
        __doc__ = f"Decoder para {type_name} ({size} bytes)."

        @staticmethod
        def decode(
            data: bytes, offset: int, config: dict[str, Any]
        ) -> tuple[int | float, int]:
            try:
                value = struct.unpack_from(fmt, data, offset)[0]
                result = FieldDecoder._apply_transform(value, config)
                # Mantém como int se não houver transformação decimal
                if (
                    not FieldDecoder._has_decimal_transform(config)
                    and result == int(result)
                ):
                    return int(result), offset + size
                return result, offset + size
            except struct.error as e:
                raise IndexError(f"Buffer insuficiente para {type_name}") from e

    IntDecoder.__name__ = type_name
    IntDecoder.__qualname__ = type_name
    return IntDecoder


def _create_float_decoder(fmt: str, size: int, type_name: str) -> type[FieldDecoder]:
    """
    Factory que cria classes de decoder para tipos float.

    Args:
        fmt: Formato struct (ex: '>f' para float big-endian)
        size: Tamanho em bytes
        type_name: Nome do tipo para mensagens de erro

    Returns:
        Classe de decoder configurada
    """

    class FloatDecoder(FieldDecoder):
        __doc__ = f"Decoder para {type_name} ({size} bytes)."

        @staticmethod
        def decode(
            data: bytes, offset: int, config: dict[str, Any]
        ) -> tuple[float, int]:
            try:
                value = struct.unpack_from(fmt, data, offset)[0]
                return FieldDecoder._apply_transform(value, config), offset + size
            except struct.error as e:
                raise IndexError(f"Buffer insuficiente para {type_name}") from e

    FloatDecoder.__name__ = type_name
    FloatDecoder.__qualname__ = type_name
    return FloatDecoder


# =============================================================================
# TIPOS GERADOS VIA FACTORY
# =============================================================================

# 8-bit
UInt8 = _create_int_decoder('B', 1, 'UInt8')
Int8 = _create_int_decoder('b', 1, 'Int8')

# 16-bit Big Endian
UInt16BE = _create_int_decoder('>H', 2, 'UInt16BE')
Int16BE = _create_int_decoder('>h', 2, 'Int16BE')

# 16-bit Little Endian
UInt16LE = _create_int_decoder('<H', 2, 'UInt16LE')
Int16LE = _create_int_decoder('<h', 2, 'Int16LE')

# 32-bit Big Endian
UInt32BE = _create_int_decoder('>I', 4, 'UInt32BE')
Int32BE = _create_int_decoder('>i', 4, 'Int32BE')

# 32-bit Little Endian
UInt32LE = _create_int_decoder('<I', 4, 'UInt32LE')
Int32LE = _create_int_decoder('<i', 4, 'Int32LE')

# 64-bit (novo)
UInt64BE = _create_int_decoder('>Q', 8, 'UInt64BE')
Int64BE = _create_int_decoder('>q', 8, 'Int64BE')
UInt64LE = _create_int_decoder('<Q', 8, 'UInt64LE')
Int64LE = _create_int_decoder('<q', 8, 'Int64LE')

# Float
FloatBE = _create_float_decoder('>f', 4, 'FloatBE')
FloatLE = _create_float_decoder('<f', 4, 'FloatLE')

# Double (novo)
DoubleBE = _create_float_decoder('>d', 8, 'DoubleBE')
DoubleLE = _create_float_decoder('<d', 8, 'DoubleLE')


# =============================================================================
# TIPOS ESPECIAIS (não gerados por factory)
# =============================================================================


class String(FieldDecoder):
    """String ASCII de tamanho fixo."""

    @staticmethod
    def decode(data: bytes, offset: int, config: dict[str, Any]) -> tuple[str, int]:
        length = config.get('length', 1)
        if offset + length > len(data):
            raise IndexError(f"Buffer insuficiente para String[{length}]")
        value = data[offset : offset + length].decode('ascii', errors='ignore')
        return value.rstrip('\x00'), offset + length


class Hex(FieldDecoder):
    """Representação hexadecimal crua (dump)."""

    @staticmethod
    def decode(data: bytes, offset: int, config: dict[str, Any]) -> tuple[str, int]:
        length = config.get('length', 1)
        if offset + length > len(data):
            raise IndexError(f"Buffer insuficiente para Hex[{length}]")
        value = data[offset : offset + length].hex().upper()
        return value, offset + length


class Array(FieldDecoder):
    """Lista de itens repetidos."""

    @staticmethod
    def decode(
        data: bytes, offset: int, config: dict[str, Any]
    ) -> tuple[list[Any], int]:
        count = config.get('count', 1)
        item_type: str = config.get('item_type', 'uint8')
        item_config: dict[str, Any] = config.get('item_config', {})
        items: list[Any] = []

        decoder_class = FIELD_TYPES.get(item_type)
        if not decoder_class:
            raise ValueError(f"Tipo de item inválido no Array: {item_type}")

        for _ in range(count):
            value, offset = decoder_class.decode(data, offset, item_config)
            items.append(value)
        
        return items, offset


class Virtual(FieldDecoder):
    """Campo virtual que não consome bytes."""

    @staticmethod
    def decode(data: bytes, offset: int, config: dict[str, Any]) -> tuple[None, int]:
        return None, offset


# =============================================================================
# REGISTRO GLOBAL DE TIPOS
# =============================================================================

FIELD_TYPES: dict[str, type[FieldDecoder]] = {
    # 8-bit
    'uint8': UInt8,
    'int8': Int8,
    # 16-bit Big Endian
    'uint16be': UInt16BE,
    'int16be': Int16BE,
    'uint16': UInt16BE,  # Alias (default BE)
    'int16': Int16BE,  # Alias (default BE)
    # 16-bit Little Endian
    'uint16le': UInt16LE,
    'int16le': Int16LE,
    # 32-bit Big Endian
    'uint32be': UInt32BE,
    'int32be': Int32BE,
    'uint32': UInt32BE,  # Alias (default BE)
    'int32': Int32BE,  # Alias (default BE)
    # 32-bit Little Endian
    'uint32le': UInt32LE,
    'int32le': Int32LE,
    # 64-bit Big Endian
    'uint64be': UInt64BE,
    'int64be': Int64BE,
    'uint64': UInt64BE,  # Alias (default BE)
    'int64': Int64BE,  # Alias (default BE)
    # 64-bit Little Endian
    'uint64le': UInt64LE,
    'int64le': Int64LE,
    # Float
    'float': FloatBE,
    'float32': FloatBE,  # Alias
    'float32be': FloatBE,
    'float32le': FloatLE,
    'floatle': FloatLE,
    # Double
    'double': DoubleBE,
    'float64': DoubleBE,  # Alias
    'float64be': DoubleBE,
    'float64le': DoubleLE,
    'doublele': DoubleLE,
    # Outros
    'string': String,
    'hex': Hex,
    'array': Array,
    'virtual': Virtual,
}


def get_supported_types() -> list[str]:
    """Retorna lista de tipos suportados."""
    return list(FIELD_TYPES.keys())


def register_type(name: str, decoder_class: type[FieldDecoder]) -> None:
    """
    Registra um novo tipo de campo.

    Args:
        name: Nome do tipo (usado no YAML)
        decoder_class: Classe que implementa FieldDecoder
    """
    if name in FIELD_TYPES:
        logger.warning("Sobrescrevendo tipo existente: %s", name)
    FIELD_TYPES[name] = decoder_class
    logger.debug("Tipo registrado: %s", name)
