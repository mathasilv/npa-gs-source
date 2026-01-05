"""
Gerenciador de dados do Dashboard.

Responsável por:
    - Armazenar dados em buffers por fonte (satélite, nós)
    - Processar pacotes recebidos
    - Gerenciar histórico de timestamps
    - Combinar dados de múltiplas fontes

Extraído de dashboard_view.py para reduzir complexidade.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set


class DashboardDataManager:
    """
    Gerenciador de buffers de dados do dashboard.
    
    Attributes:
        data_buffer: Dados por fonte {source_id: {field: [values]}}.
        timestamp_buffer: Timestamps por fonte {source_id: {field: [timestamps]}}.
        known_nodes: Conjunto de nós conhecidos.
        node_timestamps: Último timestamp por nó.
        history_limit: Limite de pontos por campo.
        current_node_filter: Filtro de nó atual.
    """
    
    # Campos exclusivos de nós relay (não vão para satélite)
    RELAY_ONLY_FIELDS: frozenset[str] = frozenset({
        'node_id', 'soil_moisture', 'ambient_temp', 'node_humidity', 
        'irrigation_status', 'rssi', 'timestamp'
    })
    
    # Campos de metadados a ignorar
    METADATA_FIELDS: frozenset[str] = frozenset({
        'decoder', 'version', '_meta', 'matched_decoder', 'sync_word'
    })
    
    # Mapeamento de campos do AgriNode
    FIELD_MAPPING: dict[str, str] = {
        'temperature': 'ambient_temp',
        'humidity': 'node_humidity',
    }
    
    def __init__(self, history_limit: int = 1000) -> None:
        """
        Inicializa o gerenciador.
        
        Args:
            history_limit: Limite de pontos por campo.
        """
        self.data_buffer: Dict[str, Dict[str, List[Any]]] = {}
        self.timestamp_buffer: Dict[str, Dict[str, List[datetime]]] = {}
        self.known_nodes: Set[str] = set()
        self.node_timestamps: Dict[str, datetime] = {}
        self.history_limit = history_limit
        self.current_node_filter = "Todos"
        self._default_history_limit = history_limit
    
    def clear(self) -> None:
        """Limpa todos os buffers."""
        self.data_buffer.clear()
        self.timestamp_buffer.clear()
        self.known_nodes.clear()
        self.node_timestamps.clear()
        self.current_node_filter = "Todos"
        self.history_limit = self._default_history_limit
    
    def process_packet(
        self, 
        data: Dict[str, Any], 
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Processa um pacote de dados recebido.
        
        Args:
            data: Dados decodificados.
            timestamp: Timestamp do pacote.
        """
        pkt_time = timestamp or datetime.now()
        
        # Armazena timestamp do satélite
        self.node_timestamps["_satellite"] = pkt_time
        
        # Processa dados do satélite
        self._store_satellite_data(data, pkt_time)
        
        # Extrai nós relay
        self._extract_relay_nodes(data, pkt_time)
    
    def _store_satellite_data(self, data: Dict[str, Any], timestamp: datetime) -> None:
        """
        Armazena dados do satélite no buffer principal.
        Detecta automaticamente se é pacote de nó direto ou satélite.
        """
        # Detecta se é pacote de nó direto
        decoder_name = data.get('decoder', '').lower()
        matched_decoder = data.get('matched_decoder', '').lower()
        
        is_node_packet = (
            'agrinode' in decoder_name or 
            'agrinode' in matched_decoder or
            'node_data' in data
        )
        
        if is_node_packet:
            self._store_node_direct_data(data, timestamp)
            return
        
        # Inicializa buffers do satélite
        if "_satellite" not in self.data_buffer:
            self.data_buffer["_satellite"] = {}
        if "_satellite" not in self.timestamp_buffer:
            self.timestamp_buffer["_satellite"] = {}
        
        target_buffer = self.data_buffer["_satellite"]
        ts_buffer = self.timestamp_buffer["_satellite"]
        
        # Extrai recursivamente
        self._recursive_extract(data, target_buffer, ts_buffer, timestamp)
    
    def _recursive_extract(
        self,
        d: Dict[str, Any],
        target_buffer: Dict[str, Any],
        ts_buffer: Dict[str, List[datetime]],
        timestamp: datetime,
        prefix: str = ""
    ) -> None:
        """Extrai dados recursivamente de um dicionário."""
        for key, value in d.items():
            # Ignora arrays de nós relay
            if key == 'relay_nodes' or 'node_data' in key.lower():
                continue
            
            # Ignora metadados
            if key in self.METADATA_FIELDS:
                continue
            
            if isinstance(value, dict):
                self._recursive_extract(value, target_buffer, ts_buffer, timestamp, f"{prefix}{key}.")
            elif isinstance(value, list):
                continue  # Ignora listas
            elif isinstance(value, (int, float)):
                # Ignora campos exclusivos de relay
                if key in self.RELAY_ONLY_FIELDS:
                    continue
                
                if key not in target_buffer:
                    target_buffer[key] = []
                    ts_buffer[key] = []
                
                target_buffer[key].append(value)
                ts_buffer[key].append(timestamp)
                
                # Aplica limite
                if len(target_buffer[key]) > self.history_limit:
                    target_buffer[key].pop(0)
                    ts_buffer[key].pop(0)
                
                target_buffer[f"{key}_last"] = value
            else:
                target_buffer[f"{key}_last"] = value
    
    def _store_node_direct_data(self, data: Dict[str, Any], timestamp: datetime) -> None:
        """Armazena dados de pacotes diretos de nós (AgriNode-Direct)."""
        node_data = data.get('node_data', {})
        if not node_data:
            return
        
        node_id = node_data.get('node_id')
        if node_id is None:
            return
        
        node_id_str = f"Node {node_id}"
        
        # Registra como nó conhecido
        self.known_nodes.add(node_id_str)
        self.node_timestamps[node_id_str] = timestamp
        
        # Inicializa buffers
        if node_id_str not in self.data_buffer:
            self.data_buffer[node_id_str] = {}
        if node_id_str not in self.timestamp_buffer:
            self.timestamp_buffer[node_id_str] = {}
        
        target_buffer = self.data_buffer[node_id_str]
        ts_buffer = self.timestamp_buffer[node_id_str]
        
        for key, value in node_data.items():
            if isinstance(value, (int, float)):
                # Aplica mapeamento de nomes
                mapped_key = self.FIELD_MAPPING.get(key, key)
                
                if mapped_key not in target_buffer:
                    target_buffer[mapped_key] = []
                    ts_buffer[mapped_key] = []
                
                target_buffer[mapped_key].append(value)
                ts_buffer[mapped_key].append(timestamp)
                
                if len(target_buffer[mapped_key]) > self.history_limit:
                    target_buffer[mapped_key].pop(0)
                    ts_buffer[mapped_key].pop(0)
                
                target_buffer[f"{mapped_key}_last"] = value
    
    def _extract_relay_nodes(self, data: Dict[str, Any], timestamp: datetime) -> None:
        """Extrai nós relay do pacote e registra como nós separados."""
        for section_name, section_data in data.items():
            if 'relay' in section_name.lower() and isinstance(section_data, list):
                for node_data in section_data:
                    if isinstance(node_data, dict):
                        relay_node_id = node_data.get('node_id', node_data.get('id'))
                        if relay_node_id is not None:
                            self._store_relay_node(relay_node_id, node_data, timestamp)
    
    def _store_relay_node(
        self, 
        node_id: Any, 
        node_data: Dict[str, Any], 
        timestamp: datetime
    ) -> None:
        """Armazena dados de um nó relay."""
        node_id_str = f"Node {node_id}"
        
        self.known_nodes.add(node_id_str)
        self.node_timestamps[node_id_str] = timestamp
        
        if node_id_str not in self.data_buffer:
            self.data_buffer[node_id_str] = {}
        if node_id_str not in self.timestamp_buffer:
            self.timestamp_buffer[node_id_str] = {}
        
        target_buffer = self.data_buffer[node_id_str]
        ts_buffer = self.timestamp_buffer[node_id_str]
        
        for key, value in node_data.items():
            if isinstance(value, (int, float)):
                if key not in target_buffer:
                    target_buffer[key] = []
                    ts_buffer[key] = []
                
                target_buffer[key].append(value)
                ts_buffer[key].append(timestamp)
                
                if len(target_buffer[key]) > self.history_limit:
                    target_buffer[key].pop(0)
                    ts_buffer[key].pop(0)
                
                target_buffer[f"{key}_last"] = value
    
    def get_combined_data(self) -> tuple[Dict[str, Any], Dict[str, List[datetime]]]:
        """
        Obtém dados combinados: satélite + nó selecionado.
        
        Returns:
            Tupla (dados, timestamps).
        """
        # Começa com dados do satélite
        result = {}
        result_ts = {}
        
        sat_data = self.data_buffer.get("_satellite", {})
        sat_ts = self.timestamp_buffer.get("_satellite", {})
        result.update(sat_data)
        result_ts.update(sat_ts)
        
        # Adiciona dados do nó selecionado
        node_data, node_ts = self._get_node_data()
        
        # Adiciona sem sobrescrever dados do satélite
        for key, value in node_data.items():
            if key not in result:
                result[key] = value
        
        for key, value in node_ts.items():
            if key not in result_ts:
                result_ts[key] = value
        
        return result, result_ts
    
    def _get_node_data(self) -> tuple[Dict[str, Any], Dict[str, List[datetime]]]:
        """Obtém dados do nó selecionado ou mais recente."""
        if self.current_node_filter == "Todos":
            # Pega o nó mais recente
            latest_node = None
            latest_time = None
            
            for node_id, ts in self.node_timestamps.items():
                if node_id == "_satellite":
                    continue
                if latest_time is None or ts > latest_time:
                    latest_time = ts
                    latest_node = node_id
            
            if latest_node and latest_node in self.data_buffer:
                return (
                    self.data_buffer[latest_node],
                    self.timestamp_buffer.get(latest_node, {})
                )
        elif self.current_node_filter in self.data_buffer:
            return (
                self.data_buffer[self.current_node_filter],
                self.timestamp_buffer.get(self.current_node_filter, {})
            )
        
        return {}, {}
    
    def get_last_satellite_timestamp(self) -> Optional[datetime]:
        """Retorna o último timestamp do satélite."""
        return self.node_timestamps.get("_satellite")
    
    def get_node_count(self) -> int:
        """Retorna quantidade de nós conhecidos (exceto satélite)."""
        return len([n for n in self.known_nodes if n != "_satellite"])
    
    def set_node_filter(self, node_filter: str) -> None:
        """Define o filtro de nó atual."""
        self.current_node_filter = node_filter
    
    def set_history_limit(self, limit: int) -> None:
        """Define o limite de histórico."""
        self.history_limit = limit
