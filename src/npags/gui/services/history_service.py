"""
Serviço de carregamento de histórico de telemetria.

Carrega dados do arquivo de log JSONL, filtrando por decoder e período.
Este serviço foi extraído de export_dialog.py e report_dialog.py
para eliminar duplicação de código.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from npags.core.decoder_engine import DecoderEngine
from npags.core.logger import get_log_directory
from npags.decoders.loader import DecoderLoader
from npags.gui.services.data_extractor import DataExtractor

logger = logging.getLogger(__name__)


@dataclass
class HistoryFilter:
    """Filtros para carregamento de histórico."""
    
    decoder_name: str
    start_time: datetime
    end_time: datetime
    limit: int = 0  # 0 = sem limite
    
    def matches_time(self, timestamp: datetime) -> bool:
        """Verifica se o timestamp está dentro do período."""
        return self.start_time <= timestamp <= self.end_time


@dataclass
class HistoryLoadResult:
    """Resultado do carregamento de histórico."""
    
    success: bool
    record_count: int
    error_message: str = ""
    extractor: DataExtractor | None = None


class HistoryService:
    """
    Serviço para carregamento de dados históricos.
    
    Encapsula a lógica de:
    - Localizar arquivo de log
    - Carregar e validar decoder
    - Ler e filtrar registros do JSONL
    - Extrair dados de forma agnóstica
    
    Attributes:
        engine: DecoderEngine carregado (após load_decoder).
        decoder_display_name: Nome do decoder para filtrar registros.
    """
    
    def __init__(self) -> None:
        """Inicializa o serviço."""
        self.engine: DecoderEngine | None = None
        self.decoder_display_name: str = ""
        self._loader = DecoderLoader()
    
    def get_available_decoders(self) -> list[str]:
        """
        Retorna lista de decoders disponíveis.
        
        Returns:
            Lista de nomes de decoders.
        """
        try:
            return self._loader.scan_decoders()
        except Exception as e:
            logger.warning("Erro ao escanear decoders: %s", e)
            return []
    
    def load_decoder(self, decoder_name: str) -> tuple[bool, str]:
        """
        Carrega um decoder pelo nome.
        
        Args:
            decoder_name: Nome do decoder.
            
        Returns:
            Tupla (sucesso, mensagem_erro).
        """
        try:
            path = self._loader.find_decoder_path(decoder_name)
            if path is None:
                return False, f"Decoder '{decoder_name}' não encontrado"
            self.engine = DecoderEngine(path)
            self.decoder_display_name = self.engine.config.get('name', decoder_name)
            return True, ""
        except Exception as e:
            self.engine = None
            self.decoder_display_name = ""
            return False, str(e)
    
    def get_log_path(self) -> Path | None:
        """
        Retorna o caminho do arquivo de log.
        
        Returns:
            Path do arquivo ou None se não existir.
        """
        log_dir = get_log_directory()
        log_path = log_dir / "station_data.jsonl"
        
        if log_path.exists():
            return log_path
        return None
    
    def load_history(
        self,
        filters: HistoryFilter,
        progress_callback: Callable[[int], None] | None = None
    ) -> HistoryLoadResult:
        """
        Carrega dados históricos do arquivo de log.
        
        Args:
            filters: Filtros de carregamento.
            progress_callback: Callback para progresso (recebe count).
            
        Returns:
            HistoryLoadResult com os dados carregados.
        """
        # Verifica se o decoder está carregado
        if not self.engine:
            success, error = self.load_decoder(filters.decoder_name)
            if not success:
                return HistoryLoadResult(
                    success=False,
                    record_count=0,
                    error_message=f"Falha ao carregar decoder: {error}"
                )
        
        # Verifica arquivo de log
        log_path = self.get_log_path()
        if not log_path:
            return HistoryLoadResult(
                success=False,
                record_count=0,
                error_message="Arquivo de histórico não encontrado. Inicie uma sessão de captura primeiro."
            )
        
        # Carrega dados
        extractor = DataExtractor()
        count = 0
        limit = filters.limit if filters.limit > 0 else float('inf')
        
        try:
            with open(log_path, encoding='utf-8') as f:
                for line in f:
                    if count >= limit:
                        break
                    
                    try:
                        record = json.loads(line)
                        
                        # Verifica timestamp
                        if 'ts' in record:
                            ts = datetime.fromisoformat(record['ts'])
                            if not filters.matches_time(ts):
                                continue
                        else:
                            ts = datetime.now()
                        
                        if 'data' not in record:
                            continue
                        
                        data = record['data']
                        
                        # Ignora registros com erro
                        if 'error' in data:
                            continue
                        
                        # Filtra pelo decoder selecionado
                        record_decoder = data.get('decoder', '')
                        if record_decoder != self.decoder_display_name:
                            continue
                        
                        # Extrai dados
                        extractor.extract(data, ts)
                        count += 1
                        
                        # Callback de progresso
                        if progress_callback and count % 100 == 0:
                            progress_callback(count)
                    
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            
            return HistoryLoadResult(
                success=True,
                record_count=count,
                extractor=extractor
            )
        
        except Exception as e:
            logger.exception("Erro ao carregar histórico")
            return HistoryLoadResult(
                success=False,
                record_count=count,
                error_message=str(e)
            )
    
    def get_field_cache(self) -> dict:
        """
        Retorna o field_cache do decoder carregado.
        
        Returns:
            Dicionário com configurações dos campos.
        """
        if self.engine and hasattr(self.engine, 'field_cache'):
            return self.engine.field_cache
        return {}
