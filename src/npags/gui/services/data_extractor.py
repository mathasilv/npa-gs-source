"""
Extrator agnóstico de dados de telemetria.

Extrai dados de pacotes decodificados de forma agnóstica,
sem assumir estrutura fixa - adapta-se ao schema do decoder.

Este serviço foi extraído de export_dialog.py e report_dialog.py
para eliminar duplicação de código.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class DataExtractor:
    """
    Extrator agnóstico de dados de telemetria.
    
    Processa pacotes decodificados e organiza os dados em buffers
    separados por fonte (principal, nós, sensores, etc).
    
    Attributes:
        data_buffer: Dados extraídos organizados por fonte e campo.
        timestamp_buffer: Timestamps correspondentes aos dados.
    """
    
    # Campos de metadados que devem ser ignorados na extração
    IGNORE_KEYS: frozenset[str] = frozenset({
        'decoder', 'version', 'header', '_meta', 
        'error', 'partial', 'matched_decoder', 'sync_word'
    })
    
    # Campos usados para identificação de nós (não são dados)
    ID_FIELDS: frozenset[str] = frozenset({
        'node_id', 'id', 'sensor_id'
    })
    
    def __init__(self) -> None:
        """Inicializa o extrator com buffers vazios."""
        self.data_buffer: dict[str, dict[str, list[Any]]] = {}
        self.timestamp_buffer: dict[str, dict[str, list[datetime]]] = {}
    
    def clear(self) -> None:
        """Limpa todos os buffers."""
        self.data_buffer.clear()
        self.timestamp_buffer.clear()
    
    def extract(self, data: dict[str, Any], timestamp: datetime) -> None:
        """
        Extrai dados de um pacote decodificado.
        
        Processa o pacote de forma agnóstica, detectando automaticamente
        seções de dados e arrays de nós/sensores.
        
        Args:
            data: Pacote decodificado (dicionário).
            timestamp: Timestamp do pacote.
        """
        for section_name, section_data in data.items():
            if section_name in self.IGNORE_KEYS:
                continue
            
            if isinstance(section_data, dict):
                # Seção com campos (ex: satellite_data, sensor_data, etc)
                self._extract_section_fields(section_data, timestamp)
            
            elif isinstance(section_data, list):
                # Array de itens (ex: relay_nodes, nodes, etc)
                self._extract_array_items(section_data, timestamp)
    
    def _extract_section_fields(
        self, 
        section_data: dict[str, Any], 
        timestamp: datetime
    ) -> None:
        """
        Extrai campos de uma seção para a fonte principal.
        
        Args:
            section_data: Dados da seção.
            timestamp: Timestamp do pacote.
        """
        source = "_principal"
        
        if source not in self.data_buffer:
            self.data_buffer[source] = {}
            self.timestamp_buffer[source] = {}
        
        target_data = self.data_buffer[source]
        target_ts = self.timestamp_buffer[source]
        
        for field_name, value in section_data.items():
            if isinstance(value, (int, float)):
                if field_name not in target_data:
                    target_data[field_name] = []
                    target_ts[field_name] = []
                target_data[field_name].append(value)
                target_ts[field_name].append(timestamp)
            
            elif isinstance(value, dict):
                # Sub-seção aninhada (ex: gps.latitude, gps.longitude)
                for sub_field, sub_value in value.items():
                    if isinstance(sub_value, (int, float)):
                        full_name = f"{field_name}_{sub_field}"
                        if full_name not in target_data:
                            target_data[full_name] = []
                            target_ts[full_name] = []
                        target_data[full_name].append(sub_value)
                        target_ts[full_name].append(timestamp)
    
    def _extract_array_items(
        self, 
        items: list[Any], 
        timestamp: datetime
    ) -> None:
        """
        Extrai itens de um array (nós, sensores, etc).
        
        Cada item do array é tratado como uma fonte separada,
        identificada pelo campo de ID (node_id, id, sensor_id).
        
        Args:
            items: Lista de itens (dicionários).
            timestamp: Timestamp do pacote.
        """
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            
            # Tenta identificar o item pelo ID
            node_id = None
            for id_field in self.ID_FIELDS:
                if id_field in item:
                    node_id = item[id_field]
                    break
            
            if node_id is None:
                node_id = i
            
            source = f"Node {node_id}"
            
            if source not in self.data_buffer:
                self.data_buffer[source] = {}
                self.timestamp_buffer[source] = {}
            
            target_data = self.data_buffer[source]
            target_ts = self.timestamp_buffer[source]
            
            for field_name, value in item.items():
                # Ignora campos de identificação
                if field_name in self.ID_FIELDS:
                    continue
                
                if isinstance(value, (int, float)):
                    if field_name not in target_data:
                        target_data[field_name] = []
                        target_ts[field_name] = []
                    target_data[field_name].append(value)
                    target_ts[field_name].append(timestamp)
    
    def get_data(self) -> dict[str, dict[str, list[Any]]]:
        """
        Retorna os dados extraídos.
        
        Returns:
            Dicionário {source_id: {field_name: [values]}}.
        """
        return self.data_buffer
    
    def get_timestamps(self) -> dict[str, dict[str, list[datetime]]]:
        """
        Retorna os timestamps dos dados extraídos.
        
        Returns:
            Dicionário {source_id: {field_name: [timestamps]}}.
        """
        return self.timestamp_buffer
    
    def get_source_ids(self) -> list[str]:
        """
        Retorna lista de IDs de fontes encontradas.
        
        Returns:
            Lista de source_ids ordenada.
        """
        return sorted(self.data_buffer.keys())
    
    def get_field_count(self, source_id: str) -> int:
        """
        Retorna quantidade de campos em uma fonte.
        
        Args:
            source_id: ID da fonte.
            
        Returns:
            Número de campos.
        """
        if source_id not in self.data_buffer:
            return 0
        return len(self.data_buffer[source_id])
    
    def get_point_count(self, source_id: str, field_name: str | None = None) -> int:
        """
        Retorna quantidade de pontos de dados.
        
        Args:
            source_id: ID da fonte.
            field_name: Nome do campo (opcional). Se None, soma todos.
            
        Returns:
            Número de pontos.
        """
        if source_id not in self.data_buffer:
            return 0
        
        source_data = self.data_buffer[source_id]
        
        if field_name is not None:
            if field_name in source_data:
                values = source_data[field_name]
                return len(values) if isinstance(values, list) else 0
            return 0
        
        # Soma todos os campos
        total = 0
        for values in source_data.values():
            if isinstance(values, list):
                total += len(values)
        return total
