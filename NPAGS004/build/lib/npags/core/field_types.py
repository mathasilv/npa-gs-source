# src/npags/core/field_types.py
"""
Definição dos tipos de dados binários suportados pelos decoders.
Utiliza o módulo 'struct' para parsing eficiente e seguro.
"""

import struct

class FieldDecoder:
    """Classe base abstrata para decodificadores de campo."""
    
    @staticmethod
    def decode(data, offset, config):
        """
        Lê bytes do buffer e retorna o valor interpretado.
        
        Args:
            data (bytes): Buffer completo.
            offset (int): Posição atual do cursor.
            config (dict): Metadados do campo (ex: scale, offset_value).
            
        Returns:
            tuple: (valor_processado, novo_offset)
        """
        raise NotImplementedError
    
    @staticmethod
    def _apply_transform(value, config):
        """Aplica pós-processamento numérico (escala, offset, limites)."""
        if 'scale' in config:
            value = value * config['scale']
        if 'offset_value' in config:
            value = value + config['offset_value']
        if 'max' in config:
            value = min(value, config['max'])
        return value

# --- Implementações de Inteiros ---

class UInt8(FieldDecoder):
    """Inteiro sem sinal de 8 bits (1 byte)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('B', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 1
        except struct.error:
            raise IndexError("Buffer insuficiente para UInt8")

class Int8(FieldDecoder):
    """Inteiro com sinal de 8 bits (1 byte)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('b', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 1
        except struct.error:
            raise IndexError("Buffer insuficiente para Int8")

class UInt16BE(FieldDecoder):
    """Inteiro sem sinal 16 bits (Big Endian)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('>H', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 2
        except struct.error:
            raise IndexError("Buffer insuficiente para UInt16BE")

class Int16BE(FieldDecoder):
    """Inteiro com sinal 16 bits (Big Endian)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('>h', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 2
        except struct.error:
            raise IndexError("Buffer insuficiente para Int16BE")

class UInt32BE(FieldDecoder):
    """Inteiro sem sinal 32 bits (Big Endian)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('>I', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 4
        except struct.error:
            raise IndexError("Buffer insuficiente para UInt32BE")

class Int32BE(FieldDecoder):
    """Inteiro com sinal 32 bits (Big Endian)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('>i', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 4
        except struct.error:
            raise IndexError("Buffer insuficiente para Int32BE")

# --- Ponto Flutuante e Strings ---

class FloatBE(FieldDecoder):
    """Float IEEE 754 de 32 bits (Big Endian)."""
    @staticmethod
    def decode(data, offset, config):
        try:
            value = struct.unpack_from('>f', data, offset)[0]
            return FieldDecoder._apply_transform(value, config), offset + 4
        except struct.error:
            raise IndexError("Buffer insuficiente para FloatBE")

class String(FieldDecoder):
    """String ASCII de tamanho fixo."""
    @staticmethod
    def decode(data, offset, config):
        length = config.get('length', 1)
        if offset + length > len(data):
            raise IndexError(f"Buffer insuficiente para String[{length}]")
            
        # Ignora erros de decodificação para não quebrar o parser
        value = data[offset:offset+length].decode('ascii', errors='ignore')
        return value, offset + length

class Hex(FieldDecoder):
    """Representação hexadecimal crua (dump)."""
    @staticmethod
    def decode(data, offset, config):
        length = config.get('length', 1)
        if offset + length > len(data):
            raise IndexError(f"Buffer insuficiente para Hex[{length}]")
            
        value = data[offset:offset+length].hex().upper()
        return value, offset + length

class Array(FieldDecoder):
    """
    Lista de itens repetidos.
    O 'count' deve ser resolvido antes de chamar este decoder (no Engine).
    """
    @staticmethod
    def decode(data, offset, config):
        # Nota: A lógica complexa de arrays dinâmicos está no decoder_engine.py.
        # Este método serve para arrays simples de tamanho fixo definidos no próprio campo.
        count = config.get('count', 1)
        item_type = config.get('item_type')
        item_config = config.get('item_config', {})
        items = []
        
        decoder_class = FIELD_TYPES.get(item_type)
        if not decoder_class:
             raise ValueError(f"Tipo de item inválido no Array: {item_type}")

        for _ in range(count):
            value, offset = decoder_class.decode(data, offset, item_config)
            items.append(value)
        
        return items, offset

# Registro global de tipos
FIELD_TYPES = {
    'uint8': UInt8,
    'int8': Int8,
    'uint16be': UInt16BE,
    'int16be': Int16BE,
    'uint32be': UInt32BE,
    'int32be': Int32BE,
    'float': FloatBE,
    'string': String,
    'hex': Hex,
    'array': Array,
}