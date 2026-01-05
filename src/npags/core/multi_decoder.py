# src/npags/core/multi_decoder.py
"""
Motor de decodificação múltipla com seleção inteligente por tamanho.
Permite tentar vários schemas diferentes em um mesmo pacote até encontrar um compatível.
"""

import logging
from typing import Any

from npags.decoders.loader import DecoderLoader
from npags.core.decoder_engine import DecoderEngine
logger = logging.getLogger(__name__)


class MultiDecoderEngine:
    """
    Fachada que gerencia múltiplos DecoderEngines.
    Seleciona o decoder mais apropriado baseado no tamanho do payload.
    
    Args:
        filter_decoders: Lista opcional de nomes de decoders para carregar.
                        Se None, carrega todos os disponíveis.
    """
    
    def __init__(self, filter_decoders: list[str] | None = None) -> None:
        self.loader = DecoderLoader()
        self.engines: dict[str, DecoderEngine] = {}
        self._filter = filter_decoders
        self._load_engines()
        
    def _load_engines(self) -> None:
        """Inicializa os decoders (todos ou apenas os filtrados)."""
        all_decoders = self.loader.scan_decoders()
        
        # Filtra se necessário
        if self._filter:
            decoder_names = [d for d in all_decoders if d in self._filter]
        else:
            decoder_names = all_decoders
        
        if not decoder_names:
            logger.warning("Nenhum decoder disponível para carregar.")
            return
            
        logger.info("Carregando %d decoder(s): %s", len(decoder_names), ', '.join(decoder_names))
        
        for name in decoder_names:
            try:
                path = self.loader.get_decoder_path(name)
                self.engines[name] = DecoderEngine(path)
            except Exception as e:
                logger.warning("Falha ao carregar decoder '%s': %s", name, e)
                
    def get_loaded_decoders(self) -> list[DecoderEngine]:
        """Retorna lista dos decoders ativos."""
        return list(self.engines.values())
    
    def get_loaded_decoder_names(self) -> list[str]:
        """Retorna lista de nomes dos decoders ativos."""
        return list(self.engines.keys())

    def _get_effective_payload_size(self, data: bytes, engine: DecoderEngine) -> int:  # noqa: PLR6301
        """
        Calcula o tamanho efetivo do payload para um decoder específico.
        Desconta preâmbulo (sync_offset) e trailer.
        """
        sync_offset: int = engine._find_sync_word(data)
        trailer_size: int = int(engine.config.get('meta', {}).get('trailer_size', 0))
        return len(data) - sync_offset - trailer_size
    
    def _get_size_constraints(self, engine: DecoderEngine) -> tuple[int, float]:  # noqa: PLR6301
        """
        Retorna (min_size, max_size) do decoder.
        """
        meta = engine.config.get('meta', {})
        min_size: int = int(meta.get('min_size', 0))
        max_size: float = float(meta.get('max_size', float('inf')))
        return min_size, max_size
    
    def _find_best_decoder(self, data: bytes) -> str | None:
        """
        Encontra o decoder mais apropriado baseado no tamanho do payload.
        
        Estratégia:
        1. Calcula o tamanho efetivo do payload para cada decoder
        2. Filtra decoders onde min_size <= payload_size <= max_size
        3. Escolhe o decoder com o range mais específico (menor diferença max-min)
        """
        candidates = []
        
        for name, engine in self.engines.items():
            # Verifica se o sync_word existe no pacote
            sync_offset = engine._find_sync_word(data)
            if sync_offset < 0 or sync_offset >= len(data):
                continue
                
            # Calcula tamanho efetivo
            effective_size = self._get_effective_payload_size(data, engine)
            min_size, max_size = self._get_size_constraints(engine)
            
            # Verifica se está dentro do range
            if min_size <= effective_size <= max_size:
                # Score: quanto menor o range, mais específico o decoder
                specificity = max_size - min_size if max_size != float('inf') else 1000
                candidates.append((name, specificity, effective_size))
        
        if not candidates:
            return None
        
        # Ordena por especificidade (menor range = mais específico = melhor)
        candidates.sort(key=lambda x: x[1])
        
        return candidates[0][0]

    def decode_payload(self, data: bytes) -> dict[str, Any]:
        """
        Decodifica o payload usando o decoder mais apropriado.
        
        Returns:
            dict: Resultado do decoder que melhor se encaixa no tamanho do payload.
                  Se nenhum funcionar, retorna um relatório de erros.
        """
        # Tenta encontrar o melhor decoder pelo tamanho
        best_decoder = self._find_best_decoder(data)
        
        if best_decoder:
            engine = self.engines[best_decoder]
            result = engine.decode_payload(data)
            
            if 'error' not in result:
                result['matched_decoder'] = best_decoder
                return result
        
        # Fallback: tenta todos os decoders
        tried_decoders = []
        
        for name, engine in self.engines.items():
            result = engine.decode_payload(data)
            
            if 'error' not in result:
                result['matched_decoder'] = name
                return result
            
            tried_decoders.append(name)
            
        # Falha total
        return {
            'error': 'Nenhum decoder compativel encontrado (Magic Bytes ou Estrutura invalida)',
            'tried_decoders': tried_decoders,
            'decoder': 'MultiDecoder'
        }

    def format_output(self, decoded_data: dict[str, Any], output_format: str = 'text') -> str:
        """
        Delega a formatação visual para o decoder específico que processou o pacote.
        """
        decoder_name = decoded_data.get('matched_decoder')
        
        if decoder_name and decoder_name in self.engines:
            return self.engines[decoder_name].format_output(decoded_data, output_format)
            
        if self.engines:
            first_engine = next(iter(self.engines.values()))
            return first_engine.format_output(decoded_data, output_format)
            
        return str(decoded_data)
